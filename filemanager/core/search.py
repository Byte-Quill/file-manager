"""Recursive file-name search engine."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import List

from .models import FileEntry


def search(
    root: Path,
    pattern: str,
    recursive: bool = True,
    match_case: bool = False,
    max_results: int = 1000,
) -> List[FileEntry]:
    """Search for files/folders whose name matches *pattern*.

    Supports ``*`` and ``?`` glob characters; otherwise a plain
    case-insensitive substring match is used.
    """
    results: List[FileEntry] = []
    needle = pattern if match_case else pattern.lower()
    is_glob = "*" in needle or "?" in needle

    def matches(name: str) -> bool:
        hay = name if match_case else name.lower()
        if is_glob:
            return fnmatch.fnmatch(hay, needle)
        return needle in hay

    def walk(directory: Path) -> None:
        if len(results) >= max_results:
            return
        try:
            with os.scandir(directory) as it:
                entries = list(it)
                entries.sort(key=lambda e: e.name.lower())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if len(results) >= max_results:
                return
            if matches(entry.name):
                try:
                    st = entry.stat()
                    results.append(
                        FileEntry(
                            name=entry.name,
                            path=Path(entry.path),
                            is_dir=entry.is_dir(follow_symlinks=False),
                            size=0 if entry.is_dir(follow_symlinks=False) else st.st_size,
                            modified=st.st_mtime,
                        )
                    )
                except OSError:
                    pass
            if recursive and entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                walk(Path(entry.path))

    walk(root)
    return results
