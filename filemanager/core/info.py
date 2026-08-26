"""File and folder metadata: sizes and property reports."""

from __future__ import annotations

import os
import time
from pathlib import Path

from .errors import FileOperationError
from .models import human_size


def folder_size(path: Path) -> int:
    """Return the total size in bytes of everything under *path*.

    Iterative (explicit stack) so arbitrarily deep trees cannot hit the
    recursion limit.
    """
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        else:
                            total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
    return total


def item_info(path: Path) -> str:
    """Return a multi-line description of a file or folder."""
    try:
        st = path.stat()
    except OSError as exc:
        raise FileOperationError(f"Cannot stat:\n{path}\n{exc}")

    lines = [
        f"Name: {path.name}",
        f"Path: {path}",
        f"Type: {'Folder' if path.is_dir() else (path.suffix.upper().lstrip('.') + ' file' if path.suffix else 'File')}",
    ]
    if path.is_dir():
        try:
            children = list(path.iterdir())
            lines.append(f"Contains: {len(children)} item(s)")
        except OSError:
            pass
    else:
        lines.append(f"Size: {human_size(st.st_size)} ({st.st_size:,} bytes)")
    lines.append(f"Modified: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}")
    lines.append(f"Accessed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_atime))}")

    mode = st.st_mode
    perms = "".join(
        "rwx"[i % 3] if mode & (1 << (8 - i)) else "-" for i in range(9)
    )
    lines.append(f"Permissions: {perms}")
    return "\n".join(lines)
