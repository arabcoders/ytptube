from __future__ import annotations

import atexit
import contextlib
import shutil
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Iterator

_TEST_RUN_ROOT = Path(gettempdir()) / "ytptube-tests" / uuid4().hex
_TEST_SYSTEM_TEMP_ROOT = _TEST_RUN_ROOT / "tmp"


def _slugify(name: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in name).strip("-") or "tmp"


def get_test_run_root() -> Path:
    return _TEST_RUN_ROOT


def get_test_system_temp_root() -> Path:
    _TEST_SYSTEM_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return _TEST_SYSTEM_TEMP_ROOT


def cleanup_test_run_root() -> None:
    shutil.rmtree(_TEST_RUN_ROOT, ignore_errors=True)


def make_in_memory_db_path(name: str) -> str:
    """Return a unique named in-memory SQLite path for test isolation."""
    slug = _slugify(name)
    return f":memory:{slug}-{uuid4().hex}"


def make_test_disk_path(*parts: str) -> Path:
    """Return a per-run temp path for tests that must write to disk."""
    _TEST_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_RUN_ROOT.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def make_test_temp_dir(name: str) -> Path:
    path = make_test_disk_path(f"{_slugify(name)}-{uuid4().hex}")
    path.mkdir(parents=True, exist_ok=False)
    return path


@contextlib.contextmanager
def temporary_test_dir(name: str) -> Iterator[Path]:
    path = make_test_temp_dir(name)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


atexit.register(cleanup_test_run_root)
