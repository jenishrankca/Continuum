"""Stage 7 storyboard / shot planning tests."""
from __future__ import annotations

from pathlib import Path

import yaml

from continuum import prompt_builder, shot_plan
from continuum.migrate import migrate_project
from continuum.project import SCHEMA_VERSION, Project, Shot, StyleBible


def _style() -> StyleBible:
    return StyleBible(
        project_name="Demo",
        style_phrase="grainy 16mm",
        lighting_phrase="soft window light",
        grain_grade_phrase="warm grade",
        genre_mode="drama",
        default_restyle_provider="manual",
    )


def _write_project(root: Path, slug: str = "demo", *, schema: int = 6) -> None:
    proj = root / "projects" / slug
    frames = proj / "frames" / "raw"
    frames.mkdir(parents=True)
    f1 = frames / "a.jpg"
    f2 = frames / "b.jpg"
    f1.write_bytes(b"a")
    f2.write_bytes(b"b")
    data = {
        "schema_version": schema,
        "slug": slug,
        "style": {
            "project_name": "Demo",
            "style_phrase": "grainy 16mm",
            "lighting_phrase": "soft window light",
            "grain_grade_phrase": "warm grade",
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
                "label": "Wide open",
                "raw_frame_path": str(f1.resolve()),
                "scene_index": 0,
                "shot_type": "wide",
                "camera_move": "static",
                "subject_action": "hero stands in doorway",
                "status": "prompted",
                "character_ids": ["hero"],
                "location_id": "office",
            },
            {
                "id": "shot-002",
                "order": 2,
                "label": "Close",
                "raw_frame_path": str(f2.resolve()),
                "scene_index": 0,
                "shot_type": "close-up",
                "camera_move": "slow push-in",
                "subject_action": "hero glances at sign",
                "status": "prompted",
            },
        ],
        "characters": [],
        "locations": [],
        "props": [],
        "continuity_states": [],
        "continuity_exceptions": [],
        "ledger_history": [],
        "continuity_checks": [],
        "continuity_reports": [],
        "film_suggestions": [],
        "film_intelligence_runs": [],
    }
    with open(proj / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def test_build_prompt_back_compat_without_stage7_fields() -> None:
    shot = Shot(
        id="shot-001",
        order=1,
        label="A",
        raw_frame_path="x.jpg",
        shot_type="wide",
        camera_move="static",
        subject_action="hero enters",
    )
    style = _style()
    prompt = prompt_builder.build_prompt(shot, style)
    assert "wide of hero enters" in prompt
    assert "static" in prompt
    assert "soft window light" in prompt
    assert prompt_builder.effective_image_prompt(shot, style) == prompt


def test_image_prompt_override_wins() -> None:
    shot = Shot(
        id="shot-001",
        order=1,
        label="A",
        raw_frame_path="x.jpg",
        shot_type="wide",
        camera_move="static",
        subject_action="hero enters",
        image_prompt="CUSTOM IMAGE PROMPT",
    )
    style = _style()
    assert prompt_builder.effective_image_prompt(shot, style) == "CUSTOM IMAGE PROMPT"
    assert "wide of" in prompt_builder.build_prompt(shot, style)


def test_angle_and_lens_enrich_built_prompt() -> None:
    shot = Shot(
        id="shot-001",
        order=1,
        label="A",
        raw_frame_path="x.jpg",
        shot_type="medium",
        camera_move="tracking",
        camera_angle="low angle",
        lens_composition="35mm, rule of thirds",
        subject_action="hero walks",
    )
    prompt = prompt_builder.build_prompt(shot, _style())
    assert "low angle" in prompt
    assert "35mm, rule of thirds" in prompt


def test_migrate_v6_to_v7_sets_defaults_and_links(tmp_path: Path) -> None:
    _write_project(tmp_path, schema=6)
    report = migrate_project(tmp_path, "demo", dry_run=False)
    assert report.to_version == SCHEMA_VERSION
    assert SCHEMA_VERSION == 7
    assert any("Stage 7" in m for m in report.messages)

    project = Project.load(tmp_path, "demo")
    assert project.schema_version == 7
    s1 = project.get_shot("shot-001")
    s2 = project.get_shot("shot-002")
    assert s1 is not None and s2 is not None
    assert s1.description == ""
    assert s1.camera_angle == ""
    assert s1.planning_approved is False
    assert s1.continuity_approved is False
    assert s1.prev_shot_id is None
    assert s1.next_shot_id == "shot-002"
    assert s2.prev_shot_id == "shot-001"
    assert s2.next_shot_id is None


def test_update_link_sync_approve(tmp_path: Path) -> None:
    _write_project(tmp_path, schema=6)
    migrate_project(tmp_path, "demo", dry_run=False)
    project = Project.load(tmp_path, "demo")

    shot_plan.update_shot(
        project,
        "shot-001",
        description="Hero framed in doorway",
        camera_angle="eye level",
        lens_composition="50mm",
        duration_s=3.5,
        dialogue_or_sound="soft room tone",
        continuity_state_id="state-scene-0",
    )
    counts = shot_plan.sync_prompts(project)
    assert counts["image_prompt"] >= 1
    shot_plan.approve_planning(project, "shot-001", approved_by="qa")
    project.save(tmp_path)

    reloaded = Project.load(tmp_path, "demo")
    s = reloaded.get_shot("shot-001")
    assert s is not None
    assert s.description == "Hero framed in doorway"
    assert s.camera_angle == "eye level"
    assert s.duration_s == 3.5
    assert s.image_prompt
    assert s.planning_approved is True
    assert s.planning_approved_by == "qa"
    assert s.continuity_approved is False  # must stay false


def test_link_sequence_overwrite(tmp_path: Path) -> None:
    _write_project(tmp_path, schema=7)
    # Pre-seed broken links
    with open(tmp_path / "projects" / "demo" / "project.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    raw["shots"][0]["prev_shot_id"] = "bogus"
    raw["shots"][0]["next_shot_id"] = "bogus"
    with open(tmp_path / "projects" / "demo" / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f)

    project = Project.load(tmp_path, "demo")
    n = shot_plan.link_sequence(project, overwrite=True)
    assert n >= 1
    assert project.get_shot("shot-001").next_shot_id == "shot-002"
    assert project.get_shot("shot-001").prev_shot_id is None
