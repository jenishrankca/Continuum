---
id: 20261121-10
title: Stage 5 — Visual continuity inspection MVP
department: Engineering
owner: backend-engineer
reviewers: [tech-lead, qa-engineer]
status: blocked
needs_jay: false
depends_on: [20261121-09]
priority: P1
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Inspection engine MVP: compare frames/refs against ledger; emit status + evidence + confidence; human override; generation complete ≠ approved.

## Done when
- [ ] Statuses: not_checked / passed / warning / failed / override
- [ ] Checks attach evidence paths + confidence
- [ ] Human override documented on the check record
- [ ] No auto-approve on generate
- [ ] Tests for status transitions; smoke on sample project

## Blockers
- Waiting on Stage 4 ledger (20261121-09)

## Out of scope
- Large model downloads unless Jay already has weights locally
- ComfyUI / video gen

## Log
- 2026-11-21 ceo: queued behind Stage 4; owner backend-engineer when unblocked.
