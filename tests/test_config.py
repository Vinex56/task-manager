"""Tests for configuration resolution."""

from __future__ import annotations

from pathlib import Path

from task_manager.config import resolve_data_file


def test_explicit_path_has_priority(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TASK_MANAGER_FILE", str(tmp_path / "env.json"))

    resolved = resolve_data_file(str(tmp_path / "cli.json"))

    assert resolved == tmp_path / "cli.json"


def test_environment_variable_is_used(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TASK_MANAGER_FILE", str(tmp_path / "env.json"))

    assert resolve_data_file() == tmp_path / "env.json"


def test_default_file_name(monkeypatch) -> None:
    monkeypatch.delenv("TASK_MANAGER_FILE", raising=False)

    assert resolve_data_file() == Path("tasks.json")


def test_tilde_is_expanded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert resolve_data_file("~/tasks.json") == tmp_path / "tasks.json"
