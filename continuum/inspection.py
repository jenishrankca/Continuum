"""AI Continuity Inspection Engine MVP (Stage 5).

Uses deterministic OpenCV metrics already in-tree (histograms, brightness,
ORB feature match). No model downloads. Generation completion never implies
continuity approval.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import cv2
import numpy as np

from .project import (
    CONTINUITY_STATUSES,
    ContinuityCheck,
    ContinuityReport,
    Project,
    Shot,
)

# Thresholds for deterministic CV (tunable; documented in metrics)
MEAN_COLOR_PASS = 35.0  # L2 of mean BGR
MEAN_COLOR_WARN = 70.0
PIXEL_DIFF_PASS = 40.0  # mean abs pixel delta after resize
PIXEL_DIFF_WARN = 80.0
BRIGHT_PASS = 25.0
BRIGHT_WARN = 45.0
ORB_PASS = 0.12
ORB_WARN = 0.05


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _load_bgr(path: Path) -> Optional[np.ndarray]:
    if not path.is_file():
        return None
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return img


def _brightness_delta(a: np.ndarray, b: np.ndarray) -> float:
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    return float(abs(float(np.mean(ga)) - float(np.mean(gb))))


def _mean_color_delta(a: np.ndarray, b: np.ndarray) -> float:
    ma = np.mean(a.reshape(-1, 3), axis=0)
    mb = np.mean(b.reshape(-1, 3), axis=0)
    return float(np.linalg.norm(ma - mb))


def _mean_pixel_diff(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    return float(np.mean(cv2.absdiff(a, b)))


def _orb_match_ratio(a: np.ndarray, b: np.ndarray) -> float:
    """Fraction of good ORB matches; 0 if too few features."""
    orb = cv2.ORB_create(nfeatures=500)
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(da, db)
    if not matches:
        return 0.0
    good = [m for m in matches if m.distance < 64]
    denom = max(len(ka), len(kb))
    return float(len(good) / denom)


def compare_frames(path_a: Path, path_b: Path) -> dict[str, Any]:
    """Deterministic visual compare. Returns metrics + suggested status."""
    img_a = _load_bgr(path_a)
    img_b = _load_bgr(path_b)
    if img_a is None or img_b is None:
        return {
            "ok": False,
            "status": "not_checked",
            "confidence": 0.0,
            "message": "Missing frame file(s) for comparison",
            "metrics": {},
        }
    h = 240
    img_a = cv2.resize(img_a, (int(img_a.shape[1] * h / img_a.shape[0]), h))
    img_b = cv2.resize(img_b, (int(img_b.shape[1] * h / img_b.shape[0]), h))
    color = _mean_color_delta(img_a, img_b)
    bright = _brightness_delta(img_a, img_b)
    pix = _mean_pixel_diff(img_a, img_b)
    orb = _orb_match_ratio(img_a, img_b)
    use_orb = orb > 0.0
    metrics = {
        "mean_color_delta": round(color, 2),
        "brightness_delta": round(bright, 2),
        "mean_pixel_diff": round(pix, 2),
        "orb_match_ratio": round(orb, 4),
        "orb_used": use_orb,
        "method": "opencv_color_bright_pixel_orb",
    }
    status = "passed"
    reasons: list[str] = []
    fail = (
        color > MEAN_COLOR_WARN
        or bright > BRIGHT_WARN
        or pix > PIXEL_DIFF_WARN
        or (use_orb and orb < ORB_WARN)
    )
    warn = (
        color > MEAN_COLOR_PASS
        or bright > BRIGHT_PASS
        or pix > PIXEL_DIFF_PASS
        or (use_orb and orb < ORB_PASS)
    )
    if fail:
        status = "failed"
        reasons.append("large visual/lighting drift")
    elif warn:
        status = "warning"
        reasons.append("moderate visual/lighting drift")
    else:
        reasons.append("frames look consistent under OpenCV metrics")

    # Closer color/pixel => higher confidence
    color_term = max(0.0, 1.0 - color / MEAN_COLOR_WARN)
    pix_term = max(0.0, 1.0 - pix / PIXEL_DIFF_WARN)
    orb_term = min(orb * 4, 1.0) if use_orb else 0.5
    conf = max(0.0, min(1.0, 0.4 * color_term + 0.3 * pix_term + 0.3 * orb_term))
    if status == "failed":
        conf = min(conf, 0.75)
    return {
        "ok": True,
        "status": status,
        "confidence": round(conf, 3),
        "message": "; ".join(reasons),
        "metrics": metrics,
    }


def _approved_exception_covers(
    project: Project,
    *,
    from_scope: str,
    from_ref: str,
    to_scope: str,
    to_ref: str,
    field: str,
) -> Optional[str]:
    for exc in project.continuity_exceptions:
        if not exc.approved:
            continue
        if (
            exc.from_scope == from_scope
            and str(exc.from_ref) == str(from_ref)
            and exc.to_scope == to_scope
            and str(exc.to_ref) == str(to_ref)
        ):
            if not exc.fields_changed:
                return exc.exception_id
            # Match loose: "wardrobe" covers "character.wardrobe"; "prop" covers "prop.*"
            field_parts = field.split(".")
            for f in exc.fields_changed:
                f_parts = f.split(".")
                if f == field:
                    return exc.exception_id
                if f in field_parts or field.endswith(f".{f}"):
                    return exc.exception_id
                if f_parts[0] == field_parts[0] and (
                    len(f_parts) == 1 or f_parts[-1] == field_parts[-1]
                ):
                    return exc.exception_id
    return None


def _shot_frame_path(root: Path, shot: Shot) -> Path:
    return Path(shot.raw_frame_path)


def _approved_ref_path(project: Project, character_id: str) -> Optional[Path]:
    for ch in project.characters:
        if ch.id != character_id:
            continue
        for asset in ch.assets:
            if asset.approved:
                return Path(asset.styled_path or asset.raw_path)
        if ch.assets:
            return Path(ch.assets[0].styled_path or ch.assets[0].raw_path)
    # Fallback: reference_images with matching tag/description id
    for ref in project.reference_images:
        if ref.ref_id == character_id or ref.tag == "character":
            if ref.ref_id == character_id:
                return Path(ref.styled_frame_path or ref.raw_frame_path)
    return None


def _make_check(
    *,
    check_type: str,
    subject: str,
    status: str,
    confidence: float,
    message: str,
    evidence_paths: list[str],
    metrics: dict[str, Any] | None = None,
    related_exception_id: Optional[str] = None,
) -> ContinuityCheck:
    if status not in CONTINUITY_STATUSES:
        raise ValueError(f"Invalid status {status}")
    return ContinuityCheck(
        check_id=_new_id("chk"),
        check_type=check_type,
        subject=subject,
        status=status,
        confidence=float(confidence),
        message=message,
        evidence_paths=list(evidence_paths),
        metrics=dict(metrics or {}),
        related_exception_id=related_exception_id,
        created_at=_now_iso(),
    )


def inspect_shot_pair(root: Path, project: Project, shot_a: Shot, shot_b: Shot) -> ContinuityCheck:
    pa = _shot_frame_path(root, shot_a)
    pb = _shot_frame_path(root, shot_b)
    result = compare_frames(pa, pb)
    evidence = []
    for p in (pa, pb):
        try:
            evidence.append(str(p.relative_to(root)).replace("\\", "/"))
        except ValueError:
            evidence.append(str(p).replace("\\", "/"))
    return _make_check(
        check_type="shot_to_shot",
        subject=f"{shot_a.id}->{shot_b.id}",
        status=result["status"],
        confidence=result["confidence"],
        message=result["message"],
        evidence_paths=evidence,
        metrics=result["metrics"],
    )


def inspect_ref_compare(root: Path, project: Project, shot: Shot) -> list[ContinuityCheck]:
    checks: list[ContinuityCheck] = []
    shot_path = _shot_frame_path(root, shot)
    for cid in shot.character_ids:
        ref_path = _approved_ref_path(project, cid)
        if ref_path is None:
            checks.append(
                _make_check(
                    check_type="ref_compare",
                    subject=f"{shot.id}:{cid}",
                    status="not_checked",
                    confidence=0.0,
                    message=f"No reference asset for character {cid}",
                    evidence_paths=[],
                    metrics={},
                )
            )
            continue
        result = compare_frames(shot_path, ref_path)
        evidence = []
        for p in (shot_path, ref_path):
            try:
                evidence.append(str(p.relative_to(root)).replace("\\", "/"))
            except ValueError:
                evidence.append(str(p).replace("\\", "/"))
        checks.append(
            _make_check(
                check_type="ref_compare",
                subject=f"{shot.id}:{cid}",
                status=result["status"],
                confidence=result["confidence"],
                message=f"Character {cid}: {result['message']}",
                evidence_paths=evidence,
                metrics=result["metrics"],
            )
        )
    return checks


def inspect_ledger_transition(
    project: Project, from_scene: int, to_scene: int
) -> list[ContinuityCheck]:
    from . import ledger as ledger_mod

    a = ledger_mod.get_state_for_scene(project, from_scene)
    b = ledger_mod.get_state_for_scene(project, to_scene)
    if a is None or b is None:
        return [
            _make_check(
                check_type="ledger_transition",
                subject=f"scene:{from_scene}->{to_scene}",
                status="not_checked",
                confidence=0.0,
                message="Missing ledger state for one or both scenes",
                evidence_paths=[],
            )
        ]
    checks: list[ContinuityCheck] = []
    # Characters
    a_chars = {c.character_id: c for c in a.character_states}
    b_chars = {c.character_id: c for c in b.character_states}
    for cid in sorted(set(a_chars) | set(b_chars)):
        ca, cb = a_chars.get(cid), b_chars.get(cid)
        if ca is None or cb is None:
            field = "character.presence"
            exc_id = _approved_exception_covers(
                project,
                from_scope="scene",
                from_ref=str(from_scene),
                to_scope="scene",
                to_ref=str(to_scene),
                field=field,
            )
            checks.append(
                _make_check(
                    check_type="ledger_transition",
                    subject=f"scene:{from_scene}->{to_scene}:character:{cid}",
                    status="passed" if exc_id else "warning",
                    confidence=0.9 if exc_id else 0.7,
                    message=(
                        f"Character {cid} appears/disappears between scenes"
                        + (f" (exception {exc_id})" if exc_id else "")
                    ),
                    evidence_paths=[],
                    metrics={"field": field},
                    related_exception_id=exc_id,
                )
            )
            continue
        for field_name, va, vb in (
            ("wardrobe", ca.wardrobe, cb.wardrobe),
            ("appearance", ca.appearance, cb.appearance),
        ):
            if (va or "") == (vb or ""):
                continue
            field = f"character.{field_name}"
            exc_id = _approved_exception_covers(
                project,
                from_scope="scene",
                from_ref=str(from_scene),
                to_scope="scene",
                to_ref=str(to_scene),
                field=field,
            )
            checks.append(
                _make_check(
                    check_type="ledger_transition",
                    subject=f"scene:{from_scene}->{to_scene}:character:{cid}:{field_name}",
                    status="passed" if exc_id else "failed",
                    confidence=0.95 if exc_id else 0.85,
                    message=(
                        f"{cid} {field_name} '{va}' -> '{vb}'"
                        + (f" covered by exception {exc_id}" if exc_id else " without approved exception")
                    ),
                    evidence_paths=[],
                    metrics={"field": field, "before": va, "after": vb},
                    related_exception_id=exc_id,
                )
            )
        if set(ca.holding_prop_ids) != set(cb.holding_prop_ids):
            field = "character.holding"
            exc_id = _approved_exception_covers(
                project,
                from_scope="scene",
                from_ref=str(from_scene),
                to_scope="scene",
                to_ref=str(to_scene),
                field=field,
            )
            checks.append(
                _make_check(
                    check_type="ledger_transition",
                    subject=f"scene:{from_scene}->{to_scene}:character:{cid}:holding",
                    status="passed" if exc_id else "warning",
                    confidence=0.9 if exc_id else 0.75,
                    message=f"{cid} holding {ca.holding_prop_ids} -> {cb.holding_prop_ids}",
                    evidence_paths=[],
                    metrics={
                        "field": field,
                        "before": list(ca.holding_prop_ids),
                        "after": list(cb.holding_prop_ids),
                    },
                    related_exception_id=exc_id,
                )
            )
    # Props
    a_props = {p.prop_id: p for p in a.prop_states}
    b_props = {p.prop_id: p for p in b.prop_states}
    for pid in sorted(set(a_props) | set(b_props)):
        pa, pb = a_props.get(pid), b_props.get(pid)
        if pa is None or pb is None:
            continue
        for field_name, va, vb in (
            ("location_note", pa.location_note, pb.location_note),
            ("owner_character_id", pa.owner_character_id or "", pb.owner_character_id or ""),
        ):
            if (va or "") == (vb or ""):
                continue
            field = f"prop.{field_name}"
            exc_id = _approved_exception_covers(
                project,
                from_scope="scene",
                from_ref=str(from_scene),
                to_scope="scene",
                to_ref=str(to_scene),
                field=field,
            )
            checks.append(
                _make_check(
                    check_type="ledger_transition",
                    subject=f"scene:{from_scene}->{to_scene}:prop:{pid}:{field_name}",
                    status="passed" if exc_id else "failed",
                    confidence=0.95 if exc_id else 0.85,
                    message=(
                        f"Prop {pid} {field_name} '{va}' -> '{vb}'"
                        + (f" covered by exception {exc_id}" if exc_id else " without approved exception")
                    ),
                    evidence_paths=[],
                    metrics={"field": field, "before": va, "after": vb},
                    related_exception_id=exc_id,
                )
            )
    # Location
    if a.location_state and b.location_state:
        if a.location_state.location_id != b.location_state.location_id:
            field = "location.id"
            exc_id = _approved_exception_covers(
                project,
                from_scope="scene",
                from_ref=str(from_scene),
                to_scope="scene",
                to_ref=str(to_scene),
                field=field,
            )
            checks.append(
                _make_check(
                    check_type="ledger_transition",
                    subject=f"scene:{from_scene}->{to_scene}:location",
                    status="passed" if exc_id else "warning",
                    confidence=0.9 if exc_id else 0.8,
                    message=(
                        f"Location {a.location_state.location_id} -> {b.location_state.location_id}"
                    ),
                    evidence_paths=[],
                    metrics={"field": field},
                    related_exception_id=exc_id,
                )
            )
    if not checks:
        checks.append(
            _make_check(
                check_type="ledger_transition",
                subject=f"scene:{from_scene}->{to_scene}",
                status="passed",
                confidence=0.8,
                message="No ledger field changes between scenes",
                evidence_paths=[],
            )
        )
    return checks


def _rollup_status(statuses: list[str]) -> str:
    order = ["failed", "warning", "human_override", "not_checked", "passed"]
    for s in order:
        if s in statuses:
            return s
    return "not_checked"


def _update_shot_rollups(project: Project, checks: list[ContinuityCheck]) -> None:
    by_shot: dict[str, list[str]] = {}
    for chk in checks:
        # subject forms: shot_a->shot_b, shot:char, shot_id alone
        subject = chk.subject
        shot_ids: list[str] = []
        if "->" in subject and chk.check_type == "shot_to_shot":
            shot_ids = subject.split("->")
        elif ":" in subject:
            shot_ids = [subject.split(":")[0]]
        for sid in shot_ids:
            by_shot.setdefault(sid, []).append(chk.status)
    for shot in project.shots:
        if shot.id in by_shot:
            shot.continuity_status = _rollup_status(by_shot[shot.id])
        # Never auto-approve from generation
        if shot.generation_complete and not shot.continuity_approved:
            # leave continuity_approved False — invariant
            pass


def run_inspection(
    root: Path,
    project: Project,
    *,
    clear_previous: bool = True,
    actor: str = "inspection",
) -> ContinuityReport:
    """Run full MVP inspection pass and append checks + report."""
    if clear_previous:
        # Keep human_override checks unless clearing is explicit — still clear all for MVP
        # but re-apply is fine; overrides can be re-issued
        project.continuity_checks = [
            c for c in project.continuity_checks if c.status == "human_override"
        ]

    new_checks: list[ContinuityCheck] = []
    shots = sorted(project.shots, key=lambda s: s.order)
    for i in range(len(shots) - 1):
        new_checks.append(inspect_shot_pair(root, project, shots[i], shots[i + 1]))
    for shot in shots:
        new_checks.extend(inspect_ref_compare(root, project, shot))

    scene_indexes = sorted(
        {
            s.scene_index
            for s in project.continuity_states
            if s.scope == "scene" and s.scene_index is not None
        }
    )
    for i in range(len(scene_indexes) - 1):
        new_checks.extend(
            inspect_ledger_transition(project, scene_indexes[i], scene_indexes[i + 1])
        )

    project.continuity_checks.extend(new_checks)
    _update_shot_rollups(project, project.continuity_checks)

    counts = {s: 0 for s in CONTINUITY_STATUSES}
    for c in new_checks:
        counts[c.status] = counts.get(c.status, 0) + 1

    report = ContinuityReport(
        report_id=_new_id("rep"),
        created_at=_now_iso(),
        scope="project",
        summary=(
            f"{len(new_checks)} checks: "
            + ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        ),
        check_ids=[c.check_id for c in new_checks],
        counts=counts,
        actor=actor,
    )
    project.continuity_reports.append(report)
    return report


def override_check(
    project: Project,
    check_id: str,
    *,
    reason: str,
    overridden_by: str = "jay",
) -> ContinuityCheck:
    if not reason.strip():
        raise ValueError("Override reason is required")
    chk = next((c for c in project.continuity_checks if c.check_id == check_id), None)
    if chk is None:
        raise ValueError(f"Unknown check_id '{check_id}'")
    chk.status = "human_override"
    chk.override_reason = reason.strip()
    chk.override_by = overridden_by
    chk.override_at = date.today().isoformat()
    # Update shot rollups
    _update_shot_rollups(project, project.continuity_checks)
    return chk


def mark_generation_complete(project: Project, shot_id: str, *, complete: bool = True) -> Shot:
    """Mark generation done without granting continuity approval."""
    shot = next((s for s in project.shots if s.id == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot_id '{shot_id}'")
    shot.generation_complete = complete
    # Invariant: generation never sets continuity_approved
    return shot


def approve_shot_continuity(
    project: Project, shot_id: str, *, approved_by: str = "jay"
) -> Shot:
    """Explicit human continuity approval (separate from generation_complete)."""
    shot = next((s for s in project.shots if s.id == shot_id), None)
    if shot is None:
        raise ValueError(f"Unknown shot_id '{shot_id}'")
    shot.continuity_approved = True
    if shot.continuity_status in ("failed", "warning", "not_checked"):
        shot.continuity_status = "passed"
    note = f"[continuity approved by {approved_by} {date.today().isoformat()}]"
    shot.notes = f"{shot.notes}\n{note}".strip() if shot.notes else note
    return shot


def summarize_inspection(project: Project) -> str:
    lines = [
        f"Inspection for {project.slug} (schema {project.schema_version})",
        f"  checks: {len(project.continuity_checks)}",
        f"  reports: {len(project.continuity_reports)}",
    ]
    if project.continuity_reports:
        latest = project.continuity_reports[-1]
        lines.append(f"  latest: {latest.report_id} — {latest.summary}")
    counts = {s: 0 for s in CONTINUITY_STATUSES}
    for c in project.continuity_checks:
        counts[c.status] = counts.get(c.status, 0) + 1
    lines.append("  status totals: " + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    gen_done = sum(1 for s in project.shots if s.generation_complete)
    approved = sum(1 for s in project.shots if s.continuity_approved)
    lines.append(
        f"  shots: generation_complete={gen_done}/{len(project.shots)} "
        f"continuity_approved={approved}/{len(project.shots)} "
        "(generation ≠ approval)"
    )
    for c in project.continuity_checks[-20:]:
        ov = f" override={c.override_by}" if c.status == "human_override" else ""
        lines.append(
            f"  - {c.check_id} [{c.status}] {c.check_type} {c.subject} "
            f"conf={c.confidence:.2f}{ov}: {c.message}"
        )
    return "\n".join(lines)


def format_check(chk: ContinuityCheck) -> str:
    lines = [
        f"Check {chk.check_id}",
        f"  type={chk.check_type} subject={chk.subject}",
        f"  status={chk.status} confidence={chk.confidence}",
        f"  message={chk.message}",
        f"  evidence={chk.evidence_paths}",
        f"  metrics={chk.metrics}",
    ]
    if chk.related_exception_id:
        lines.append(f"  exception={chk.related_exception_id}")
    if chk.override_reason:
        lines.append(
            f"  override by {chk.override_by} at {chk.override_at}: {chk.override_reason}"
        )
    return "\n".join(lines)
