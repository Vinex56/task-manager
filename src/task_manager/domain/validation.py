"""Validation and parsing of user input.

This module was drafted with the help of an AI assistant (see
``docs/ai_usage.md``) and then reviewed and covered with tests.  Keeping the
rules here makes them reusable by any future user interface (CLI, web, ...).
"""

from __future__ import annotations

import re
from datetime import date, datetime

from task_manager.domain.exceptions import ValidationError
from task_manager.domain.models import Priority

DATE_FORMAT = "%d.%m.%Y"
DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000

PRIORITY_ALIASES: dict[str, Priority] = {
    "1": Priority.HIGH,
    "высокий": Priority.HIGH,
    "высокая": Priority.HIGH,
    "в": Priority.HIGH,
    "2": Priority.MEDIUM,
    "средний": Priority.MEDIUM,
    "средняя": Priority.MEDIUM,
    "с": Priority.MEDIUM,
    "3": Priority.LOW,
    "низкий": Priority.LOW,
    "низкая": Priority.LOW,
    "н": Priority.LOW,
}


def validate_title(raw_title: str) -> str:
    """Normalise and validate a task title.

    Leading/trailing spaces are removed and inner whitespace runs are
    collapsed.  A title consisting only of whitespace is rejected.
    """
    title = " ".join(raw_title.split())
    if not title:
        raise ValidationError("Название задачи не может быть пустым.")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(
            f"Название слишком длинное: {len(title)} символов "
            f"(максимум {MAX_TITLE_LENGTH})."
        )
    return title


def validate_description(raw_description: str) -> str:
    """Validate and normalise an optional task description."""
    description = raw_description.strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(
            f"Описание слишком длинное: {len(description)} символов "
            f"(максимум {MAX_DESCRIPTION_LENGTH})."
        )
    return description


def parse_due_date(raw_date: str, *, today: date | None = None) -> date:
    """Parse a date in ``ДД.ММ.ГГГГ`` format and reject past dates.

    The current date is allowed.  ``today`` can be injected to make the
    function deterministic in tests.
    """
    text = raw_date.strip()
    if not text:
        raise ValidationError(
            "Срок выполнения не может быть пустым. "
            "Укажите дату в формате ДД.ММ.ГГГГ, например 31.12.2026."
        )
    if not DATE_PATTERN.fullmatch(text):
        raise ValidationError(
            f"Дата «{text}» не соответствует формату ДД.ММ.ГГГГ. "
            "Пример: 31.12.2026."
        )
    try:
        parsed = datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise ValidationError(
            f"Дата «{text}» не существует. Проверьте день и месяц."
        ) from None

    current = today or date.today()
    if parsed < current:
        raise ValidationError(
            "Срок выполнения не может быть в прошлом "
            f"(сегодня {current.strftime(DATE_FORMAT)})."
        )
    return parsed


def parse_priority(raw_priority: str) -> Priority:
    """Parse a priority from its number or Russian name."""
    key = raw_priority.strip().casefold()
    try:
        return PRIORITY_ALIASES[key]
    except KeyError:
        raise ValidationError(
            "Некорректный приоритет. Выберите: "
            "1 — высокий, 2 — средний, 3 — низкий."
        ) from None
