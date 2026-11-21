"""Stage 8 local image generation orchestrator + providers."""
from __future__ import annotations

from .orchestrator import (
    approve_candidate,
    enqueue_shot,
    list_jobs,
    process_job,
    process_queue,
    reject_candidate,
    retry_job,
    show_job,
)
from .pack import assemble_continuity_pack, format_pack
from .providers import list_providers, probe_provider

__all__ = [
    "approve_candidate",
    "assemble_continuity_pack",
    "enqueue_shot",
    "format_pack",
    "list_jobs",
    "list_providers",
    "probe_provider",
    "process_job",
    "process_queue",
    "reject_candidate",
    "retry_job",
    "show_job",
]
