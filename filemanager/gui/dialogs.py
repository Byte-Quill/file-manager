"""Small reusable dialogs shared across the GUI."""

from __future__ import annotations

import tkinter
from typing import Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Dialog


class _StringDialog(Dialog):
    """Modal text-input dialog built on the documented Dialog API."""

    def __init__(self, title: str, prompt: str, initial: str,
                 parent: Optional[tkinter.Misc] = None) -> None:
        super().__init__(parent=parent, title=title)
        self._prompt = prompt
        self._initial = initial
        self.result: Optional[str] = None

    def create_body(self, master: tkinter.Misc) -> None:
        body = ttk.Frame(master, padding=16)
        body.pack(fill=BOTH, expand=YES)
        ttk.Label(body, text=self._prompt).pack(anchor=W, pady=(0, 6))
        self._entry = ttk.Entry(body, width=40)
        self._entry.insert(0, self._initial)
        self._entry.pack(fill=X)
        self._entry.select_range(0, END)
        self._entry.bind("<Return>", lambda _e: self._submit())
        self._initial_focus = self._entry

    def create_buttonbox(self, master: tkinter.Misc) -> None:
        bar = ttk.Frame(master, padding=(16, 0, 16, 12))
        bar.pack(fill=X)
        ttk.Button(bar, text="Cancel", bootstyle="secondary-outline",
                   command=self.close).pack(side=RIGHT, padx=6)
        ttk.Button(bar, text="OK", bootstyle="primary",
                   command=self._submit).pack(side=RIGHT)

    def _submit(self) -> None:
        self.result = self._entry.get()
        self.close()


def ask_string(parent, title: str, prompt: str, initial: str) -> Optional[str]:
    """Show a modal text-input dialog. Returns ``None`` when cancelled."""
    dialog = _StringDialog(title, prompt, initial, parent=parent)
    dialog.show()
    return dialog.result
