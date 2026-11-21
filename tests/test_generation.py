"""Stage 8 image generation + model registry tests (mock/dry-run only)."""
from __future__ import annotations

from pathlib import Path

import yaml

from continuum import generation, model_registry
from continuum.migrate import migrate_project
from continuum.project import SCHEMA_VERSION, Project, Shot, StyleBible


def _write_project(root: Path, slug: str = "demo") -> None:
    proj = root / "projects" / slug
    frames = proj / "frames" / "raw"
    frames.mkdir(parents=True)
    f1 = frames / "a.jpg"
    f1.write_bytes(b"fake-jpg")
    data = {
        "schema_version": 7,
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
                "label": "Wide",
                "raw_frame_path": str(f1.resolve()),
                "scene_index": 0,
                "shot_type": "wide",
                "camera_move": "static",
                "subject_action": "hero stands",
                "status": "prompted",
                "character_ids": ["hero"],
                "location_id": "office",
            }
        ],
        "characters": [
            {
                "id": "hero",
                "name": "Hero",
                "assets": [
                    {
                        "asset_id": "hero-a",
                        "raw_path": str(f1.resolve()),
                        "approved": True,
                    }
                ],
                "approved": True,
            }
        ],
        "locations": [
            {
                "id": "office",
                "name": "Office",
                "assets": [
                    {
                        "asset_id": "office-a",
                        "raw_path": str(f1.resolve()),
                        "approved": True,
                    }
                ],
                "approved": True,
            }
        ],
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


def test_registry_loads_and_models_empty() -> None:
    reg = model_registry.load_registry()
    assert reg.schema_version == 1
    assert reg.models == []
    assert reg.get_adapter("mock") is not None
    assert reg.get_adapter("comfy") is not None
    errors = model_registry.validate_registry(
        {"schema_version": 1, "adapters": [{"id": "x", "kind": "image"}], "models": []}
    )
    assert errors == []


def test_migrate_to_schema_8(tmp_path: Path) -> None:
    _write_project(tmp_path)
    report = migrate_project(tmp_path, "demo", dry_run=False)
    assert report.to_version == SCHEMA_VERSION
    assert SCHEMA_VERSION == 8
    assert any("Stage 8" in m for m in report.messages)
    project = Project.load(tmp_path, "demo")
    assert project.image_generations == []


def test_pack_assembles_bible_refs(tmp_path: Path) -> None:
    _write_project(tmp_path)
    migrate_project(tmp_path, "demo", dry_run=False)
    project = Project.load(tmp_path, "demo")
    pack = generation.assemble_continuity_pack(project, "shot-001")
    roles = {r.role for r in pack.references}
    assert "character" in roles
    assert "location" in roles
    assert "raw_frame" in roles
    assert pack.prompt


def test_mock_enqueue_run_never_overwrites_on_retry(tmp_path: Path) -> None:
    _write_project(tmp_path)
    migrate_project(tmp_path, "demo", dry_run=False)
    project = Project.load(tmp_path, "demo")

    job = generation.enqueue_shot(tmp_path, project, "shot-001", provider="mock", actor="test")
    generation.process_job(tmp_path, project, job.job_id)
    assert job.status == "completed"
    assert len(job.candidates) == 1
    first_path = job.candidates[0].path
    assert Path(first_path).is_file()

    generation.retry_job(tmp_path, project, job.job_id)
    assert len(job.candidates) == 2
    assert job.candidates[0].path == first_path
    assert job.candidates[1].path != first_path
    assert Path(job.candidates[0].path).is_file()
    assert Path(job.candidates[1].path).is_file()

    generation.approve_candidate(project, job.job_id, job.candidates[0].asset_id, approved_by="qa")
    project.save(tmp_path)
    reloaded = Project.load(tmp_path, "demo")
    assert len(reloaded.image_generations) == 1
    assert reloaded.image_generations[0].candidates[0].approval == "approved"
    # generation approval ≠ continuity approval
    shot = reloaded.get_shot("shot-001")
    assert shot is not None
    assert shot.continuity_approved is False


def test_dry_run_writes_no_candidate_file(tmp_path: Path) -> None:
    _write_project(tmp_path)
    migrate_project(tmp_path, "demo", dry_run=False)
    project = Project.load(tmp_path, "demo")
    job = generation.enqueue_shot(
        tmp_path, project, "shot-001", provider="mock", dry_run=True, actor="test"
    )
    generation.process_job(tmp_path, project, job.job_id)
    assert job.status == "dry_run"
    assert job.candidates == []
    gen_dir = tmp_path / "projects" / "demo" / "generations" / job.job_id
    assert not gen_dir.exists() or not any(gen_dir.glob("*.png"))


def test_providers_probe_includes_mock() -> None:
    rows = {r["name"]: r for r in generation.list_providers()}
    assert rows["mock"]["available"] is True
    assert rows["dry-run"]["available"] is True
    # local/comfy may be DOWN on this machine — that is OK
    assert "local" in rows
    assert "comfy" in rows
