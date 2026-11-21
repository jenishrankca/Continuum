# Continuum — Claude / Studio rules

- Prefer the existing Phase 1 CLI in `continuum/`; do not add automatic video generation unless Jay asks.
- Keep style / lighting / grade phrases locked in `projects/<slug>/project.yaml` and reuse them identically in every shot prompt.
- Never commit `.env`, `.venv/`, or personal film source files.
- Before handing back code changes: the package imports cleanly (`python -m continuum --help` or equivalent) and any touched project still passes `generate-shotlist --strict` when a slug exists.
- Jay approves anything public, paid, new accounts, new libraries, or big scope changes.
- Studio CEO dashboard is **local HTML** at `company/dashboard/index.html` (see `dashboard_url` in `company/studio.json`). After board/activity edits, run `python -m continuum studio-dashboard --rebuild`. Do not use Claude.ai ArtifactData URLs for Continuum’s Studio board.
