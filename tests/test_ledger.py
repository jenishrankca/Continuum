"""Unit tests for continuum.ledger (Stage 4)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from continuum import ledger
from continuum.migrate import migrate_project
from continuum.project import (
    SCHEMA_VERSION,
    Character,
    Location,
    Project,
    Prop,
    StyleBible,
)


def _project_with_bible() -> Project:
    return Project(
        schema_version=SCHEMA_VERSION,
        slug="demo",
        style=StyleBible(
            project_name="Demo",
            style_phrase="s",
            lighting_phrase="l",
            grain_grade_phrase="g",
        ),
        source_video_path="projects/clip.mp4",
        scenes=[],
        characters=[Character(id="hero", name="Hero")],
        locations=[Location(id="studio", name="Studio")],
        props=[Prop(id="suitcase", name="Suitcase")],
    )


def test_scene_state_set_and_query() -> None:
    project = _project_with_bible()
    # Scene index validation needs a scene row
    from continuum.project import DetectedScene

    project.scenes.append(
        DetectedScene(scene_index=0, start_s=0.0, end_s=1.0, reviewed=True, kept=True)
    )
    project.scenes.append(
        DetectedScene(scene_index=1, start_s=1.0, end_s=2.0, reviewed=True, kept=True)
    )

    s0 = ledger.ensure_scene_state(project, 0, actor="test")
    ledger.set_character_state(
        project,
        s0,
        character_id="hero",
        wardrobe="red jacket",
        holding_prop_ids=["suitcase"],
        actor="test",
    )
    ledger.set_location_state(
        project, s0, location_id="studio", time_of_day="day", actor="test"
    )
    ledger.set_prop_state(
        project,
        s0,
        prop_id="suitcase",
        location_note="right hand",
        owner_character_id="hero",
        actor="test",
    )

    rows = ledger.query_character(project, "hero")
    assert len(rows) == 1
    assert rows[0]["wardrobe"] == "red jacket"
    assert rows[0]["holding_prop_ids"] == ["suitcase"]

    s1 = ledger.copy_state(
        project, from_state=s0, to_scope="scene", to_scene_index=1, actor="test"
    )
    ledger.set_prop_state(
        project,
        s1,
        prop_id="suitcase",
        location_note="beside the door",
        clear_owner=True,
        actor="test",
    )
    prop_rows = ledger.query_prop(project, "suitcase")
    assert len(prop_rows) == 2
    assert prop_rows[1]["location_note"] == "beside the door"
    assert prop_rows[1]["owner_character_id"] is None


def test_exception_approval_is_audited_and_immutable_history() -> None:
    project = _project_with_bible()
    from continuum.project import DetectedScene

    project.scenes.append(DetectedScene(scene_index=0, start_s=0.0, end_s=1.0))
    project.scenes.append(DetectedScene(scene_index=1, start_s=1.0, end_s=2.0))
    ledger.ensure_scene_state(project, 0, actor="test")
    ledger.ensure_scene_state(project, 1, actor="test")

    exc = ledger.add_exception(
        project,
        from_scope="scene",
        from_ref="0",
        to_scope="scene",
        to_ref="1",
        reason="Wardrobe change is intentional mid-sketch gag",
        fields_changed=["wardrobe"],
        actor="test",
    )
    assert exc.approved is False
    hist_len = len(project.ledger_history)
    first_id = project.ledger_history[0].entry_id

    approved = ledger.approve_exception(project, exc.exception_id, approved_by="jay", actor="test")
    assert approved.approved is True
    assert approved.approved_by == "jay"
    assert len(project.ledger_history) == hist_len + 1
    # Prior history rows untouched
    assert project.ledger_history[0].entry_id == first_id

    with pytest.raises(ValueError, match="already approved"):
        ledger.approve_exception(project, exc.exception_id, approved_by="jay")


def test_unknown_bible_id_rejected() -> None:
    project = _project_with_bible()
    from continuum.project import DetectedScene

    project.scenes.append(DetectedScene(scene_index=0, start_s=0.0, end_s=1.0))
    state = ledger.ensure_scene_state(project, 0, actor="test")
    with pytest.raises(ValueError, match="Unknown character"):
        ledger.set_character_state(project, state, character_id="nope", wardrobe="x")


def test_migrate_to_schema_4(tmp_path: Path) -> None:
    slug = "demo"
    proj = tmp_path / "projects" / slug
    proj.mkdir(parents=True)
    frame = proj / "frames" / "raw"
    frame.mkdir(parents=True)
    jpg = frame / "a.jpg"
    jpg.write_bytes(b"x")
    data = {
        "schema_version": 3,
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
    }
    with open(proj / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)

    report = migrate_project(tmp_path, slug, dry_run=False)
    assert report.to_version == 4
    loaded = Project.load(tmp_path, slug)
    assert loaded.schema_version == 4
    assert loaded.continuity_states == []
    assert loaded.continuity_exceptions == []
    assert loaded.ledger_history == []
    assert loaded.shots[0].continuity_state_id is None


def test_roundtrip_yaml(tmp_path: Path) -> None:
    project = _project_with_bible()
    from continuum.project import DetectedScene, Shot

    project.scenes.append(DetectedScene(scene_index=0, start_s=0.0, end_s=1.0))
    project.shots.append(
        Shot(id="shot-001", order=1, label="A", raw_frame_path="projects/demo/a.jpg", scene_index=0)
    )
    state = ledger.ensure_scene_state(project, 0, actor="test")
    ledger.set_character_state(project, state, character_id="hero", wardrobe="coat", actor="test")
    project.slug = "rt"
    (tmp_path / "projects" / "rt").mkdir(parents=True)
    project.save(tmp_path)
    loaded = Project.load(tmp_path, "rt")
    assert loaded.schema_version == 4
    assert len(loaded.continuity_states) == 1
    assert loaded.continuity_states[0].character_states[0].wardrobe == "coat"
    assert len(loaded.ledger_history) >= 2
