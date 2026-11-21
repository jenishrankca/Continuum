# Continuum CEO run — allocate Stages 4–9

**When:** 2026-11-21  
**Context:** Stages 1–3 done; product dashboard :8765; Studio HTML at `company/dashboard/`. IWantThatApp-Studio GitHub untouched.

## Setup check
- `company/studio.json` → `dashboard_url`: `company/dashboard/index.html` (local, not claude.ai)
- Board: prior items 00–08 in `done/`
- Ponytail / ComfyUI surveys completed (see board 13 + AGENTS)

## Active streams (max 3)
| # | Item | Owner | Status |
| --- | --- | --- | --- |
| 1 | 20261121-09 Stage 4 ledger | tech-lead | **doing** |
| 2 | 20261121-15 Model registry stub | backend-engineer | **todo** |
| 3 | 20261121-12 Stage 7 field map (doc only) | shotlist-engineer | **idea** — start map, not schema fight |

## Queued / blocked
| Item | Owner | Status | Blocker |
| --- | --- | --- | --- |
| 10 Stage 5 inspection | backend-engineer | blocked | Stage 4 |
| 11 Stage 6 film intelligence | product-manager | idea | Stage 4 (+ Jay for new libs) |
| 13 Stage 8 local image gen | tech-lead | blocked | 4–5 + Jay (needs_jay) |
| 14 Stage 9 local video gen | tech-lead | blocked | Stage 8 + Jay |

## Waiting for Jay
- Stage 8/9: approve any ComfyUI local install / model download / new libraries when ready (not now)
- Dates in `studio.json` still blank (deferred earlier)

## Dashboard
Rebuilt local HTML: `python -m continuum studio-dashboard --rebuild`  
Open: `C:\Users\jenis\App\Continuum\company\dashboard\index.html`

## Tomorrow
Tech-lead lands Stage 4 skeleton; backend-engineer registry stub; shotlist-engineer Stage 7 field map draft.
