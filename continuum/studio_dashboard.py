"""Local Studio CEO dashboard: HTML + data.js under company/dashboard/."""
from __future__ import annotations

import json
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DASHBOARD_DIRNAME = "company/dashboard"
DATA_JS_NAME = "data.js"
INDEX_NAME = "index.html"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def dashboard_dir(root: Path) -> Path:
    return root / "company" / "dashboard"


def dashboard_index_path(root: Path) -> Path:
    return dashboard_dir(root) / INDEX_NAME


def dashboard_data_js_path(root: Path) -> Path:
    return dashboard_dir(root) / DATA_JS_NAME


def _parse_frontmatter(text: str) -> dict[str, Any]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1)) or {}
    return data if isinstance(data, dict) else {}


def _load_board_items(root: Path) -> list[dict[str, Any]]:
    board = root / "company" / "board"
    items: list[dict[str, Any]] = []
    if not board.is_dir():
        return items
    for path in sorted(board.rglob("*.md")):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = _parse_frontmatter(text)
        if not meta.get("id"):
            continue
        in_done = "done" in path.parts
        status = str(meta.get("status") or ("done" if in_done else "idea"))
        items.append(
            {
                "id": str(meta["id"]),
                "title": str(meta.get("title") or path.stem),
                "department": str(meta.get("department") or ""),
                "owner": str(meta.get("owner") or ""),
                "status": status,
                "needs_jay": bool(meta.get("needs_jay", False)),
                "due": str(meta.get("due") or ""),
                "updated": str(meta.get("updated") or meta.get("created") or ""),
                "link": str(path.relative_to(root)).replace("\\", "/"),
                "done_folder": in_done,
            }
        )
    return items


def _load_activity(root: Path, limit: int = 50) -> list[dict[str, Any]]:
    path = root / "company" / "activity.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _derive_agents(items: list[dict[str, Any]], activity: list[dict[str, Any]]) -> list[dict[str, Any]]:
    owners = {i["owner"] for i in items if i.get("owner")}
    agents_from_activity = {a.get("agent") for a in activity if a.get("agent")}
    names = sorted((owners | agents_from_activity) - {None, ""})
    open_by_owner: dict[str, int] = {}
    for item in items:
        if item.get("done_folder") or item.get("status") == "done":
            continue
        owner = item.get("owner") or ""
        open_by_owner[owner] = open_by_owner.get(owner, 0) + 1
    last_by_agent: dict[str, str] = {}
    for row in activity:
        agent = str(row.get("agent") or "")
        if agent:
            last_by_agent[agent] = str(row.get("ts") or "")
    result = []
    for name in names:
        open_count = open_by_owner.get(name, 0)
        status = "working" if open_count else "idle"
        result.append(
            {
                "name": name,
                "department": "",
                "status": status,
                "current_item": "",
                "items_open": open_count,
                "items_done_week": 0,
                "last_run": last_by_agent.get(name, ""),
            }
        )
    return result


def _kpis(root: Path, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    open_items = sum(1 for i in items if not i.get("done_folder") and i.get("status") != "done")
    waiting = sum(1 for i in items if i.get("needs_jay") and i.get("status") != "done")
    done = sum(1 for i in items if i.get("done_folder") or i.get("status") == "done")
    as_of = datetime.now(timezone.utc).date().isoformat()
    return [
        {
            "key": "board_open",
            "label": "Open board items",
            "group": "plan",
            "value": open_items,
            "target": "",
            "source": "company/board",
            "as_of": as_of,
        },
        {
            "key": "waiting_for_jay",
            "label": "Waiting for Jay",
            "group": "plan",
            "value": waiting,
            "target": "0",
            "source": "company/board needs_jay",
            "as_of": as_of,
        },
        {
            "key": "board_done",
            "label": "Done items",
            "group": "plan",
            "value": done,
            "target": "",
            "source": "company/board/done",
            "as_of": as_of,
        },
        {
            "key": "product_dashboard",
            "label": "Product UI",
            "group": "product",
            "value": "http://127.0.0.1:8765/",
            "target": "",
            "source": "python -m continuum dashboard",
            "as_of": as_of,
        },
    ]


def build_dashboard_payload(root: Path) -> dict[str, Any]:
    studio_path = root / "company" / "studio.json"
    studio: dict[str, Any] = {}
    if studio_path.is_file():
        studio = json.loads(studio_path.read_text(encoding="utf-8"))
    items = _load_board_items(root)
    activity = _load_activity(root)
    agents = _derive_agents(items, activity)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    open_titles = [
        i["title"]
        for i in items
        if not i.get("done_folder") and i.get("status") not in ("done",)
    ]
    summary = (
        f"{len(open_titles)} open · {sum(1 for i in items if i.get('done_folder'))} done"
        if items
        else "No board items yet"
    )
    return {
        "project": studio.get("project") or "Continuum",
        "updated": now,
        "local_root": str(root.resolve()),
        "product_dashboard_url": "http://127.0.0.1:8765/",
        "dates": studio.get("dates") or {},
        "run": {
            "last_run": now,
            "summary": summary,
            "beta_date": (studio.get("dates") or {}).get("beta", ""),
            "website_live_date": (studio.get("dates") or {}).get("website_live", ""),
            "launch_date": (studio.get("dates") or {}).get("launch", ""),
        },
        "agents": agents,
        "items": items,
        "kpis": _kpis(root, items),
        "activity": [
            {
                "at": row.get("ts") or "",
                "agent": row.get("agent") or "",
                "item": row.get("item") or "",
                "summary": row.get("summary") or "",
            }
            for row in activity
        ],
    }


def write_data_js(root: Path, payload: dict[str, Any] | None = None) -> Path:
    dash = dashboard_dir(root)
    dash.mkdir(parents=True, exist_ok=True)
    data = payload or build_dashboard_payload(root)
    path = dashboard_data_js_path(root)
    body = (
        "/* Generated by continuum studio-dashboard — do not edit by hand */\n"
        "window.CONTINUUM_STUDIO_DASHBOARD = "
        + json.dumps(data, indent=2, ensure_ascii=False)
        + ";\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def ensure_index_html(root: Path) -> Path:
    """Copy packaged template index if missing, or always refresh from package template."""
    package_template = Path(__file__).resolve().parent / "studio_dashboard_static" / "index.html"
    dest = dashboard_index_path(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(package_template.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


def rebuild(root: Path) -> Path:
    ensure_index_html(root)
    write_data_js(root)
    return dashboard_index_path(root)


def open_dashboard(root: Path, *, rebuild_first: bool = True) -> Path:
    path = rebuild(root) if rebuild_first else dashboard_index_path(root)
    if not path.is_file():
        path = rebuild(root)
    webbrowser.open(path.resolve().as_uri())
    return path


def serve_dashboard(
    root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8766,
    rebuild_first: bool = True,
) -> None:
    """Tiny HTTP server for company/dashboard/ (alternative to file://)."""
    import http.server
    import socketserver

    if rebuild_first:
        rebuild(root)
    directory = dashboard_dir(root)
    if not directory.is_dir():
        raise FileNotFoundError(f"Missing Studio dashboard dir: {directory}")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            print(f"[studio-dashboard] {format % args}")

    with socketserver.TCPServer((host, port), Handler) as httpd:
        print(f"Studio dashboard at http://{host}:{port}/")
        print(f"Files: {directory}")
        httpd.serve_forever()
