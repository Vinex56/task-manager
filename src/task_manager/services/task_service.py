"""Application service: task use cases, filtering and sorting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from enum import StrEnum

from task_manager.domain.exceptions import TaskNotFoundError, ValidationError
from task_manager.domain.models import Priority, Task
from task_manager.domain.validation import (
    validate_description,
    validate_title,
)
from task_manager.reporting import summarise
from task_manager.repositories.base import TaskRepository


class StatusFilter(StrEnum):
    """Which tasks to show."""

    ALL = "all"
    ACTIVE = "active"
    COMPLETED = "completed"


class SortField(StrEnum):
    """Available task sort orders."""

    DUE_DATE = "due_date"
    PRIORITY = "priority"
    STATUS = "status"


class TaskService:
    """Coordinates task operations and persistence.

    Every mutating operation saves the whole list *before* committing the
    change in memory.  If saving fails, the in-memory state stays untouched,
    so the user never sees data that was not persisted.
    """

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository
        result = repository.load()
        self._tasks: list[Task] = result.tasks
        self.load_warnings: tuple[str, ...] = tuple(result.warnings)

    @property
    def location(self) -> str:
        """Return the storage location for display in the UI."""
        return self._repository.location

    @property
    def tasks(self) -> tuple[Task, ...]:
        """Return an immutable snapshot of all tasks."""
        return tuple(self._tasks)

    def add_task(
        self,
        *,
        title: str,
        due_date: date,
        priority: Priority,
        description: str = "",
        today: date | None = None,
    ) -> Task:
        """Create a task, persist it and return it.

        ``today`` can be injected to keep the "no past dates" rule
        deterministic in tests.
        """
        if not isinstance(due_date, date):
            raise ValidationError("Некорректный срок выполнения.")
        if not isinstance(priority, Priority):
            raise ValidationError("Некорректный приоритет.")
        if due_date < (today or date.today()):
            raise ValidationError("Срок выполнения не может быть в прошлом.")

        task = Task(
            id=self._next_id(),
            title=validate_title(title),
            description=validate_description(description),
            due_date=due_date,
            priority=priority,
        )
        self._commit([*self._tasks, task])
        return task

    def complete_task(self, task_id: int) -> Task:
        """Mark a task as completed and persist the change."""
        task = self.get(task_id)
        if task.completed:
            raise ValidationError(f"Задача «{task.title}» уже выполнена.")

        updated = replace(task, completed=True)
        self._commit(
            [updated if item.id == task_id else item for item in self._tasks]
        )
        return updated

    def delete_task(self, task_id: int) -> Task:
        """Delete a task and persist the change."""
        task = self.get(task_id)
        self._commit([item for item in self._tasks if item.id != task_id])
        return task

    def get(self, task_id: int) -> Task:
        """Return a task by its identifier."""
        for task in self._tasks:
            if task.id == task_id:
                return task
        raise TaskNotFoundError(f"Задача с номером {task_id} не найдена.")

    def list_tasks(
        self,
        status: StatusFilter = StatusFilter.ALL,
        sort_by: SortField = SortField.DUE_DATE,
    ) -> list[Task]:
        """Return tasks filtered by status and sorted by the given field."""
        filtered = [
            task for task in self._tasks if self._matches(task, status)
        ]
        return sorted(filtered, key=self._sort_key(sort_by))

    def search(
        self,
        keyword: str,
        *,
        sort_by: SortField = SortField.DUE_DATE,
    ) -> list[Task]:
        """Find tasks whose title or description contains ``keyword``."""
        needle = keyword.strip().casefold()
        if not needle:
            return []
        found = [
            task
            for task in self._tasks
            if needle in task.title.casefold()
            or needle in task.description.casefold()
        ]
        return sorted(found, key=self._sort_key(sort_by))

    def stats(self, *, today: date | None = None) -> dict[str, int]:
        """Return task counters (total/active/completed/overdue)."""
        return summarise(self._tasks, today=today)

    def _next_id(self) -> int:
        return max((task.id for task in self._tasks), default=0) + 1

    @staticmethod
    def _matches(task: Task, status: StatusFilter) -> bool:
        match status:
            case StatusFilter.ACTIVE:
                return not task.completed
            case StatusFilter.COMPLETED:
                return task.completed
            case _:
                return True

    @staticmethod
    def _sort_key(sort_by: SortField) -> Callable[[Task], tuple[object, ...]]:
        if sort_by is SortField.PRIORITY:
            # rank 3 (high) must come first, hence the minus sign
            return lambda task: (
                -task.priority.rank,
                task.due_date,
                task.id,
            )
        if sort_by is SortField.STATUS:
            # False (active) sorts before True (completed)
            return lambda task: (
                task.completed,
                -task.priority.rank,
                task.due_date,
                task.id,
            )
        return lambda task: (
            task.due_date,
            -task.priority.rank,
            task.id,
        )

    def _commit(self, tasks: list[Task]) -> None:
        """Persist the new state first, then update memory."""
        self._repository.save(tasks)
        self._tasks = tasks
