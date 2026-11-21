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
```

Use `py -3.13` for the venv on this Windows machine (not bare `python3`).

## Secrets

- Optional `GEMINI_API_KEY` in `.env` (gitignored) for `restyle --provider gemini`.
- Optional `LOCAL_SD_URL` for a local Automatic1111 WebUI (`restyle --provider local`).

## IWantThatApp Studio

IWantThatApp Studio works here; the CEO playbook and board rules apply. Plugin: `iwantthatapp-studio@iwantthatapp` (repo `jenishrankca/IWantThatApp-Studio`). Board lives in `company/board/`; project config is `company/studio.json`. Project specialists are in `.claude/agents/` (shotlist-engineer). This file and `CLAUDE.md` win over Studio defaults.

Run the studio from this folder in Claude Code with `/iwantthatapp-studio:ceo`.
