---
id: 20261121-13
title: Stage 8 — Local image generation adapter
department: Engineering
owner: tech-lead
reviewers: [qa-engineer, security-officer]
status: blocked
needs_jay: true
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

## Done when
- [ ] Adapter interface generalization plan (RestyleProvider → image gen jobs)
- [ ] Local backend runs without paid API (A1111 and/or Comfy when installed)
- [ ] Continuity pack attached to jobs; full generation history retained
- [ ] Jay approves any new library / install / model download

## Recommendation
**Integrate later — do not scaffold Comfy adapter now.** Finish Stages 4–5 first. When Jay wants Stage 8: install local ComfyUI (or point at A1111), then add `comfy` provider. Do not download large models unless already local.

## Log
- 2026-11-21 ceo: research logged; blocked on continuity Stages 4–5 + Jay gate for installs.
