"""Domain and application level exceptions.

All exceptions inherit from :class:`TaskManagerError` so that the
presentation layer can handle them in one place without ever showing a
traceback to the user.
"""

from __future__ import annotations


class TaskManagerError(Exception):
    """Base class for all expected application errors."""


class ValidationError(TaskManagerError):
    """Raised when user input or a domain value is invalid."""


class StorageError(TaskManagerError):
    """Raised when the task storage cannot be read or written."""


class InputError(TaskManagerError):
    """Raised when console input cannot be read or decoded."""


class TaskNotFoundError(TaskManagerError):
    """Raised when a task with the requested identifier does not exist."""
