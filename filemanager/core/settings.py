"""Tiny JSON settings store (window state, recent folders, preferences).

Best-effort: failures to read or write never raise, they just yield an
empty state or a no-op, so the app always works without a config dir.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

APP_NAME = "file-manager"


def settings_path() -> Path:
    """Return the platform-appropriate settings file location."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / APP_NAME / "settings.json"


def load() -> Dict[str, Any]:
    """Load settings; returns {} when missing or unreadable."""
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: Dict[str, Any]) -> None:
    """Persist settings; silently ignores write failures."""
    try:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
