---
id: 20261121-03
title: Stage 2 — continuity-ready store, relative paths, migrate harness
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, shotlist-engineer, security-officer]
status: done
needs_jay: false
depends_on: [20261121-01]
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Stage 2: project-relative paths, migrate harness, tests scaffold.

## Done when
- [x] v1 sample project still loads after migrate
- [x] Absolute paths rewritten to project-relative on load/save
- [x] `continuum migrate <slug> [--dry-run]`
- [x] Unit tests for path resolver + migrate (6 passed)
- [x] Phase 1 CLI still works (`status` shows schema 2)

## Checks
- [x] shotlist-engineer: CLI regression (`--help`, `status`, `migrate`)
- [x] qa-engineer: pytest 6 passed
- [x] security-officer: no secrets in migrate output (paths only)

## Log
- 2026-11-21 ceo: unblocked after Jay Stage 1 approval.
- 2026-11-21 tech-lead: added continuum/paths.py, migrate.py, schema_version 2, pyproject.toml, tests/. Migrated roller-skating-snl. Closing.
