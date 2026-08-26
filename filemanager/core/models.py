"""Data models shared across the core layer."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


def human_size(num: float) -> str:
    """Convert a byte count into a human readable string (e.g. ``1.4 MB``)."""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB", "EB"):
        if abs(num) < 1024.0:
            break
        num /= 1024.0
    return f"{int(num)} B" if unit == "B" else f"{num:.1f} {unit}"


@dataclass
class FileEntry:
    """A single row in a file listing."""

    name: str
    path: Path
    is_dir: bool
    size: int = 0
    modified: float = 0.0

    @property
    def extension(self) -> str:
        if self.is_dir:
            return ""
        return self.path.suffix.lower().lstrip(".")

    @property
    def size_display(self) -> str:
        if self.is_dir:
            return "—"
        return human_size(self.size)

    @property
    def modified_display(self) -> str:
        if self.modified <= 0:
            return "—"
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.modified))
