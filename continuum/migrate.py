"""Schema / path migrations for Continuum projects."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from . import bible, paths
from .project import SCHEMA_VERSION, Project


@dataclass
class MigrateReport:
    slug: str
    from_version: int
    to_version: int
    paths_rewritten: int
    dry_run: bool
    messages: list[str]
    bible_created: dict[str, int] | None = None


def _rewrite_path(root: Path, value: str | None, rewritten: list[str], label: str) -> str | None:
    if value is None or value == "":
        return value
    stored = paths.to_stored(root, value)
    if stored != value.replace("\\", "/"):
        if Path(value).is_absolute() or stored != value:
            rewritten.append(f"{label}: {value} -> {stored}")
    return stored


def _rewrite_all_paths(root: Path, raw: dict, rewritten: list[str]) -> None:
    raw["source_video_path"] = _rewrite_path(
        root, raw.get("source_video_path"), rewritten, "source_video_path"
    )
    for scene in raw.get("scenes", []) or []:
        idx = scene.get("scene_index")
        scene["chosen_frame_path"] = _rewrite_path(
            root, scene.get("chosen_frame_path"), rewritten, f"scene[{idx}].chosen_frame_path"
        )
        for i, cand in enumerate(scene.get("candidates", []) or []):
            cand["path"] = _rewrite_path(
                root, cand.get("path"), rewritten, f"scene[{idx}].candidates[{i}].path"
            )
    for ref in raw.get("reference_images", []) or []:
        rid = ref.get("ref_id")
        ref["raw_frame_path"] = _rewrite_path(
            root, ref.get("raw_frame_path"), rewritten, f"ref[{rid}].raw_frame_path"
        )
        ref["styled_frame_path"] = _rewrite_path(
            root, ref.get("styled_frame_path"), rewritten, f"ref[{rid}].styled_frame_path"
        )
    for shot in raw.get("shots", []) or []:
        sid = shot.get("id")
        shot["raw_frame_path"] = _rewrite_path(
            root, shot.get("raw_frame_path"), rewritten, f"shot[{sid}].raw_frame_path"
        )
        shot["start_keyframe_path"] = _rewrite_path(
            root, shot.get("start_keyframe_path"), rewritten, f"shot[{sid}].start_keyframe_path"
        )
        shot["end_keyframe_path"] = _rewrite_path(
            root, shot.get("end_keyframe_path"), rewritten, f"shot[{sid}].end_keyframe_path"
        )
        shot.setdefault("character_ids", [])
        shot.setdefault("prop_ids", [])
        if "location_id" not in shot:
            shot["location_id"] = None
        if "continuity_state_id" not in shot:
            shot["continuity_state_id"] = None
        shot.setdefault("continuity_status", "not_checked")
        shot.setdefault("generation_complete", False)
        shot.setdefault("continuity_approved", False)
        # Stage 7 storyboard / shot planning defaults
        shot.setdefault("description", "")
        shot.setdefault("camera_angle", "")
        shot.setdefault("lens_composition", "")
        if "prev_shot_id" not in shot:
            shot["prev_shot_id"] = None
        if "next_shot_id" not in shot:
            shot["next_shot_id"] = None
        if "start_keyframe_path" not in shot:
            shot["start_keyframe_path"] = None
        if "end_keyframe_path" not in shot:
            shot["end_keyframe_path"] = None
        if "duration_s" not in shot:
            shot["duration_s"] = None
        shot.setdefault("dialogue_or_sound", "")
        shot.setdefault("image_prompt", "")
        shot.setdefault("video_prompt", "")
        shot.setdefault("planning_approved", False)
        if "planning_approved_at" not in shot:
            shot["planning_approved_at"] = None
        shot.setdefault("planning_approved_by", "")
    for group in ("characters", "locations", "props"):
        for ent in raw.get(group, []) or []:
            eid = ent.get("id")
            for asset in ent.get("assets", []) or []:
                aid = asset.get("asset_id")
                asset["raw_path"] = _rewrite_path(
                    root, asset.get("raw_path"), rewritten, f"{group}[{eid}].asset[{aid}].raw_path"
                )
                asset["styled_path"] = _rewrite_path(
                    root,
                    asset.get("styled_path"),
                    rewritten,
                    f"{group}[{eid}].asset[{aid}].styled_path",
                )


def migrate_project(root: Path, slug: str, *, dry_run: bool = False) -> MigrateReport:
    """Rewrite paths to root-relative form, promote bible entities, bump schema_version."""
    path = Project.yaml_path(root, slug)
    if not path.exists():
        raise FileNotFoundError(f"No project.yaml for slug '{slug}' at {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    from_version = int(raw.get("schema_version", 1))
    rewritten: list[str] = []
    _rewrite_all_paths(root, raw, rewritten)

    raw.setdefault("characters", [])
    raw.setdefault("locations", [])
    raw.setdefault("props", [])
    raw.setdefault("continuity_states", [])
    raw.setdefault("continuity_exceptions", [])
    raw.setdefault("ledger_history", [])
    raw.setdefault("continuity_checks", [])
    raw.setdefault("continuity_reports", [])
    raw.setdefault("film_suggestions", [])
    raw.setdefault("film_intelligence_runs", [])

    # Temporarily write so Project.load can promote (or work in-memory)
    raw["schema_version"] = SCHEMA_VERSION
    messages = list(rewritten)
    if from_version != SCHEMA_VERSION:
        messages.append(f"schema_version: {from_version} -> {SCHEMA_VERSION}")
    if from_version < 4:
        messages.append("Stage 4: continuity ledger lists initialized (empty until CLI writes)")
    if from_version < 5:
        messages.append("Stage 5: continuity inspection checks/reports initialized")
    if from_version < 6:
        messages.append("Stage 6: film intelligence suggestions initialized (editable; not auto-fact)")
    if from_version < 7:
        messages.append(
            "Stage 7: storyboard/shot planning fields initialized "
            "(camera_angle, keyframes, prompts, prev/next, planning_approved)"
        )
        # Wire prev/next from order only when both unset (non-destructive)
        ordered = sorted(raw.get("shots", []) or [], key=lambda s: int(s.get("order", 0)))
        linked = 0
        for i, shot in enumerate(ordered):
            if shot.get("prev_shot_id") is None and shot.get("next_shot_id") is None:
                if i > 0:
                    shot["prev_shot_id"] = ordered[i - 1].get("id")
                if i + 1 < len(ordered):
                    shot["next_shot_id"] = ordered[i + 1].get("id")
                linked += 1
        if linked:
            messages.append(f"Stage 7: linked prev/next for {linked} shot(s) from order")

    bible_created: dict[str, int] | None = None
    if dry_run:
        # Simulate promote without writing
        project = Project._from_dict(raw)
        before = (
            len(project.characters),
            len(project.locations),
            len(project.props),
        )
        bible_created = bible.promote_from_reference_images(project)
        messages.append(
            f"bible promote (dry-run): +{bible_created['character']} characters, "
            f"+{bible_created['location']} locations, +{bible_created['prop']} props "
            f"(skipped {bible_created['skipped']}); was {before}"
        )
    else:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)
        project = Project.load(root, slug)
        bible_created = bible.promote_from_reference_images(project)
        messages.append(
            f"bible promote: +{bible_created['character']} characters, "
            f"+{bible_created['location']} locations, +{bible_created['prop']} props "
            f"(skipped {bible_created['skipped']})"
        )
        project.save(root)

    return MigrateReport(
        slug=slug,
        from_version=from_version,
        to_version=SCHEMA_VERSION,
        paths_rewritten=len(rewritten),
        dry_run=dry_run,
        messages=messages,
        bible_created=bible_created,
    )
