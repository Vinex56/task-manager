"""Rendering of task tables with optional ANSI colours."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from task_manager.cli.colors import Palette
from task_manager.domain.models import Priority, Task
from task_manager.reporting import (
    TABLE_HEADERS,
    column_widths,
    task_table_rows,
)


def render_task_table(
    tasks: Sequence[Task],
    palette: Palette,
    *,
    today: date | None = None,
) -> str:
    """Render tasks as an aligned, optionally coloured table."""
    current = today or date.today()
    if not tasks:
        return palette.dim("  Задачи не найдены.")

    rows = task_table_rows(tasks)
    widths = column_widths(TABLE_HEADERS, rows)
    lines = [_render_row(TABLE_HEADERS, widths, palette.bold)]
    lines.append("  ".join("-" * width for width in widths))

    for task, row in zip(tasks, rows, strict=True):
        cells = list(row)
        cells[1] = (
            palette.green(cells[1])
            if task.completed
            else palette.cyan(cells[1])
        )
        if task.is_overdue(current):
            cells[2] = palette.red(cells[2])
        elif not task.completed and task.due_date == current:
            cells[2] = palette.yellow(cells[2])
        cells[3] = _colour_priority(task.priority, cells[3], palette)
        if task.completed:
            cells[4] = palette.dim(cells[4])
        lines.append(_render_row(cells, widths, plain=row))

    if any(task.is_overdue(current) for task in tasks):
        lines.append(palette.red("  Красным выделен срок просроченных задач."))
    return "\n".join(lines)


def _render_row(
    cells: Sequence[str],
    widths: Sequence[int],
    style=None,
    *,
    plain: Sequence[str] | None = None,
) -> str:
    """Pad a row using the visible (uncoloured) text width."""
    visible = plain or cells
    padded = [
        cell + " " * (width - len(visible[index]))
        for index, (cell, width) in enumerate(zip(cells, widths, strict=True))
    ]
    line = "  ".join(padded).rstrip()
    return style(line) if style else line


def _colour_priority(
    priority: Priority,
    text: str,
    palette: Palette,
) -> str:
    match priority:
        case Priority.HIGH:
            return palette.red(text)
        case Priority.MEDIUM:
            return palette.yellow(text)
        case _:
            return palette.green(text)
