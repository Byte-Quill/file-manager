"""Recursive file-name search engine."""

from __future__ import annotations

import fnmatch
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
            children = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError):
            return
        for child in children:
            if len(results) >= max_results:
                return
            if matches(child.name):
                try:
                    st = child.stat()
                    results.append(
                        FileEntry(
                            name=child.name,
                            path=child,
                            is_dir=child.is_dir(),
                            size=0 if child.is_dir() else st.st_size,
                            modified=st.st_mtime,
                        )
                    )
                except OSError:
                    pass
            if recursive and child.is_dir() and not child.is_symlink():
                walk(child)

    walk(root)
    return results
