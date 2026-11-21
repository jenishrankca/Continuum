---
id: 20261121-08
title: Studio CEO local HTML dashboard
department: product
owner: web-engineer
status: done
needs_jay: false
created: 2026-11-21
updated: 2026-11-21
---

# Studio CEO local HTML dashboard

Replace Claude.ai ArtifactData URL with a Ponytail-style local HTML board under Continuum.

## Acceptance

- [x] Self-contained `company/dashboard/index.html` + `data.js` (from board + activity)
- [x] `company/studio.json` `dashboard_url` → `company/dashboard/index.html`
- [x] CLI `python -m continuum studio-dashboard` (`--rebuild` / `--open` / `--serve`)
- [x] Product dashboard stays on :8765; Studio HTML links to it
- [x] IWantThatApp-Studio GitHub untouched

## Notes

- Open: `C:\Users\jenis\App\Continuum\company\dashboard\index.html` (file://) or `--open`
- Rebuild after board/activity changes
