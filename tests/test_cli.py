"""End-to-end tests of the console application."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from task_manager.cli import prompts
from task_manager.cli.main import main
from task_manager.domain.exceptions import InputError


def feed_input(monkeypatch: pytest.MonkeyPatch, values: list[str]) -> None:
    """Replace the raw line reader with a scripted sequence of answers."""
    iterator = iter(values)

    def fake_read_line(prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration:
            raise AssertionError(
                f"Неожиданный запрос ввода: {prompt!r}"
            ) from None

    monkeypatch.setattr(prompts, "_read_line", fake_read_line)


def read_tasks(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return document["tasks"]


def test_full_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_file = tmp_path / "tasks.json"
    feed_input(
        monkeypatch,
        [
            "1",  # добавить
            "Купить молоко",
            "Молоко 2.5%",
            "31.12.2099",
            "1",  # высокий приоритет
            "2",  # показать
            "1",  # все
            "1",  # по сроку
            "3",  # выполнить
            "1",  # первая задача
            "4",  # удалить
            "1",  # первая задача
            "да",  # подтверждение
            "0",  # выход
        ],
    )

    exit_code = main(["--data-file", str(data_file), "--no-color"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Купить молоко" in output
    assert "высокий" in output
    assert "добавлена" in output
    assert "отмечена как выполненная" in output
    assert "удалена" in output
    assert "До свидания" in output
    assert read_tasks(data_file) == []


def test_invalid_input_is_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_file = tmp_path / "tasks.json"
    feed_input(
        monkeypatch,
        [
            "1",  # добавить
            "   ",  # пустое название -> ошибка
            "Нормальное название",
            "",  # пустое описание допустимо
            "31.12.2099",
            "9",  # неверный приоритет -> ошибка
            "2",  # средний
            "0",  # выход
        ],
    )

    exit_code = main(["--data-file", str(data_file), "--no-color"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Название задачи не может быть пустым" in output
    assert "Некорректный приоритет" in output

    tasks = read_tasks(data_file)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Нормальное название"
    assert tasks[0]["priority"] == "medium"
    assert tasks[0]["completed"] is False


def test_delete_can_be_cancelled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_file = tmp_path / "tasks.json"
    feed_input(
        monkeypatch,
        [
            "1",
            "Не удалять",
            "",
            "31.12.2099",
            "3",
            "4",  # удалить
            "1",
            "нет",  # отмена подтверждения
            "0",
        ],
    )

    main(["--data-file", str(data_file), "--no-color"])

    output = capsys.readouterr().out
    assert "Удаление отменено" in output
    assert len(read_tasks(data_file)) == 1


def test_corrupted_file_is_reported_and_backed_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_file = tmp_path / "tasks.json"
    data_file.write_text("{это не json", encoding="utf-8")
    feed_input(monkeypatch, ["0"])

    exit_code = main(["--data-file", str(data_file), "--no-color"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "повреждён" in output
    assert list(tmp_path.glob("tasks.json.corrupt-*"))
    # The broken file is replaced with a valid empty document.
    assert read_tasks(data_file) == []


def test_eof_finishes_gracefully(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def raise_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr(prompts, "_read_line", raise_eof)

    exit_code = main(
        ["--data-file", str(tmp_path / "tasks.json"), "--no-color"]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Завершение работы" in output


def test_input_error_is_reported_without_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter([InputError("Ошибка кодировки ввода."), "0"])

    def fake_read_line(prompt: str = "") -> str:
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(prompts, "_read_line", fake_read_line)

    exit_code = main(
        ["--data-file", str(tmp_path / "tasks.json"), "--no-color"]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Ошибка кодировки ввода" in output
    assert "До свидания" in output


def test_search_and_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_file = tmp_path / "tasks.json"
    export_file = tmp_path / "report.csv"
    feed_input(
        monkeypatch,
        [
            "1",
            "Найти меня",
            "Описание для поиска",
            "31.12.2099",
            "2",
            "5",  # поиск
            "меня",
            "6",  # экспорт
            "1",  # CSV
            str(export_file),
            "0",
        ],
    )

    main(["--data-file", str(data_file), "--no-color"])

    output = capsys.readouterr().out
    assert "Результаты поиска" in output
    assert "Найти меня" in output
    assert export_file.exists()
    assert "Найти меня" in export_file.read_text(encoding="utf-8-sig")
