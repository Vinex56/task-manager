"""Domain entities and value objects of the task manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class Priority(StrEnum):
    """Task priority.

    The string values are part of the JSON storage format, therefore they
    must stay stable.  Human-readable labels live in :attr:`label`.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def label(self) -> str:
        """Return the Russian label shown in the console interface."""
        return {
            Priority.HIGH: "высокий",
            Priority.MEDIUM: "средний",
            Priority.LOW: "низкий",
        }[self]

    @property
    def rank(self) -> int:
        """Return a numeric weight (higher means more important)."""
        return {
            Priority.HIGH: 3,
            Priority.MEDIUM: 2,
            Priority.LOW: 1,
        }[self]


@dataclass(slots=True)
class Task:
    """A single to-do item."""

    id: int
    title: str
    due_date: date
    priority: Priority
    description: str = ""
    completed: bool = False
    created_at: datetime = field(
        default_factory=lambda: datetime.now().replace(microsecond=0)
    )

    def is_overdue(self, today: date | None = None) -> bool:
        """Return ``True`` when an active task is past its due date."""
        return not self.completed and self.due_date < (today or date.today())

    def to_dict(self) -> dict[str, Any]:
        """Convert the task to a JSON-serialisable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat(),
            "priority": self.priority.value,
            "completed": self.completed,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Task:
        """Build a task from a JSON object.

        Raises:
            ValueError: if the record is malformed.  The repository catches
                this error, reports a warning and skips the broken record.
        """
        if not isinstance(data, dict):
            raise ValueError("запись задачи должна быть JSON-объектом")

        task_id = data.get("id")
        if (
            not isinstance(task_id, int)
            or isinstance(task_id, bool)
            or task_id <= 0
        ):
            raise ValueError(
                "поле 'id' должно быть положительным целым числом"
            )

        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("поле 'title' должно быть непустой строкой")

        description = data.get("description", "")
        if description is None:
            description = ""
        if not isinstance(description, str):
            raise ValueError("поле 'description' должно быть строкой")

        raw_due_date = data.get("due_date")
        if not isinstance(raw_due_date, str):
            raise ValueError("поле 'due_date' должно быть строкой")
        try:
            due_date = date.fromisoformat(raw_due_date)
        except ValueError:
            raise ValueError(
                f"поле 'due_date' содержит некорректную дату: {raw_due_date!r}"
            ) from None

        raw_priority = data.get("priority")
        try:
            priority = Priority(raw_priority)
        except ValueError:
            raise ValueError(
                "поле 'priority' содержит неизвестный приоритет: "
                f"{raw_priority!r}"
            ) from None

        completed = data.get("completed", False)
        if not isinstance(completed, bool):
            raise ValueError("поле 'completed' должно быть true или false")

        raw_created_at = data.get("created_at")
        if isinstance(raw_created_at, str):
            try:
                created_at = datetime.fromisoformat(raw_created_at)
            except ValueError:
                created_at = datetime.now().replace(microsecond=0)
        else:
            created_at = datetime.now().replace(microsecond=0)

        return cls(
            id=task_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            completed=completed,
            created_at=created_at,
        )
