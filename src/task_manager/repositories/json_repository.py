"""JSON implementation of the task repository.

Error handling in this module (missing file, corrupted JSON, permissions)
was generated with an AI assistant and then reviewed and tested, see
``docs/ai_usage.md``.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from task_manager.domain.exceptions import StorageError
from task_manager.domain.models import Task
from task_manager.repositories.base import LoadResult, TaskRepository

SCHEMA_VERSION = 1


class JsonTaskRepository(TaskRepository):
    """Store tasks in a human-readable JSON document.

    The file is written atomically: data goes to a temporary file first and
    only then replaces the real one.  A crash in the middle of a write can
    therefore never destroy the previous task list.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        """Return the path of the JSON file."""
        return self._path

    @property
    def location(self) -> str:
        return str(self._path.resolve())

    def load(self) -> LoadResult:
        """Read tasks from disk.

        Missing and empty files are treated as an empty task list.  A
        corrupted file is copied to ``<name>.corrupt-<timestamp>`` and the
        application continues with an empty list, so the user never loses
        the original data and the program never crashes.
        """
        if not self._path.exists():
            return LoadResult()

        try:
            raw = self._path.read_text(encoding="utf-8")
        except PermissionError:
            raise StorageError(
                f"Нет прав на чтение файла «{self._path}». "
                "Проверьте права доступа или укажите другой файл "
                "через --data-file."
            ) from None
        except OSError as exc:
            raise StorageError(
                f"Не удалось прочитать файл «{self._path}»: {exc}."
            ) from exc

        if not raw.strip():
            return LoadResult(
                warnings=[
                    f"Файл «{self._path}» пуст — начинаем "
                    "с пустого списка задач."
                ]
            )

        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            return self._recover_from_corruption(
                f"Файл «{self._path}» повреждён (строка {exc.lineno}, "
                f"колонка {exc.colno}): {exc.msg}."
            )

        records = self._extract_records(document)
        if records is None:
            return self._recover_from_corruption(
                f"Файл «{self._path}» имеет неожиданную структуру: ожидался "
                "объект с полем 'tasks' или список задач."
            )

        tasks: list[Task] = []
        warnings: list[str] = []
        seen_ids: set[int] = set()

        for position, record in enumerate(records, start=1):
            try:
                task = Task.from_dict(record)
            except (ValueError, TypeError) as exc:
                warnings.append(f"Запись №{position} пропущена: {exc}.")
                continue

            if task.id in seen_ids:
                warnings.append(
                    f"Запись №{position} пропущена: "
                    f"повторяющийся id={task.id}."
                )
                continue

            seen_ids.add(task.id)
            tasks.append(task)

        return LoadResult(tasks=tasks, warnings=warnings)

    def save(self, tasks: Sequence[Task]) -> None:
        """Write the complete task list to disk atomically."""
        payload = self._serialise(tasks)
        temporary = self._path.with_name(f"{self._path.name}.tmp")

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, self._path)
        except PermissionError:
            temporary.unlink(missing_ok=True)
            raise StorageError(
                f"Нет прав на запись в файл «{self._path}». "
                "Проверьте права доступа к каталогу."
            ) from None
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError(
                f"Не удалось сохранить задачи в файл «{self._path}»: {exc}."
            ) from exc

    @staticmethod
    def _extract_records(document: Any) -> list[Any] | None:
        """Return the task list from the supported document shapes."""
        if isinstance(document, list):
            # Tolerant mode: a plain JSON array is also accepted.
            return document
        if isinstance(document, dict):
            records = document.get("tasks")
            if isinstance(records, list):
                return records
        return None

    @staticmethod
    def _serialise(tasks: Sequence[Task]) -> str:
        document = {
            "version": SCHEMA_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "tasks": [task.to_dict() for task in tasks],
        }
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    def _recover_from_corruption(self, message: str) -> LoadResult:
        backup = self._backup_corrupted_file()
        warning = f"{message} Список задач будет пустым."
        if backup is not None:
            warning += f" Резервная копия сохранена в «{backup}»."
        else:
            warning += " Создать резервную копию не удалось."

        # Replace the broken file with a valid empty document so that the
        # next launch does not create yet another backup.
        with contextlib.suppress(StorageError):
            self.save([])

        return LoadResult(warnings=[warning])

    def _backup_corrupted_file(self) -> Path | None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        try:
            shutil.copy2(self._path, backup)
        except OSError:
            return None
        return backup
