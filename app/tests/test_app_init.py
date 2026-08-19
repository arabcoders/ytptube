import os
import sys
from pathlib import Path

import pytest

from app import _add_package_paths


def test_adds_package_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("YTP_CONFIG_PATH", str(config))
    monkeypatch.setenv("YTP_PYTHON_PATH", os.pathsep.join((str(first), str(second))))
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    user_site = config / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
    assert sys.path == [str(first), str(second), str(user_site), "bundled"]


def test_ignores_missing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    monkeypatch.delenv("YTP_CONFIG_PATH", raising=False)
    monkeypatch.setenv("YTP_PYTHON_PATH", os.pathsep.join((str(tmp_path / "missing"), str(existing))))
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    assert sys.path == [str(existing), "bundled"]


def test_moves_existing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.delenv("YTP_CONFIG_PATH", raising=False)
    monkeypatch.setenv("YTP_PYTHON_PATH", str(external))
    monkeypatch.setattr(sys, "path", ["bundled", str(external)])

    _add_package_paths()

    assert sys.path == [str(external), "bundled"]


def test_ignores_package_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config"
    config.mkdir()
    user_site = config / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
    user_site.write_text("not a directory")
    monkeypatch.setenv("YTP_CONFIG_PATH", str(config))
    monkeypatch.delenv("YTP_PYTHON_PATH", raising=False)
    monkeypatch.setattr(sys, "path", ["bundled"])

    _add_package_paths()

    assert sys.path == ["bundled"]
