"""Application bootstrap — creates the themed window and starts the event loop."""

from __future__ import annotations


#: ttkbootstrap theme used for the whole application.
THEME = "darkly"


def run() -> None:
    """Create the main window and run the Tk event loop."""
    import ttkbootstrap as ttk  # deferred import for faster startup

    from .gui import FileManagerApp

    root = ttk.Window(themename=THEME)
    FileManagerApp(root)
    root.mainloop()
