"""Main File Manager window (ttkbootstrap + ttk.Treeview)."""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from .. import core
from ..core import FileEntry, FileOperationError
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
        self._sort_reverse: Dict[str, bool] = {}
        self._busy = False
        self._action_buttons: List[ttk.Button] = []

        self._build_ui()
        self._bind_shortcuts()
        self.navigate_to(self.current_dir, push_history=False)
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
        if sys.platform == "darwin":
            # On macOS Button-2 is right-click; on Linux it is middle-click.
            self.tree.bind("<Button-2>", self._on_context_menu)

        self._build_context_menu()

        # ---- Status bar ---------------------------------------------------- #
        self.status_var = ttk.StringVar(value="Ready")
        status = ttk.Label(self.root, textvariable=self.status_var, anchor=W,
                           padding=(10, 4), bootstyle="inverse-secondary")
        status.pack(fill=X, side=BOTTOM)

    def _build_context_menu(self) -> None:
        self.menu = ttk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Open", command=self.open_selected)
        self.menu.add_command(label="Reveal in Finder", command=self.reveal_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Cut  ⌘X", command=self.cut_selected)
        self.menu.add_command(label="Copy  ⌘C", command=self.copy_selected)
        self.menu.add_command(label="Paste  ⌘V", command=self.paste)
        self.menu.add_separator()
        self.menu.add_command(label="Rename…", command=self.rename_selected)
        self.menu.add_command(label="Duplicate", command=self.duplicate_selected)
        self.menu.add_command(label="Move to Trash  ⌘⌫", command=self.delete_selected)
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
        }
        for seq, func in bindings.items():
            self.root.bind(seq, lambda _e, f=func: f())
            # Also bind Control- variants for Linux/Windows friendliness
            self.root.bind(seq.replace("Command", "Control"), lambda _e, f=func: f())

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
        self.path_var.set(str(path))
        self.refresh()

    def refresh(self) -> None:
        if self.search_mode:
            self.run_search()
            return
        try:
            entries = core.list_directory(self.current_dir, self.show_hidden.get())
        except FileOperationError as exc:
            self._error(exc)
            return
        self._fill_tree(entries)
        n_dirs = sum(1 for e in entries if e.is_dir)
        n_files = len(entries) - n_dirs
        self.status_var.set(f"{self.current_dir}   —   {n_dirs} folder(s), {n_files} file(s)")
        self._update_nav_buttons()

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
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def _selected_paths(self) -> List[str]:
        return [self.tree.item(iid, "tags")[0] for iid in self.tree.selection()]

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
                    self.status_var.set(
                        f"Search “{query}” — {len(results)} result(s) in {root}")
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
        self._set_busy(True, f"{verb} {len(sources)} item(s)…")

        def worker() -> None:
            try:
                op = core.move_items if cut else core.copy_items
                op(sources, dest,
                   progress=lambda msg: self.bg_queue.put(("status", msg)))
                self.bg_queue.put(("op-done", f"Pasted {len(sources)} item(s)", cut))
            except Exception as exc:
                self.bg_queue.put(("op-error", exc))

        threading.Thread(target=worker, daemon=True).start()

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
        self._set_busy(True, f"Deleting {count} item(s)…")

        def worker() -> None:
            try:
                core.delete_items(targets, use_trash=use_trash)
                self.bg_queue.put(("op-done", f"Deleted {count} item(s)", False))
            except Exception as exc:
                self.bg_queue.put(("op-error", exc))

        threading.Thread(target=worker, daemon=True).start()

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
    def _sort_column(self, col: str) -> None:
        def key(iid: str):
            tags = self.tree.item(iid, "tags")
            if col == "size":
                # Folders sort first, then files by raw byte count (numeric).
                return (0, 0) if tags[1] == "dir" else (1, int(tags[2]))
            if col == "modified":
                return float(tags[3])
            return self.tree.set(iid, col).lower()

        reverse = self._sort_reverse.get(col, False)
        for index, iid in enumerate(
                sorted(self.tree.get_children(), key=key, reverse=reverse)):
            self.tree.move(iid, "", index)
        self._sort_reverse[col] = not reverse

    # -------------------------------------------------------------- helpers -- #
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

    def _error(self, exc: Exception) -> None:
        Messagebox.show_error(str(exc), "Error", alert=True)
