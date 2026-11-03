"""Repository interfaces (the Repository pattern).

The application service depends on this abstraction instead of a concrete
storage implementation.  Thanks to that the storage can be replaced with a
database or an in-memory fake without touching business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field

from task_manager.domain.models import Task


@dataclass(slots=True)
class LoadResult:
    """Result of loading tasks from a repository.

    ``warnings`` contains non-fatal problems (for example a corrupted file
    that was backed up or a single malformed record that was skipped).
    """

    tasks: list[Task] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TaskRepository(ABC):
    """Abstract storage for tasks."""

    @property
    def location(self) -> str:
        """Human-readable storage location for the UI."""
        return "хранилище в памяти"

    @abstractmethod
    def load(self) -> LoadResult:
        """Load all tasks.

        Implementations must not return ``None`` and should recover from
        corrupted data where possible.
        """

    @abstractmethod
    def save(self, tasks: Sequence[Task]) -> None:
        """Persist the complete task list, replacing the previous state."""
