"""Custom exceptions for the File Manager core layer."""

from __future__ import annotations


class FileOperationError(Exception):
    """Raised when a file operation fails.

    The GUI layer catches this exception and presents its message to the
    user, so core modules should wrap low-level ``OSError`` s into this
    type with a helpful, multi-line message.
    """
