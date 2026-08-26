"""Directory listing and places/drives discovery."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .errors import FileOperationError
from .models import FileEntry


def list_directory(path: Path, show_hidden: bool = False) -> List[FileEntry]:
    """Return the entries of *path* sorted: directories first, then files."""
    if not path.exists():
        raise FileOperationError(f"Path does not exist:\n{path}")
    if not path.is_dir():
        raise FileOperationError(f"Not a directory:\n{path}")

    entries: List[FileEntry] = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                name = entry.name
                if not show_hidden and name.startswith("."):
                    continue
                try:
                    # DirEntry caches stat() results; no extra syscall.
                    # follow_symlinks=False keeps stat consistent with is_dir:
                    # a symlink shows its own metadata, not the target's.
                    is_dir = entry.is_dir(follow_symlinks=False)
                    st = entry.stat(follow_symlinks=False)
                    entries.append(
                        FileEntry(
                            name=name,
                            path=Path(entry.path),
                            is_dir=is_dir,
                            size=0 if is_dir else st.st_size,
                            modified=st.st_mtime,
                        )
                    )
                except OSError:
                    # Broken symlink or permission problem — still show it.
                    entries.append(FileEntry(name=name, path=Path(entry.path), is_dir=False))
    except PermissionError:
        raise FileOperationError(f"Permission denied:\n{path}")
    except OSError as exc:
        raise FileOperationError(f"Cannot read directory:\n{path}\n{exc}")

    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
    return entries


def get_drives() -> List[Path]:
    """Return a list of 'root' locations for the sidebar."""
    roots: List[Path] = []
    home = Path.home()
    roots.append(home)
    for name in ("Desktop", "Documents", "Downloads", "Music", "Pictures", "Videos"):
        candidate = home / name
        if candidate.is_dir():
            roots.append(candidate)
    # macOS: every mounted volume appears under /Volumes.
    volumes = Path("/Volumes")
    if volumes.is_dir():
        roots.append(volumes)
    else:
        # Linux: list the actual mounted volumes for this user instead of
        # the bare /media and /mnt roots.
        user = home.name
        for base in (Path("/media") / user, Path("/run/media") / user):
            if base.is_dir():
                try:
                    roots.extend(sorted(p for p in base.iterdir() if p.is_dir()))
                except OSError:
                    pass
    roots.append(Path("/"))
    return roots
