"""Directory listing and places/drives discovery."""

from __future__ import annotations

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
        for child in path.iterdir():
            name = child.name
            if not show_hidden and name.startswith("."):
                continue
            try:
                st = child.stat()
                entries.append(
                    FileEntry(
                        name=name,
                        path=child,
                        is_dir=child.is_dir(),
                        size=0 if child.is_dir() else st.st_size,
                        modified=st.st_mtime,
                    )
                )
            except OSError:
                # Broken symlink or permission problem — still show it.
                entries.append(FileEntry(name=name, path=child, is_dir=False))
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
    # macOS / Linux volume mount points
    for mount in ("/Volumes", "/mnt", "/media"):
        mp = Path(mount)
        if mp.is_dir():
            roots.append(mp)
    roots.append(Path("/"))
    return roots
