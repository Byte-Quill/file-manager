"""Recursive file-name search engine."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import List

from .models import FileEntry

#: Default cap on the number of results returned by :func:`search`.
MAX_RESULTS = 1000


def search(
    root: Path,
    pattern: str,
    recursive: bool = True,
    match_case: bool = False,
    max_results: int = MAX_RESULTS,
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

    # Iterative DFS (explicit stack) so deep trees cannot hit the
    # recursion limit.
    stack = [root]
    while stack and len(results) < max_results:
        directory = stack.pop()
        try:
            with os.scandir(directory) as it:
                entries = sorted(it, key=lambda e: e.name.lower())
        except (PermissionError, OSError):
            continue
        subdirs: List[Path] = []
        for entry in entries:
            if len(results) >= max_results:
                break
            is_dir = entry.is_dir(follow_symlinks=False)
            if matches(entry.name):
                try:
                    # Don't follow symlinks: keeps size/type consistent with
                    # is_dir above and avoids hangs on symlinked network mounts.
                    st = entry.stat(follow_symlinks=False)
                    results.append(
                        FileEntry(
                            name=entry.name,
                            path=Path(entry.path),
                            is_dir=is_dir,
                            size=0 if is_dir else st.st_size,
                            modified=st.st_mtime,
                        )
                    )
                except OSError:
                    pass
            if recursive and is_dir and not entry.is_symlink():
                subdirs.append(Path(entry.path))
        # Push in reverse so the first subdirectory is visited first.
        stack.extend(reversed(subdirs))
    return results
