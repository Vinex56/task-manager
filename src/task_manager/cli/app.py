"""Interactive console application (presentation layer)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from task_manager.cli.colors import Palette
from task_manager.cli.prompts import (
    ask,
    ask_choice,
    ask_confirm,
    ask_index,
    ask_validated,
)
from task_manager.cli.render import render_task_table
from task_manager.domain.exceptions import TaskManagerError
from task_manager.domain.validation import (
    parse_due_date,
    parse_priority,
    validate_description,
    validate_title,
)
from task_manager.services.exporter import export_csv, export_txt
from task_manager.services.task_service import (
    SortField,
    StatusFilter,
    TaskService,
)

STATUS_OPTIONS = {
    "1": "все",
    "2": "только активные",
    "3": "только выполненные",
}
STATUS_MAP = {
    "1": StatusFilter.ALL,
    "2": StatusFilter.ACTIVE,
    "3": StatusFilter.COMPLETED,
}

SORT_OPTIONS = {
    "1": "по сроку",
    "2": "по приоритету",
    "3": "по статусу",
}
SORT_MAP = {
    "1": SortField.DUE_DATE,
    "2": SortField.PRIORITY,
    "3": SortField.STATUS,
}

EXPORT_OPTIONS = {"1": "CSV", "2": "TXT"}

MENU_ITEMS = (
    ("1", "Добавить задачу"),
    ("2", "Показать задачи"),
    ("3", "Отметить задачу выполненной"),
    ("4", "Удалить задачу"),
    ("5", "Найти задачи"),
    ("6", "Экспортировать задачи"),
    ("0", "Выход"),
)


class TaskManagerApp:
    """Console menu and user interaction."""

    def __init__(self, service: TaskService, palette: Palette) -> None:
        self._service = service
        self._palette = palette
        self._handlers = {
            "1": self._add_task,
            "2": self._show_tasks,
            "3": self._complete_task,
            "4": self._delete_task,
            "5": self._search_tasks,
            "6": self._export_tasks,
        }

    def run(self) -> int:
        """Run the main menu loop until the user exits."""
        self._print_welcome()

        while True:
            self._print_menu()
            try:
                choice = ask("Выберите пункт: ")
                if choice in {"0", "q", "Q", "exit", "выход", "Выход"}:
                    self._info("До свидания!")
                    return 0

                handler = self._handlers.get(choice)
                if handler is None:
                    self._error(
                        f"Неизвестный пункт меню «{choice}». "
                        "Введите число от 0 до 6."
                    )
                    continue
                handler()
            except TaskManagerError as exc:
                self._error(str(exc))
            except UnicodeError:
                self._error(
                    "Ошибка кодировки консоли. Настройте локаль UTF-8 "
                    "(например, export LANG=C.UTF-8) и перезапустите "
                    "программу."
                )
            except EOFError, KeyboardInterrupt:
                self._print("")
                self._info("Завершение работы.")
                return 0

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------
    def _add_task(self) -> None:
        self._print(self._palette.bold("\nНовая задача"))
        title = ask_validated("Название: ", validate_title, self._palette)
        description = ask_validated(
            "Описание (необязательно): ",
            validate_description,
            self._palette,
        )
        due_date = ask_validated(
            "Срок выполнения (ДД.ММ.ГГГГ): ",
            parse_due_date,
            self._palette,
        )
        priority = ask_validated(
            "Приоритет (1 — высокий, 2 — средний, 3 — низкий) [2]: ",
            lambda raw: parse_priority(raw or "2"),
            self._palette,
        )

        task = self._service.add_task(
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
        )
        self._success(
            f"Задача №{task.id} «{task.title}» добавлена. "
            f"Срок: {task.due_date:%d.%m.%Y}, "
            f"приоритет: {task.priority.label}."
        )

    def _show_tasks(self) -> None:
        status_choice = ask_choice(
            "Что показать", STATUS_OPTIONS, self._palette, default="1"
        )
        sort_choice = ask_choice(
            "Сортировка", SORT_OPTIONS, self._palette, default="1"
        )
        tasks = self._service.list_tasks(
            STATUS_MAP[status_choice], SORT_MAP[sort_choice]
        )
        self._print()
        self._print(
            self._palette.bold(
                f"Задачи ({STATUS_OPTIONS[status_choice]}, "
                f"{SORT_OPTIONS[sort_choice]}):"
            )
        )
        self._print(render_task_table(tasks, self._palette))
        self._print()

    def _complete_task(self) -> None:
        tasks = self._service.list_tasks(
            StatusFilter.ACTIVE, SortField.DUE_DATE
        )
        if not tasks:
            self._info("Активных задач нет — всё выполнено!")
            return

        self._print()
        self._print(self._palette.bold("Активные задачи:"))
        self._print(render_task_table(tasks, self._palette))
        index = ask_index(
            "\nНомер задачи для выполнения (0 — отмена): ",
            len(tasks),
            self._palette,
        )
        if index is None:
            self._info("Отменено.")
            return

        task = tasks[index - 1]
        completed = self._service.complete_task(task.id)
        self._success(f"Задача «{completed.title}» отмечена как выполненная.")

    def _delete_task(self) -> None:
        tasks = self._service.list_tasks(StatusFilter.ALL, SortField.STATUS)
        if not tasks:
            self._info("Список задач пуст — удалять нечего.")
            return

        self._print()
        self._print(self._palette.bold("Все задачи:"))
        self._print(render_task_table(tasks, self._palette))
        index = ask_index(
            "\nНомер задачи для удаления (0 — отмена): ",
            len(tasks),
            self._palette,
        )
        if index is None:
            self._info("Отменено.")
            return

        task = tasks[index - 1]
        if not ask_confirm(
            f"Удалить задачу «{task.title}» безвозвратно?",
            self._palette,
        ):
            self._info("Удаление отменено.")
            return

        self._service.delete_task(task.id)
        self._success(f"Задача «{task.title}» удалена.")

    def _search_tasks(self) -> None:
        keyword = ask("Ключевое слово в названии или описании: ")
        if not keyword:
            self._error("Поисковый запрос не может быть пустым.")
            return

        tasks = self._service.search(keyword)
        self._print()
        self._print(
            self._palette.bold(f"Результаты поиска по запросу «{keyword}»:")
        )
        self._print(render_task_table(tasks, self._palette))
        self._print()

    def _export_tasks(self) -> None:
        tasks = list(self._service.tasks)
        if not tasks:
            self._info("Список задач пуст — экспортировать нечего.")
            return

        format_choice = ask_choice(
            "Формат файла", EXPORT_OPTIONS, self._palette, default="1"
        )
        suffix = ".csv" if format_choice == "1" else ".txt"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"tasks_export_{stamp}{suffix}"
        raw_path = ask(f"Путь к файлу [{default_name}]: ") or default_name

        target = Path(raw_path).expanduser()
        if not target.suffix:
            target = target.with_suffix(suffix)

        exporter = export_csv if format_choice == "1" else export_txt
        exported = exporter(tasks, target)
        self._success(
            f"Экспортировано задач: {len(tasks)}. Файл: {exported.resolve()}."
        )

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------
    def _print_welcome(self) -> None:
        self._print(self._palette.bold("=== Менеджер задач ==="))
        self._print(f"Файл данных: {self._service.location}")
        for warning in self._service.load_warnings:
            self._warn(warning)
        self._print(self._format_stats())
        self._print()

    def _print_menu(self) -> None:
        self._print(self._palette.dim("-" * 46))
        for key, label in MENU_ITEMS:
            self._print(f"  {key}. {label}")
        self._print(self._palette.dim("-" * 46))

    def _format_stats(self) -> str:
        stats = self._service.stats()
        overdue = str(stats["overdue"])
        if stats["overdue"]:
            overdue = self._palette.red(overdue)
        return (
            f"Всего задач: {stats['total']} | "
            f"активных: {stats['active']} | "
            f"выполненных: {stats['completed']} | "
            f"просрочено: {overdue}"
        )

    def _print(self, message: str = "") -> None:
        print(message)

    def _info(self, message: str) -> None:
        self._print(self._palette.cyan(message))

    def _success(self, message: str) -> None:
        self._print(self._palette.green(f"✔ {message}"))

    def _warn(self, message: str) -> None:
        self._print(self._palette.yellow(f"Предупреждение: {message}"))

    def _error(self, message: str) -> None:
        self._print(self._palette.red(f"Ошибка: {message}"))
