"""Tests for robust console input helpers."""

from __future__ import annotations

import sys

import pytest

from task_manager.cli import prompts
from task_manager.domain.exceptions import InputError


class FakeBuffer:
    """Minimal stand-in for ``sys.stdin.buffer``."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def readline(self) -> bytes:
        return self._data


class FakeStdin:
    """Minimal stand-in for ``sys.stdin`` with a binary buffer."""

    encoding = "utf-8"

    def __init__(self, data: bytes) -> None:
        self.buffer = FakeBuffer(data)


class TextOnlyStdin:
    """Stand-in for a stream without a binary buffer."""

    encoding = "utf-8"


def test_decode_input_uses_utf8() -> None:
    assert prompts._decode_input("Тестовая задача\n".encode()) == (
        "Тестовая задача\n"
    )


def test_decode_input_falls_back_to_cp1251(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", TextOnlyStdin())

    decoded = prompts._decode_input("Тестовая задача".encode("cp1251"))

    assert decoded == "Тестовая задача"


def test_decode_input_falls_back_to_koi8r(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", TextOnlyStdin())
    monkeypatch.setattr(prompts, "FALLBACK_ENCODINGS", ("utf-8", "koi8-r"))

    decoded = prompts._decode_input("Задача".encode("koi8-r"))

    assert decoded == "Задача"


def test_decode_input_replaces_undecodable_bytes(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", TextOnlyStdin())
    monkeypatch.setattr(prompts, "FALLBACK_ENCODINGS", ("utf-8",))

    assert prompts._decode_input(b"\xff") == "\ufffd"


def test_read_line_reads_raw_bytes(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", FakeStdin(b"hello\r\n"))

    assert prompts._read_line("> ") == "hello"
    assert "> " in capsys.readouterr().out


def test_read_line_decodes_cp1251(monkeypatch) -> None:
    data = "Купить молоко\n".encode("cp1251")
    monkeypatch.setattr(sys, "stdin", FakeStdin(data))

    assert prompts._read_line("> ") == "Купить молоко"


def test_read_line_raises_eof(monkeypatch) -> None:
    monkeypatch.setattr(sys, "stdin", FakeStdin(b""))

    with pytest.raises(EOFError):
        prompts._read_line("> ")


def test_read_line_reports_os_error(monkeypatch) -> None:
    class BrokenBuffer:
        def readline(self) -> bytes:
            raise OSError("поток закрыт")

    class BrokenStdin:
        encoding = "utf-8"
        buffer = BrokenBuffer()

    monkeypatch.setattr(sys, "stdin", BrokenStdin())

    with pytest.raises(InputError, match="Не удалось прочитать ввод"):
        prompts._read_line("> ")


def test_read_line_wraps_unicode_error_without_buffer(
    monkeypatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", TextOnlyStdin())

    def broken_input(prompt: str = "") -> str:
        raise UnicodeDecodeError("utf-8", b"\xd1", 0, 1, "bad byte")

    monkeypatch.setattr("builtins.input", broken_input)

    with pytest.raises(InputError, match="кодировки терминала"):
        prompts._read_line("> ")
