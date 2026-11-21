"""Generation queue + history. Retries append candidates; never overwrite."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..model_registry import load_registry
from ..project import GeneratedAsset, ImageGenerationJob, Project
from .pack import ContinuityPack, assemble_continuity_pack, format_pack
from .providers import ImageGenRequest, get_provider


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _candidate_dir(root: Path, slug: str, job_id: str) -> Path:
    return Project.project_dir(root, slug) / "generations" / job_id


def _require_job(project: Project, job_id: str) -> ImageGenerationJob:
    job = project.get_image_generation(job_id)
    if job is None:
        raise KeyError(f"Unknown generation job '{job_id}'")
    return job


def enqueue_shot(
    root: Path,
    project: Project,
    shot_id: str,
    *,
    provider: str = "mock",
    dry_run: bool = False,
    seed: Optional[int] = None,
    negative_prompt: Optional[str] = None,
    actor: str = "system",
    max_attempts: int = 3,
) -> ImageGenerationJob:
    if project.get_shot(shot_id) is None:
        raise KeyError(f"Unknown shot id '{shot_id}'")
    pack = assemble_continuity_pack(project, shot_id)
    provider_name = "dry-run" if dry_run else provider
    # Resolve licence hint from registry when possible
    model_licence = "n/a"
    try:
        reg = load_registry()
        adapter = reg.get_adapter(provider_name)
        if adapter:
            model_licence = adapter.licence or model_licence
    except Exception:
        pass

    job = ImageGenerationJob(
        job_id=_new_id("igen"),
        shot_id=shot_id,
        provider=provider_name,
        status="queued",
        prompt=pack.prompt,
        negative_prompt=negative_prompt if negative_prompt is not None else pack.negative_prompt,
        seed=seed,
        model_licence=model_licence,
        workflow={"kind": "continuity_pack_v1", "dry_run": dry_run or provider_name == "dry-run"},
        settings={},
        reference_assets=deepcopy(pack.references),
        candidates=[],
        continuity_pack_summary=pack.summary,
        queue_attempts=0,
        max_attempts=max_attempts,
        created_at=_now_iso(),
        updated_at=_now_iso(),
        actor=actor,
    )
    project.image_generations.append(job)
    return job


def process_job(root: Path, project: Project, job_id: str, *, force: bool = False) -> ImageGenerationJob:
    job = _require_job(project, job_id)
    if job.status in ("completed", "dry_run") and not force:
        return job
    if job.status == "cancelled":
        raise ValueError(f"Job {job_id} is cancelled")
    if job.queue_attempts >= job.max_attempts and not force:
        job.status = "failed"
        job.last_error = f"max_attempts ({job.max_attempts}) exhausted"
        job.updated_at = _now_iso()
        return job

    job.status = "running"
    job.queue_attempts += 1
    job.updated_at = _now_iso()

    asset_id = _new_id("gasset")
    dest = _candidate_dir(root, project.slug, job.job_id) / f"{asset_id}.png"
    # Never reuse a prior candidate path
    for existing in job.candidates:
        if Path(existing.path).resolve() == dest.resolve():
            asset_id = _new_id("gasset")
            dest = _candidate_dir(root, project.slug, job.job_id) / f"{asset_id}.png"
            break

    ref_paths = [Path(r.path) for r in job.reference_assets if r.path and Path(r.path).is_file()]
    provider = get_provider(job.provider)
    req = ImageGenRequest(
        prompt=job.prompt,
        negative_prompt=job.negative_prompt,
        dest_path=dest,
        reference_paths=ref_paths,
        seed=job.seed,
        settings=dict(job.settings),
        dry_run=job.provider == "dry-run" or bool(job.workflow.get("dry_run")),
    )
    result = provider.generate(req)

    job.model_id = result.model_id or job.model_id
    job.model_version = result.model_version or job.model_version
    job.model_licence = result.model_licence or job.model_licence
    if result.seed is not None:
        job.seed = result.seed

    if result.status == "dry_run":
        job.status = "dry_run"
        job.last_error = ""
        job.updated_at = _now_iso()
        return job

    if result.status in ("failed", "unavailable"):
        job.status = "failed"
        job.last_error = result.message
        job.updated_at = _now_iso()
        return job

    # completed — append candidate; do not touch prior candidates
    out_path = result.output_path or dest
    # Store path even for manual (may not exist yet); still a history row
    candidate = GeneratedAsset(
        asset_id=asset_id,
        path=str(out_path),
        created_at=_now_iso(),
        approval="pending",
        provider=job.provider,
        message=result.message,
    )
    job.candidates.append(candidate)
    job.status = "completed"
    job.last_error = ""
    job.updated_at = _now_iso()
    return job


def process_queue(
    root: Path,
    project: Project,
    *,
    limit: int = 10,
    job_ids: Optional[list[str]] = None,
) -> list[ImageGenerationJob]:
    done: list[ImageGenerationJob] = []
    pending = [
        j
        for j in project.image_generations
        if j.status == "queued" and (job_ids is None or j.job_id in job_ids)
    ]
    for job in pending[:limit]:
        done.append(process_job(root, project, job.job_id))
    return done


def retry_job(root: Path, project: Project, job_id: str) -> ImageGenerationJob:
    """Re-queue and run; appends a new candidate on success (never overwrites)."""
    job = _require_job(project, job_id)
    prior_count = len(job.candidates)
    prior_paths = [c.path for c in job.candidates]
    job.status = "queued"
    job.last_error = ""
    job.updated_at = _now_iso()
    # Allow one more attempt beyond prior failures if exhausted
    if job.queue_attempts >= job.max_attempts:
        job.max_attempts = job.queue_attempts + 1
    processed = process_job(root, project, job_id, force=True)
    # Invariant: previous candidates untouched
    assert len(processed.candidates) >= prior_count
    for i, path in enumerate(prior_paths):
        assert processed.candidates[i].path == path
    return processed


def approve_candidate(
    project: Project,
    job_id: str,
    asset_id: str,
    *,
    approved_by: str = "jay",
) -> GeneratedAsset:
    job = _require_job(project, job_id)
    for cand in job.candidates:
        if cand.asset_id == asset_id:
            cand.approval = "approved"
            cand.approved_by = approved_by
            cand.approved_at = _now_iso()
            cand.rejection_reason = ""
            job.updated_at = _now_iso()
            return cand
    raise KeyError(f"Unknown candidate '{asset_id}' on job '{job_id}'")


def reject_candidate(
    project: Project,
    job_id: str,
    asset_id: str,
    *,
    reason: str = "rejected",
    rejected_by: str = "jay",
) -> GeneratedAsset:
    job = _require_job(project, job_id)
    for cand in job.candidates:
        if cand.asset_id == asset_id:
            cand.approval = "rejected"
            cand.approved_by = rejected_by
            cand.approved_at = _now_iso()
            cand.rejection_reason = reason
            job.updated_at = _now_iso()
            return cand
    raise KeyError(f"Unknown candidate '{asset_id}' on job '{job_id}'")


def list_jobs(project: Project) -> str:
    lines = [f"{len(project.image_generations)} image generation job(s):"]
    for job in project.image_generations:
        lines.append(
            f"  {job.job_id}  shot={job.shot_id}  provider={job.provider}  "
            f"status={job.status}  attempts={job.queue_attempts}/{job.max_attempts}  "
            f"candidates={len(job.candidates)}"
        )
    return "\n".join(lines)


def show_job(project: Project, job_id: str) -> str:
    job = _require_job(project, job_id)
    lines = [
        f"Job {job.job_id}",
        f"  shot: {job.shot_id}",
        f"  provider: {job.provider}",
        f"  status: {job.status}",
        f"  attempts: {job.queue_attempts}/{job.max_attempts}",
        f"  model: {job.model_id or '—'}@{job.model_version or '?'} licence={job.model_licence or '—'}",
        f"  seed: {job.seed}",
        f"  pack: {job.continuity_pack_summary}",
        f"  prompt: {job.prompt[:240]}{'…' if len(job.prompt) > 240 else ''}",
        f"  negative: {job.negative_prompt}",
        f"  last_error: {job.last_error or '(none)'}",
        f"  created: {job.created_at}  updated: {job.updated_at}  actor: {job.actor}",
        f"  references ({len(job.reference_assets)}):",
    ]
    for r in job.reference_assets:
        lines.append(
            f"    - {r.role} {r.entity_id or ''} path={r.path or '(missing)'} "
            f"approved={r.approved}"
        )
    lines.append(f"  candidates ({len(job.candidates)}) — append-only:")
    for c in job.candidates:
        lines.append(
            f"    - {c.asset_id} [{c.approval}] {c.path} "
            f"({c.provider}) {c.message}"
        )
    return "\n".join(lines)


# Re-export pack helpers for CLI convenience
__all__ = [
    "approve_candidate",
    "assemble_continuity_pack",
    "enqueue_shot",
    "format_pack",
    "list_jobs",
    "process_job",
    "process_queue",
    "reject_candidate",
    "retry_job",
    "show_job",
    "ContinuityPack",
]
