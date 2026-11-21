---
id: 20261121-03
title: Stage 2 — continuity-ready store, relative paths, migrate harness
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, shotlist-engineer, security-officer]
status: in-progress
needs_jay: false
depends_on: [20261121-01]
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Stage 2: project-relative paths, additive schema migrate harness, tests scaffold — without breaking Phase 1 CLI or existing projects/.

## Done when
- v1 sample project still loads
- Absolute paths rewritten to project-relative on load/save
- `continuum migrate <slug>` dry-run + apply
- Unit tests for path resolver + migrate
- All Phase 1 CLI commands still work

## Checks
- [ ] tech-lead design note
- [ ] shotlist-engineer: Phase 1 CLI regression
- [ ] qa-engineer: tests pass
- [ ] security-officer: no secrets in logs/migrations

## Log
- 2026-11-21 ceo: created blocked on 01.
- 2026-11-21 ceo: Jay approved Stage 1. Unblocked → in-progress after rebrand push.
