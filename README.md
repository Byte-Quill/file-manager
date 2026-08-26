# 📂 File Manager

A modern, cross-platform **file management system with a GUI**, built with
Python 3, Tkinter and [ttkbootstrap](https://ttkbootstrap.readthedocs.io/).

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![GUI](https://img.shields.io/badge/GUI-ttkbootstrap-green)

## ✨ Features

- **Browse** files and folders in a sortable, icon-rich list view
- **Places sidebar** — Home, Desktop, Documents, Downloads, mounted volumes
- **Navigation** — back / forward history, parent folder, editable path bar
- **Search** — live name search (substring or `*`/`?` globs), recursive
- **File operations**
  - Create folders & files
  - Cut / Copy / Paste (with automatic name de-duplication)
  - Rename, Duplicate
  - Delete (moves to the OS Trash when `send2trash` is installed)
- **Open with OS default app** and **Reveal in Finder / Explorer**
- **Properties dialog** — size, dates, permissions
- **🧹 Temp File Cleaner** — scans a folder tree for junk (`.DS_Store`,
  `*.tmp`, `__pycache__`, backups, caches, empty folders…), previews matches
  by category with sizes, and safely deletes selected items to the Trash
- **Show / hide hidden files** toggle
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
| `Enter` / double-click | Open item |

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
    │   ├── fileops.py           # Create / rename / delete / copy / move
    │   ├── search.py            # Recursive name search engine
    │   ├── info.py              # Folder sizes, property metadata
    │   ├── osintegration.py     # Open with default app, reveal in Finder
    │   └── cleaner.py           # Temp-file categories + scan engine
    │
    └── gui/                     # 🎨 All ttkbootstrap/Tkinter code
        ├── __init__.py
        ├── icons.py             # File-type icon map
        ├── dialogs.py           # Reusable dialogs (text input)
        ├── main_window.py       # Main File Manager window
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
