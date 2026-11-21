---
id: 20261121-11
title: Stage 6 — Film intelligence MVP
department: Engineering
owner: product-manager
reviewers: [tech-lead, shotlist-engineer]
status: done
needs_jay: false
depends_on: [20261121-09]
priority: P2
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
AI film analysis (scene/character/env suggestions) that is human-editable; uncertain IDs never auto-confirmed.

## Done when
- [x] Analysis outputs stored as editable suggestions (not silent writes to bible)
- [x] Uncertain entity IDs require human confirm (`--allow-uncertain` or edit first)
- [x] CLI surface to accept/edit/reject (`python -m continuum intel …`)
- [x] Spec followed: OpenCV/scene-detect heuristics only; no model downloads

## Log
- 2026-11-21 ceo: roadmap item; plan after Stage 4 starts landing.
- 2026-11-21 tech-lead: schema 6 + intelligence module + CLI; sample analyze/accept/reject; closed.
