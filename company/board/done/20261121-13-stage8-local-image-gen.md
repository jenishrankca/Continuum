---
id: 20261121-13
title: Stage 8 — Local image generation adapter
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, security-officer]
status: done
needs_jay: false
depends_on: [20261121-09, 20261121-10]
priority: P3
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Local image gen behind Continuum provider adapters (ComfyUI / existing A1111), with continuity packs + generation history. Manual path stays offline-capable.

## Machine survey (2026-11-21)
- Comfy Desktop Electron present (`AppData\Local\Programs\Comfy Desktop`)
- Only remote install: Comfy Cloud (`cloud.comfy.org`) — no local ComfyUI server under `ComfyUI-Installs`
- Shared models tree empty (no `.safetensors` / checkpoints)
- Continuum already has `restyle` providers: `manual` | `gemini` | `local` (A1111 at `LOCAL_SD_URL`)
- ComfyUI OSS is typically GPL-3.0; model/checkpoint licences are separate — check per weight before bundling
- Re-probe 2026-11-21 Stage 8 implement: A1111 `:7860` DOWN; Comfy `:8188` DOWN — adapters probe-only until local server exists

## Done when
- [x] Adapter interface generalization plan (RestyleProvider → image gen jobs)
- [x] Local backend runs without paid API (A1111 and/or Comfy when installed; **mock/dry-run** always)
- [x] Continuity pack attached to jobs; full generation history retained
- [x] Jay approves any new library / install / model download — **none added**; no downloads

## Shipped
- Schema 8: `image_generations` with append-only `candidates`
- Providers: `mock`, `dry-run`, `manual`, `local` (A1111), `comfy` (probe + workflow gate)
- CLI: `python -m continuum gen …`
- Continuity pack assembly from bible + ledger + prev frame / keyframes
- Retry appends new candidate paths; never overwrites prior ones
- Candidate approve ≠ `continuity_approved`

## Log
- 2026-11-21 ceo: research logged; blocked on continuity Stages 4–5 + Jay gate for installs.
- 2026-11-21 tech-lead: Jay unblocked; implemented without model downloads; board closed.
