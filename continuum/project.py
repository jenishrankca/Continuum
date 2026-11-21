"""Project data model: the single project.yaml source of truth."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from . import paths

# schema_version 2: root-relative paths
# schema_version 3: character / location / prop bible entities
# schema_version 4: continuity ledger + scene/shot state + exceptions + history
# schema_version 5: continuity inspection checks + reports
# schema_version 6: film intelligence suggestions (editable; never auto-fact)
# schema_version 7: storyboard / shot planning fields (vision §7)
SCHEMA_VERSION = 7

CONTINUITY_STATUSES = (
    "not_checked",
    "passed",
    "warning",
    "failed",
    "human_override",
)

SUGGESTION_STATUSES = ("proposed", "edited", "accepted", "rejected")
CONFIRM_CONFIDENCE = 0.75  # below this → uncertain; human must explicitly accept


@dataclass
class StyleBible:
    project_name: str
    style_phrase: str
    lighting_phrase: str
    grain_grade_phrase: str
    genre_mode: str = "drama"  # "drama" | "comedy"
    default_restyle_provider: str = "manual"


@dataclass
class CandidateFrame:
    path: str
    timestamp_s: float
    frame_number: int
    sharpness: float


@dataclass
class DetectedScene:
    scene_index: int
    start_s: float
    end_s: float
    candidates: list[CandidateFrame] = field(default_factory=list)
    reviewed: bool = False
    kept: bool = False
    chosen_frame_path: Optional[str] = None


@dataclass
class ReferenceImage:
    ref_id: str
    tag: str  # "character" | "set" | "prop"
    description: str
    raw_frame_path: str
    styled_frame_path: Optional[str] = None
    restyle_status: str = "pending"  # pending | pending_manual | completed
    restyle_provider: Optional[str] = None


@dataclass
class ReferenceAsset:
    """Versioned reference image on a bible entity. Approved paths are immutable."""

    asset_id: str
    raw_path: str
    styled_path: Optional[str] = None
    source_ref_id: Optional[str] = None
    approved: bool = False
    approved_at: Optional[str] = None
    notes: str = ""


@dataclass
class Character:
    id: str
    name: str
    description: str = ""
    appearance_notes: str = ""
    wardrobe_notes: str = ""
    assets: list[ReferenceAsset] = field(default_factory=list)
    approved: bool = False


@dataclass
class Location:
    id: str
    name: str
    description: str = ""
    lighting_notes: str = ""
    assets: list[ReferenceAsset] = field(default_factory=list)
    approved: bool = False


@dataclass
class Prop:
    id: str
    name: str
    description: str = ""
    ownership_notes: str = ""
    assets: list[ReferenceAsset] = field(default_factory=list)
    approved: bool = False


@dataclass
class Shot:
    id: str
    order: int
    label: str
    raw_frame_path: str
    scene_index: Optional[int] = None
    anchor_ref_id: Optional[str] = None
    shot_type: str = ""
    camera_move: str = ""
    subject_action: str = ""
    character_count: int = 1
    beat_before_gag: str = ""
    notes: str = ""
    status: str = "detected"  # detected | kept | anchored | prompted
    character_ids: list[str] = field(default_factory=list)
    location_id: Optional[str] = None
    prop_ids: list[str] = field(default_factory=list)
    continuity_state_id: Optional[str] = None
    continuity_status: str = "not_checked"
    generation_complete: bool = False
    continuity_approved: bool = False  # never set True merely because generation finished
    # Stage 7 — vision §7 storyboard / shot planning (additive; migrate setdefaults)
    description: str = ""
    camera_angle: str = ""
    lens_composition: str = ""
    prev_shot_id: Optional[str] = None
    next_shot_id: Optional[str] = None
    start_keyframe_path: Optional[str] = None
    end_keyframe_path: Optional[str] = None
    duration_s: Optional[float] = None
    dialogue_or_sound: str = ""
    image_prompt: str = ""  # empty → prompt_builder.build_prompt at export time
    video_prompt: str = ""
    planning_approved: bool = False  # storyboard plan approval; ≠ continuity_approved
    planning_approved_at: Optional[str] = None
    planning_approved_by: str = ""


@dataclass
class CharacterState:
    """What is true about a character at a ledger point."""

    character_id: str
    wardrobe: str = ""
    appearance: str = ""
    holding_prop_ids: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class LocationState:
    location_id: str
    time_of_day: str = ""
    notes: str = ""


@dataclass
class PropState:
    prop_id: str
    location_note: str = ""
    owner_character_id: Optional[str] = None
    notes: str = ""


@dataclass
class ContinuityState:
    """Continuity facts attached to a scene or shot."""

    state_id: str
    scope: str  # "scene" | "shot"
    scene_index: Optional[int] = None
    shot_id: Optional[str] = None
    character_states: list[CharacterState] = field(default_factory=list)
    location_state: Optional[LocationState] = None
    prop_states: list[PropState] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ContinuityException:
    """Intentional continuity break; only approved exceptions silence inspection later."""

    exception_id: str
    from_scope: str
    from_ref: str
    to_scope: str
    to_ref: str
    reason: str
    fields_changed: list[str] = field(default_factory=list)
    approved: bool = False
    approved_at: Optional[str] = None
    approved_by: str = ""
    created_at: str = ""


@dataclass
class LedgerHistoryEntry:
    """Append-only audit row. Do not mutate after append."""

    entry_id: str
    ts: str
    action: str
    actor: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContinuityCheck:
    """One inspection finding with status, confidence, and evidence paths."""

    check_id: str
    check_type: str  # shot_to_shot | ref_compare | ledger_transition
    subject: str
    status: str  # CONTINUITY_STATUSES
    confidence: float = 0.0
    message: str = ""
    evidence_paths: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    related_exception_id: Optional[str] = None
    override_reason: str = ""
    override_by: str = ""
    override_at: Optional[str] = None
    created_at: str = ""


@dataclass
class ContinuityReport:
    """Summary of an inspection run."""

    report_id: str
    created_at: str
    scope: str = "project"
    summary: str = ""
    check_ids: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    actor: str = ""


@dataclass
class FilmSuggestion:
    """Editable film-intelligence suggestion. Not fact until status=accepted."""

    suggestion_id: str
    kind: str  # scene_summary | character_appearance | environment | prop_presence
    target_scope: str  # scene | shot | project
    target_ref: str = ""
    proposed_entity_id: Optional[str] = None
    entity_kind: Optional[str] = None  # character | location | prop
    title: str = ""
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    uncertain: bool = True
    status: str = "proposed"  # SUGGESTION_STATUSES
    source: str = "heuristic_opencv"
    evidence_paths: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    reviewed_by: str = ""
    review_note: str = ""


@dataclass
class FilmIntelligenceRun:
    run_id: str
    created_at: str
    source: str = "heuristic_opencv"
    summary: str = ""
    suggestion_ids: list[str] = field(default_factory=list)
    actor: str = ""


@dataclass
class Project:
    schema_version: int
    slug: str
    style: StyleBible
    source_video_path: str
    scenes: list[DetectedScene] = field(default_factory=list)
    reference_images: list[ReferenceImage] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    characters: list[Character] = field(default_factory=list)
    locations: list[Location] = field(default_factory=list)
    props: list[Prop] = field(default_factory=list)
    continuity_states: list[ContinuityState] = field(default_factory=list)
    continuity_exceptions: list[ContinuityException] = field(default_factory=list)
    ledger_history: list[LedgerHistoryEntry] = field(default_factory=list)
    continuity_checks: list[ContinuityCheck] = field(default_factory=list)
    continuity_reports: list[ContinuityReport] = field(default_factory=list)
    film_suggestions: list[FilmSuggestion] = field(default_factory=list)
    film_intelligence_runs: list[FilmIntelligenceRun] = field(default_factory=list)

    @staticmethod
    def project_dir(root: Path, slug: str) -> Path:
        return root / "projects" / slug

    @staticmethod
    def yaml_path(root: Path, slug: str) -> Path:
        return Project.project_dir(root, slug) / "project.yaml"

    def _to_storage_dict(self, root: Path) -> dict:
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
        data["source_video_path"] = paths.to_stored(root, self.source_video_path)
        for scene in data.get("scenes", []):
            scene["chosen_frame_path"] = paths.to_stored(root, scene.get("chosen_frame_path"))
            for cand in scene.get("candidates", []):
                cand["path"] = paths.to_stored(root, cand.get("path"))
        for ref in data.get("reference_images", []):
            ref["raw_frame_path"] = paths.to_stored(root, ref.get("raw_frame_path"))
            ref["styled_frame_path"] = paths.to_stored(root, ref.get("styled_frame_path"))
        for shot in data.get("shots", []):
            shot["raw_frame_path"] = paths.to_stored(root, shot.get("raw_frame_path"))
            shot["start_keyframe_path"] = paths.to_stored(root, shot.get("start_keyframe_path"))
            shot["end_keyframe_path"] = paths.to_stored(root, shot.get("end_keyframe_path"))
        for group in ("characters", "locations", "props"):
            for ent in data.get(group, []):
                for asset in ent.get("assets", []):
                    asset["raw_path"] = paths.to_stored(root, asset.get("raw_path"))
                    asset["styled_path"] = paths.to_stored(root, asset.get("styled_path"))
        return data

    def _resolve_runtime_paths(self, root: Path) -> None:
        self.source_video_path = paths.to_absolute(root, self.source_video_path) or ""
        for scene in self.scenes:
            scene.chosen_frame_path = paths.to_absolute(root, scene.chosen_frame_path)
            for cand in scene.candidates:
                cand.path = paths.to_absolute(root, cand.path) or cand.path
        for ref in self.reference_images:
            ref.raw_frame_path = paths.to_absolute(root, ref.raw_frame_path) or ref.raw_frame_path
            ref.styled_frame_path = paths.to_absolute(root, ref.styled_frame_path)
        for shot in self.shots:
            shot.raw_frame_path = paths.to_absolute(root, shot.raw_frame_path) or shot.raw_frame_path
            shot.start_keyframe_path = paths.to_absolute(root, shot.start_keyframe_path)
            shot.end_keyframe_path = paths.to_absolute(root, shot.end_keyframe_path)
        for ent in [*self.characters, *self.locations, *self.props]:
            for asset in ent.assets:
                asset.raw_path = paths.to_absolute(root, asset.raw_path) or asset.raw_path
                asset.styled_path = paths.to_absolute(root, asset.styled_path)

    def save(self, root: Path) -> None:
        path = self.yaml_path(root, self.slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._to_storage_dict(root)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        self.schema_version = SCHEMA_VERSION

    @staticmethod
    def load(root: Path, slug: str) -> "Project":
        path = Project.yaml_path(root, slug)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        project = Project._from_dict(data)
        project._resolve_runtime_paths(root)
        return project

    @staticmethod
    def _parse_assets(raw_assets: list[dict[str, Any]] | None) -> list[ReferenceAsset]:
        assets: list[ReferenceAsset] = []
        for a in raw_assets or []:
            assets.append(
                ReferenceAsset(
                    asset_id=a["asset_id"],
                    raw_path=a["raw_path"],
                    styled_path=a.get("styled_path"),
                    source_ref_id=a.get("source_ref_id"),
                    approved=bool(a.get("approved", False)),
                    approved_at=a.get("approved_at"),
                    notes=a.get("notes", "") or "",
                )
            )
        return assets

    @staticmethod
    def _from_dict(data: dict) -> "Project":
        style = StyleBible(**data["style"])
        scenes = [
            DetectedScene(
                scene_index=s["scene_index"],
                start_s=s["start_s"],
                end_s=s["end_s"],
                candidates=[CandidateFrame(**c) for c in s.get("candidates", [])],
                reviewed=s.get("reviewed", False),
                kept=s.get("kept", False),
                chosen_frame_path=s.get("chosen_frame_path"),
            )
            for s in data.get("scenes", [])
        ]
        refs = [ReferenceImage(**r) for r in data.get("reference_images", [])]
        shots: list[Shot] = []
        for sh in data.get("shots", []):
            duration_raw = sh.get("duration_s")
            duration_s: Optional[float] = None
            if duration_raw is not None and duration_raw != "":
                duration_s = float(duration_raw)
            shots.append(
                Shot(
                    id=sh["id"],
                    order=sh["order"],
                    label=sh["label"],
                    raw_frame_path=sh["raw_frame_path"],
                    scene_index=sh.get("scene_index"),
                    anchor_ref_id=sh.get("anchor_ref_id"),
                    shot_type=sh.get("shot_type", ""),
                    camera_move=sh.get("camera_move", ""),
                    subject_action=sh.get("subject_action", ""),
                    character_count=sh.get("character_count", 1),
                    beat_before_gag=sh.get("beat_before_gag", ""),
                    notes=sh.get("notes", ""),
                    status=sh.get("status", "detected"),
                    character_ids=list(sh.get("character_ids") or []),
                    location_id=sh.get("location_id"),
                    prop_ids=list(sh.get("prop_ids") or []),
                    continuity_state_id=sh.get("continuity_state_id"),
                    continuity_status=sh.get("continuity_status", "not_checked") or "not_checked",
                    generation_complete=bool(sh.get("generation_complete", False)),
                    continuity_approved=bool(sh.get("continuity_approved", False)),
                    description=sh.get("description", "") or "",
                    camera_angle=sh.get("camera_angle", "") or "",
                    lens_composition=sh.get("lens_composition", "") or "",
                    prev_shot_id=sh.get("prev_shot_id"),
                    next_shot_id=sh.get("next_shot_id"),
                    start_keyframe_path=sh.get("start_keyframe_path"),
                    end_keyframe_path=sh.get("end_keyframe_path"),
                    duration_s=duration_s,
                    dialogue_or_sound=sh.get("dialogue_or_sound", "") or "",
                    image_prompt=sh.get("image_prompt", "") or "",
                    video_prompt=sh.get("video_prompt", "") or "",
                    planning_approved=bool(sh.get("planning_approved", False)),
                    planning_approved_at=sh.get("planning_approved_at"),
                    planning_approved_by=sh.get("planning_approved_by", "") or "",
                )
            )
        characters = [
            Character(
                id=c["id"],
                name=c["name"],
                description=c.get("description", "") or "",
                appearance_notes=c.get("appearance_notes", "") or "",
                wardrobe_notes=c.get("wardrobe_notes", "") or "",
                assets=Project._parse_assets(c.get("assets")),
                approved=bool(c.get("approved", False)),
            )
            for c in data.get("characters", []) or []
        ]
        locations = [
            Location(
                id=loc["id"],
                name=loc["name"],
                description=loc.get("description", "") or "",
                lighting_notes=loc.get("lighting_notes", "") or "",
                assets=Project._parse_assets(loc.get("assets")),
                approved=bool(loc.get("approved", False)),
            )
            for loc in data.get("locations", []) or []
        ]
        props = [
            Prop(
                id=p["id"],
                name=p["name"],
                description=p.get("description", "") or "",
                ownership_notes=p.get("ownership_notes", "") or "",
                assets=Project._parse_assets(p.get("assets")),
                approved=bool(p.get("approved", False)),
            )
            for p in data.get("props", []) or []
        ]
        continuity_states = [
            Project._parse_continuity_state(raw) for raw in data.get("continuity_states") or []
        ]
        continuity_exceptions = [
            ContinuityException(
                exception_id=e["exception_id"],
                from_scope=e["from_scope"],
                from_ref=str(e["from_ref"]),
                to_scope=e["to_scope"],
                to_ref=str(e["to_ref"]),
                reason=e.get("reason", "") or "",
                fields_changed=list(e.get("fields_changed") or []),
                approved=bool(e.get("approved", False)),
                approved_at=e.get("approved_at"),
                approved_by=e.get("approved_by", "") or "",
                created_at=e.get("created_at", "") or "",
            )
            for e in data.get("continuity_exceptions") or []
        ]
        ledger_history = [
            LedgerHistoryEntry(
                entry_id=h["entry_id"],
                ts=h["ts"],
                action=h["action"],
                actor=h.get("actor", "") or "",
                summary=h.get("summary", "") or "",
                payload=dict(h.get("payload") or {}),
            )
            for h in data.get("ledger_history") or []
        ]
        continuity_checks = [
            ContinuityCheck(
                check_id=c["check_id"],
                check_type=c["check_type"],
                subject=c["subject"],
                status=c.get("status", "not_checked") or "not_checked",
                confidence=float(c.get("confidence", 0.0) or 0.0),
                message=c.get("message", "") or "",
                evidence_paths=list(c.get("evidence_paths") or []),
                metrics=dict(c.get("metrics") or {}),
                related_exception_id=c.get("related_exception_id"),
                override_reason=c.get("override_reason", "") or "",
                override_by=c.get("override_by", "") or "",
                override_at=c.get("override_at"),
                created_at=c.get("created_at", "") or "",
            )
            for c in data.get("continuity_checks") or []
        ]
        continuity_reports = [
            ContinuityReport(
                report_id=r["report_id"],
                created_at=r.get("created_at", "") or "",
                scope=r.get("scope", "project") or "project",
                summary=r.get("summary", "") or "",
                check_ids=list(r.get("check_ids") or []),
                counts={str(k): int(v) for k, v in (r.get("counts") or {}).items()},
                actor=r.get("actor", "") or "",
            )
            for r in data.get("continuity_reports") or []
        ]
        film_suggestions = [
            FilmSuggestion(
                suggestion_id=s["suggestion_id"],
                kind=s["kind"],
                target_scope=s.get("target_scope", "project") or "project",
                target_ref=str(s.get("target_ref", "") or ""),
                proposed_entity_id=s.get("proposed_entity_id"),
                entity_kind=s.get("entity_kind"),
                title=s.get("title", "") or "",
                summary=s.get("summary", "") or "",
                details=dict(s.get("details") or {}),
                confidence=float(s.get("confidence", 0.0) or 0.0),
                uncertain=bool(s.get("uncertain", True)),
                status=s.get("status", "proposed") or "proposed",
                source=s.get("source", "heuristic_opencv") or "heuristic_opencv",
                evidence_paths=list(s.get("evidence_paths") or []),
                created_at=s.get("created_at", "") or "",
                updated_at=s.get("updated_at", "") or "",
                reviewed_by=s.get("reviewed_by", "") or "",
                review_note=s.get("review_note", "") or "",
            )
            for s in data.get("film_suggestions") or []
        ]
        film_intelligence_runs = [
            FilmIntelligenceRun(
                run_id=r["run_id"],
                created_at=r.get("created_at", "") or "",
                source=r.get("source", "heuristic_opencv") or "heuristic_opencv",
                summary=r.get("summary", "") or "",
                suggestion_ids=list(r.get("suggestion_ids") or []),
                actor=r.get("actor", "") or "",
            )
            for r in data.get("film_intelligence_runs") or []
        ]
        return Project(
            schema_version=data.get("schema_version", 1),
            slug=data["slug"],
            style=style,
            source_video_path=data["source_video_path"],
            scenes=scenes,
            reference_images=refs,
            shots=shots,
            characters=characters,
            locations=locations,
            props=props,
            continuity_states=continuity_states,
            continuity_exceptions=continuity_exceptions,
            ledger_history=ledger_history,
            continuity_checks=continuity_checks,
            continuity_reports=continuity_reports,
            film_suggestions=film_suggestions,
            film_intelligence_runs=film_intelligence_runs,
        )

    @staticmethod
    def _parse_continuity_state(raw: dict[str, Any]) -> ContinuityState:
        loc_raw = raw.get("location_state")
        location_state = None
        if isinstance(loc_raw, dict) and loc_raw.get("location_id"):
            location_state = LocationState(
                location_id=loc_raw["location_id"],
                time_of_day=loc_raw.get("time_of_day", "") or "",
                notes=loc_raw.get("notes", "") or "",
            )
        character_states = [
            CharacterState(
                character_id=c["character_id"],
                wardrobe=c.get("wardrobe", "") or "",
                appearance=c.get("appearance", "") or "",
                holding_prop_ids=list(c.get("holding_prop_ids") or []),
                notes=c.get("notes", "") or "",
            )
            for c in raw.get("character_states") or []
        ]
        prop_states = [
            PropState(
                prop_id=p["prop_id"],
                location_note=p.get("location_note", "") or "",
                owner_character_id=p.get("owner_character_id"),
                notes=p.get("notes", "") or "",
            )
            for p in raw.get("prop_states") or []
        ]
        return ContinuityState(
            state_id=raw["state_id"],
            scope=raw["scope"],
            scene_index=raw.get("scene_index"),
            shot_id=raw.get("shot_id"),
            character_states=character_states,
            location_state=location_state,
            prop_states=prop_states,
            notes=raw.get("notes", "") or "",
            created_at=raw.get("created_at", "") or "",
            updated_at=raw.get("updated_at", "") or "",
        )

    def get_scene(self, scene_index: int) -> Optional[DetectedScene]:
        for s in self.scenes:
            if s.scene_index == scene_index:
                return s
        return None

    def get_ref(self, ref_id: str) -> Optional[ReferenceImage]:
        for r in self.reference_images:
            if r.ref_id == ref_id:
                return r
        return None

    def get_shot(self, shot_id: str) -> Optional[Shot]:
        for s in self.shots:
            if s.id == shot_id:
                return s
        return None


def slugify(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "project"
