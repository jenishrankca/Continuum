"""Schema / path migrations for Continuum projects."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import paths
from .project import SCHEMA_VERSION, Project


@dataclass
class MigrateReport:
    slug: str
    from_version: int
    to_version: int
    paths_rewritten: int
    dry_run: bool
    messages: list[str]


def _rewrite_path(root: Path, value: str | None, rewritten: list[str], label: str) -> str | None:
    if value is None or value == "":
        return value
    stored = paths.to_stored(root, value)
    if stored != value.replace("\\", "/"):
        # Count when absolute → relative, or slash normalization changes meaning of storage
        if Path(value).is_absolute() or stored != value:
            rewritten.append(f"{label}: {value} -> {stored}")
    return stored


def migrate_project(root: Path, slug: str, *, dry_run: bool = False) -> MigrateReport:
    """Load a project, rewrite paths to root-relative form, bump schema_version."""
    path = Project.yaml_path(root, slug)
    if not path.exists():
        raise FileNotFoundError(f"No project.yaml for slug '{slug}' at {path}")

    # Load without resolving so we can see raw stored values
    import yaml

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    from_version = int(raw.get("schema_version", 1))
    rewritten: list[str] = []

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

    raw["schema_version"] = SCHEMA_VERSION
    messages = list(rewritten)
    if from_version != SCHEMA_VERSION:
        messages.append(f"schema_version: {from_version} -> {SCHEMA_VERSION}")

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)
        # Round-trip through Project to ensure it still loads
        Project.load(root, slug)

    return MigrateReport(
        slug=slug,
        from_version=from_version,
        to_version=SCHEMA_VERSION,
        paths_rewritten=len(rewritten),
        dry_run=dry_run,
        messages=messages,
    )
