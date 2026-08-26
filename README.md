# 📂 File Manager

A modern, cross-platform **file management system with a GUI**, built with
Python 3, Tkinter and [ttkbootstrap](https://ttkbootstrap.readthedocs.io/).

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![GUI](https://img.shields.io/badge/GUI-ttkbootstrap-green)

## ✨ Features

- **Browse** files and folders in a sortable, icon-rich list view
- **Places sidebar** — Home, Desktop, Documents, Downloads, mounted
  volumes and **recent folders**
- **Navigation** — back / forward history, parent folder, editable path
  bar, **clickable breadcrumb bar**, **type-ahead** (start typing to jump
  to a file)
- **Search** — live name search (substring or `*`/`?` globs), recursive
- **File operations**
  - Create folders & files
  - Cut / Copy / Paste (with automatic name de-duplication)
  - Rename, **Bulk Rename** (edit many names at once, live validation,
    supports swaps), Duplicate
  - Delete (moves to the OS Trash when `send2trash` is installed)
  - **Compress to ZIP / Extract ZIP** (stdlib-only, zip-slip safe)
  - **Copy Path / Copy Name** to clipboard
- **Open with OS default app**, **Reveal in Finder / Explorer** and
  **Open Terminal Here**
- **Preview panel** — metadata plus a text snippet for small files
- **Folder sizes** computed lazily in the background
- **Properties dialog** — size, dates, permissions
- **🧹 Temp File Cleaner** — scans a folder tree for junk (`.DS_Store`,
  `*.tmp`, `__pycache__`, backups, caches, empty folders…), previews matches
  by category with sizes, and safely deletes selected items to the Trash
- **Show / hide hidden files** toggle
- **Remembers your state** — window size, last folder, sort order,
  hidden-files toggle and recent folders persist between sessions
- **Keyboard shortcuts** (⌘/Ctrl variants both supported)

| Shortcut | Action |
|---|---|
| `⌘/Ctrl + C / X / V` | Copy / Cut / Paste |
| `⌘/Ctrl + ⌫` | Delete (to Trash) |
| `⌘/Ctrl + I` | Properties |
| `⌘/Ctrl + U` | Go up one level |
| `⌘/Ctrl + [ / ]` | Back / Forward |
| `⌘/Ctrl + F` | Focus search |
| `⌘/Ctrl + L` | Focus path bar |
| `⌘/Ctrl + R` | Refresh |
| `⌘/Ctrl + Shift + K` | Open Temp File Cleaner |
| `⌘/Ctrl + Shift + C` | Copy path(s) to clipboard |
| `F2` | Rename selected item |
| `Delete` | Delete (to Trash) |
| `Escape` | Clear search / selection |
| `Alt + ← / → / ↑` | Back / Forward / Up |
| `Enter` / double-click | Open item |
| type letters in the list | Jump to matching entry |

## 🚀 Getting Started

### 1. Install dependencies

A project virtual environment is recommended:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` includes `ttkbootstrap` (the GUI theme engine) and
`send2trash` (so deletes go to the OS Trash instead of being permanent).
Without `send2trash`, deletes are permanent and the app says so.

### 2. Run

```bash
python main.py
# or
python -m filemanager
```

### 3. Test

```bash
python -m unittest discover -s tests
```

## 🗂️ Project Structure

The codebase is organized into two cleanly separated layers:

```
file-manager/
├── main.py                      # Entry point (thin wrapper)
├── requirements.txt
├── README.md
├── tests/                       # Core-layer unit tests (stdlib unittest)
└── filemanager/
    ├── __init__.py              # Package docs + version
    ├── __main__.py              # Enables `python -m filemanager`
    ├── app.py                   # Bootstrap: themed window + event loop
    │
    ├── core/                    # 🧠 Pure logic — NO GUI imports
    │   ├── __init__.py          # Public API re-exports
    │   ├── errors.py            # FileOperationError
    │   ├── models.py            # FileEntry dataclass, human_size()
    │   ├── filesystem.py        # Directory listing, places/drives
    │   ├── fileops.py           # Create / rename / bulk rename / delete / copy / move
    │   ├── search.py            # Recursive name search engine
    │   ├── info.py              # Folder sizes, property metadata
    │   ├── archive.py           # ZIP compress / extract (stdlib)
    │   ├── osintegration.py     # Open / reveal / terminal
    │   ├── settings.py          # JSON settings store
    │   └── cleaner.py           # Temp-file categories + scan engine
    │
    └── gui/                     # 🎨 All ttkbootstrap/Tkinter code
        ├── __init__.py
        ├── icons.py             # File-type icon map
        ├── dialogs.py           # Reusable dialogs (text input)
        ├── main_window.py       # Main File Manager window
        ├── bulk_rename_dialog.py # Bulk rename with live validation
        └── cleaner_dialog.py    # Temp File Cleaner dialog
```

## 🧩 Architecture

The app follows a strict **core / GUI separation**:

- **`filemanager/core/`** — pure filesystem logic with zero GUI imports.
  Every module has a single responsibility and raises `FileOperationError`
  on failure. Fully testable and reusable from a CLI.
- **`filemanager/gui/`** — all UI code. Imports from `core`, never the other
  way around. Long-running work (search, temp scans) runs on background
  threads and reports back through thread-safe queues, so the UI never
  freezes.
- **`filemanager/app.py`** — tiny bootstrap that wires the themed window to
  the main window class.

Dependency rule: `gui → core` only. `core` never imports `gui`.

## 📝 Notes

- Works on **macOS, Windows and Linux**.
- Requires **Python 3.9+**.
- Deleting without `send2trash` is permanent — a confirmation dialog is
  always shown first, and it clearly states whether the delete goes to
  the Trash or is irreversible.
