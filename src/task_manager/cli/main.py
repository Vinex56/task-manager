"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from task_manager.cli.app import TaskManagerApp
from task_manager.cli.colors import Palette, supports_colour
from task_manager.config import VERSION, resolve_data_file
from task_manager.domain.exceptions import StorageError
from task_manager.repositories.json_repository import JsonTaskRepository
from task_manager.services.task_service import TaskService


def configure_console() -> None:
    """Make console streams tolerant to the terminal encoding.

    ``errors="replace"`` guarantees that printing a message never crashes
    because of an unsupported character.  Input is additionally read as raw
    bytes in :mod:`task_manager.cli.prompts`, so this is only a safety net.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except OSError, ValueError:
            continue


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="task-manager",
        description="Консольный менеджер задач с сохранением в JSON-файл.",
    )
    parser.add_argument(
        "-f",
        "--data-file",
        metavar="PATH",
        help=(
            "путь к JSON-файлу с задачами "
            "(по умолчанию tasks.json или $TASK_MANAGER_FILE)"
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="отключить цветной вывод",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the application and return a process exit code."""
    configure_console()
    args = build_parser().parse_args(argv)
    palette = Palette(enabled=supports_colour() and not args.no_color)
    repository = JsonTaskRepository(resolve_data_file(args.data_file))

    try:
        service = TaskService(repository)
    except StorageError as exc:
        print(palette.red(f"Ошибка: {exc}"))
        return 1

    return TaskManagerApp(service, palette).run()
