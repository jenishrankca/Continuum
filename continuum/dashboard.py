"""Local Continuum production dashboard (browser UI on localhost)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from .project import Project

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _list_project_slugs(root: Path) -> list[str]:
    projects = root / "projects"
    if not projects.is_dir():
        return []
    slugs: list[str] = []
    for child in sorted(projects.iterdir()):
        if child.is_dir() and (child / "project.yaml").is_file():
            slugs.append(child.name)
    return slugs


def _project_summary(root: Path, slug: str) -> dict[str, Any]:
    project = Project.load(root, slug)
    total_scenes = len(project.scenes)
    reviewed = sum(1 for s in project.scenes if s.reviewed)
    kept = sum(1 for s in project.scenes if s.kept)
    shots_total = len(project.shots)
    shots_prompted = sum(1 for s in project.shots if s.status == "prompted")
    refs = len(project.reference_images)
    refs_done = sum(1 for r in project.reference_images if r.restyle_status == "completed")
    out_dir = Project.project_dir(root, slug) / "output"
    return {
        "slug": slug,
        "name": project.style.project_name,
        "schema_version": project.schema_version,
        "scenes_reviewed": reviewed,
        "scenes_total": total_scenes,
        "scenes_kept": kept,
        "shots_prompted": shots_prompted,
        "shots_total": shots_total,
        "refs_done": refs_done,
        "refs_total": refs,
        "characters": len(project.characters),
        "locations": len(project.locations),
        "props": len(project.props),
        "has_storyboard": (out_dir / "storyboard.html").is_file(),
        "has_shotlist": (out_dir / "shotlist.md").is_file(),
        "has_review_overview": (out_dir / "review_overview.html").is_file(),
        "gen_jobs": len(project.image_generations),
        "gen_candidates": sum(len(j.candidates) for j in project.image_generations),
        "gen_queued": sum(1 for j in project.image_generations if j.status == "queued"),
    }


def _project_detail(root: Path, slug: str) -> dict[str, Any]:
    project = Project.load(root, slug)
    summary = _project_summary(root, slug)
    characters = [
        {
            "id": c.id,
            "name": c.name,
            "approved": c.approved,
            "assets": len(c.assets),
            "approved_assets": sum(1 for a in c.assets if a.approved),
        }
        for c in project.characters
    ]
    locations = [
        {
            "id": loc.id,
            "name": loc.name,
            "approved": loc.approved,
            "assets": len(loc.assets),
            "approved_assets": sum(1 for a in loc.assets if a.approved),
        }
        for loc in project.locations
    ]
    props = [
        {
            "id": p.id,
            "name": p.name,
            "approved": p.approved,
            "assets": len(p.assets),
            "approved_assets": sum(1 for a in p.assets if a.approved),
        }
        for p in project.props
    ]
    shots = [
        {
            "id": s.id,
            "order": s.order,
            "label": s.label,
            "description": s.description,
            "status": s.status,
            "shot_type": s.shot_type,
            "camera_angle": s.camera_angle,
            "camera_move": s.camera_move,
            "lens_composition": s.lens_composition,
            "duration_s": s.duration_s,
            "prev_shot_id": s.prev_shot_id,
            "next_shot_id": s.next_shot_id,
            "continuity_state_id": s.continuity_state_id,
            "continuity_status": s.continuity_status,
            "planning_approved": s.planning_approved,
            "anchor_ref_id": s.anchor_ref_id,
            "character_ids": s.character_ids,
            "location_id": s.location_id,
            "prop_ids": s.prop_ids,
        }
        for s in sorted(project.shots, key=lambda x: x.order)
    ]
    scenes = [
        {
            "scene_index": sc.scene_index,
            "reviewed": sc.reviewed,
            "kept": sc.kept,
            "start_s": sc.start_s,
            "end_s": sc.end_s,
            "candidates": len(sc.candidates),
        }
        for sc in project.scenes
    ]
    generations = [
        {
            "job_id": j.job_id,
            "shot_id": j.shot_id,
            "provider": j.provider,
            "status": j.status,
            "candidates": len(j.candidates),
            "attempts": j.queue_attempts,
            "model_id": j.model_id,
        }
        for j in project.image_generations
    ]
    return {
        **summary,
        "style_phrase": project.style.style_phrase,
        "genre_mode": project.style.genre_mode,
        "source_video_path": project.source_video_path,
        "characters_detail": characters,
        "locations_detail": locations,
        "props_detail": props,
        "shots": shots,
        "scenes": scenes,
        "generations": generations,
    }


def create_app(root: Optional[Path] = None) -> FastAPI:
    continuum_root = (root or Path.cwd()).resolve()
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app = FastAPI(title="Continuum Dashboard", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        slugs = _list_project_slugs(continuum_root)
        projects = []
        for slug in slugs:
            try:
                projects.append(_project_summary(continuum_root, slug))
            except Exception as exc:  # noqa: BLE001 — show load errors in UI
                projects.append({"slug": slug, "error": str(exc)})
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "root": str(continuum_root),
                "projects": projects,
            },
        )

    @app.get("/projects/{slug}", response_class=HTMLResponse)
    def project_page(request: Request, slug: str) -> HTMLResponse:
        yaml_path = Project.yaml_path(continuum_root, slug)
        if not yaml_path.is_file():
            raise HTTPException(status_code=404, detail=f"Unknown project '{slug}'")
        try:
            detail = _project_detail(continuum_root, slug)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "project.html",
            {"project": detail, "root": str(continuum_root)},
        )

    @app.get("/projects/{slug}/output/{filename}")
    def project_output(slug: str, filename: str) -> FileResponse:
        if "/" in filename or "\\" in filename or filename.startswith("."):
            raise HTTPException(status_code=400, detail="Invalid filename")
        path = Project.project_dir(continuum_root, slug) / "output" / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Output not found")
        media = "text/html" if filename.endswith(".html") else "text/markdown"
        return FileResponse(path, media_type=media)

    return app


def run_dashboard(host: str = "127.0.0.1", port: int = 8765, root: Optional[Path] = None) -> None:
    import uvicorn

    continuum_root = (root or Path.cwd()).resolve()
    app = create_app(continuum_root)
    print(f"Continuum dashboard: http://{host}:{port}/")
    print(f"Root: {continuum_root}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host=host, port=port, log_level="info")
