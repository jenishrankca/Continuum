---
id: 20261121-09
title: Stage 4 — Continuity ledger + scene/shot state
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, shotlist-engineer]
status: doing
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
- [ ] Schema bump (additive) for ledger entities / scene–shot state links
- [ ] CLI or library API to read/write ledger state per scene and shot
- [ ] Intentional continuity exceptions with approval record
- [ ] Immutable history of approved changes
- [ ] Unit tests for transitions + migrate dry-run
- [ ] Sample project still opens; Phase 1 CLI still works

## Out of scope
- Visual CV inspection (Stage 5)
- Generation adapters (Stages 8–9)
- Changing IWantThatApp-Studio GitHub

## Brief (tech-lead)
Start Stage 4 now. Prefer smallest schema that supports queries; keep YAML export/debug path. Author never self-checks — qa-engineer + shotlist-engineer review.

## Log
- 2026-11-21 ceo: allocated as P0 active stream after Stages 1–3 + dashboards.
