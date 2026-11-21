"""Project-rooted path helpers: store relative paths, resolve absolute at runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def to_stored(root: Path, path: Optional[str | Path]) -> Optional[str]:
    """Convert a path to a root-relative POSIX string when it lives under root.

    Paths outside the Continuum root stay absolute (external source videos).
    Already-relative paths are normalized to POSIX.
    """
    if path is None or path == "":
        return None
    p = Path(path)
    root_resolved = root.resolve()
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(root_resolved).as_posix()
    except ValueError:
        return str(p.resolve())


def to_absolute(root: Path, path: Optional[str]) -> Optional[str]:
    """Resolve a stored path to an absolute filesystem path."""
    if path is None or path == "":
        return None
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str((root / p).resolve())


def is_relative_stored(path: Optional[str]) -> bool:
    """True when the stored string is relative (or empty/None)."""
    if path is None or path == "":
        return True
    return not Path(path).is_absolute()
