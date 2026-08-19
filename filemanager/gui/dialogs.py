"""Small reusable dialogs shared across the GUI."""

from __future__ import annotations

from typing import Dict, Optional

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Dialog


def ask_string(parent, title: str, prompt: str, initial: str) -> Optional[str]:
    """Show a modal text-input dialog. Returns ``None`` when cancelled."""
    dialog = Dialog(title, parent)
    ttk.Label(dialog, text=prompt, font=("Helvetica", 12)).pack(
        padx=16, pady=(14, 4), anchor=W)
    entry = ttk.Entry(dialog, font=("Helvetica", 12), width=40)
    entry.insert(0, initial)
    entry.pack(padx=16, pady=(0, 10), fill=X)
    entry.select_range(0, END)
    entry.focus_set()

    result: Dict[str, Optional[str]] = {"value": None}

    def ok(_e=None) -> None:
        result["value"] = entry.get()
        dialog.destroy()

    def cancel(_e=None) -> None:
        dialog.destroy()

    entry.bind("<Return>", ok)
    dialog.bind("<Escape>", cancel)
    btns = ttk.Frame(dialog)
    btns.pack(pady=(0, 12))
    ttk.Button(btns, text="Cancel", command=cancel,
               bootstyle="secondary-outline").pack(side=LEFT, padx=6)
    ttk.Button(btns, text="OK", command=ok, bootstyle="primary").pack(side=LEFT, padx=6)
    dialog.wait_window()
    return result["value"]
