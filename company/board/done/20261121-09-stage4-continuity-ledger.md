---
id: 20261121-09
title: Stage 4 — Continuity ledger + scene/shot state
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, shotlist-engineer]
status: done
needs_jay: false
depends_on: [20261121-06]
priority: P0
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Record what is true at each scene/shot (character/wardrobe/prop/location state), with transitions, intentional exceptions, and auditable history. Exit gate from proposal: ledger queries work; exceptions approved.

## Done when
- [x] Schema bump (additive) for ledger entities / scene–shot state links → `schema_version` 4
- [x] CLI or library API to read/write ledger state per scene and shot → `python -m continuum ledger …`
- [x] Intentional continuity exceptions with approval record
- [x] Immutable history of approved changes (`ledger_history` append-only)
- [x] Unit tests for transitions + migrate dry-run (`tests/test_ledger.py`)
- [x] Sample project still opens; Phase 1 CLI still works (`roller-skating-snl` on schema 4)

## Out of scope
- Visual CV inspection (Stage 5)
- Generation adapters (Stages 8–9)
- Changing IWantThatApp-Studio GitHub

## Log
- 2026-11-21 ceo: allocated as P0 active stream after Stages 1–3 + dashboards.
- 2026-11-21 tech-lead: implemented `continuum/ledger.py`, schema 4, CLI, migrate, tests (18 pass); seeded sample ledger; closed.
