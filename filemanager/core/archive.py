"""ZIP archive support using only the standard library."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Callable, Iterable, Optional

from .errors import FileOperationError


def compress_zip(
    sources: Iterable[Path],
    dest_zip: Path,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    """Compress files and/or folders into *dest_zip*. Returns the archive."""
    dest_zip = Path(dest_zip)
    try:
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for src in sources:
                src = Path(src)
                if src.is_dir():
                    for dirpath, _dirnames, filenames in os.walk(src):
                        for fn in filenames:
                            full = Path(dirpath) / fn
                            if progress:
                                progress(f"Adding {full.name}…")
                            zf.write(full, full.relative_to(src.parent))
                else:
                    if progress:
                        progress(f"Adding {src.name}…")
                    zf.write(src, src.name)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise FileOperationError(f"Cannot create archive:\n{dest_zip}\n{exc}")
    return dest_zip


def extract_zip(
    zip_path: Path,
    dest_dir: Path,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    """Extract *zip_path* into *dest_dir* (created if missing).

    Rejects archive members that would escape *dest_dir* (zip-slip).
    """
    zip_path, dest_dir = Path(zip_path), Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = str(dest_dir.resolve())
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.infolist():
                target = (dest_dir / member.filename).resolve()
                if str(target) != dest_root and not str(target).startswith(
                        dest_root + os.sep):
                    raise FileOperationError(
                        f"Unsafe path in archive, aborted:\n{member.filename}")
                if progress:
                    progress(f"Extracting {member.filename}…")
                zf.extract(member, dest_dir)
    except FileOperationError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise FileOperationError(f"Cannot extract:\n{zip_path}\n{exc}")
    return dest_dir
