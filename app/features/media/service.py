from __future__ import annotations

import importlib
import inspect
import pkgutil
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from app.features.media import config, handlers
from app.features.media.types import Handler

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from yt_dlp import YoutubeDL


class MediaHandler:
    def __init__(self, downloader: YoutubeDL) -> None:
        self.handler: Handler | None = None
        options = config.args(downloader.params)
        if not options:
            return
        if not (name := options.get("type")):
            msg = "Media options require a type"
            raise ValueError(msg)
        cls = next((cls for cls in self._discover() if cls.name == name), None)
        if cls is None:
            msg = "Unknown media handler type"
            raise ValueError(msg)
        settings, path = config.load(name, options)
        self.handler = cls(downloader, settings, options, path)

    @staticmethod
    def _discover() -> list[type[Handler]]:
        found = []
        names = set()
        for _, name, _ in sorted(pkgutil.iter_modules(handlers.__path__), key=lambda item: item.name):
            if name.startswith("_"):
                continue
            module = importlib.import_module(f"{handlers.__name__}.{name}")
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__ or not issubclass(cls, Handler) or inspect.isabstract(cls):
                    continue
                if cls.name in names:
                    msg = f"Duplicate media handler type: {cls.name}"
                    raise ValueError(msg)
                names.add(cls.name)
                found.append(cls)
        return found

    @contextmanager
    def process(self, info: dict[str, Any]) -> Generator[None]:
        if self.handler is None:
            yield
            return
        with self.handler.process(info):
            yield

    def download(
        self,
        callback: Callable[..., tuple[bool, bool]],
        name: str,
        info: dict[str, Any],
        *,
        subtitle: bool,
        test: bool,
    ) -> tuple[bool, bool]:
        if self.handler is not None:
            return self.handler.download(callback, name, info, subtitle=subtitle, test=test)
        return callback(name, info, subtitle=subtitle, test=test)
