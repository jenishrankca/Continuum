"""AI Film Intelligence MVP (Stage 6).

Produces structured, editable *suggestions* from scene detect metadata and
local OpenCV heuristics. Suggestions are never written into the bible/ledger
as fact until a human accepts them. Uncertain IDs cannot be auto-confirmed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import cv2
import numpy as np

from .project import (
    CONFIRM_CONFIDENCE,
    SUGGESTION_STATUSES,
    FilmIntelligenceRun,
    FilmSuggestion,
    Project,
)

SOURCE_HEURISTIC = "heuristic_opencv"
SOURCE_SCENE = "scene_detect"
SOURCE_MANUAL = "manual"
SOURCE_LOCAL_LLM = "local_llm"  # reserved; only if LOCAL_LLM_URL configured


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _rel(root: Path, path: Path | str | None) -> Optional[str]:
    if path is None or path == "":
        return None
    p = Path(path)
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _load_bgr(path: Path) -> Optional[np.ndarray]:
    if not path.is_file():
        return None
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def _frame_env_metrics(path: Path) -> dict[str, Any]:
    img = _load_bgr(path)
    if img is None:
        return {}
    small = cv2.resize(img, (160, 120))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    hue = float(np.mean(hsv[:, :, 0]))
    sat = float(np.mean(hsv[:, :, 1]))
    if brightness < 55:
        lighting = "dim / low-key"
    elif brightness > 170:
        lighting = "bright / high-key"
    else:
        lighting = "even / mid"
    if sat < 40:
        palette = "muted / neutral"
    elif 10 <= hue <= 25:
        palette = "warm"
    elif 90 <= hue <= 140:
        palette = "cool"
    else:
        palette = "mixed"
    # Heuristic confidence stays moderate — never "certain"
    conf = 0.55 if 40 < brightness < 200 else 0.45
    return {
        "brightness": round(brightness, 1),
        "hue_mean": round(hue, 1),
        "sat_mean": round(sat, 1),
        "lighting_guess": lighting,
        "palette_guess": palette,
        "confidence": conf,
    }


def _make_suggestion(
    *,
    kind: str,
    target_scope: str,
    target_ref: str,
    title: str,
    summary: str,
    details: dict[str, Any],
    confidence: float,
    source: str,
    evidence_paths: list[str] | None = None,
    proposed_entity_id: Optional[str] = None,
    entity_kind: Optional[str] = None,
    force_uncertain: bool = False,
) -> FilmSuggestion:
    uncertain = force_uncertain or confidence < CONFIRM_CONFIDENCE or (
        proposed_entity_id is not None and confidence < CONFIRM_CONFIDENCE
    )
    # Any guessed entity id without high confidence is uncertain by policy
    if proposed_entity_id and confidence < CONFIRM_CONFIDENCE:
        uncertain = True
    now = _now_iso()
    return FilmSuggestion(
        suggestion_id=_new_id("sug"),
        kind=kind,
        target_scope=target_scope,
        target_ref=str(target_ref),
        proposed_entity_id=proposed_entity_id,
        entity_kind=entity_kind,
        title=title,
        summary=summary,
        details=dict(details),
        confidence=float(round(confidence, 3)),
        uncertain=uncertain,
        status="proposed",
        source=source,
        evidence_paths=list(evidence_paths or []),
        created_at=now,
        updated_at=now,
    )


def analyze_project(
    root: Path,
    project: Project,
    *,
    clear_proposed: bool = True,
    actor: str = "intelligence",
) -> FilmIntelligenceRun:
    """Generate editable suggestions. Does not mutate bible/ledger entities."""
    if clear_proposed:
        project.film_suggestions = [
            s for s in project.film_suggestions if s.status in ("accepted", "edited", "rejected")
        ]
        # Keep edited? Board says editable — keep accepted/rejected/edited
        project.film_suggestions = [
            s for s in project.film_suggestions if s.status != "proposed"
        ]

    new: list[FilmSuggestion] = []

    # --- Scene summaries from detect metadata ---
    for scene in project.scenes:
        duration = max(0.0, float(scene.end_s) - float(scene.start_s))
        frame = scene.chosen_frame_path or (
            scene.candidates[0].path if scene.candidates else None
        )
        evidence = []
        rel = _rel(root, frame) if frame else None
        if rel:
            evidence.append(rel)
        status_bits = []
        if scene.reviewed:
            status_bits.append("reviewed")
        if scene.kept:
            status_bits.append("kept")
        else:
            status_bits.append("not kept")
        summary = (
            f"Scene {scene.scene_index}: {duration:.2f}s "
            f"({scene.start_s:.2f}–{scene.end_s:.2f}), {', '.join(status_bits)}; "
            f"{len(scene.candidates)} candidate frame(s)."
        )
        conf = 0.9 if scene.reviewed else 0.7
        new.append(
            _make_suggestion(
                kind="scene_summary",
                target_scope="scene",
                target_ref=str(scene.scene_index),
                title=f"Scene {scene.scene_index} summary",
                summary=summary,
                details={
                    "duration_s": round(duration, 3),
                    "start_s": scene.start_s,
                    "end_s": scene.end_s,
                    "kept": scene.kept,
                    "reviewed": scene.reviewed,
                    "candidate_count": len(scene.candidates),
                },
                confidence=conf,
                source=SOURCE_SCENE,
                evidence_paths=evidence,
            )
        )

        # Environment heuristic from chosen/candidate frame
        if frame:
            metrics = _frame_env_metrics(Path(frame))
            if metrics:
                env_summary = (
                    f"Possible lighting '{metrics['lighting_guess']}', "
                    f"palette '{metrics['palette_guess']}' "
                    f"(brightness={metrics['brightness']}). Uncertain — review before use."
                )
                new.append(
                    _make_suggestion(
                        kind="environment",
                        target_scope="scene",
                        target_ref=str(scene.scene_index),
                        title=f"Scene {scene.scene_index} environment guess",
                        summary=env_summary,
                        details=metrics,
                        confidence=float(metrics["confidence"]),
                        source=SOURCE_HEURISTIC,
                        evidence_paths=evidence,
                        entity_kind="location",
                        proposed_entity_id=None,  # never invent location ids
                        force_uncertain=True,
                    )
                )

    # --- Character appearances from shot links (high confidence only if linked) ---
    char_names = {c.id: c.name for c in project.characters}
    for shot in project.shots:
        evidence = []
        rel = _rel(root, shot.raw_frame_path)
        if rel:
            evidence.append(rel)
        for cid in shot.character_ids:
            name = char_names.get(cid, cid)
            # Linked in project = stronger signal but still a suggestion until accepted
            conf = 0.82 if cid in char_names else 0.4
            new.append(
                _make_suggestion(
                    kind="character_appearance",
                    target_scope="shot",
                    target_ref=shot.id,
                    title=f"{name} in {shot.id}",
                    summary=(
                        f"Shot {shot.id} links character '{name}' ({cid}). "
                        "Confirm before treating as continuity fact."
                    ),
                    details={
                        "shot_label": shot.label,
                        "scene_index": shot.scene_index,
                        "character_id": cid,
                        "character_name": name,
                        "in_bible": cid in char_names,
                    },
                    confidence=conf,
                    source=SOURCE_SCENE,
                    evidence_paths=evidence,
                    proposed_entity_id=cid if cid in char_names else None,
                    entity_kind="character",
                    force_uncertain=cid not in char_names,
                )
            )
        if shot.location_id:
            loc_ok = any(loc.id == shot.location_id for loc in project.locations)
            conf = 0.8 if loc_ok else 0.35
            new.append(
                _make_suggestion(
                    kind="environment",
                    target_scope="shot",
                    target_ref=shot.id,
                    title=f"Location link on {shot.id}",
                    summary=(
                        f"Shot {shot.id} links location_id '{shot.location_id}'. "
                        + ("In bible." if loc_ok else "Not in bible — uncertain.")
                    ),
                    details={"location_id": shot.location_id, "in_bible": loc_ok},
                    confidence=conf,
                    source=SOURCE_SCENE,
                    evidence_paths=evidence,
                    proposed_entity_id=shot.location_id if loc_ok else None,
                    entity_kind="location",
                    force_uncertain=not loc_ok,
                )
            )
        for pid in shot.prop_ids:
            prop_ok = any(p.id == pid for p in project.props)
            conf = 0.8 if prop_ok else 0.35
            new.append(
                _make_suggestion(
                    kind="prop_presence",
                    target_scope="shot",
                    target_ref=shot.id,
                    title=f"Prop {pid} in {shot.id}",
                    summary=(
                        f"Shot {shot.id} links prop '{pid}'. "
                        + ("In bible." if prop_ok else "Not in bible — uncertain.")
                    ),
                    details={"prop_id": pid, "in_bible": prop_ok},
                    confidence=conf,
                    source=SOURCE_SCENE,
                    evidence_paths=evidence,
                    proposed_entity_id=pid if prop_ok else None,
                    entity_kind="prop",
                    force_uncertain=not prop_ok,
                )
            )

    # --- Unlinked reference_images as uncertain identity proposals ---
    linked_ref_ids = set()
    for ent in [*project.characters, *project.locations, *project.props]:
        for asset in ent.assets:
            if asset.source_ref_id:
                linked_ref_ids.add(asset.source_ref_id)
    for ref in project.reference_images:
        if ref.ref_id in linked_ref_ids:
            continue
        entity_kind = {"character": "character", "set": "location", "prop": "prop"}.get(
            ref.tag, None
        )
        evidence = []
        rel = _rel(root, ref.raw_frame_path)
        if rel:
            evidence.append(rel)
        new.append(
            _make_suggestion(
                kind=(
                    "character_appearance"
                    if entity_kind == "character"
                    else "prop_presence"
                    if entity_kind == "prop"
                    else "environment"
                ),
                target_scope="project",
                target_ref="",
                title=f"Unconfirmed ref {ref.ref_id}",
                summary=(
                    f"Reference '{ref.ref_id}' tagged '{ref.tag}': {ref.description or '(no description)'}. "
                    "Not linked to a bible entity — do not treat as confirmed identity."
                ),
                details={
                    "ref_id": ref.ref_id,
                    "tag": ref.tag,
                    "description": ref.description,
                    "restyle_status": ref.restyle_status,
                },
                confidence=0.35,
                source=SOURCE_HEURISTIC,
                evidence_paths=evidence,
                proposed_entity_id=None,
                entity_kind=entity_kind,
                force_uncertain=True,
            )
        )

    project.film_suggestions.extend(new)
    run = FilmIntelligenceRun(
        run_id=_new_id("intel"),
        created_at=_now_iso(),
        source=SOURCE_HEURISTIC,
        summary=(
            f"{len(new)} suggestions "
            f"({sum(1 for s in new if s.uncertain)} uncertain); "
            "none applied to bible/ledger"
        ),
        suggestion_ids=[s.suggestion_id for s in new],
        actor=actor,
    )
    project.film_intelligence_runs.append(run)
    return run


def get_suggestion(project: Project, suggestion_id: str) -> FilmSuggestion:
    sug = next((s for s in project.film_suggestions if s.suggestion_id == suggestion_id), None)
    if sug is None:
        raise ValueError(f"Unknown suggestion_id '{suggestion_id}'")
    return sug


def edit_suggestion(
    project: Project,
    suggestion_id: str,
    *,
    summary: Optional[str] = None,
    title: Optional[str] = None,
    proposed_entity_id: Optional[str] = None,
    clear_entity_id: bool = False,
    confidence: Optional[float] = None,
    details_update: Optional[dict[str, Any]] = None,
    reviewed_by: str = "human",
) -> FilmSuggestion:
    sug = get_suggestion(project, suggestion_id)
    if sug.status == "rejected":
        raise ValueError("Cannot edit a rejected suggestion; re-analyze or leave rejected")
    if summary is not None:
        sug.summary = summary
    if title is not None:
        sug.title = title
    if clear_entity_id:
        sug.proposed_entity_id = None
    elif proposed_entity_id is not None:
        sug.proposed_entity_id = proposed_entity_id
    if confidence is not None:
        sug.confidence = float(confidence)
    if details_update:
        sug.details = {**sug.details, **details_update}
    sug.uncertain = sug.confidence < CONFIRM_CONFIDENCE or sug.proposed_entity_id is None and sug.entity_kind in (
        "character",
        "location",
        "prop",
    )
    # After human edit, still not fact until accept
    if sug.status == "proposed":
        sug.status = "edited"
    sug.reviewed_by = reviewed_by
    sug.updated_at = _now_iso()
    return sug


def accept_suggestion(
    project: Project,
    suggestion_id: str,
    *,
    reviewed_by: str = "jay",
    review_note: str = "",
    allow_uncertain: bool = False,
) -> FilmSuggestion:
    """Human accepts a suggestion as reviewed. Never silently writes bible rows."""
    sug = get_suggestion(project, suggestion_id)
    if sug.status == "rejected":
        raise ValueError("Cannot accept a rejected suggestion")
    if sug.uncertain and not allow_uncertain:
        raise ValueError(
            f"Suggestion {suggestion_id} is uncertain (confidence={sug.confidence}). "
            "Edit it, or pass allow_uncertain=True / --allow-uncertain after human review."
        )
    if sug.entity_kind and sug.proposed_entity_id:
        # Validate id exists in bible — still don't auto-create
        ids = {
            "character": {c.id for c in project.characters},
            "location": {loc.id for loc in project.locations},
            "prop": {p.id for p in project.props},
        }.get(sug.entity_kind, set())
        if sug.proposed_entity_id not in ids and not allow_uncertain:
            raise ValueError(
                f"proposed_entity_id '{sug.proposed_entity_id}' not in bible "
                f"{sug.entity_kind}s; edit the id or use --allow-uncertain"
            )
    sug.status = "accepted"
    sug.reviewed_by = reviewed_by
    sug.review_note = review_note or sug.review_note
    sug.updated_at = _now_iso()
    # Accepting clears uncertain flag only when human explicitly allowed or confident
    if not sug.uncertain or allow_uncertain:
        sug.uncertain = False
    return sug


def reject_suggestion(
    project: Project,
    suggestion_id: str,
    *,
    reviewed_by: str = "jay",
    review_note: str = "",
) -> FilmSuggestion:
    sug = get_suggestion(project, suggestion_id)
    sug.status = "rejected"
    sug.reviewed_by = reviewed_by
    sug.review_note = review_note or "rejected"
    sug.updated_at = _now_iso()
    return sug


def summarize_intelligence(project: Project) -> str:
    lines = [
        f"Film intelligence for {project.slug} (schema {project.schema_version})",
        f"  suggestions: {len(project.film_suggestions)}",
        f"  runs: {len(project.film_intelligence_runs)}",
    ]
    counts = {s: 0 for s in SUGGESTION_STATUSES}
    uncertain = 0
    for sug in project.film_suggestions:
        counts[sug.status] = counts.get(sug.status, 0) + 1
        if sug.uncertain:
            uncertain += 1
    lines.append(
        "  status: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        + f"; uncertain={uncertain}"
    )
    lines.append("  policy: uncertain suggestions are never treated as confirmed fact")
    if project.film_intelligence_runs:
        latest = project.film_intelligence_runs[-1]
        lines.append(f"  latest run: {latest.run_id} — {latest.summary}")
    for sug in project.film_suggestions[-30:]:
        flag = " uncertain" if sug.uncertain else ""
        lines.append(
            f"  - {sug.suggestion_id} [{sug.status}]{flag} {sug.kind} "
            f"{sug.target_scope}:{sug.target_ref or '—'} conf={sug.confidence:.2f}: {sug.title}"
        )
    return "\n".join(lines)


def format_suggestion(sug: FilmSuggestion) -> str:
    lines = [
        f"Suggestion {sug.suggestion_id}",
        f"  kind={sug.kind} status={sug.status} uncertain={sug.uncertain}",
        f"  scope={sug.target_scope}:{sug.target_ref or '—'}",
        f"  entity={sug.entity_kind or '—'} id={sug.proposed_entity_id or '—'}",
        f"  confidence={sug.confidence} source={sug.source}",
        f"  title={sug.title}",
        f"  summary={sug.summary}",
        f"  details={sug.details}",
        f"  evidence={sug.evidence_paths}",
    ]
    if sug.reviewed_by:
        lines.append(f"  reviewed_by={sug.reviewed_by} note={sug.review_note}")
    return "\n".join(lines)


def local_llm_available() -> bool:
    """True only if a local LLM endpoint is already configured (no downloads)."""
    import os

    return bool(os.environ.get("LOCAL_LLM_URL") or os.environ.get("OLLAMA_HOST"))
