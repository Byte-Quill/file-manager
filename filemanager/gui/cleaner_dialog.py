"""Temp File Cleaner dialog — scan preview + safe deletion UI."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Dict, List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox

from .. import core
from ..core import FileOperationError, cleaner, human_size
from ..core.cleaner import TempMatch, summarize


class CleanerDialog(ttk.Toplevel):
    """Modal dialog that scans a folder for temporary files and deletes them."""

    def __init__(self, master, initial_dir: Path) -> None:
        super().__init__(master)
        self.title("🧹 Temp File Cleaner")
        self.geometry("860x620")
        self.minsize(720, 480)
        self.transient(master)

        self.initial_dir = Path(initial_dir)
        self.matches: List[TempMatch] = []
        self.scan_thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._category_vars: Dict[str, ttk.BooleanVar] = {}
        self._msg_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

    # ------------------------------------------------------------------ UI -- #
    def _build_ui(self) -> None:
        # ---- Scan options -------------------------------------------------- #
        opts = ttk.Labelframe(self, text="Scan options", padding=10)
        opts.pack(fill=X, padx=10, pady=(10, 6))

        row1 = ttk.Frame(opts)
        row1.pack(fill=X)
        ttk.Label(row1, text="Folder to clean:").pack(side=LEFT)
        self.dir_var = ttk.StringVar(value=str(self.initial_dir))
        dir_entry = ttk.Entry(row1, textvariable=self.dir_var)
        dir_entry.pack(side=LEFT, fill=X, expand=True, padx=8)
        ttk.Button(row1, text="Browse…", bootstyle="secondary-outline",
                   command=self._browse, takefocus=False).pack(side=LEFT)

        row2 = ttk.Frame(opts)
        row2.pack(fill=X, pady=(8, 0))
        self.recursive_var = ttk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Include subfolders", variable=self.recursive_var,
                        bootstyle="round-toggle", takefocus=False).pack(side=LEFT)
        self.hidden_var = ttk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Scan hidden folders", variable=self.hidden_var,
                        bootstyle="round-toggle", takefocus=False).pack(side=LEFT, padx=16)

        # ---- Category checkboxes ------------------------------------------- #
        cats = ttk.Labelframe(self, text="What to look for", padding=10)
        cats.pack(fill=X, padx=10, pady=6)
        for i, cat in enumerate(cleaner.CATEGORIES):
            var = ttk.BooleanVar(value=cat.default_enabled)
            self._category_vars[cat.key] = var
            cb = ttk.Checkbutton(cats, text=f"{cat.label}  —  {cat.description}",
                                 variable=var, takefocus=False)
            cb.grid(row=i // 2, column=i % 2, sticky=W, padx=(0, 24), pady=2)
        cats.columnconfigure(0, weight=1)
        cats.columnconfigure(1, weight=1)

        # ---- Action row ----------------------------------------------------- #
        actions = ttk.Frame(self, padding=(10, 4))
        actions.pack(fill=X)
        self.scan_btn = ttk.Button(actions, text="🔍 Scan", bootstyle="primary",
                                   command=self.start_scan, takefocus=False)
        self.scan_btn.pack(side=LEFT)
        self.cancel_btn = ttk.Button(actions, text="Stop", bootstyle="danger-outline",
                                     command=self._cancel.set, state=DISABLED,
                                     takefocus=False)
        self.cancel_btn.pack(side=LEFT, padx=8)

        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=220)
        self.progress.pack(side=LEFT, padx=8)

        self.summary_var = ttk.StringVar(value="Choose options and press Scan.")
        ttk.Label(actions, textvariable=self.summary_var).pack(side=RIGHT)

        # ---- Results -------------------------------------------------------- #
        results = ttk.Frame(self, padding=(10, 4))
        results.pack(fill=BOTH, expand=True)

        columns = ("sel", "category", "name", "size", "reason")
        self.tree = ttk.Treeview(results, columns=columns, show="headings",
                                 selectmode="extended")
        for col, text, width, anchor in (
            ("sel", "✓", 40, CENTER),
            ("category", "Category", 150, W),
            ("name", "Path", 420, W),
            ("size", "Size", 90, E),
            ("reason", "Matched", 110, W),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor,
                             stretch=(col == "name"))

        vsb = ttk.Scrollbar(results, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)

        self.tree.bind("<Button-1>", self._on_tree_click)

        sel_row = ttk.Frame(self, padding=(10, 2))
        sel_row.pack(fill=X)
        ttk.Button(sel_row, text="Select all", bootstyle="secondary-outline",
                   command=lambda: self._set_all(True), takefocus=False).pack(side=LEFT)
        ttk.Button(sel_row, text="Deselect all", bootstyle="secondary-outline",
                   command=lambda: self._set_all(False), takefocus=False).pack(side=LEFT, padx=6)

        # ---- Footer ---------------------------------------------------------- #
        footer = ttk.Frame(self, padding=(10, 8))
        footer.pack(fill=X, side=BOTTOM)
        self.delete_btn = ttk.Button(footer, text="🗑️ Delete selected",
                                     bootstyle="danger", command=self.delete_selected,
                                     state=DISABLED, takefocus=False)
        self.delete_btn.pack(side=RIGHT)
        self.footer_var = ttk.StringVar(value="")
        ttk.Label(footer, textvariable=self.footer_var).pack(side=RIGHT, padx=12)

    # ------------------------------------------------------------- scanning -- #
    def _browse(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.home()),
                                         title="Choose folder to clean", parent=self)
        if chosen:
            self.dir_var.set(chosen)

    def start_scan(self) -> None:
        if self.scan_thread is not None and self.scan_thread.is_alive():
            return
        root = Path(self.dir_var.get().strip() or "~").expanduser()
        enabled = [k for k, v in self._category_vars.items() if v.get()]
        if not enabled:
            Messagebox.show_warning("Enable at least one category to scan for.",
                                    "Temp File Cleaner", parent=self)
            return

        # Capture all Tk variable values on the UI thread before spawning.
        recursive = self.recursive_var.get()
        include_hidden = self.hidden_var.get()

        self.matches = []
        self.tree.delete(*self.tree.get_children())
        self._cancel.clear()
        self.scan_btn.configure(state=DISABLED)
        self.cancel_btn.configure(state=NORMAL)
        self.delete_btn.configure(state=DISABLED)
        self.progress.start(12)
        self.summary_var.set("Scanning…")

        def worker() -> None:
            try:
                found = cleaner.scan_for_temp_files(
                    root, enabled,
                    recursive=recursive,
                    include_hidden=include_hidden,
                    progress=lambda n, d: self._msg_queue.put(("progress", n)),
                    should_cancel=self._cancel.is_set,
                )
                self._msg_queue.put(("done", found, None))
            except Exception as exc:  # surface any error in the UI thread
                self._msg_queue.put(("done", [], exc))

        self.scan_thread = threading.Thread(target=worker, daemon=True)
        self.scan_thread.start()

    def _poll_queue(self) -> None:
        """Drain worker-thread messages on the UI thread (thread-safe)."""
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                if msg[0] == "progress":
                    self.summary_var.set(f"Scanned {msg[1]} items…")
                elif msg[0] == "done":
                    self._scan_done(msg[1], msg[2])
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._poll_queue)

    def _scan_done(self, found: List[TempMatch], error: Optional[Exception]) -> None:
        self.progress.stop()
        self.scan_btn.configure(state=NORMAL)
        self.cancel_btn.configure(state=DISABLED)

        if error is not None:
            self.summary_var.set("Scan failed.")
            Messagebox.show_error(str(error), "Temp File Cleaner", parent=self)
            return

        self.matches = found
        for i, m in enumerate(found):
            self.tree.insert("", END, iid=str(i),
                             values=("☑", m.label, str(m.path),
                                     m.size_display, m.reason),
                             tags=("checked",))
        self.tree.tag_configure("checked", foreground="#7ad07a")
        self.tree.tag_configure("unchecked", foreground="#8a8a8a")

        count, total = summarize(found)
        cancelled = " (stopped early)" if self._cancel.is_set() else ""
        self.summary_var.set(
            f"Found {count} item(s), {human_size(total)}{cancelled}")
        self.delete_btn.configure(state=NORMAL if found else DISABLED)
        self._update_footer()

    # ------------------------------------------------------------ selection -- #
    def _on_tree_click(self, event) -> None:
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        tags = self.tree.item(iid, "tags")
        if "checked" in tags:
            self.tree.item(iid, values=("☐",) + self.tree.item(iid, "values")[1:],
                           tags=("unchecked",))
        else:
            self.tree.item(iid, values=("☑",) + self.tree.item(iid, "values")[1:],
                           tags=("checked",))
        self._update_footer()

    def _set_all(self, checked: bool) -> None:
        mark, tag = ("☑", "checked") if checked else ("☐", "unchecked")
        for iid in self.tree.get_children():
            self.tree.item(iid, values=(mark,) + self.tree.item(iid, "values")[1:],
                           tags=(tag,))
        self._update_footer()

    def _checked_matches(self) -> List[TempMatch]:
        out: List[TempMatch] = []
        for iid in self.tree.get_children():
            if "checked" in self.tree.item(iid, "tags"):
                out.append(self.matches[int(iid)])
        return out

    def _update_footer(self) -> None:
        sel = self._checked_matches()
        count, total = summarize(sel)
        self.footer_var.set(f"{count} selected — {human_size(total)}")

    # ------------------------------------------------------------- deletion -- #
    def delete_selected(self) -> None:
        sel = self._checked_matches()
        if not sel:
            Messagebox.show_info("Nothing is selected for deletion.",
                                 "Temp File Cleaner", parent=self)
            return
        count, total = summarize(sel)
        answer = Messagebox.yesno(
            f"Move {count} item(s) ({human_size(total)}) to the Trash?\n\n"
            "You can restore them from the Trash if needed.",
            "Confirm Cleanup", parent=self, alert=True)
        if answer != "Yes":
            return

        deleted_iids: List[str] = []
        errors: List[str] = []
        for iid in self.tree.get_children():
            if "checked" not in self.tree.item(iid, "tags"):
                continue
            m = self.matches[int(iid)]
            if not m.path.exists():
                deleted_iids.append(iid)  # already gone
                continue
            try:
                core.delete_items([m.path], use_trash=True)
                deleted_iids.append(iid)
            except FileOperationError as exc:
                errors.append(str(exc))

        for iid in deleted_iids:
            self.tree.delete(iid)

        # Row iids are stable indices into self.matches — no remapping needed.
        remaining = [self.matches[int(i)] for i in self.tree.get_children()]

        self._update_footer()
        count_left, total_left = summarize(remaining)
        self.summary_var.set(f"{count_left} item(s) remaining — {human_size(total_left)}")
        self.delete_btn.configure(state=NORMAL if remaining else DISABLED)

        if errors:
            Messagebox.show_warning(
                f"Deleted successfully, but {len(errors)} item(s) failed:\n\n"
                + "\n".join(errors[:5]),
                "Temp File Cleaner", parent=self)
        else:
            Messagebox.show_info(
                f"Cleanup complete — {len(deleted_iids)} item(s) moved to Trash.",
                "Temp File Cleaner", parent=self)

    # ---------------------------------------------------------------- misc -- #
    def _on_close(self) -> None:
        self._cancel.set()
        self.destroy()
