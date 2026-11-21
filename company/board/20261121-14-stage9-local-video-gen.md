---
id: 20261121-14
title: Stage 9 — Local video generation + keyframe handoff
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, security-officer]
status: blocked
needs_jay: true
depends_on: [20261121-13]
priority: P3
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Local video gen with keyframe-conditioned handoff; candidates versioned; continuity-aware.

## Done when
- [ ] Video adapter behind same registry as Stage 8
- [ ] Keyframe handoff from approved stills
- [ ] Candidates versioned; never overwrite approved clips
- [ ] Hardware/licence notes documented

## Blockers
- Stage 8 local image path
- No local ComfyUI workflows/models on machine today
- Jay gate for installs / paid APIs / new libraries

## Log
- 2026-11-21 ceo: parked after Stage 8; no scaffold now.
