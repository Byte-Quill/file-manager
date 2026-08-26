"""Core layer — GUI-independent file management logic.

Everything in this subpackage is pure Python filesystem logic with no
Tkinter/ttkbootstrap imports, so it can be tested and reused independently
of the GUI (e.g. from a CLI or unit tests).

Modules
-------
errors        Custom exceptions
models        Data models (FileEntry) and formatting helpers
filesystem    Directory listing and places/drives discovery
fileops       Create / rename / delete / copy / move operations
search        Recursive file-name search engine
info          Sizes and property metadata
osintegration Open with default app, reveal in Finder/Explorer
cleaner       Temp-file categories + scan engine
"""

from . import cleaner
from .errors import FileOperationError
from .filesystem import get_drives, list_directory
from .fileops import (
    TRASH_AVAILABLE,
    copy_items,
    create_file,
    create_folder,
    delete_items,
    move_items,
    rename_item,
    unique_name,
)
from .info import folder_size, item_info
from .models import FileEntry, human_size
from .osintegration import open_in_system, reveal_in_finder
from .search import search

__all__ = [
    "FileOperationError",
    "FileEntry",
    "human_size",
    "get_drives",
    "list_directory",
    "TRASH_AVAILABLE",
    "copy_items",
    "create_file",
    "create_folder",
    "delete_items",
    "move_items",
    "rename_item",
    "unique_name",
    "search",
    "folder_size",
    "item_info",
    "open_in_system",
    "reveal_in_finder",
    "cleaner",
]
