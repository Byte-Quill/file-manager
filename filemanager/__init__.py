"""File Manager — a modern cross-platform file management system with a GUI.

Built with Python, Tkinter and ttkbootstrap.

Architecture
------------
``filemanager.core``
    GUI-independent filesystem logic: listing, copy/move/delete, search,
    metadata, OS integration and the temp-file cleaner engine.
``filemanager.gui``
    All ttkbootstrap/Tkinter UI code: main window, cleaner dialog, dialogs
    and icons.
``filemanager.app``
    Application bootstrap (window creation + event loop).

Run with ``python main.py`` or ``python -m filemanager``.
"""

__version__ = "1.1.0"
