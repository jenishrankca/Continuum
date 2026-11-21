"""Unit tests for continuum.bible (Stage 3)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from continuum import bible
from continuum.migrate import migrate_project
from continuum.project import Project, ReferenceImage, SCHEMA_VERSION, Shot, StyleBible


def _seed_project(root: Path, slug: str = "demo") -> Project:
    proj = root / "projects" / slug
    frames = proj / "frames" / "raw"
    frames.mkdir(parents=True)
    frame = frames / "a.jpg"
    frame.write_bytes(b"x")
    source = root / "projects" / "clip.mp4"
    source.write_bytes(b"x")
    data = {
        "schema_version": 2,
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
        "reference_images": [
            {
                "ref_id": "hero_ref",
                "tag": "character",
                "description": "Hero in coat",
                "raw_frame_path": "projects/demo/frames/raw/a.jpg",
                "styled_frame_path": None,
                "restyle_status": "pending",
                "restyle_provider": "manual",
            },
            {
                "ref_id": "office_set",
                "tag": "set",
                "description": "Office floor",
                "raw_frame_path": "projects/demo/frames/raw/a.jpg",
                "styled_frame_path": None,
                "restyle_status": "pending",
                "restyle_provider": "manual",
            },
            {
                "ref_id": "sign_prop",
                "tag": "prop",
                "description": "Danger sign",
                "raw_frame_path": "projects/demo/frames/raw/a.jpg",
                "styled_frame_path": None,
                "restyle_status": "completed",
                "restyle_provider": "manual",
            },
        ],
        "shots": [
            {
                "id": "shot_001",
                "order": 1,
                "label": "Open",
                "raw_frame_path": "projects/demo/frames/raw/a.jpg",
                "anchor_ref_id": "hero_ref",
                "status": "prompted",
            },
            {
                "id": "shot_002",
                "order": 2,
                "label": "Wide",
                "raw_frame_path": "projects/demo/frames/raw/a.jpg",
                "anchor_ref_id": "office_set",
                "status": "prompted",
            },
        ],
        "characters": [],
        "locations": [],
        "props": [],
    }
    with open(proj / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    return Project.load(root, slug)


def test_promote_creates_entities_and_links_shots(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    counts = bible.promote_from_reference_images(project)
    assert counts["character"] == 1
    assert counts["location"] == 1
    assert counts["prop"] == 1
    assert bible.get_character(project, "hero_ref") is not None
    assert bible.get_location(project, "office_set") is not None
    assert bible.get_prop(project, "sign_prop") is not None
    assert project.shots[0].character_ids == ["hero_ref"]
    assert project.shots[1].location_id == "office_set"
    # completed restyle → asset pre-approved
    assert bible.get_prop(project, "sign_prop").assets[0].approved is True


def test_approve_asset_blocks_overwrite(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    bible.promote_from_reference_images(project)
    bible.approve_asset(
        project, kind="character", entity_id="hero_ref", asset_id="hero_ref-asset"
    )
    with pytest.raises(ValueError, match="approved"):
        bible.attach_asset(
            project,
            kind="character",
            entity_id="hero_ref",
            asset_id="hero_ref-asset",
            raw_path="projects/demo/frames/raw/other.jpg",
        )
    # New asset id is allowed
    asset = bible.attach_asset(
        project,
        kind="character",
        entity_id="hero_ref",
        asset_id="hero_ref-asset-v2",
        raw_path="projects/demo/frames/raw/a.jpg",
    )
    assert asset.asset_id == "hero_ref-asset-v2"
    assert len(bible.get_character(project, "hero_ref").assets) == 2


def test_migrate_to_v3_promotes_bible(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    report = migrate_project(tmp_path, "demo", dry_run=False)
    assert report.to_version == SCHEMA_VERSION
    assert report.bible_created is not None
    assert report.bible_created["character"] == 1
    project = Project.load(tmp_path, "demo")
    assert project.schema_version == SCHEMA_VERSION
    assert len(project.characters) == 1
    assert project.shots[0].character_ids == ["hero_ref"]


def test_link_shot_and_add_entity(tmp_path: Path) -> None:
    project = _seed_project(tmp_path)
    bible.promote_from_reference_images(project)
    bible.add_character(project, entity_id="extra", name="Extra")
    bible.link_shot(project, shot_id="shot_001", character_ids=["extra"])
    assert "extra" in project.shots[0].character_ids
    assert "hero_ref" in project.shots[0].character_ids
    project.save(tmp_path)
    reloaded = Project.load(tmp_path, "demo")
    assert "extra" in reloaded.shots[0].character_ids
