"""Main File Manager window (ttkbootstrap + ttk.Treeview)."""

from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from .. import core
from ..core import FileEntry, FileOperationError
from ..core.models import human_size
from ..core.search import MAX_RESULTS as SEARCH_MAX_RESULTS
from .dialogs import ask_string
from .icons import icon_for


class FileManagerApp:
    """The main application window: navigation, listing and file actions."""

    def __init__(self, root: ttk.Window) -> None:
        self.root = root
        root.title("File Manager")
        root.geometry("1180x720")
        root.minsize(900, 560)

        # Navigation state
        self.current_dir: Path = Path.home()
        self.history: List[Path] = [self.current_dir]
        self.history_index: int = 0
        self.show_hidden = ttk.BooleanVar(value=False)
        self.clipboard: List[Path] = []
        self.clipboard_cut = False
        self.search_mode = False
        self.bg_queue: queue.Queue = queue.Queue()
        self._search_token = 0
        self._list_token = 0
        self._sort_reverse: Dict[str, bool] = {}
        self._busy = False
        self._action_buttons: List[ttk.Button] = []
        self._typeahead = ""
        self._typeahead_time = 0.0
        self._size_token = 0
        self._preview_after: Optional[str] = None
        self._sort_col: Optional[str] = None
        self.folder_sizes_var = ttk.BooleanVar(value=True)
        self._settings = core.settings.load()

        self._apply_saved_state()
        self._build_ui()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.navigate_to(self.current_dir, push_history=False)
        self._restore_sort()
        self.root.after(250, self._poll_bg_queue)

    # ------------------------------------------------------------------ UI -- #
    def _build_ui(self) -> None:
        style = ttk.Style()
        style.configure("Treeview", rowheight=28, font=("Helvetica", 12))
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))

        # ---- Toolbar ------------------------------------------------------ #
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(fill=X)

        self.btn_back = ttk.Button(toolbar, text="←", width=3, bootstyle="secondary",
                                   command=self.go_back, takefocus=False)
        self.btn_back.pack(side=LEFT, padx=(0, 4))
        self.btn_forward = ttk.Button(toolbar, text="→", width=3, bootstyle="secondary",
                                      command=self.go_forward, takefocus=False)
        self.btn_forward.pack(side=LEFT, padx=(0, 4))
        self.btn_up = ttk.Button(toolbar, text="↑", width=3, bootstyle="secondary",
                                 command=self.go_up, takefocus=False)
        self.btn_up.pack(side=LEFT, padx=(0, 10))

        self.path_var = ttk.StringVar(value=str(self.current_dir))
        self.path_entry = ttk.Entry(toolbar, textvariable=self.path_var, font=("Helvetica", 12))
        self.path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))
        self.path_entry.bind("<Return>", self._on_path_enter)

        self.search_var = ttk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=24,
                                      font=("Helvetica", 12))
        self.search_entry.pack(side=LEFT, padx=(0, 6))
        self.search_entry.insert(0, "Search…")
        self.search_entry.bind("<FocusIn>", self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)
        self.search_entry.bind("<Return>", self._on_search_enter)

        ttk.Button(toolbar, text="🔍", width=3, bootstyle="info",
                   command=self.run_search, takefocus=False).pack(side=LEFT)

        # ---- Breadcrumb bar ------------------------------------------------ #
        self.crumb_bar = ttk.Frame(self.root, padding=(8, 0, 8, 2))
        self.crumb_bar.pack(fill=X)

        # ---- Second toolbar row (actions) --------------------------------- #
        actions = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        actions.pack(fill=X)

        def action_btn(text, style, command, padx):
            btn = ttk.Button(actions, text=text, bootstyle=style,
                             command=command, takefocus=False)
            btn.pack(side=LEFT, padx=padx)
            self._action_buttons.append(btn)
            return btn

        action_btn("➕ New Folder", "success-outline", self.new_folder, (0, 6))
        action_btn("📄 New File", "success-outline", self.new_file, (0, 12))
        action_btn("✂️ Cut", "secondary-outline", self.cut_selected, (0, 4))
        action_btn("📋 Copy", "secondary-outline", self.copy_selected, (0, 4))
        action_btn("📥 Paste", "secondary-outline", self.paste, (0, 12))
        action_btn("✏️ Rename", "warning-outline", self.rename_selected, (0, 4))
        action_btn("🗑️ Delete", "danger-outline", self.delete_selected, (0, 12))
        action_btn("🧹 Clean Temp Files", "info", self.open_cleaner, (0, 12))

        ttk.Checkbutton(actions, text="Show hidden files", variable=self.show_hidden,
                        command=self.refresh, bootstyle="round-toggle",
                        takefocus=False).pack(side=RIGHT)
        ttk.Checkbutton(actions, text="Folder sizes", variable=self.folder_sizes_var,
                        command=self._start_folder_sizes, bootstyle="round-toggle",
                        takefocus=False).pack(side=RIGHT, padx=(0, 12))
        self.show_preview = ttk.BooleanVar(value=True)
        ttk.Checkbutton(actions, text="Preview", variable=self.show_preview,
                        command=self._toggle_preview, bootstyle="round-toggle",
                        takefocus=False).pack(side=RIGHT, padx=(0, 12))

        # ---- Main pane: sidebar + file list ------------------------------- #
        pane = ttk.Panedwindow(self.root, orient=HORIZONTAL)
        pane.pack(fill=BOTH, expand=True, padx=8, pady=(0, 4))

        sidebar_frame = ttk.Labelframe(pane, text="Places", padding=4)
        pane.add(sidebar_frame, weight=0)

        self.sidebar = ttk.Treeview(sidebar_frame, show="tree", selectmode="browse",
                                    columns=("path",))
        self.sidebar.column("#0", width=190, stretch=False)
        self.sidebar.pack(fill=BOTH, expand=True)
        self.sidebar.bind("<<TreeviewSelect>>", self._on_sidebar_select)
        self._populate_sidebar()

        list_frame = ttk.Frame(pane)
        pane.add(list_frame, weight=1)

        columns = ("name", "size", "modified")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 selectmode="extended")
        self.tree.heading("name", text="Name",
                          command=lambda: self._sort_column("name"))
        self.tree.heading("size", text="Size",
                          command=lambda: self._sort_column("size"))
        self.tree.heading("modified", text="Modified",
                          command=lambda: self._sort_column("modified"))
        self.tree.column("name", width=480, anchor=W)
        self.tree.column("size", width=110, anchor=E)
        self.tree.column("modified", width=160, anchor=CENTER)

        vsb = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_context_menu)
        self.tree.bind("<Control-Button-1>", self._on_context_menu)
        self.tree.bind("<Key>", self._on_tree_key)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        if sys.platform == "darwin":
            # On macOS Button-2 is right-click; on Linux it is middle-click.
            self.tree.bind("<Button-2>", self._on_context_menu)

        self._build_context_menu()

        # ---- Status bar ---------------------------------------------------- #
        self.status_var = ttk.StringVar(value="Ready")
        status = ttk.Label(self.root, textvariable=self.status_var, anchor=W,
                           padding=(10, 4), bootstyle="inverse-secondary")
        status.pack(fill=X, side=BOTTOM)

        # ---- Preview panel (packed above the status bar) ------------------- #
        self.preview_var = ttk.StringVar(value="")
        self.preview_frame = ttk.Labelframe(self.root, text="Preview", padding=6)
        ttk.Label(self.preview_frame, textvariable=self.preview_var,
                  justify=LEFT, wraplength=1100, anchor=W).pack(fill=X)
        self.preview_frame.pack(fill=X, side=BOTTOM, padx=8, pady=(0, 4))

    def _build_context_menu(self) -> None:
        self.menu = ttk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Open", command=self.open_selected)
        self.menu.add_command(label="Reveal in Finder", command=self.reveal_selected)
        self.menu.add_command(label="Open Terminal Here", command=self.open_terminal_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Cut  ⌘X", command=self.cut_selected)
        self.menu.add_command(label="Copy  ⌘C", command=self.copy_selected)
        self.menu.add_command(label="Paste  ⌘V", command=self.paste)
        self.menu.add_command(label="Copy Path  ⌘⇧C", command=self.copy_path)
        self.menu.add_command(label="Copy Name", command=self.copy_name)
        self.menu.add_separator()
        self.menu.add_command(label="Rename…  F2", command=self.rename_selected)
        self.menu.add_command(label="Bulk Rename…", command=self.bulk_rename_selected)
        self.menu.add_command(label="Duplicate", command=self.duplicate_selected)
        self.menu.add_command(label="Move to Trash  ⌘⌫", command=self.delete_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Compress to ZIP…", command=self.compress_selected)
        self.menu.add_command(label="Extract Here", command=self.extract_selected)
        self._extract_index = self.menu.index(END)
        self.menu.add_separator()
        self.menu.add_command(label="Properties  ⌘I", command=self.show_properties)

    def _populate_sidebar(self) -> None:
        self.sidebar.delete(*self.sidebar.get_children())
        for loc in core.get_drives():
            label = loc.name or str(loc)
            if loc == Path.home():
                label = "🏠 Home"
            elif loc == Path("/"):
                label = "💽 Computer"
            self.sidebar.insert("", END, text=f"  {label}", values=(str(loc),))
        recents = [Path(p) for p in self._settings.get("recent_dirs", [])
                   if Path(p).is_dir()]
        if recents:
            self.sidebar.insert("", END, text="  ── Recent ──", values=("",))
            for loc in recents:
                self.sidebar.insert("", END, text=f"  🕘 {loc.name}",
                                    values=(str(loc),))

    # ------------------------------------------------------------- shortcuts #
    def _bind_shortcuts(self) -> None:
        bindings = {
            "<Command-Return>": self.open_selected,
            "<Command-c>": self.copy_selected,
            "<Command-x>": self.cut_selected,
            "<Command-v>": self.paste,
            "<Command-BackSpace>": self.delete_selected,
            "<Command-i>": self.show_properties,
            "<Command-u>": self.go_up,
            "<Command-r>": self.refresh,
            "<Command-f>": lambda e: self.search_entry.focus_set(),
            "<Command-l>": lambda e: self.path_entry.focus_set(),
            "<Command-bracketleft>": self.go_back,
            "<Command-bracketright>": self.go_forward,
            "<Command-Shift-k>": self.open_cleaner,
            "<Command-Shift-c>": self.copy_path,
        }
        for seq, func in bindings.items():
            self.root.bind(seq, lambda _e, f=func: f())
            # Also bind Control- variants for Linux/Windows friendliness
            self.root.bind(seq.replace("Command", "Control"), lambda _e, f=func: f())

        # Plain (non-modifier) and Alt shortcuts, same on every platform.
        self.root.bind("<F2>", lambda _e: self.rename_selected())
        self.root.bind("<Delete>", lambda _e: self.delete_selected())
        self.root.bind("<Escape>", lambda _e: self._escape())
        self.root.bind("<Alt-Left>", lambda _e: self.go_back())
        self.root.bind("<Alt-Right>", lambda _e: self.go_forward())
        self.root.bind("<Alt-Up>", lambda _e: self.go_up())

    # ------------------------------------------------------------ navigation #
    def navigate_to(self, path: Path, push_history: bool = True) -> None:
        path = Path(path).expanduser().resolve()
        if not path.is_dir():
            self._error(FileOperationError(f"Not a directory:\n{path}"))
            return
        self.current_dir = path
        self.search_mode = False
        if push_history:
            self.history = self.history[: self.history_index + 1]
            self.history.append(path)
            self.history_index = len(self.history) - 1
        self._add_recent(path)
        self.path_var.set(str(path))
        self._update_breadcrumbs()
        self.refresh()

    def _add_recent(self, path: Path) -> None:
        """Remember the folder in the persisted recent list (max 8)."""
        recents = self._settings.get("recent_dirs", [])
        s = str(path)
        if s in recents:
            recents.remove(s)
        recents.insert(0, s)
        self._settings["recent_dirs"] = recents[:8]
        core.settings.save(self._settings)
        self._populate_sidebar()

    def _update_breadcrumbs(self) -> None:
        """Rebuild the clickable path segment bar for the current folder."""
        for child in self.crumb_bar.winfo_children():
            child.destroy()
        parts = self.current_dir.parts or ("/",)
        acc = Path(parts[0])
        for i, part in enumerate(parts):
            if i > 0:
                acc = acc / part
                ttk.Label(self.crumb_bar, text="›").pack(side=LEFT)
            target = acc
            ttk.Button(self.crumb_bar, text=part if part != "/" else "💽 /",
                       bootstyle="link", width=len(part) + 2, takefocus=False,
                       command=lambda t=target: self.navigate_to(t)).pack(side=LEFT)

    def refresh(self) -> None:
        if self.search_mode:
            self.run_search()
            return
        # List on a worker thread so slow mounts never freeze the UI.
        target = self.current_dir
        show_hidden = self.show_hidden.get()
        self._list_token += 1
        token = self._list_token

        def worker() -> None:
            try:
                entries = core.list_directory(target, show_hidden)
                self.bg_queue.put(("listing", token, target, entries, None))
            except Exception as exc:
                self.bg_queue.put(("listing", token, target, [], exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_listing(self, token: int, target: Path,
                    entries: List[FileEntry], error: Optional[Exception]) -> None:
        if token != self._list_token or target != self.current_dir:
            return  # stale listing from a superseded navigation
        if error is not None:
            self._error(error)
            return
        self._fill_tree(entries)
        self._start_folder_sizes()
        n_dirs = sum(1 for e in entries if e.is_dir)
        n_files = len(entries) - n_dirs
        self.status_var.set(f"{self.current_dir}   —   {n_dirs} folder(s), {n_files} file(s)")
        self._update_nav_buttons()

    def _start_folder_sizes(self) -> None:
        """Compute folder sizes in the background and fill them in lazily."""
        if not self.folder_sizes_var.get():
            return
        dirs = [(iid, self.tree.item(iid, "tags")[0])
                for iid in self.tree.get_children()
                if self.tree.item(iid, "tags")[1] == "dir"]
        if not dirs:
            return
        self._size_token += 1
        token = self._size_token

        def worker() -> None:
            for iid, path in dirs:
                try:
                    size = core.folder_size(Path(path))
                except Exception:
                    size = 0
                self.bg_queue.put(("dir-size", token, iid, size))

        threading.Thread(target=worker, daemon=True).start()

    def _fill_tree(self, entries: List[FileEntry]) -> None:
        self.tree.delete(*self.tree.get_children())
        for entry in entries:
            self.tree.insert(
                "", END,
                values=(f"{icon_for(entry)}  {entry.name}",
                        entry.size_display,
                        entry.modified_display),
                # Extra tags carry raw values so sorting stays correct.
                tags=(str(entry.path), "dir" if entry.is_dir else "file",
                      str(entry.size), str(entry.modified)),
            )

    def _update_nav_buttons(self) -> None:
        self.btn_back.configure(state=NORMAL if self.history_index > 0 else DISABLED)
        self.btn_forward.configure(
            state=NORMAL if self.history_index < len(self.history) - 1 else DISABLED)
        self.btn_up.configure(state=NORMAL if self.current_dir.parent != self.current_dir
                              else DISABLED)

    def go_back(self) -> None:
        if self.history_index > 0:
            self.history_index -= 1
            self._goto_history()

    def go_forward(self) -> None:
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._goto_history()

    def _goto_history(self) -> None:
        path = self.history[self.history_index]
        self.current_dir = path
        self.search_mode = False
        self.path_var.set(str(path))
        self._update_breadcrumbs()
        self.refresh()

    def go_up(self) -> None:
        if self.current_dir.parent != self.current_dir:
            self.navigate_to(self.current_dir.parent)

    # -------------------------------------------------------------- events -- #
    def _on_path_enter(self, _event=None) -> None:
        self.navigate_to(Path(self.path_var.get().strip()))

    def _on_sidebar_select(self, _event=None) -> None:
        sel = self.sidebar.selection()
        if not sel:
            return
        path = self.sidebar.item(sel[0], "values")[0]
        if not path:  # section separator row
            return
        self.navigate_to(Path(path))

    def _on_double_click(self, _event=None) -> None:
        for path in self._selected_paths():
            p = Path(path)
            if p.is_dir():
                self.navigate_to(p)
            else:
                try:
                    core.open_in_system(p)
                except FileOperationError as exc:
                    self._error(exc)
            break  # only act on the first item

    def _on_context_menu(self, event) -> None:
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        if self.tree.selection():
            sel = self._selected_paths()
            zip_ok = len(sel) == 1 and sel[0].lower().endswith(".zip")
            self.menu.entryconfigure(self._extract_index,
                                     state=NORMAL if zip_ok else DISABLED)
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def _selected_paths(self) -> List[str]:
        return [self.tree.item(iid, "tags")[0] for iid in self.tree.selection()]

    def _on_tree_key(self, event) -> None:
        """Type-ahead: typing jumps to the first matching entry."""
        if not event.char or not event.char.isprintable():
            return
        now = time.monotonic()
        if now - self._typeahead_time > 0.8:
            self._typeahead = ""
        self._typeahead_time = now
        self._typeahead += event.char.lower()
        prefix = self._typeahead
        for iid in self.tree.get_children():
            name = Path(self.tree.item(iid, "tags")[0]).name.lower()
            if name.startswith(prefix):
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    def _escape(self) -> None:
        """Escape clears search mode, then the search box, then selection."""
        if self.search_mode:
            self.search_mode = False
            self.search_var.set("")
            self.refresh()
        elif self.search_var.get():
            self.search_var.set("")
        elif self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def copy_path(self) -> None:
        paths = self._selected_paths()
        if paths:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(paths))
            self.status_var.set(f"Copied {len(paths)} path(s) to clipboard")

    def copy_name(self) -> None:
        paths = self._selected_paths()
        if paths:
            names = [Path(p).name for p in paths]
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(names))
            self.status_var.set(f"Copied {len(names)} name(s) to clipboard")

    # --------------------------------------------------------------- search -- #
    def _search_focus_in(self, _event=None) -> None:
        if self.search_var.get() == "Search…":
            self.search_entry.delete(0, END)

    def _search_focus_out(self, _event=None) -> None:
        if not self.search_var.get().strip():
            self.search_entry.insert(0, "Search…")

    def _on_search_enter(self, _event=None) -> None:
        self.run_search()

    def run_search(self) -> None:
        query = self.search_var.get().strip()
        if not query or query == "Search…":
            return
        self.search_mode = True
        # Capture state on the UI thread; the worker must not read live attrs.
        root = self.current_dir
        self._search_token += 1
        token = self._search_token
        self.status_var.set(f"Searching for “{query}” in {root}…")
        self.root.update_idletasks()

        def worker() -> None:
            try:
                results = core.search(root, query)
                self.bg_queue.put(("search-results", token, query, root, results))
            except Exception as exc:  # pragma: no cover
                self.bg_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_bg_queue(self) -> None:
        try:
            while True:
                item = self.bg_queue.get_nowait()
                kind = item[0]
                if kind == "search-results":
                    _, token, query, root, results = item
                    if token != self._search_token:
                        continue  # stale result from a superseded search
                    self._fill_tree(results)
                    suffix = (" (limit reached)"
                              if len(results) >= SEARCH_MAX_RESULTS else "")
                    self.status_var.set(
                        f"Search “{query}” — {len(results)} result(s) in {root}{suffix}")
                elif kind == "listing":
                    self._on_listing(item[1], item[2], item[3], item[4])
                elif kind == "error":
                    self._error(item[1])
                elif kind == "status":
                    self.status_var.set(item[1])
                elif kind == "op-done":
                    _, msg, was_cut = item
                    if was_cut:
                        self.clipboard = []
                    self._set_busy(False)
                    self.refresh()
                    self.status_var.set(msg)
                elif kind == "op-error":
                    self._set_busy(False)
                    self.refresh()
                    self._error(item[1])
                elif kind == "dir-size":
                    _, token, iid, size = item
                    if token != self._size_token or not self.tree.exists(iid):
                        continue  # stale update from a previous listing
                    tags = list(self.tree.item(iid, "tags"))
                    tags[2] = str(size)
                    values = self.tree.item(iid, "values")
                    self.tree.item(iid, tags=tuple(tags),
                                   values=(values[0], human_size(size), values[2]))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_bg_queue)

    # ------------------------------------------------------------ operations #
    def new_folder(self) -> None:
        name = ask_string(self.root, "New Folder", "Folder name:", "Untitled Folder")
        if name is None:
            return
        try:
            path = core.create_folder(self.current_dir, name)
            self.refresh()
            self._select_path(path)
        except FileOperationError as exc:
            self._error(exc)

    def new_file(self) -> None:
        name = ask_string(self.root, "New File", "File name:", "untitled.txt")
        if name is None:
            return
        try:
            path = core.create_file(self.current_dir, name)
            self.refresh()
            self._select_path(path)
        except FileOperationError as exc:
            self._error(exc)

    def open_selected(self) -> None:
        for path in self._selected_paths():
            try:
                core.open_in_system(Path(path))
            except FileOperationError as exc:
                self._error(exc)

    def reveal_selected(self) -> None:
        paths = self._selected_paths()
        if paths:
            try:
                core.reveal_in_finder(Path(paths[0]))
            except FileOperationError as exc:
                self._error(exc)

    def open_terminal_selected(self) -> None:
        paths = self._selected_paths()
        target = Path(paths[0]) if paths else self.current_dir
        try:
            core.open_terminal(target)
        except FileOperationError as exc:
            self._error(exc)

    def copy_selected(self) -> None:
        paths = self._selected_paths()
        if paths:
            self.clipboard = [Path(p) for p in paths]
            self.clipboard_cut = False
            self.status_var.set(f"Copied {len(paths)} item(s) to clipboard")

    def cut_selected(self) -> None:
        paths = self._selected_paths()
        if paths:
            self.clipboard = [Path(p) for p in paths]
            self.clipboard_cut = True
            self.status_var.set(f"Cut {len(paths)} item(s) to clipboard")

    def paste(self) -> None:
        if not self.clipboard or self._busy:
            return
        sources = [p for p in self.clipboard if p.exists()]
        if not sources:
            self.status_var.set("Clipboard items no longer exist")
            self.clipboard = []
            return
        cut = self.clipboard_cut
        dest = self.current_dir
        verb = "Moving" if cut else "Copying"
        op = core.move_items if cut else core.copy_items
        self._run_bg(
            lambda: op(sources, dest,
                       progress=lambda msg: self.bg_queue.put(("status", msg))),
            f"Pasted {len(sources)} item(s)", was_cut=cut,
            busy_status=f"{verb} {len(sources)} item(s)…")

    def rename_selected(self) -> None:
        paths = self._selected_paths()
        if len(paths) != 1:
            Messagebox.show_warning("Select exactly one item to rename.", "Rename")
            return
        path = Path(paths[0])
        new_name = ask_string(self.root, "Rename", "New name:", path.name)
        if new_name is None or new_name == path.name:
            return
        try:
            target = core.rename_item(path, new_name)
            self.refresh()
            self._select_path(target)
        except FileOperationError as exc:
            self._error(exc)

    def duplicate_selected(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        try:
            core.copy_items([Path(p) for p in paths], self.current_dir)
            self.refresh()
        except FileOperationError as exc:
            self._error(exc)

    def bulk_rename_selected(self) -> None:
        paths = [Path(p) for p in self._selected_paths()]
        if not paths:
            return
        from .bulk_rename_dialog import BulkRenameDialog

        dialog = BulkRenameDialog(
            self.root, paths,
            lambda names, p=paths: self._do_bulk_rename(p, names))
        dialog.grab_set()

    def _do_bulk_rename(self, paths: List[Path], new_names: List[str]) -> None:
        if not paths:
            return
        self._run_bg(lambda: core.bulk_rename(paths, new_names),
                     f"Renamed {len(paths)} item(s)",
                     busy_status=f"Renaming {len(paths)} item(s)…")

    def compress_selected(self) -> None:
        paths = [Path(p) for p in self._selected_paths()]
        if not paths or self._busy:
            return
        default = (paths[0].stem if len(paths) == 1 else "archive") + ".zip"
        name = ask_string(self.root, "Compress", "Archive name:", default)
        if not name:
            return
        dest = self.current_dir / name
        self._run_bg(
            lambda: core.compress_zip(
                paths, dest, progress=lambda msg: self.bg_queue.put(("status", msg))),
            f"Created {dest.name}",
            busy_status=f"Compressing {len(paths)} item(s)…")

    def extract_selected(self) -> None:
        paths = [Path(p) for p in self._selected_paths()]
        if len(paths) != 1 or self._busy:
            return
        archive = paths[0]
        # Extract into a subfolder named after the archive to avoid clutter.
        dest = self.current_dir / core.unique_name(self.current_dir, archive.stem)
        self._run_bg(
            lambda: core.extract_zip(
                archive, dest, progress=lambda msg: self.bg_queue.put(("status", msg))),
            f"Extracted to {dest.name}",
            busy_status=f"Extracting {archive.name}…")

    def delete_selected(self) -> None:
        paths = self._selected_paths()
        if not paths or self._busy:
            return
        count = len(paths)
        if core.TRASH_AVAILABLE:
            prompt = (f"Move {count} item(s) to the Trash?\n\n"
                      f"You can restore them from the Trash later.")
        else:
            prompt = (f"Permanently delete {count} item(s)?\n\n"
                      f"send2trash is not installed, so this CANNOT be undone.")
        confirm = Messagebox.yesno(prompt, "Confirm Delete", alert=True)
        if confirm != "Yes":
            return
        targets = [Path(p) for p in paths]
        use_trash = core.TRASH_AVAILABLE
        self._run_bg(lambda: core.delete_items(targets, use_trash=use_trash),
                     f"Deleted {count} item(s)",
                     busy_status=f"Deleting {count} item(s)…")

    def show_properties(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        try:
            info = core.item_info(Path(paths[0]))
        except FileOperationError as exc:
            self._error(exc)
            return
        Messagebox.show_info(info, "Properties")

    def open_cleaner(self) -> None:
        """Open the Temp File Cleaner dialog for the current folder."""
        from .cleaner_dialog import CleanerDialog

        dialog = CleanerDialog(self.root, self.current_dir)
        dialog.grab_set()

    # -------------------------------------------------------------- sorting -- #
    _HEADINGS = {"name": "Name", "size": "Size", "modified": "Modified"}

    def _sort_column(self, col: str) -> None:
        reverse = self._sort_reverse.get(col, False)
        self._apply_sort(col, reverse)
        self._sort_reverse[col] = not reverse
        self._sort_col = col

    def _apply_sort(self, col: str, reverse: bool) -> None:
        def key(iid: str):
            tags = self.tree.item(iid, "tags")
            if col == "size":
                # Folders sort first, then files by raw byte count (numeric).
                return (0, 0) if tags[1] == "dir" else (1, int(tags[2]))
            if col == "modified":
                return float(tags[3])
            return self.tree.set(iid, col).lower()

        for index, iid in enumerate(
                sorted(self.tree.get_children(), key=key, reverse=reverse)):
            self.tree.move(iid, "", index)
        # Show a direction arrow on the active heading only.
        for c, text in self._HEADINGS.items():
            if c == col:
                self.tree.heading(c, text=f"{text} {'▼' if not reverse else '▲'}")
            else:
                self.tree.heading(c, text=text)

    # -------------------------------------------------------------- helpers -- #
    def _run_bg(self, work, done_msg: str, was_cut: bool = False,
               busy_status: Optional[str] = None) -> None:
        """Run *work()* on a daemon thread; report result via the bg queue."""
        if self._busy:
            return
        if busy_status:
            self._set_busy(True, busy_status)

        def worker() -> None:
            try:
                work()
                self.bg_queue.put(("op-done", done_msg, was_cut))
            except Exception as exc:
                self.bg_queue.put(("op-error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _set_busy(self, busy: bool, status: Optional[str] = None) -> None:
        """Block file operations while a background op is running."""
        self._busy = busy
        state = DISABLED if busy else NORMAL
        for btn in self._action_buttons:
            btn.configure(state=state)
        if status:
            self.status_var.set(status)

    def _select_path(self, path: Path) -> None:
        for iid in self.tree.get_children():
            if self.tree.item(iid, "tags")[0] == str(path):
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    # -------------------------------------------------------------- preview -- #
    def _toggle_preview(self) -> None:
        if self.show_preview.get():
            self.preview_frame.pack(fill=X, side=BOTTOM, padx=8, pady=(0, 4))
            self._update_preview()
        else:
            self.preview_frame.pack_forget()

    def _on_tree_select(self, _event=None) -> None:
        # Debounce: fast arrow-key navigation should not thrash the disk.
        if self._preview_after:
            self.root.after_cancel(self._preview_after)
        self._preview_after = self.root.after(200, self._update_preview)

    def _update_preview(self) -> None:
        self._preview_after = None
        if not self.show_preview.get():
            return
        paths = self._selected_paths()
        if not paths:
            self.preview_var.set("")
            return
        p = Path(paths[0])
        try:
            st = p.stat()
        except OSError:
            self.preview_var.set(f"{p.name} — unavailable")
            return
        if p.is_dir():
            kind, size_txt = "Folder", "…"
        else:
            kind = (p.suffix.lstrip(".").upper() + " file") if p.suffix else "File"
            size_txt = human_size(st.st_size)
        meta = (f"{p.name}   •   {kind}   •   {size_txt}   •   "
                f"modified {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}")
        snippet = ""
        if not p.is_dir() and 0 < st.st_size <= 1_000_000:
            try:
                text = p.read_bytes()[:4096].decode("utf-8")
                snippet = "\n" + text[:1500].replace("\r", "")
            except (OSError, UnicodeDecodeError):
                snippet = ""  # binary file — metadata only
        self.preview_var.set(meta + snippet)

    # ---------------------------------------------------- state persistence -- #
    def _apply_saved_state(self) -> None:
        s = self._settings
        if s.get("geometry"):
            try:
                self.root.geometry(s["geometry"])
            except Exception:
                pass
        self.show_hidden.set(bool(s.get("show_hidden", False)))
        last = s.get("last_dir")
        if last and Path(last).is_dir():
            self.current_dir = Path(last)
            self.history = [self.current_dir]

    def _restore_sort(self) -> None:
        sort = self._settings.get("sort") or {}
        col = sort.get("column")
        if col in self._HEADINGS:
            reverse = bool(sort.get("reverse", False))
            self._apply_sort(col, reverse)
            self._sort_col = col
            # Next click must flip the restored direction.
            self._sort_reverse[col] = not reverse

    def _on_close(self) -> None:
        # _sort_reverse stores the direction of the NEXT click, so the
        # current direction is its inverse.
        current_reverse = (not self._sort_reverse.get(self._sort_col, False)
                           if self._sort_col else False)
        self._settings.update({
            "geometry": self.root.geometry(),
            "show_hidden": self.show_hidden.get(),
            "last_dir": str(self.current_dir),
            "sort": {"column": self._sort_col, "reverse": current_reverse},
        })
        core.settings.save(self._settings)
        self.root.destroy()

    def _error(self, exc: Exception) -> None:
        Messagebox.show_error(str(exc), "Error", alert=True)
