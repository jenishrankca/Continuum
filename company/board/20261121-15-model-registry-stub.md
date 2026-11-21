---
id: 20261121-15
title: Model registry stub (empty, no downloads)
department: Engineering
owner: backend-engineer
reviewers: [tech-lead]
status: todo
needs_jay: false
depends_on: []
priority: P1
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Empty model/adapter registry metadata (name, licence field, local path optional) so Stages 8–9 have a home. No model downloads.

## Done when
- [ ] Registry module or YAML stub with schema for adapters (manual/gemini/local/comfy-future)
- [ ] Licence + path fields; empty by default
- [ ] Documented in AGENTS.md; tests for load/validate
- [ ] Does not pull network weights

## Why now
Proposal “immediate recommendations” item 3. Small parallel stream beside Stage 4; unblocks Stage 8 design without installing Comfy.

## Log
- 2026-11-21 ceo: allocated as second active stream (with Stage 4).
