"""Tests for the domain model serialisation."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from task_manager.domain.models import Priority, Task


def make_task(**overrides) -> Task:
    values = {
        "id": 1,
        "title": "Проверить отчёт",
        "description": "До обеда",
        "due_date": date(2026, 12, 31),
        "priority": Priority.HIGH,
        "completed": False,
        "created_at": datetime(2026, 11, 3, 10, 30),
    }
    values.update(overrides)
    return Task(**values)


def test_task_round_trip_keeps_all_fields() -> None:
    task = make_task()
    restored = Task.from_dict(task.to_dict())

    assert restored == task
    assert restored.priority is Priority.HIGH
    assert restored.due_date == date(2026, 12, 31)
    assert restored.completed is False


def test_completed_task_round_trip() -> None:
    task = make_task(completed=True)
    assert Task.from_dict(task.to_dict()).completed is True


def test_from_dict_accepts_plain_array_record_without_optional_fields() -> (
    None
):
    restored = Task.from_dict(
        {
            "id": 7,
            "title": "Без описания",
            "due_date": "2026-01-01",
            "priority": "low",
        }
    )
    assert restored.description == ""
    assert restored.completed is False
    assert restored.priority is Priority.LOW


@pytest.mark.parametrize(
    "payload",
    [
        "not a dict",
        {"id": 0, "title": "x", "due_date": "2026-01-01", "priority": "low"},
        {
            "id": True,
            "title": "x",
            "due_date": "2026-01-01",
            "priority": "low",
        },
        {"id": 1, "title": "   ", "due_date": "2026-01-01", "priority": "low"},
        {"id": 1, "title": "x", "due_date": "31.12.2026", "priority": "low"},
        {
            "id": 1,
            "title": "x",
            "due_date": "2026-01-01",
            "priority": "urgent",
        },
        {
            "id": 1,
            "title": "x",
            "due_date": "2026-01-01",
            "priority": "low",
            "completed": "yes",
        },
    ],
)
def test_from_dict_rejects_malformed_records(payload) -> None:
    with pytest.raises(ValueError):
        Task.from_dict(payload)


def test_is_overdue_only_for_active_tasks() -> None:
    today = date(2026, 11, 3)
    assert make_task(due_date=date(2026, 11, 2)).is_overdue(today) is True
    assert make_task(due_date=date(2026, 11, 3)).is_overdue(today) is False
    assert (
        make_task(due_date=date(2026, 11, 2), completed=True).is_overdue(today)
        is False
    )
