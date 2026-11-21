"""Unit tests for continuum.intelligence (Stage 6)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from continuum import intelligence
from continuum.migrate import migrate_project
from continuum.project import (
    SCHEMA_VERSION,
    Character,
    DetectedScene,
    Project,
    ReferenceImage,
    Shot,
    StyleBible,
)


def _jpg(path: Path, color: tuple[int, int, int] = (80, 80, 80)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.zeros((48, 48, 3), dtype=np.uint8)
    img[:] = color
    cv2.imwrite(str(path), img)


def _project(tmp: Path) -> Project:
    frame = tmp / "projects" / "demo" / "frames" / "s0.jpg"
    _jpg(frame, (200, 200, 200))
    return Project(
        schema_version=SCHEMA_VERSION,
        slug="demo",
        style=StyleBible("Demo", "s", "l", "g"),
        source_video_path="projects/clip.mp4",
        scenes=[
            DetectedScene(
                scene_index=0,
                start_s=0.0,
                end_s=2.5,
                reviewed=True,
                kept=True,
                chosen_frame_path=str(frame),
                candidates=[],
            )
        ],
        shots=[
            Shot(
                id="shot-001",
                order=1,
                label="A",
                raw_frame_path=str(frame),
                scene_index=0,
                character_ids=["hero"],
            )
        ],
        characters=[Character(id="hero", name="Hero")],
        reference_images=[
            ReferenceImage(
                ref_id="orphan_ref",
                tag="prop",
                description="mystery object",
                raw_frame_path=str(frame),
            )
        ],
    )


def test_analyze_creates_editable_uncertain_suggestions(tmp_path: Path) -> None:
    project = _project(tmp_path)
    run = intelligence.analyze_project(tmp_path, project)
    assert run.suggestion_ids
    assert any(s.kind == "scene_summary" for s in project.film_suggestions)
    assert any(s.kind == "environment" and s.uncertain for s in project.film_suggestions)
    assert any(s.kind == "character_appearance" for s in project.film_suggestions)
    orphan = next(s for s in project.film_suggestions if "orphan_ref" in s.title)
    assert orphan.uncertain is True
    assert orphan.status == "proposed"
    # Analyze must not invent bible rows
    assert len(project.characters) == 1
    assert len(project.props) == 0


def test_uncertain_accept_requires_flag(tmp_path: Path) -> None:
    project = _project(tmp_path)
    intelligence.analyze_project(tmp_path, project)
    uncertain = next(s for s in project.film_suggestions if s.uncertain)
    with pytest.raises(ValueError, match="uncertain"):
        intelligence.accept_suggestion(project, uncertain.suggestion_id)
    accepted = intelligence.accept_suggestion(
        project, uncertain.suggestion_id, allow_uncertain=True, reviewed_by="jay"
    )
    assert accepted.status == "accepted"
    assert accepted.reviewed_by == "jay"


def test_edit_then_accept_high_confidence(tmp_path: Path) -> None:
    project = _project(tmp_path)
    intelligence.analyze_project(tmp_path, project)
    char = next(s for s in project.film_suggestions if s.kind == "character_appearance")
    edited = intelligence.edit_suggestion(
        project,
        char.suggestion_id,
        summary="Hero clearly in opening beat",
        confidence=0.9,
        reviewed_by="editor",
    )
    assert edited.status == "edited"
    accepted = intelligence.accept_suggestion(project, edited.suggestion_id, reviewed_by="jay")
    assert accepted.status == "accepted"
    assert accepted.uncertain is False


def test_reject(tmp_path: Path) -> None:
    project = _project(tmp_path)
    intelligence.analyze_project(tmp_path, project)
    sug = project.film_suggestions[0]
    rejected = intelligence.reject_suggestion(project, sug.suggestion_id, review_note="noise")
    assert rejected.status == "rejected"


def test_migrate_to_schema_6(tmp_path: Path) -> None:
    slug = "demo"
    proj = tmp_path / "projects" / slug
    proj.mkdir(parents=True)
    jpg = proj / "f.jpg"
    jpg.write_bytes(b"x")
    data = {
        "schema_version": 5,
        "slug": slug,
        "style": {
            "project_name": "Demo",
            "style_phrase": "s",
            "lighting_phrase": "l",
            "grain_grade_phrase": "g",
            "genre_mode": "drama",
            "default_restyle_provider": "manual",
        },
        "source_video_path": "projects/clip.mp4",
        "scenes": [],
        "reference_images": [],
        "shots": [],
        "characters": [],
        "locations": [],
        "props": [],
        "continuity_states": [],
        "continuity_exceptions": [],
        "ledger_history": [],
        "continuity_checks": [],
        "continuity_reports": [],
    }
    with open(proj / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)
    report = migrate_project(tmp_path, slug, dry_run=False)
    assert report.to_version == 6
    loaded = Project.load(tmp_path, slug)
    assert loaded.schema_version == 6
    assert loaded.film_suggestions == []
    assert loaded.film_intelligence_runs == []


def test_roundtrip(tmp_path: Path) -> None:
    project = _project(tmp_path)
    intelligence.analyze_project(tmp_path, project)
    project.slug = "demo"
    (tmp_path / "projects" / "demo").mkdir(parents=True, exist_ok=True)
    project.save(tmp_path)
    loaded = Project.load(tmp_path, "demo")
    assert loaded.schema_version == 6
    assert len(loaded.film_suggestions) >= 1
    assert len(loaded.film_intelligence_runs) == 1
