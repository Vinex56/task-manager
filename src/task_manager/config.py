"""Application configuration and command-line defaults."""

from __future__ import annotations

import os
from pathlib import Path

try:  # pragma: no cover - depends on the installation method
    from importlib.metadata import PackageNotFoundError, version

    VERSION = version("task-manager")
except PackageNotFoundError:  # pragma: no cover
    VERSION = "0.1.0"

DEFAULT_DATA_FILENAME = "tasks.json"
DATA_FILE_ENV_VAR = "TASK_MANAGER_FILE"


def resolve_data_file(cli_value: str | None = None) -> Path:
    """Resolve the task storage path.

    Priority: explicit command-line argument, ``TASK_MANAGER_FILE``
    environment variable, then ``tasks.json`` in the current directory.
    """
    if cli_value:
        return Path(cli_value).expanduser()
    env_value = os.environ.get(DATA_FILE_ENV_VAR)
    if env_value:
        return Path(env_value).expanduser()
    return Path(DEFAULT_DATA_FILENAME)
