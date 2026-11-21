---
id: 20261121-12
title: Stage 7 — Storyboard / shot model expansion
department: Engineering
owner: shotlist-engineer
reviewers: [tech-lead, qa-engineer]
status: done
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
- [x] Shot record covers deferred vision fields or documents deferrals
- [x] `generate-shotlist` / prompt builder still usable
- [x] Links to bible entities remain valid
- [x] Tests for prompt back-compat

## Field map (vision §7 → model)

| Vision field | Continuum field | Notes |
|---|---|---|
| Unique shot ID | `id` | existing |
| Scene ID | `scene_index` | existing int index |
| Shot description | `description` (+ `label`) | Stage 7 |
| Shot type | `shot_type` | existing |
| Camera angle | `camera_angle` | Stage 7 |
| Camera movement | `camera_move` | existing |
| Lens and composition | `lens_composition` | Stage 7 |
| Character / location / prop refs | `character_ids` / `location_id` / `prop_ids` | existing bible links |
| Required continuity state | `continuity_state_id` | existing ledger link |
| Previous / next shot dependency | `prev_shot_id` / `next_shot_id` | Stage 7; migrate + `shot link-sequence` |
| Starting / ending keyframe | `start_keyframe_path` / `end_keyframe_path` | Stage 7 |
| Duration | `duration_s` | Stage 7 |
| Action description | `subject_action` | existing |
| Dialogue or sound | `dialogue_or_sound` | Stage 7 |
| Image-generation prompt | `image_prompt` | empty → `prompt_builder.build_prompt` |
| Video-generation prompt | `video_prompt` | Stage 7; builder derives if empty |
| Continuity validation status | `continuity_status` | existing Stage 5 |
| Approval status | `planning_approved` (+ at/by) | ≠ `continuity_approved` |

Deferred / out of scope for this stage: automatic shot *suggestions* (vision “Support automatic shot suggestions”) — leave for later; manual `shot set` + interactive `shots` cover editing.

## CLI
`python -m continuum shot {list,show,set,link-sequence,sync-prompts,approve} <slug> …`

## Log
- 2026-11-21 ceo: allocated to shotlist-engineer; start with field map, not a big rewrite.
- 2026-11-21 shotlist-engineer: schema 7 + shot_plan + CLI/dashboard; sample migrated; board closed.
