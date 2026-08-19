"""File-type icons (emoji keep the app dependency-free and cross-platform)."""

from __future__ import annotations

from typing import Dict

from ..core.models import FileEntry

ICON_FOLDER = "📁"
ICON_FILE = "📄"

EXT_ICONS: Dict[str, str] = {
    "py": "🐍", "js": "🟨", "ts": "🟦", "json": "🧾", "md": "📝", "txt": "📃",
    "pdf": "📕", "zip": "🗜️", "tar": "🗜️", "gz": "🗜️", "rar": "🗜️",
    "png": "🖼️", "jpg": "🖼️", "jpeg": "🖼️", "gif": "🖼️", "svg": "🖼️", "webp": "🖼️",
    "mp3": "🎵", "wav": "🎵", "flac": "🎵", "mp4": "🎬", "mov": "🎬", "mkv": "🎬",
    "doc": "📘", "docx": "📘", "xls": "📗", "xlsx": "📗", "ppt": "📙", "pptx": "📙",
    "sh": "⚙️", "yml": "⚙️", "yaml": "⚙️", "toml": "⚙️", "ini": "⚙️", "csv": "📊",
    "html": "🌐", "css": "🎨", "app": "🚀", "dmg": "💿", "iso": "💿",
}


def icon_for(entry: FileEntry) -> str:
    """Return the icon to display for *entry*."""
    if entry.is_dir:
        return ICON_FOLDER
    return EXT_ICONS.get(entry.extension, ICON_FILE)
