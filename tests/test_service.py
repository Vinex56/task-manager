"""Tests for the application service (use cases)."""

from __future__ import annotations

from datetime import date

import pytest

from task_manager.domain.exceptions import (
    StorageError,
    TaskNotFoundError,
    ValidationError,
)
from task_manager.domain.models import Priority, Task
from task_manager.repositories.base import LoadResult, TaskRepository
from task_manager.repositories.json_repository import JsonTaskRepository
from task_manager.services.task_service import (
    SortField,
    StatusFilter,
    TaskService,
)

TODAY = date(2026, 11, 3)


@pytest.fixture
def repository(tmp_path) -> JsonTaskRepository:
    return JsonTaskRepository(tmp_path / "tasks.json")


@pytest.fixture
def service(repository: JsonTaskRepository) -> TaskService:
    return TaskService(repository)


def add(
    service: TaskService,
    title: str,
    due: date = date(2026, 12, 31),
    priority: Priority = Priority.MEDIUM,
    description: str = "",
    *,
    today: date = TODAY,
) -> Task:
    return service.add_task(
        title=title,
        due_date=due,
        priority=priority,
        description=description,
        today=today,
    )


def test_add_task_stores_all_fields(service: TaskService) -> None:
    task = add(
        service,
        "  Купить молоко  ",
        due=date(2026, 11, 5),
        priority=Priority.HIGH,
        description=" 2.5% ",
    )

    assert task.id == 1
    assert task.title == "Купить молоко"
    assert task.description == "2.5%"
    assert task.due_date == date(2026, 11, 5)
    assert task.priority is Priority.HIGH
    assert task.completed is False
    assert service.tasks == (task,)


def test_add_task_persists_data(
    service: TaskService, repository: JsonTaskRepository
) -> None:
    add(service, "Сохранить меня")

    reloaded = TaskService(repository)
    assert [task.title for task in reloaded.tasks] == ["Сохранить меня"]


def test_add_task_rejects_empty_title(service: TaskService) -> None:
    with pytest.raises(ValidationError, match="не может быть пустым"):
        add(service, "   ")
    assert service.tasks == ()


def test_add_task_rejects_past_due_date(service: TaskService) -> None:
    with pytest.raises(ValidationError, match="не может быть в прошлом"):
        add(service, "Вчера", due=date(2026, 11, 2))
    assert service.tasks == ()


def test_add_task_rejects_invalid_types(service: TaskService) -> None:
    with pytest.raises(ValidationError, match="срок"):
        service.add_task(
            title="Задача",
            due_date="31.12.2026",  # type: ignore[arg-type]
            priority=Priority.LOW,
        )
    with pytest.raises(ValidationError, match="приоритет"):
        service.add_task(
            title="Задача",
            due_date=date(2026, 12, 31),
            priority="high",  # type: ignore[arg-type]
        )


def test_ids_are_unique_after_deletion(service: TaskService) -> None:
    first = add(service, "Первая")
    second = add(service, "Вторая")
    service.delete_task(second.id)
    third = add(service, "Третья")

    assert second.id == 2
    assert third.id not in {first.id}
    assert {task.id for task in service.tasks} == {first.id, third.id}


def test_complete_task_marks_and_persists(
    service: TaskService, repository: JsonTaskRepository
) -> None:
    task = add(service, "Сделать")

    completed = service.complete_task(task.id)

    assert completed.completed is True
    assert service.get(task.id).completed is True
    assert TaskService(repository).get(task.id).completed is True


def test_complete_task_twice_is_rejected(service: TaskService) -> None:
    task = add(service, "Сделать")
    service.complete_task(task.id)

    with pytest.raises(ValidationError, match="уже выполнена"):
        service.complete_task(task.id)


