"""Unit tests for continuum.migrate."""
from __future__ import annotations

from pathlib import Path

import yaml

from continuum.migrate import migrate_project
from continuum.project import SCHEMA_VERSION, Project, StyleBible


def _write_v1_project(root: Path, slug: str) -> None:
    proj_dir = root / "projects" / slug
    frames = proj_dir / "frames" / "raw"
    frames.mkdir(parents=True)
    frame = frames / "scene0000_cand0.jpg"
    frame.write_bytes(b"fake")
    source = root / "projects" / "clip.mp4"
    source.write_bytes(b"fake-mp4")

    data = {
        "schema_version": 1,
        "slug": slug,
        "style": {
            "project_name": "Demo",
            "style_phrase": "test style",
            "lighting_phrase": "flat light",
            "grain_grade_phrase": "clean",
            "genre_mode": "drama",
            "default_restyle_provider": "manual",
        },
        "source_video_path": str(source.resolve()),
        "scenes": [
            {
                "scene_index": 0,
                "start_s": 0.0,
                "end_s": 1.0,
                "candidates": [
                    {
                        "path": str(frame.resolve()),
                        "timestamp_s": 0.5,
                        "frame_number": 12,
                        "sharpness": 1.0,
                    }
                ],
                "reviewed": True,
                "kept": True,
                "chosen_frame_path": str(frame.resolve()),
            }
        ],
        "reference_images": [],
        "shots": [
            {
                "id": "shot-001",
                "order": 1,
                "label": "A",
                "raw_frame_path": str(frame.resolve()),
                "scene_index": 0,
                "status": "kept",
            }
        ],
    }
    yaml_path = proj_dir / "project.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def test_migrate_dry_run_does_not_write(tmp_path: Path) -> None:
    slug = "demo"
    _write_v1_project(tmp_path, slug)
    before = (tmp_path / "projects" / slug / "project.yaml").read_text(encoding="utf-8")
    report = migrate_project(tmp_path, slug, dry_run=True)
    after = (tmp_path / "projects" / slug / "project.yaml").read_text(encoding="utf-8")
    assert report.dry_run is True
    assert report.paths_rewritten >= 1
    assert before == after


def test_migrate_rewrites_and_loads(tmp_path: Path) -> None:
    slug = "demo"
    _write_v1_project(tmp_path, slug)
    report = migrate_project(tmp_path, slug, dry_run=False)
    assert report.to_version == SCHEMA_VERSION
    assert report.paths_rewritten >= 1

    with open(tmp_path / "projects" / slug / "project.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    assert raw["schema_version"] == SCHEMA_VERSION
    assert not Path(raw["source_video_path"]).is_absolute()
    assert raw["source_video_path"].startswith("projects/")

    project = Project.load(tmp_path, slug)
    assert Path(project.source_video_path).is_absolute()
    assert Path(project.source_video_path).exists()
    assert project.schema_version == SCHEMA_VERSION


def test_save_writes_relative_paths(tmp_path: Path) -> None:
    slug = "demo"
    _write_v1_project(tmp_path, slug)
    migrate_project(tmp_path, slug, dry_run=False)
    project = Project.load(tmp_path, slug)
    project.style = StyleBible(
        project_name="Demo2",
        style_phrase=project.style.style_phrase,
        lighting_phrase=project.style.lighting_phrase,
        grain_grade_phrase=project.style.grain_grade_phrase,
    )
    project.save(tmp_path)
    with open(tmp_path / "projects" / slug / "project.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    assert raw["style"]["project_name"] == "Demo2"
    assert not Path(raw["shots"][0]["raw_frame_path"]).is_absolute()
