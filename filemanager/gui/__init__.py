"""GUI layer — all ttkbootstrap/Tkinter code lives here.

Modules
-------
icons           File-type icon map
dialogs         Small reusable dialogs (text input)
main_window     The main File Manager window
cleaner_dialog  Temp File Cleaner dialog
"""

from .main_window import FileManagerApp

__all__ = ["FileManagerApp"]