def test_complete_unknown_task_is_rejected(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.complete_task(999)


def test_delete_task_removes_and_persists(
    service: TaskService, repository: JsonTaskRepository
) -> None:
    task = add(service, "Удалить меня")

    deleted = service.delete_task(task.id)

    assert deleted.id == task.id
    assert service.tasks == ()
    assert TaskService(repository).tasks == ()
    with pytest.raises(TaskNotFoundError):
        service.get(task.id)


def test_delete_unknown_task_is_rejected(service: TaskService) -> None:
    with pytest.raises(TaskNotFoundError):
        service.delete_task(42)


def test_list_tasks_filters_by_status(service: TaskService) -> None:
    active = add(service, "Активная")
    completed = add(service, "Выполненная")
    service.complete_task(completed.id)

    all_ids = {task.id for task in service.list_tasks(StatusFilter.ALL)}
    active_ids = {task.id for task in service.list_tasks(StatusFilter.ACTIVE)}
    completed_ids = {
        task.id for task in service.list_tasks(StatusFilter.COMPLETED)
    }

    assert all_ids == {active.id, completed.id}
    assert active_ids == {active.id}
    assert completed_ids == {completed.id}


def test_sort_by_due_date_puts_nearest_first(service: TaskService) -> None:
    add(service, "Поздняя", due=date(2027, 1, 10), priority=Priority.LOW)
    add(service, "Срочная", due=date(2026, 11, 5), priority=Priority.HIGH)
    add(service, "Средняя", due=date(2026, 12, 1))

    titles = [
        task.title for task in service.list_tasks(sort_by=SortField.DUE_DATE)
    ]
    assert titles == ["Срочная", "Средняя", "Поздняя"]


def test_sort_by_priority_puts_high_first(service: TaskService) -> None:
    add(service, "Низкая", due=date(2026, 11, 4), priority=Priority.LOW)
    add(service, "Высокая", due=date(2027, 1, 10), priority=Priority.HIGH)
    add(service, "Средняя", due=date(2026, 12, 1))

    titles = [
        task.title for task in service.list_tasks(sort_by=SortField.PRIORITY)
    ]
    assert titles == ["Высокая", "Средняя", "Низкая"]


def test_sort_by_status_puts_active_first(service: TaskService) -> None:
    completed = add(service, "Выполненная", priority=Priority.HIGH)
    add(service, "Активная низкая", priority=Priority.LOW)
    add(service, "Активная высокая", priority=Priority.HIGH)
    service.complete_task(completed.id)

    tasks = service.list_tasks(sort_by=SortField.STATUS)

    assert [task.completed for task in tasks] == [False, False, True]
    assert tasks[-1].title == "Выполненная"


def test_search_matches_title_and_description(service: TaskService) -> None:
    add(service, "Купить молоко", description="В магазине")
    add(service, "Позвонить маме", description="Купить билеты")

    by_title = service.search("МОЛОКО")
    by_description = service.search("билет")

    assert [task.title for task in by_title] == ["Купить молоко"]
    assert [task.title for task in by_description] == ["Позвонить маме"]
    assert service.search("   ") == []


def test_stats_counts_active_completed_and_overdue(
    service: TaskService,
) -> None:
    add(
        service, "Просроченная", due=date(2026, 11, 1), today=date(2026, 11, 1)
    )
    completed = add(
        service,
        "Выполненная",
        due=date(2026, 11, 2),
        today=date(2026, 11, 2),
    )
    service.complete_task(completed.id)
    add(service, "Будущая", due=date(2026, 12, 1))

    stats = service.stats(today=TODAY)

    assert stats == {
        "total": 3,
        "active": 2,
        "completed": 1,
        "overdue": 1,
    }


def test_load_warnings_are_exposed(tmp_path) -> None:
    path = tmp_path / "tasks.json"
    path.write_text("{broken", encoding="utf-8")
    service = TaskService(JsonTaskRepository(path))

    assert service.tasks == ()
    assert service.load_warnings
    assert "повреждён" in service.load_warnings[0]


class FailingRepository(TaskRepository):
    """Fake repository whose save can be switched to fail."""

    def __init__(self) -> None:
        self.saved: list[Task] = []
        self.fail = False

    def load(self) -> LoadResult:
        return LoadResult()

    def save(self, tasks) -> None:
        if self.fail:
            raise StorageError("диск недоступен")
        self.saved = list(tasks)


def test_failed_save_does_not_change_memory_state() -> None:
    repository = FailingRepository()
    service = TaskService(repository)
    task = add(service, "Первая")

    repository.fail = True
    with pytest.raises(StorageError):
        add(service, "Вторая")

    assert service.tasks == (task,)
    assert repository.saved == [task]
