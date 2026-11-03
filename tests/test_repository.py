"""Tests for the JSON repository, including error recovery."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from task_manager.domain.exceptions import StorageError
from task_manager.domain.models import Priority, Task
from task_manager.repositories.json_repository import JsonTaskRepository


def make_task(task_id: int = 1, title: str = "Задача") -> Task:
    return Task(
        id=task_id,
        title=title,
        due_date=date(2026, 12, 31),
        priority=Priority.MEDIUM,
    )


@pytest.fixture
def repository(tmp_path: Path) -> JsonTaskRepository:
    return JsonTaskRepository(tmp_path / "tasks.json")


def test_missing_file_returns_empty_result(
    repository: JsonTaskRepository,
) -> None:
    result = repository.load()
    assert result.tasks == []
    assert result.warnings == []


def test_save_and_load_round_trip(repository: JsonTaskRepository) -> None:
    tasks = [make_task(1, "Первая"), make_task(2, "Вторая")]
    repository.save(tasks)

    result = repository.load()
    assert result.tasks == tasks
    assert result.warnings == []
    assert repository.path.exists()


def test_save_creates_missing_parent_directories(tmp_path: Path) -> None:
    repository = JsonTaskRepository(tmp_path / "nested" / "dir" / "tasks.json")
    repository.save([make_task()])
    assert repository.path.exists()


def test_save_is_atomic_and_leaves_no_temporary_file(
    repository: JsonTaskRepository,
) -> None:
    repository.save([make_task()])
    assert not repository.path.with_name("tasks.json.tmp").exists()

    document = json.loads(repository.path.read_text(encoding="utf-8"))
    assert document["version"] == 1
    assert len(document["tasks"]) == 1


def test_empty_file_is_treated_as_empty_list(
    repository: JsonTaskRepository,
) -> None:
    repository.path.write_text("   \n", encoding="utf-8")

    result = repository.load()
    assert result.tasks == []
    assert result.warnings
    assert "пуст" in result.warnings[0]


def test_corrupted_json_is_backed_up_and_ignored(
    repository: JsonTaskRepository,
) -> None:
    repository.path.write_text('{"tasks": [', encoding="utf-8")

    result = repository.load()

    assert result.tasks == []
    assert any("повреждён" in warning for warning in result.warnings)
    backups = list(repository.path.parent.glob("tasks.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == '{"tasks": ['


def test_unexpected_document_structure_is_backed_up(
    repository: JsonTaskRepository,
) -> None:
    repository.path.write_text('{"items": []}', encoding="utf-8")

    result = repository.load()

    assert result.tasks == []
    assert any(
        "неожиданную структуру" in warning for warning in result.warnings
    )


def test_broken_records_are_skipped_with_warnings(
    repository: JsonTaskRepository,
) -> None:
    repository.path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": 1,
                        "title": "Валидная",
                        "due_date": "2026-12-31",
                        "priority": "high",
                    },
                    {"id": 2, "title": "Без даты"},
                    "мусор",
                ]
            }
        ),
        encoding="utf-8",
    )

    result = repository.load()

    assert [task.title for task in result.tasks] == ["Валидная"]
    assert len(result.warnings) == 2


def test_duplicate_ids_are_skipped_with_warning(
    repository: JsonTaskRepository,
) -> None:
    record = {
        "id": 1,
        "title": "Дубль",
        "due_date": "2026-12-31",
        "priority": "low",
    }
    repository.path.write_text(
        json.dumps({"tasks": [record, record]}), encoding="utf-8"
    )

    result = repository.load()

    assert len(result.tasks) == 1
    assert any("повторяющийся id" in warning for warning in result.warnings)


def test_plain_json_array_is_accepted(
    repository: JsonTaskRepository,
) -> None:
    repository.path.write_text(
        json.dumps(
            [
                {
                    "id": 5,
                    "title": "Массив",
                    "due_date": "2026-12-31",
                    "priority": "medium",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = repository.load()
    assert [task.id for task in result.tasks] == [5]


def test_load_permission_error_is_reported(
    repository: JsonTaskRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository.path.write_text("{}", encoding="utf-8")

    def deny_read(self, *args, **kwargs):
        raise PermissionError

    monkeypatch.setattr(Path, "read_text", deny_read)

    with pytest.raises(StorageError, match="Нет прав на чтение"):
        repository.load()


def test_save_permission_error_is_reported(
    repository: JsonTaskRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    def deny_write(self, *args, **kwargs):
        raise PermissionError

    monkeypatch.setattr(Path, "write_text", deny_write)

    with pytest.raises(StorageError, match="Нет прав на запись"):
        repository.save([make_task()])


def test_save_os_error_is_reported(
    repository: JsonTaskRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(*args, **kwargs):
        raise OSError("диск переполнен")

    monkeypatch.setattr(
        "task_manager.repositories.json_repository.os.replace", fail_replace
    )

    with pytest.raises(StorageError, match="Не удалось сохранить"):
        repository.save([make_task()])
