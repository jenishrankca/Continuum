"""Unit tests for continuum.inspection (Stage 5)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from continuum import inspection
from continuum.migrate import migrate_project
from continuum.project import (
    SCHEMA_VERSION,
    Character,
    CharacterState,
    ContinuityException,
    ContinuityState,
    DetectedScene,
    Location,
    LocationState,
    Project,
    Prop,
    PropState,
    Shot,
    StyleBible,
)


def _write_solid(path: Path, bgr: tuple[int, int, int], size: int = 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.zeros((size, size, 3), dtype=np.uint8)
    img[:] = bgr
    cv2.imwrite(str(path), img)


def _base_project(tmp: Path) -> Project:
    frames = tmp / "projects" / "demo" / "frames"
    a = frames / "a.jpg"
    b = frames / "b.jpg"
    _write_solid(a, (40, 40, 200))  # reddish
    _write_solid(b, (40, 40, 190))  # similar
    return Project(
        schema_version=SCHEMA_VERSION,
        slug="demo",
        style=StyleBible("Demo", "s", "l", "g"),
        source_video_path="projects/clip.mp4",
        scenes=[
            DetectedScene(0, 0.0, 1.0),
            DetectedScene(1, 1.0, 2.0),
        ],
        shots=[
            Shot(
                id="shot-001",
                order=1,
                label="A",
                raw_frame_path=str(a),
                scene_index=0,
                character_ids=["hero"],
            ),
            Shot(
                id="shot-002",
                order=2,
                label="B",
                raw_frame_path=str(b),
                scene_index=1,
                character_ids=["hero"],
            ),
        ],
        characters=[
            Character(
                id="hero",
                name="Hero",
                assets=[],
            )
        ],
        locations=[Location(id="studio", name="Studio")],
        props=[Prop(id="bag", name="Bag")],
    )


def test_compare_similar_frames(tmp_path: Path) -> None:
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_solid(a, (30, 30, 30))
    _write_solid(b, (32, 32, 32))
    result = inspection.compare_frames(a, b)
    assert result["ok"] is True
    assert result["status"] in ("passed", "warning")
    assert 0.0 <= result["confidence"] <= 1.0


def test_compare_divergent_frames(tmp_path: Path) -> None:
    a = tmp_path / "a.jpg"
    b = tmp_path / "b.jpg"
    _write_solid(a, (0, 0, 0))
    _write_solid(b, (0, 0, 255))
    result = inspection.compare_frames(a, b)
    assert result["ok"] is True
    assert result["status"] in ("warning", "failed")


def test_ledger_transition_respects_approved_exception(tmp_path: Path) -> None:
    project = _base_project(tmp_path)
    project.continuity_states = [
        ContinuityState(
            state_id="s0",
            scope="scene",
            scene_index=0,
            character_states=[CharacterState(character_id="hero", wardrobe="red")],
            location_state=LocationState(location_id="studio"),
            prop_states=[PropState(prop_id="bag", location_note="hand")],
        ),
        ContinuityState(
            state_id="s1",
            scope="scene",
            scene_index=1,
            character_states=[CharacterState(character_id="hero", wardrobe="blue")],
            location_state=LocationState(location_id="studio"),
            prop_states=[PropState(prop_id="bag", location_note="floor")],
        ),
    ]
    checks = inspection.inspect_ledger_transition(project, 0, 1)
    assert any(c.status == "failed" for c in checks)

    project.continuity_exceptions.append(
        ContinuityException(
            exception_id="exc-1",
            from_scope="scene",
            from_ref="0",
            to_scope="scene",
            to_ref="1",
            reason="costume gag",
            fields_changed=["wardrobe", "prop.location_note"],
            approved=True,
            approved_by="jay",
        )
    )
    checks2 = inspection.inspect_ledger_transition(project, 0, 1)
    assert all(c.status != "failed" for c in checks2)
    assert any(c.related_exception_id == "exc-1" for c in checks2)


def test_generation_complete_does_not_approve(tmp_path: Path) -> None:
    project = _base_project(tmp_path)
    shot = inspection.mark_generation_complete(project, "shot-001")
    assert shot.generation_complete is True
    assert shot.continuity_approved is False
    approved = inspection.approve_shot_continuity(project, "shot-001", approved_by="jay")
    assert approved.continuity_approved is True


def test_override_check(tmp_path: Path) -> None:
    project = _base_project(tmp_path)
    report = inspection.run_inspection(tmp_path, project)
    assert report.check_ids
    chk_id = report.check_ids[0]
    chk = inspection.override_check(
        project, chk_id, reason="Intentional cut", overridden_by="jay"
    )
    assert chk.status == "human_override"
    assert chk.override_reason == "Intentional cut"


def test_migrate_to_schema_5(tmp_path: Path) -> None:
    slug = "demo"
    proj = tmp_path / "projects" / slug
    proj.mkdir(parents=True)
    jpg = proj / "f.jpg"
    jpg.write_bytes(b"x")
    data = {
        "schema_version": 4,
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
        "shots": [
            {
                "id": "shot-001",
                "order": 1,
                "label": "A",
                "raw_frame_path": str(jpg),
                "character_ids": [],
                "prop_ids": [],
            }
        ],
        "characters": [],
        "locations": [],
        "props": [],
        "continuity_states": [],
        "continuity_exceptions": [],
        "ledger_history": [],
    }
    with open(proj / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)
    report = migrate_project(tmp_path, slug, dry_run=False)
    assert report.to_version == 5
    loaded = Project.load(tmp_path, slug)
    assert loaded.schema_version == 5
    assert loaded.continuity_checks == []
    assert loaded.shots[0].continuity_status == "not_checked"
    assert loaded.shots[0].generation_complete is False
    assert loaded.shots[0].continuity_approved is False


def test_run_inspection_writes_report(tmp_path: Path) -> None:
    project = _base_project(tmp_path)
    report = inspection.run_inspection(tmp_path, project)
    assert len(project.continuity_checks) >= 1
    assert report.report_id in {r.report_id for r in project.continuity_reports}
    project.slug = "demo"
    (tmp_path / "projects" / "demo").mkdir(parents=True, exist_ok=True)
    project.save(tmp_path)
    loaded = Project.load(tmp_path, "demo")
    assert loaded.schema_version == 5
    assert len(loaded.continuity_checks) >= 1
