"""Integration with the desktop environment (open / reveal)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .errors import FileOperationError


def open_in_system(path: Path) -> None:
    """Open a file/folder with the OS default application."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        raise FileOperationError(f"Cannot open:\n{path}\n{exc}")


def reveal_in_finder(path: Path) -> None:
    """Show the item in the OS file browser (Finder / Explorer / xdg)."""
    target = path if path.exists() else path.parent
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target.parent)])
    except OSError as exc:
        raise FileOperationError(f"Cannot reveal:\n{path}\n{exc}")
