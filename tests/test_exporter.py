"""Tests for CSV/TXT export and table formatting."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import pytest

from task_manager.domain.exceptions import StorageError
from task_manager.domain.models import Priority, Task
from task_manager.reporting import format_plain_table, summarise
from task_manager.services.exporter import (
    build_text_report,
    export_csv,
    export_txt,
)


def make_task(
    task_id: int = 1,
    title: str = "Задача",
    *,
    description: str = "",
    completed: bool = False,
    priority: Priority = Priority.HIGH,
) -> Task:
    return Task(
        id=task_id,
        title=title,
        description=description,
        due_date=date(2026, 12, 31),
        priority=priority,
        completed=completed,
        created_at=datetime(2026, 11, 3, 10, 0),
    )


def test_export_csv_writes_bom_headers_and_rows(tmp_path: Path) -> None:
    target = tmp_path / "export.csv"
    tasks = [
        make_task(1, "Первая", description="Описание"),
        make_task(2, "Вторая", completed=True, priority=Priority.LOW),
    ]

    exported = export_csv(tasks, target)

    assert exported == target
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM for Excel

    with target.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream, delimiter=";"))

    assert rows[0] == [
        "№",
        "Название",
        "Описание",
        "Срок",
        "Приоритет",
        "Статус",
        "Создана",
    ]
    assert rows[1] == [
        "1",
        "Первая",
        "Описание",
        "31.12.2026",
        "высокий",
        "активна",
        "03.11.2026",
    ]
    assert rows[2][5] == "выполнена"
    assert rows[2][4] == "низкий"


def test_export_txt_contains_table_and_descriptions(tmp_path: Path) -> None:
    target = tmp_path / "export.txt"
    tasks = [
        make_task(1, "Первая", description="Строка один\nСтрока два"),
        make_task(2, "Вторая", completed=True),
    ]

    export_txt(tasks, target)
    content = target.read_text(encoding="utf-8")

    assert "Список задач" in content
    assert "Всего: 2 | активных: 1 | выполненных: 1" in content
    assert "Первая" in content
    assert "Вторая" in content
    assert "Описания:" in content
    assert "Строка один Строка два" in content


def test_build_text_report_handles_empty_list() -> None:
    report = build_text_report([], today=datetime(2026, 11, 3, 12, 30))
    assert "Всего: 0" in report
    assert "Задачи не найдены." in report


def test_export_csv_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_write(self, *args, **kwargs):
        raise PermissionError

    monkeypatch.setattr(Path, "open", deny_write)

    with pytest.raises(StorageError, match="Нет прав на запись"):
        export_csv([make_task()], tmp_path / "export.csv")


def test_export_txt_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_write(self, *args, **kwargs):
        raise PermissionError

    monkeypatch.setattr(Path, "write_text", deny_write)

    with pytest.raises(StorageError, match="Нет прав на запись"):
        export_txt([make_task()], tmp_path / "export.txt")


def test_format_plain_table_is_aligned_and_numbered() -> None:
    tasks = [make_task(1, "Короткая"), make_task(2, "Очень длинная задача")]
    lines = format_plain_table(tasks)

    assert "№" in lines[0]
    assert "Название" in lines[0]
    assert lines[2].startswith("1")
    assert lines[3].startswith("2")
    assert "Очень длинная задача" in lines[3]


def test_format_plain_table_for_empty_list() -> None:
    assert format_plain_table([]) == ["Задачи не найдены."]


def test_summarise_counts_states() -> None:
    tasks = [
        make_task(1, "Просроченная"),
        make_task(2, "Выполненная", completed=True),
    ]
    tasks[0] = Task(
        id=1,
        title="Просроченная",
        due_date=date(2026, 11, 1),
        priority=Priority.HIGH,
    )

    assert summarise(tasks, today=date(2026, 11, 3)) == {
        "total": 2,
        "active": 1,
        "completed": 1,
        "overdue": 1,
    }
