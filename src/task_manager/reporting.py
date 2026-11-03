"""Formatting helpers shared by the console UI and the file exporters."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from task_manager.domain.models import Task
from task_manager.domain.validation import DATE_FORMAT

TABLE_HEADERS: tuple[str, ...] = (
    "№",
    "Статус",
    "Срок",
    "Приоритет",
    "Название",
)


def status_label(task: Task) -> str:
    """Return the human-readable task status."""
    return "выполнена" if task.completed else "активна"


def task_table_rows(tasks: Sequence[Task]) -> list[tuple[str, ...]]:
    """Build plain-text table rows for the given tasks."""
    return [
        (
            str(index),
            status_label(task),
            task.due_date.strftime(DATE_FORMAT),
            task.priority.label,
            task.title,
        )
        for index, task in enumerate(tasks, start=1)
    ]


def column_widths(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
) -> list[int]:
    """Calculate the width of every table column."""
    all_rows = [headers, *rows]
    return [
        max(len(row[column]) for row in all_rows)
        for column in range(len(headers))
    ]


def format_plain_table(tasks: Sequence[Task]) -> list[str]:
    """Render tasks as a plain table (without colours)."""
    if not tasks:
        return ["Задачи не найдены."]

    rows = task_table_rows(tasks)
    widths = column_widths(TABLE_HEADERS, rows)
    lines = [
        "  ".join(
            header.ljust(width)
            for header, width in zip(TABLE_HEADERS, widths, strict=True)
        )
    ]
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
        lines.append(
            "  ".join(
                cell.ljust(width)
                for cell, width in zip(row, widths, strict=True)
            ).rstrip()
        )
    return lines


def summarise(
    tasks: Sequence[Task], *, today: date | None = None
) -> dict[str, int]:
    """Return counters used in headers and text exports."""
    current = today or date.today()
    active = sum(1 for task in tasks if not task.completed)
    overdue = sum(1 for task in tasks if task.is_overdue(current))
    return {
        "total": len(tasks),
        "active": active,
        "completed": len(tasks) - active,
        "overdue": overdue,
    }
