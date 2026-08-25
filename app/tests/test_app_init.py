import os
import sys
from pathlib import Path

import pytest

from app import _add_package_paths
from app.tests.helpers import set_test_env


def test_adds_package_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    set_test_env(monkeypatch, {"config_path": config, "python_path": os.pathsep.join((str(first), str(second)))})
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    user_site = config / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
    assert sys.path == [str(first), str(second), str(user_site), "bundled"]


def test_ignores_missing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    set_test_env(monkeypatch, {"python_path": os.pathsep.join((str(tmp_path / "missing"), str(existing)))})
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    assert sys.path == [str(existing), "bundled"]


def test_moves_existing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    external = tmp_path / "external"
    external.mkdir()
    set_test_env(monkeypatch, {"python_path": external})
    monkeypatch.setattr(sys, "path", ["bundled", str(external)])

    _add_package_paths()

    assert sys.path == [str(external), "bundled"]


def test_ignores_package_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config"
    config.mkdir()
    user_site = config / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
    user_site.write_text("not a directory")
    set_test_env(monkeypatch, {"config_path": config})
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    assert sys.path == ["bundled"]
