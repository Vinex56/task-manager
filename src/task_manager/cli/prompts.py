"""Reusable console prompts with validation and retry.

The delete-confirmation helper and the retry loops were generated with the
help of an AI assistant and then reviewed and tested, see
``docs/ai_usage.md``.

Input is read from ``sys.stdin.buffer`` when possible.  Reading raw bytes
and decoding a complete line prevents ``UnicodeDecodeError`` crashes when
the terminal encoding does not match Python's locale (a common problem in
IDE consoles and non-UTF-8 terminals).
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping

from task_manager.cli.colors import Palette
from task_manager.domain.exceptions import InputError, ValidationError

YES_ANSWERS = {"да", "д", "yes", "y", "1"}
NO_ANSWERS = {"нет", "н", "no", "n", "0"}

FALLBACK_ENCODINGS = ("utf-8", "cp1251", "koi8-r", "cp866")

ENCODING_HINT = (
    "Не удалось прочитать ввод из-за кодировки терминала. "
    "Настройте локаль UTF-8 (например, export LANG=C.UTF-8 "
    "LC_ALL=C.UTF-8) или запустите программу с PYTHONUTF8=1."
)


def _decode_input(data: bytes) -> str:
    """Decode a raw input line using the terminal encoding and fallbacks."""
    encodings = []
    if sys.stdin.encoding:
        encodings.append(sys.stdin.encoding)
    encodings.extend(FALLBACK_ENCODINGS)

    tried: set[str] = set()
    for encoding in encodings:
        normalized = encoding.lower()
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return data.decode(encoding)
        except UnicodeDecodeError, LookupError:
            continue

    # Last resort: never crash because of one bad byte.
    return data.decode("utf-8", errors="replace")


def _read_line(prompt: str) -> str:
    """Print ``prompt`` and read one line without crashing on bad bytes."""
    print(prompt, end="", flush=True)
    stream = getattr(sys.stdin, "buffer", None)

    if stream is None:
        # stdin was replaced by a text-only stream (tests, IDLE, Jupyter).
        try:
            return input()
        except UnicodeDecodeError as exc:
            raise InputError(ENCODING_HINT) from exc

    try:
        data = stream.readline()
    except (OSError, ValueError) as exc:
        raise InputError(f"Не удалось прочитать ввод: {exc}.") from exc

    if not data:
        raise EOFError

    return _decode_input(data).rstrip("\r\n")


def ask(prompt: str) -> str:
    """Read a trimmed line of input."""
    return _read_line(prompt).strip()


def ask_validated[T](
    prompt: str,
    parser: Callable[[str], T],
    palette: Palette,
) -> T:
    """Ask until ``parser`` accepts the value.

    ``parser`` is expected to raise :class:`ValidationError` for bad input.
    """
    while True:
        raw = ask(prompt)
        try:
            return parser(raw)
        except ValidationError as exc:
            print(palette.red(f"  ✖ {exc}"))


def ask_choice(
    prompt: str,
    options: Mapping[str, str],
    palette: Palette,
    *,
    default: str,
) -> str:
    """Ask the user to pick one of the numbered options."""
    variants = ", ".join(f"{key} — {label}" for key, label in options.items())
    while True:
        raw = ask(f"{prompt} ({variants}) [{default}]: ") or default
        if raw in options:
            return raw
        allowed = ", ".join(options)
        print(palette.red(f"  ✖ Введите одно из значений: {allowed}."))


def ask_index(prompt: str, count: int, palette: Palette) -> int | None:
    """Ask for a 1-based index in ``1..count``; ``0`` cancels."""
    while True:
        raw = ask(prompt)
        if raw in {"", "0"}:
            return None
        if raw.isdigit() and 1 <= int(raw) <= count:
            return int(raw)
        print(
            palette.red(f"  ✖ Введите число от 1 до {count} или 0 для отмены.")
        )


def ask_confirm(
    prompt: str,
    palette: Palette,
    *,
    default: bool = False,
) -> bool:
    """Ask a yes/no question; an empty answer returns ``default``."""
    default_label = "да" if default else "нет"
    while True:
        raw = ask(f"{prompt} [{default_label}]: ").casefold()
        if not raw:
            return default
        if raw in YES_ANSWERS:
            return True
        if raw in NO_ANSWERS:
            return False
        print(palette.red("  ✖ Ответьте «да» или «нет»."))
