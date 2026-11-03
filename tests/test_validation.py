"""Tests for input validation and parsing."""

from __future__ import annotations

from datetime import date

import pytest

from task_manager.domain.exceptions import ValidationError
from task_manager.domain.models import Priority
from task_manager.domain.validation import (
    MAX_DESCRIPTION_LENGTH,
    MAX_TITLE_LENGTH,
    parse_due_date,
    parse_priority,
    validate_description,
    validate_title,
)

TODAY = date(2026, 11, 3)


def test_validate_title_strips_and_collapses_whitespace() -> None:
    assert validate_title("  Купить   молоко  ") == "Купить молоко"


@pytest.mark.parametrize("value", ["", "   ", "\t\n  "])
def test_validate_title_rejects_empty_values(value: str) -> None:
    with pytest.raises(ValidationError, match="не может быть пустым"):
        validate_title(value)


def test_validate_title_rejects_too_long_value() -> None:
    with pytest.raises(ValidationError, match="слишком длинное"):
        validate_title("я" * (MAX_TITLE_LENGTH + 1))


def test_validate_description_allows_empty_value() -> None:
    assert validate_description("   ") == ""
    assert validate_description("  подробности  ") == "подробности"


def test_validate_description_rejects_too_long_value() -> None:
    with pytest.raises(ValidationError, match="слишком длинное"):
        validate_description("я" * (MAX_DESCRIPTION_LENGTH + 1))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("31.12.2026", date(2026, 12, 31)),
        ("03.11.2026", date(2026, 11, 3)),  # today is allowed
        ("01.01.2030", date(2030, 1, 1)),
    ],
)
def test_parse_due_date_accepts_valid_future_dates(
    raw: str, expected: date
) -> None:
    assert parse_due_date(raw, today=TODAY) == expected


def test_parse_due_date_strips_spaces() -> None:
    assert parse_due_date("  31.12.2026  ", today=TODAY) == date(2026, 12, 31)


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "2026-12-31", "31/12/2026", "1.1.2026", "31.13.2026"],
)
def test_parse_due_date_rejects_wrong_format(raw: str) -> None:
    with pytest.raises(ValidationError):
        parse_due_date(raw, today=TODAY)


def test_parse_due_date_rejects_nonexistent_date() -> None:
    with pytest.raises(ValidationError, match="не существует"):
        parse_due_date("31.02.2026", today=TODAY)


def test_parse_due_date_rejects_past_date() -> None:
    with pytest.raises(ValidationError, match="не может быть в прошлом"):
        parse_due_date("02.11.2026", today=TODAY)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", Priority.HIGH),
        ("высокий", Priority.HIGH),
        ("ВЫСОКАЯ", Priority.HIGH),
        ("2", Priority.MEDIUM),
        ("средний", Priority.MEDIUM),
        ("3", Priority.LOW),
        ("низкий", Priority.LOW),
        (" низкая ", Priority.LOW),
    ],
)
def test_parse_priority_accepts_numbers_and_names(
    raw: str, expected: Priority
) -> None:
    assert parse_priority(raw) is expected


@pytest.mark.parametrize("raw", ["", "0", "4", "очень высокий"])
def test_parse_priority_rejects_unknown_values(raw: str) -> None:
    with pytest.raises(ValidationError, match="Некорректный приоритет"):
        parse_priority(raw)
