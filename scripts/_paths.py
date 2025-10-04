from __future__ import annotations

"""Shared helpers for scripts launched from the repository root."""

from pathlib import Path
import sys


def repo_root() -> Path:
    """Return the absolute repository root path."""
    return Path(__file__).resolve().parents[1]


def ensure_on_sys_path(path: Path) -> None:
    """Ensure `path` is available on `sys.path` for on-demand imports."""
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def ensure_src_on_path() -> Path:
    """Add the `src` directory to `sys.path` when running from sources."""
    src_path = repo_root() / "src"
    ensure_on_sys_path(src_path)
    return src_path


def ensure_simple_gui_on_path() -> Path:
    """Add the simple GUI folder to `sys.path` for ad-hoc launches."""
    gui_path = repo_root() / "gui-simple"
    ensure_on_sys_path(gui_path)
    return gui_path
