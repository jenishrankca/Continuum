# Continuum

Open-source AI Continuity and Production Engine. Phase 1 is a Python CLI that turns a source `.mp4` into a director-ready shot list and storyboard package (`python -m continuum`). Phase 1 does not generate video automatically.

## Commands

```
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m continuum init <slug> --source <film.mp4> --style "..." --lighting "..." --grade "..."
python -m continuum ingest <slug>
python -m continuum review <slug>
python -m continuum restyle <slug> [--provider manual|gemini|local]
python -m continuum shots <slug>
python -m continuum generate-shotlist <slug> [--strict]
python -m continuum status <slug>
python -m continuum migrate <slug> [--dry-run]
python -m continuum bible list|promote|add-character|… <slug>
python -m continuum dashboard [--port 8765]
python -m continuum studio-dashboard [--rebuild|--open|--serve]
```

Use `py -3.13` for the venv on this Windows machine (not bare `python3`).

## Secrets

- Optional `GEMINI_API_KEY` in `.env` (gitignored) for `restyle --provider gemini`.
- Optional `LOCAL_SD_URL` for a local Automatic1111 WebUI (`restyle --provider local`).

## IWantThatApp Studio

IWantThatApp Studio works here; the CEO playbook and board rules apply. Plugin: `iwantthatapp-studio@iwantthatapp` (repo `jenishrankca/IWantThatApp-Studio`). Board lives in `company/board/`; project config is `company/studio.json`. Project specialists are in `.claude/agents/` (shotlist-engineer). This file and `CLAUDE.md` win over Studio defaults.

Run the studio from this folder in Claude Code with `/iwantthatapp-studio:ceo`.

### Studio CEO dashboard (local HTML — not claude.ai)

- Artifact board: `company/dashboard/index.html` + `data.js` (regenerated from board/activity).
- `company/studio.json` → `dashboard_url`: `company/dashboard/index.html`.
- After board or activity changes: `python -m continuum studio-dashboard --rebuild`.
- Open: double-click the HTML, or `python -m continuum studio-dashboard --open`, or `--serve` on http://127.0.0.1:8766/.
- Product Continuum UI stays separate: `python -m continuum dashboard` → http://127.0.0.1:8765/ (linked from the Studio HTML).
- Do **not** push Studio CEO updates to ArtifactData / claude.ai URLs — update local files only.
