from __future__ import annotations

from pathlib import Path

from app.tests.helpers import (
    get_test_run_root,
    get_test_system_temp_root,
    make_test_disk_path,
    make_test_temp_dir,
)


def test_make_test_disk_path_uses_test_run_root() -> None:
    path = make_test_disk_path("artifacts", "example.txt")

    assert path.parent.exists()
    assert path.is_relative_to(get_test_run_root())


def test_make_test_temp_dir_creates_directory() -> None:
    path = make_test_temp_dir("helpers")

    assert path.exists()
    assert path.is_dir()
    assert path.is_relative_to(get_test_run_root())


def test_tmp_path_runs_under_custom_temp_root(tmp_path: Path) -> None:
    expected_root = get_test_run_root() / "pytest"

    assert tmp_path.is_relative_to(expected_root)
    assert get_test_system_temp_root().is_relative_to(get_test_run_root())
