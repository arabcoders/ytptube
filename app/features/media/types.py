from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from pathlib import Path

    from yt_dlp import YoutubeDL


class Handler(ABC):
    name: ClassVar[str]

    def __init__(self, downloader: YoutubeDL, config: dict[str, Any], options: dict[str, str], path: Path) -> None:
        self.downloader = downloader
        self.config = config
        self.options = options
        self.path = path

    @abstractmethod
    def process(self, info: dict[str, Any]) -> AbstractContextManager[None]: ...

    @abstractmethod
    def download(
        self,
        callback: Callable[..., tuple[bool, bool]],
        name: str,
        info: dict[str, Any],
        *,
        subtitle: bool,
        test: bool,
    ) -> tuple[bool, bool]: ...
