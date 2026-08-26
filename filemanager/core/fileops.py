"""Create, rename, delete, copy and move operations."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Iterable, Optional

from .errors import FileOperationError

try:
    import send2trash as _send2trash  # optional dependency
except ImportError:  # pragma: no cover
    _send2trash = None

#: True when deletes can go to the OS Trash instead of being permanent.
TRASH_AVAILABLE = _send2trash is not None


# --------------------------------------------------------------------------- #
# Create / rename / delete
# --------------------------------------------------------------------------- #
def _validate_name(name: str, kind: str) -> str:
    """Return a stripped, safe single-component name or raise."""
    name = name.strip()
    if not name:
        raise FileOperationError(f"{kind} name cannot be empty.")
    if name in (".", "..") or os.sep in name or (os.altsep and os.altsep in name):
        raise FileOperationError(
            f"{kind} name must be a single name without path separators:\n{name!r}")
    return name


def create_folder(parent: Path, name: str) -> Path:
    """Create a new folder inside *parent* and return its path."""
    target = parent / _validate_name(name, "Folder")
    if target.exists():
        raise FileOperationError(f"Already exists:\n{target}")
    try:
        target.mkdir(parents=False)
    except OSError as exc:
        raise FileOperationError(f"Cannot create folder:\n{target}\n{exc}")
    return target


def create_file(parent: Path, name: str) -> Path:
    """Create a new empty file inside *parent* and return its path."""
    target = parent / _validate_name(name, "File")
    if target.exists():
        raise FileOperationError(f"Already exists:\n{target}")
    try:
        target.touch()
    except OSError as exc:
        raise FileOperationError(f"Cannot create file:\n{target}\n{exc}")
    return target


def unique_name(parent: Path, name: str) -> str:
    """Return *name* or a numbered variant that does not exist yet."""
    candidate = name
    stem, suffix = os.path.splitext(name)
    counter = 1
    while (parent / candidate).exists():
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def rename_item(path: Path, new_name: str) -> Path:
    """Rename *path* within its parent folder and return the new path."""
    new_name = _validate_name(new_name, "New")
    target = path.parent / new_name
    if target.exists():
        raise FileOperationError(f"Already exists:\n{target}")
    try:
        path.rename(target)
    except OSError as exc:
        raise FileOperationError(f"Cannot rename:\n{path}\n{exc}")
    return target


def delete_items(paths: Iterable[Path], use_trash: bool = True) -> None:
    """Delete files/folders. Uses the OS trash when requested and available.

    When *use_trash* is True but ``send2trash`` is missing or fails, the
    operation raises instead of silently deleting permanently.
    """
    for path in paths:
        if use_trash:
            if _send2trash is None:
                raise FileOperationError(
                    f"Cannot move to Trash (send2trash not installed):\n{path}")
            try:
                _send2trash.send2trash(str(path))
                continue
            except Exception as exc:
                raise FileOperationError(f"Cannot move to Trash:\n{path}\n{exc}")
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            raise FileOperationError(f"Cannot delete:\n{path}\n{exc}")


# --------------------------------------------------------------------------- #
# Copy / move
# --------------------------------------------------------------------------- #
def copy_items(
    sources: Iterable[Path],
    dest_dir: Path,
    progress: Optional[Callable[[str], None]] = None,
) -> None:
    """Copy every item in *sources* into *dest_dir* (de-duplicating names)."""
    for src in sources:
        target = dest_dir / unique_name(dest_dir, src.name)
        try:
            if progress:
                progress(f"Copying {src.name}…")
            if src.is_dir():
                shutil.copytree(src, target, symlinks=True)
            else:
                shutil.copy2(src, target)
        except (OSError, shutil.Error) as exc:
            raise FileOperationError(f"Cannot copy:\n{src}\n{exc}")


def move_items(
    sources: Iterable[Path],
    dest_dir: Path,
    progress: Optional[Callable[[str], None]] = None,
) -> None:
    """Move every item in *sources* into *dest_dir* (de-duplicating names)."""
    for src in sources:
        target = dest_dir / unique_name(dest_dir, src.name)
        try:
            if progress:
                progress(f"Moving {src.name}…")
            shutil.move(str(src), str(target))
        except (OSError, shutil.Error) as exc:
            raise FileOperationError(f"Cannot move:\n{src}\n{exc}")
