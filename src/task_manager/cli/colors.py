"""ANSI colour helpers.

``colorama`` is used to make escape sequences work on Windows.  If the
library is not installed (for example when running the sources directly),
the module falls back to plain text.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

try:  # pragma: no cover - platform dependent
    from colorama import just_fix_windows_console
except ImportError:  # pragma: no cover - fallback for a missing dependency

    def just_fix_windows_console() -> None:
        """No-op fallback when colorama is unavailable."""


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


def supports_colour(stream: TextIO | None = None) -> bool:
    """Return ``True`` when coloured output makes sense for the stream."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    target = stream or sys.stdout
    isatty = getattr(target, "isatty", None)
    return bool(isatty and isatty())


class Palette:
    """Apply ANSI styles only when colours are enabled."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        if enabled:
            just_fix_windows_console()

    def paint(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        return f"{''.join(styles)}{text}{RESET}"

    def bold(self, text: str) -> str:
        return self.paint(text, BOLD)

    def dim(self, text: str) -> str:
        return self.paint(text, DIM)

    def red(self, text: str) -> str:
        return self.paint(text, RED)

    def green(self, text: str) -> str:
        return self.paint(text, GREEN)

    def yellow(self, text: str) -> str:
        return self.paint(text, YELLOW)

    def cyan(self, text: str) -> str:
        return self.paint(text, CYAN)

    def magenta(self, text: str) -> str:
        return self.paint(text, MAGENTA)
