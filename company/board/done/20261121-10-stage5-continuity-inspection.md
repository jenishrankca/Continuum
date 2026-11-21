---
id: 20261121-10
title: Stage 5 — Visual continuity inspection MVP
department: Engineering
owner: backend-engineer
reviewers: [tech-lead, qa-engineer]
status: done
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
- [x] Statuses: not_checked / passed / warning / failed / human_override
- [x] Checks attach evidence paths + confidence
- [x] Human override documented on the check record
- [x] No auto-approve on generate (`generation_complete` ≠ `continuity_approved`)
- [x] Tests for status transitions; smoke on sample project

## Out of scope
- Large model downloads (used OpenCV already in deps)
- ComfyUI / video gen

## Log
- 2026-11-21 ceo: queued behind Stage 4; owner backend-engineer when unblocked.
- 2026-11-21 tech-lead: unblocked after Stage 4 ledger landed; status todo.
- 2026-11-21 backend-engineer: schema 5 + `continuum/inspection.py` + CLI `inspect`; sample run 13 checks; closed.
