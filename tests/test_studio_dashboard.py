"""Tests for local Studio CEO HTML dashboard (company/dashboard/)."""
from __future__ import annotations

import json
from pathlib import Path

from continuum import studio_dashboard as sd


def _seed_company(root: Path) -> None:
    board = root / "company" / "board"
    board.mkdir(parents=True)
    (board / "20261121-99-open.md").write_text(
        "---\n"
        "id: 20261121-99\n"
        "title: Open item\n"
        "owner: ceo\n"
        "status: doing\n"
        "needs_jay: true\n"
        "updated: 2026-11-21\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )
    done = board / "done"
    done.mkdir()
    (done / "20261121-98-done.md").write_text(
        "---\n"
        "id: 20261121-98\n"
        "title: Done item\n"
        "owner: tech-lead\n"
        "status: done\n"
        "needs_jay: false\n"
        "updated: 2026-11-20\n"
        "---\n\nDone.\n",
        encoding="utf-8",
    )
    (root / "company" / "activity.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-11-21T12:00:00Z",
                "agent": "ceo",
                "event": "stop",
                "item": "20261121-99",
                "summary": "Seed activity",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "company" / "studio.json").write_text(
        json.dumps({"project": "Continuum", "dashboard_url": "company/dashboard/index.html"}),
        encoding="utf-8",
    )


def test_rebuild_writes_index_and_data_js(tmp_path: Path) -> None:
    _seed_company(tmp_path)
    index = sd.rebuild(tmp_path)
    assert index.is_file()
    assert index.name == "index.html"
    data_js = sd.dashboard_data_js_path(tmp_path)
    assert data_js.is_file()
    text = data_js.read_text(encoding="utf-8")
    assert "window.CONTINUUM_STUDIO_DASHBOARD" in text
    assert "Open item" in text
    assert "Done item" in text
    assert "Seed activity" in text
    assert "http://127.0.0.1:8765/" in text
    html = index.read_text(encoding="utf-8")
    assert "data.js" in html
    assert "Continuum" in html


def test_payload_kpis_and_agents(tmp_path: Path) -> None:
    _seed_company(tmp_path)
    payload = sd.build_dashboard_payload(tmp_path)
    assert payload["project"] == "Continuum"
    assert len(payload["items"]) == 2
    assert any(k["key"] == "board_open" and k["value"] == 1 for k in payload["kpis"])
    assert any(a["name"] == "ceo" and a["items_open"] == 1 for a in payload["agents"])
