"""Unit tests for continuum.paths."""
from __future__ import annotations

from pathlib import Path

from continuum.paths import is_relative_stored, to_absolute, to_stored


def test_to_stored_relative_under_root(tmp_path: Path) -> None:
    root = tmp_path
    media = root / "projects" / "demo" / "frames" / "a.jpg"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"x")
    stored = to_stored(root, media)
    assert stored == "projects/demo/frames/a.jpg"
    assert is_relative_stored(stored)


def test_to_stored_keeps_external_absolute(tmp_path: Path) -> None:
    root = tmp_path / "app"
    root.mkdir()
    external = tmp_path / "outside" / "film.mp4"
    external.parent.mkdir()
    external.write_bytes(b"x")
    stored = to_stored(root, external)
    assert Path(stored).is_absolute()
    assert "outside" in stored.replace("\\", "/")


def test_to_absolute_round_trip(tmp_path: Path) -> None:
    root = tmp_path
    rel = "projects/demo/frames/a.jpg"
    abs_path = to_absolute(root, rel)
    assert abs_path is not None
    assert Path(abs_path).is_absolute()
    assert to_stored(root, abs_path) == rel
