"""Export tasks to CSV and plain-text files."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from task_manager.domain.exceptions import StorageError
from task_manager.domain.models import Task
from task_manager.domain.validation import DATE_FORMAT
from task_manager.reporting import format_plain_table, status_label, summarise

CSV_DELIMITER = ";"
CSV_HEADERS = (
    "№",
    "Название",
    "Описание",
    "Срок",
    "Приоритет",
    "Статус",
    "Создана",
)


def export_csv(tasks: Sequence[Task], path: str | Path) -> Path:
    """Write tasks to a CSV file and return its path.

    ``utf-8-sig`` and the semicolon delimiter make the file open correctly
    in Russian versions of Excel.
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=CSV_DELIMITER)
            writer.writerow(CSV_HEADERS)
            for index, task in enumerate(tasks, start=1):
                writer.writerow(
                    [
                        index,
                        task.title,
                        task.description,
                        task.due_date.strftime(DATE_FORMAT),
                        task.priority.label,
                        status_label(task),
                        task.created_at.strftime(DATE_FORMAT),
                    ]
                )
    except PermissionError:
        raise StorageError(
            f"Нет прав на запись в файл «{target}». "
            "Выберите другой путь или проверьте права доступа."
        ) from None
    except OSError as exc:
        raise StorageError(
            f"Не удалось записать CSV-файл «{target}»: {exc}."
        ) from exc
    return target


def export_txt(tasks: Sequence[Task], path: str | Path) -> Path:
    """Write tasks to a human-readable text report."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_text_report(tasks), encoding="utf-8")
    except PermissionError:
        raise StorageError(
            f"Нет прав на запись в файл «{target}». "
            "Выберите другой путь или проверьте права доступа."
        ) from None
    except OSError as exc:
        raise StorageError(
            f"Не удалось записать текстовый файл «{target}»: {exc}."
        ) from exc
    return target


def build_text_report(
    tasks: Sequence[Task],
    *,
    today: datetime | None = None,
) -> str:
    """Build the content of a plain-text export."""
    moment = today or datetime.now()
    counters = summarise(tasks, today=moment.date())
    lines = [
        "Список задач",
        f"Дата экспорта: {moment.strftime('%d.%m.%Y %H:%M')}",
        (
            f"Всего: {counters['total']} | "
            f"активных: {counters['active']} | "
            f"выполненных: {counters['completed']} | "
            f"просрочено: {counters['overdue']}"
        ),
        "",
        *format_plain_table(tasks),
    ]

    described = [
        (index, task)
        for index, task in enumerate(tasks, start=1)
        if task.description
    ]
    if described:
        lines.extend(["", "Описания:"])
        for index, task in described:
            description = " ".join(task.description.splitlines())
            lines.append(f"  №{index}: {description}")

    return "\n".join(lines) + "\n"
