from __future__ import annotations

import sys
from contextlib import contextmanager, nullcontext
from importlib.machinery import PathFinder
from pkgutil import ModuleInfo
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import pytest
from yt_dlp import YoutubeDL

from app.features.media import handlers
from app.features.media.service import MediaHandler
from app.features.media.types import Handler
from app.features.ytdlp.ytdlp_opts import ARGSMerger

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path


class FakeHandler(Handler):
    def __init__(self, downloader: YoutubeDL, config: dict[str, Any], options: dict[str, str], path: Path) -> None:
        super().__init__(downloader, config, options, path)
        self.events: list[str] = downloader.params["events"]
        self.events.append(f"{self.name}:init")

    @contextmanager
    def process(self, info: dict[str, Any]) -> Generator[None]:
        self.events.append(f"{self.name}:enter")
        if self.config.get("fail_enter"):
            raise RuntimeError("prepare failed")
        try:
            yield
        finally:
            self.events.append(f"{self.name}:exit")

    def download(
        self,
        callback: Callable[..., tuple[bool, bool]],
        name: str,
        info: dict[str, Any],
        *,
        subtitle: bool,
        test: bool,
    ) -> tuple[bool, bool]:
        self.events.append(f"{self.name}:before")
        try:
            return callback(name, info, subtitle=subtitle, test=test)
        finally:
            self.events.append(f"{self.name}:after")


@pytest.fixture(autouse=True)
def backends(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, type[Handler]]:
    class First(FakeHandler):
        name = "first"

    class Second(FakeHandler):
        name = "second"

    classes: dict[str, type[Handler]] = {"first": First, "second": Second}
    modules = [ModuleInfo(PathFinder, "_private", False)]
    for name, cls in classes.items():
        module = ModuleType(f"{handlers.__name__}.media_test_{name}")
        cls.__module__ = module.__name__
        module.__dict__["Backend"] = cls
        monkeypatch.setitem(sys.modules, module.__name__, module)
        modules.append(ModuleInfo(PathFinder, f"media_test_{name}", False))
    monkeypatch.setattr("app.features.media.service.pkgutil", SimpleNamespace(iter_modules=lambda _path: iter(modules)))
    monkeypatch.setattr("app.features.media.config.Config.get_instance", lambda: Mock(config_path=str(tmp_path)))
    return classes


@pytest.mark.parametrize("name", ["first", "second"])
def test_discovers_configuration(tmp_path: Path, backends: dict[str, type[Handler]], name: str) -> None:
    path = tmp_path / "media.toml"
    path.write_text('[first]\nvalue = "first"\n[second]\nvalue = "second"\n')
    events = []
    options = ARGSMerger().add(f'--extractor-args "media:type={name};config={path}"').as_ytdlp()
    downloader = YoutubeDL(
        {"quiet": True, "events": events, "extractor_args": options["extractor_args"]}, auto_init=False
    )

    media = MediaHandler(downloader)

    handler = media.handler
    assert handler is not None
    assert type(handler) is backends[name]
    assert handler.downloader is downloader
    assert handler.config == {"value": name}
    assert handler.options == {"type": name, "config": str(path)}
    assert handler.path == path
    assert events == [f"{name}:init"]


def test_scopes_presets(tmp_path: Path) -> None:
    root = tmp_path
    (root / "media.toml").write_text('[first]\nvalue = "original"\n[second]\nvalue = "shared"\n')
    folder = root / "presets"
    folder.mkdir()
    (folder / "custom.toml").write_text('[first]\nvalue = "preset"\n')
    downloader = YoutubeDL(
        {
            "quiet": True,
            "events": [],
            "extractor_args": {
                "media": {"type": ["first"], "config": ["presets/custom.toml"], "tag": ["override"]},
            },
        },
        auto_init=False,
    )

    selected = MediaHandler(downloader)
    original = MediaHandler(
        YoutubeDL(
            {"quiet": True, "events": [], "extractor_args": {"media": {"type": ["first"], "config": ["media.toml"]}}},
            auto_init=False,
        )
    )

    assert selected.handler is not None
    assert original.handler is not None
    assert selected.handler.config == {"value": "preset"}
    assert selected.handler.options == {"type": "first", "config": "presets/custom.toml", "tag": "override"}
    assert selected.handler.path == folder / "custom.toml"
    assert original.handler.config == {"value": "original"}
    assert original.handler is not selected.handler


@pytest.mark.parametrize("failure", [None, "download", "prepare"])
def test_lifecycle_cleanup(tmp_path: Path, failure: str | None) -> None:
    (tmp_path / "media.toml").write_text("[first]\nfail_enter = " + str(failure == "prepare").lower() + "\n")
    events = []
    media = MediaHandler(
        YoutubeDL(
            {
                "quiet": True,
                "events": events,
                "extractor_args": {"media": {"type": ["first"], "config": ["media.toml"]}},
            },
            auto_init=False,
        )
    )
    events.clear()
    info = {"id": "item"}

    def download(name, data, *, subtitle, test):
        assert name == "output.mp4"
        assert data is info
        assert subtitle is False
        assert test is False
        events.append("download")
        if failure == "download":
            raise RuntimeError("download failed")
        return True, False

    with pytest.raises(RuntimeError, match="failed") if failure else nullcontext():
        with media.process(info):
            assert media.download(download, "output.mp4", info, subtitle=False, test=False) == (True, False)

    if failure == "prepare":
        assert events == ["first:enter"]
    else:
        assert events == [
            "first:enter",
            "first:before",
            "download",
            "first:after",
            "first:exit",
        ]


def test_unconfigured_passthrough() -> None:
    downloader = YoutubeDL({"quiet": True, "events": []}, auto_init=False)
    media = MediaHandler(downloader)
    callback = Mock(return_value=(True, True))
    info = {"id": "item"}

    with media.process(info):
        assert media.download(callback, "output.mp4", info, subtitle=True, test=True) == (True, True)

    assert media.handler is None
    assert downloader.params["events"] == []
    callback.assert_called_once_with("output.mp4", info, subtitle=True, test=True)


def test_duplicate_type(backends: dict[str, type[Handler]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backends["second"], "name", "first")
    downloader = YoutubeDL(
        {"quiet": True, "events": [], "extractor_args": {"media": {"type": ["first"], "config": ["media.toml"]}}},
        auto_init=False,
    )

    with pytest.raises(ValueError, match="Duplicate media handler type: first"):
        MediaHandler(downloader)

    assert downloader.params["events"] == []


def test_ignores_helpers(backends: dict[str, type[Handler]], monkeypatch: pytest.MonkeyPatch) -> None:
    module = sys.modules[backends["first"].__module__]
    monkeypatch.setitem(module.__dict__, "ImportedHandler", backends["second"])

    assert MediaHandler._discover() == [backends["first"], backends["second"]]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"config": ["media.toml"]}, "require a type"),
        ({"type": ["unknown"], "config": ["media.toml"]}, "Unknown media handler type"),
        ({"type": ["first"]}, "require a config file"),
        ({"type": ["first", "second"], "config": ["media.toml"]}, "single non-blank value"),
        ({"type": [" "], "config": ["media.toml"]}, "single non-blank value"),
        ({"type": ["first"], "config": [""]}, "single non-blank value"),
    ],
)
def test_invalid_selection(options: dict[str, list[str]], message: str) -> None:
    downloader = YoutubeDL({"quiet": True, "events": [], "extractor_args": {"media": options}}, auto_init=False)

    with pytest.raises(ValueError, match=message):
        MediaHandler(downloader)

    assert downloader.params["events"] == []
