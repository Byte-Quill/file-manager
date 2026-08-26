"""Temporary-file scanning engine.

Scans a directory tree for well-known temporary, cache and junk files.
The scan itself is strictly read-only — deletion is performed by the GUI
layer through :func:`filemanager.core.fileops.delete_items`.

Safety rules built into the scanner:

* The scan root itself is never reported.
* Symbolic links are never followed and never reported.
* Version-control metadata folders (``.git``, ``.svn``, ``.hg``) are skipped.
* When a directory matches a pattern it is reported once and pruned, so
  results never contain nested duplicates.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from .errors import FileOperationError
from .info import folder_size
from .models import human_size


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Category:
    """A group of temp-file patterns the user can enable or disable."""

    key: str
    label: str
    description: str
    file_patterns: Tuple[str, ...] = ()
    dir_patterns: Tuple[str, ...] = ()
    default_enabled: bool = True


CATEGORIES: Tuple[Category, ...] = (
    Category(
        key="system_junk",
        label="System junk",
        description=".DS_Store, Thumbs.db, desktop.ini and other OS metadata",
        file_patterns=(".ds_store", "thumbs.db", "desktop.ini", ".directory", ".apdisk"),
    ),
    Category(
        key="temp_files",
        label="Temporary files",
        description="*.tmp, *.temp, partial downloads, Office lock files (~$…)",
        file_patterns=(
            "*.tmp", "*.temp", "*.tmp.*", "*.tlb", "~$*",
            "*.part", "*.partial", "*.crdownload", "*.download",
        ),
    ),
    Category(
        key="backup_files",
        label="Backup & swap files",
        description="*~, *.bak, *.old, *.orig, *.rej, editor swap files",
        file_patterns=(
            "*~", "*.bak", "*.backup", "*.old", "*.orig", "*.rej",
            "*.swp", "*.swo", ".*.swp", ".*.swo", "#*#", "*.save",
        ),
    ),
    Category(
        key="python_cache",
        label="Python caches",
        description="__pycache__, *.pyc, .pytest_cache, .mypy_cache, .tox …",
        file_patterns=("*.pyc", "*.pyo"),
        dir_patterns=(
            "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            ".pytype", ".tox", ".nox", ".ipynb_checkpoints",
        ),
    ),
    Category(
        key="app_cache",
        label="App & build caches",
        description=".cache, .parcel-cache, .vite, *.cache and similar folders",
        file_patterns=("*.cache", ".eslintcache", ".stylelintcache"),
        dir_patterns=(
            ".cache", ".parcel-cache", ".webpack-cache", ".rollup.cache",
            ".turbo", ".vite", ".sass-cache",
        ),
    ),
    Category(
        key="log_files",
        label="Log files",
        description="*.log files — disabled by default, review before deleting",
        file_patterns=("*.log", "*.log.[0-9]", "*.log.gz"),
        default_enabled=False,
    ),
    Category(
        key="empty_dirs",
        label="Empty folders",
        description="Folders that contain no files or subfolders",
        default_enabled=False,
    ),
)


#: Directories that must never be scanned or reported.
PROTECTED_DIRS = frozenset({".git", ".svn", ".hg"})


# Pre-compile fnmatch patterns to regex for faster matching
def _compile_patterns(patterns: Tuple[str, ...]) -> List[Tuple[re.Pattern, str]]:
    """Convert fnmatch patterns to (case-insensitive regex, original pattern)."""
    return [(re.compile(fnmatch.translate(p), re.IGNORECASE), p) for p in patterns]


# Pre-compiled pattern regexes for each category
_FILE_PATTERNS: Dict[str, List[Tuple[re.Pattern, str]]] = {}
_DIR_PATTERNS: Dict[str, List[Tuple[re.Pattern, str]]] = {}

for cat in CATEGORIES:
    if cat.file_patterns:
        _FILE_PATTERNS[cat.key] = _compile_patterns(cat.file_patterns)
    if cat.dir_patterns:
        _DIR_PATTERNS[cat.key] = _compile_patterns(cat.dir_patterns)


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #
@dataclass
class TempMatch:
    """A single file or folder flagged by the scanner."""

    path: Path
    category: str
    label: str
    reason: str
    is_dir: bool = False
    size: int = 0

    @property
    def size_display(self) -> str:
        return human_size(self.size)


def summarize(matches: Iterable[TempMatch]) -> Tuple[int, int]:
    """Return ``(count, total_size_bytes)`` for a list of matches."""
    ms = list(matches)
    return len(ms), sum(m.size for m in ms)


def _safe_folder_size(path: Path) -> int:
    try:
        return folder_size(path)
    except OSError:
        return 0


# --------------------------------------------------------------------------- #
# Scanner
# --------------------------------------------------------------------------- #
def scan_for_temp_files(
    root: Path,
    enabled_keys: Iterable[str],
    recursive: bool = True,
    include_hidden: bool = False,
    progress: Optional[Callable[[int, str], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> List[TempMatch]:
    """Scan *root* for temporary/junk files.

    Parameters
    ----------
    root:
        Directory to scan.
    enabled_keys:
        Keys of :data:`CATEGORIES` to look for.
    recursive:
        When ``False`` only the top level of *root* is inspected.
    include_hidden:
        When ``False`` hidden directories are not descended into.  Hidden
        files that match a pattern (e.g. ``.DS_Store``) are still reported.
    progress:
        Optional callback ``(items_scanned, current_dir)``.
    should_cancel:
        Optional callback; when it returns ``True`` the scan stops early.

    Returns a list of :class:`TempMatch` sorted by location.
    """
    root = Path(root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileOperationError(f"Not a directory:\n{root}")

    enabled: Set[str] = set(enabled_keys)
    cats = [c for c in CATEGORIES if c.key in enabled]
    if not cats:
        return []

    file_cats = [c for c in cats if c.file_patterns]
    dir_cats = [c for c in cats if c.dir_patterns]
    empty_cat = next((c for c in cats if c.key == "empty_dirs"), None)

    matches: List[TempMatch] = []
    scanned = 0

    def match_name(name: str, cats, table):
        for cat in cats:
            for regex, pat in table.get(cat.key, ()):
                if regex.match(name):
                    return cat, pat
        return None

    match_file = lambda name: match_name(name, file_cats, _FILE_PATTERNS)
    match_dir = lambda name: match_name(name, dir_cats, _DIR_PATTERNS)

    # Iterative DFS (explicit stack) so deep trees cannot hit the
    # recursion limit.
    stack = [root]
    while stack:
        if should_cancel is not None and should_cancel():
            break
        directory = stack.pop()

        try:
            with os.scandir(directory) as it:
                entries = list(it)
        except (PermissionError, OSError):
            continue

        # Separate dirs and files for processing order
        dir_entries = []
        file_entries = []
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                dir_entries.append(entry)
            else:
                file_entries.append(entry)

        # Process directories first
        for entry in dir_entries:
            name = entry.name
            child_path = Path(entry.path)

            # Skip protected dirs
            if name in PROTECTED_DIRS:
                continue

            # Skip symlinks
            if entry.is_symlink():
                continue

            # Check if directory matches a pattern
            hit = match_dir(name)
            if hit:
                cat, pat = hit
                matches.append(TempMatch(
                    path=child_path, category=cat.key, label=cat.label,
                    reason=pat, is_dir=True, size=_safe_folder_size(child_path)))
                continue  # prune: reported once, not descended into

            # Skip hidden directories if not included — before the empty-dir
            # check so hidden empty folders are never reported either.
            if name.startswith(".") and not include_hidden:
                continue

            # Check for empty directories
            if empty_cat is not None:
                try:
                    # Quick check: try to read one entry
                    with os.scandir(child_path) as it:
                        if next(it, None) is None:
                            matches.append(TempMatch(
                                path=child_path, category=empty_cat.key,
                                label=empty_cat.label, reason="empty folder",
                                is_dir=True, size=0))
                            continue  # nothing inside to scan
                except OSError:
                    pass

            # Queue subdirectory for scanning
            if recursive:
                stack.append(child_path)

        # Process files
        for entry in file_entries:
            if should_cancel is not None and should_cancel():
                break

            name = entry.name
            child_path = Path(entry.path)

            # Skip symlinks
            if entry.is_symlink():
                continue

            hit = match_file(name)
            if hit:
                cat, pat = hit
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                matches.append(TempMatch(
                    path=child_path, category=cat.key, label=cat.label,
                    reason=pat, is_dir=False, size=size))

        scanned += len(dir_entries) + len(file_entries)
        if progress is not None:
            progress(scanned, str(directory))

    matches.sort(key=lambda m: (str(m.path.parent), m.path.name.lower()))
    return matches
