---
id: 20261121-12
title: Stage 7 — Storyboard / shot model expansion
department: Engineering
owner: shotlist-engineer
reviewers: [tech-lead, qa-engineer]
status: idea
needs_jay: false
depends_on: [20261121-06]
priority: P2
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Expand shot/storyboard records toward vision §7 fields while keeping prompt export + generate-shotlist back-compat.

## Done when
- [ ] Shot record covers deferred vision fields or documents deferrals
- [ ] `generate-shotlist` / prompt builder still usable
- [ ] Links to bible entities remain valid
- [ ] Tests for prompt back-compat

## Notes
Can draft field map in parallel with Stage 4, but schema implementation should not fight ledger work. Prefer field map doc first, code after Stage 4 merge shape is clear.

## Log
- 2026-11-21 ceo: allocated to shotlist-engineer; start with field map, not a big rewrite.
