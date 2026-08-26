"""Integration with the desktop environment (open / reveal / terminal)."""

from __future__ import annotations

import os
import shutil
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


def open_terminal(path: Path) -> None:
    """Open a terminal window in *path* (or its parent if it is a file)."""
    folder = path if path.is_dir() else path.parent
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", str(folder)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/K",
                              f"cd /D {folder}"], shell=False)
        else:
            term = (shutil.which("x-terminal-emulator")
                    or shutil.which("gnome-terminal")
                    or shutil.which("konsole")
                    or shutil.which("xfce4-terminal")
                    or shutil.which("xterm"))
            if not term:
                raise FileOperationError("No terminal emulator found.")
            subprocess.Popen([term], cwd=str(folder))
    except FileOperationError:
        raise
    except OSError as exc:
        raise FileOperationError(f"Cannot open terminal:\n{folder}\n{exc}")


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
