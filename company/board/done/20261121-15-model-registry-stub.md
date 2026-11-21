---
id: 20261121-15
title: Model registry stub (empty, no downloads)
department: Engineering
owner: backend-engineer
reviewers: [tech-lead]
status: done
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
- [x] Registry module or YAML stub with schema for adapters (manual/gemini/local/comfy-future)
- [x] Licence + path fields; empty by default
- [x] Documented in AGENTS.md; tests for load/validate
- [x] Does not pull network weights

## Shipped
- `continuum/model_registry.yaml` + `continuum/model_registry.py`
- `python -m continuum gen registry`
- `models: []` by design

## Log
- 2026-11-21 ceo: allocated as second active stream (with Stage 4).
- 2026-11-21 backend-engineer: stub landed with Stage 8; board closed.
