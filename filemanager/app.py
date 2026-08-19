"""Application bootstrap — creates the themed window and starts the event loop."""

from __future__ import annotations

import ttkbootstrap as ttk

from .gui import FileManagerApp

#: ttkbootstrap theme used for the whole application.
THEME = "darkly"


def run() -> None:
    """Create the main window and run the Tk event loop."""
    root = ttk.Window(themename=THEME)
    FileManagerApp(root)
    root.mainloop()
