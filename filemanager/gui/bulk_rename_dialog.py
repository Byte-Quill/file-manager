"""Bulk rename dialog — edit several names at once with live validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from ..core.fileops import _validate_name
from ..core.errors import FileOperationError


class BulkRenameDialog(ttk.Toplevel):
    """Modal dialog listing selected items with an editable name per row.

    Calls *on_apply(new_names)* with the final names (same order as
    *paths*) when the user confirms. Validation runs live: duplicate or
    invalid names are highlighted and block the Apply button.
    """

    def __init__(self, master, paths: List[Path], on_apply) -> None:
        super().__init__(master)
        self.title("🔠 Bulk Rename")
        self.geometry("640x480")
        self.minsize(480, 320)
        self.transient(master)

        self.paths = paths
        self.on_apply = on_apply
        self.entries: List[ttk.Entry] = []

        ttk.Label(self, text=f"Renaming {len(paths)} item(s):",
                  font=("Helvetica", 12, "bold")).pack(anchor=W, padx=12, pady=(10, 4))

        # Scrollable row area
        canvas = ttk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient=VERTICAL, command=canvas.yview)
        self.rows = ttk.Frame(canvas)
        self.rows.bind("<Configure>",
                       lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.rows, anchor=NW)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=(12, 0), pady=4)
        vsb.pack(side=RIGHT, fill=Y, pady=4)
        self.rows.columnconfigure(1, weight=1)

        for i, path in enumerate(paths):
            ttk.Label(self.rows, text=path.name).grid(
                row=i, column=0, sticky=W, padx=(0, 8), pady=2)
            entry = ttk.Entry(self.rows, font=("Helvetica", 11))
            entry.insert(0, path.name)
            entry.grid(row=i, column=1, sticky=EW, pady=2)
            entry.bind("<KeyRelease>", lambda _e: self._validate())
            self.entries.append(entry)

        self.hint_var = ttk.StringVar(value="")
        ttk.Label(self, textvariable=self.hint_var, bootstyle="danger",
                  wraplength=600).pack(anchor=W, padx=12)

        btns = ttk.Frame(self)
        btns.pack(fill=X, padx=12, pady=10)
        self.apply_btn = ttk.Button(btns, text="Rename", bootstyle="primary",
                                    command=self._apply, takefocus=False)
        self.apply_btn.pack(side=RIGHT)
        ttk.Button(btns, text="Cancel", bootstyle="secondary-outline",
                   command=self.destroy, takefocus=False).pack(side=RIGHT, padx=8)

        self.bind("<Escape>", lambda _e: self.destroy())
        self._validate()
        if self.entries:
            self.entries[0].focus_set()
            self.entries[0].select_range(0, END)

    def _new_names(self) -> List[str]:
        return [e.get() for e in self.entries]

    def _validate(self) -> Optional[str]:
        """Return an error message, or None when all names are valid."""
        names = self._new_names()
        seen = set()
        error = None
        for entry, name in zip(self.entries, names):
            try:
                clean = _validate_name(name, "New")
            except FileOperationError as exc:
                entry.configure(bootstyle="danger")
                error = str(exc)
                continue
            if clean in seen:
                entry.configure(bootstyle="danger")
                error = f"Duplicate target name: {clean}"
            else:
                seen.add(clean)
                entry.configure(bootstyle="default")
        self.hint_var.set(error or "")
        self.apply_btn.configure(state=DISABLED if error else NORMAL)
        return error

    def _apply(self) -> None:
        if self._validate():
            return
        self.on_apply(self._new_names())
        self.destroy()
