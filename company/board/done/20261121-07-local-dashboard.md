---
id: 20261121-07
title: Local Continuum browser dashboard
department: Engineering
owner: web-engineer
reviewers: [tech-lead, qa-engineer]
status: done
needs_jay: false
depends_on: []
due: ""
created: 2026-11-21
updated: 2026-11-21
---

## Goal
Serve a local production dashboard on localhost so Jay can open Continuum status in a browser.

## Done when
- [x] `python -m continuum dashboard` serves http://127.0.0.1:8765/
- [x] Projects list + project detail (scenes/shots/bible/schema/outputs)
- [x] CLI still works; Continuum-only push
- [x] Smoke test + pytest

## Log
- 2026-11-21 web-engineer: FastAPI + Jinja templates; live smoke GET / and project page 200.
