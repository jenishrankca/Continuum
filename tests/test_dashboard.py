"""Smoke tests for the local Continuum dashboard."""
from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from continuum.dashboard import create_app


def _mini_project(root: Path, slug: str = "demo") -> None:
    proj = root / "projects" / slug
    proj.mkdir(parents=True)
    data = {
        "schema_version": 3,
        "slug": slug,
        "style": {
            "project_name": "Demo Film",
            "style_phrase": "test",
            "lighting_phrase": "flat",
            "grain_grade_phrase": "clean",
            "genre_mode": "drama",
            "default_restyle_provider": "manual",
        },
        "source_video_path": "projects/clip.mp4",
        "scenes": [],
        "reference_images": [],
        "shots": [],
        "characters": [{"id": "hero", "name": "Hero", "assets": [], "approved": False}],
        "locations": [],
        "props": [],
    }
    with open(proj / "project.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)


def test_dashboard_home_and_project(tmp_path: Path) -> None:
    _mini_project(tmp_path)
    client = TestClient(create_app(tmp_path))
    home = client.get("/")
    assert home.status_code == 200
    assert "Continuum" in home.text
    assert "Demo Film" in home.text
    detail = client.get("/projects/demo")
    assert detail.status_code == 200
    assert "hero" in detail.text
    assert "schema v3" in detail.text
