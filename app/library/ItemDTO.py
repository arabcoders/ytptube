import json
import time
import uuid
from dataclasses import dataclass, field
from email.utils import formatdate
from typing import Any


@dataclass(kw_only=True)
class ItemDTO:
    """
    ItemDTO is a data transfer object that represents a single item in the queue.
    It contains all the required information for both the frontend and the backend to process the item.
    """

    _id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)

    error: str | None = None
    id: str
    title: str
    url: str
    quality: str | None = None
    format: str | None = None
    preset: str = "default"
    folder: str
    download_dir: str | None = None
    temp_dir: str | None = None
    status: str | None = None
    cookies: str | None = None
    config: dict = field(default_factory=dict)
    template: str | None = None
    template_chapter: str | None = None
    timestamp: float = time.time_ns()
    is_live: bool | None = None
    datetime: str = field(default_factory=lambda: str(formatdate(time.time())))
    live_in: str | None = None
    file_size: int | None = None
    options: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)

    # yt-dlp injected fields.
    tmpfilename: str | None = None
    filename: str | None = None
    total_bytes: int | None = None
    total_bytes_estimate: int | None = None
    downloaded_bytes: int | None = None
    msg: str | None = None
    percent: int | None = None
    speed: str | None = None
    eta: str | None = None

    # DEPRECATED: These fields are deprecated and will be removed in the future.
    thumbnail: str | None = None
    ytdlp_cookies: str | None = None
    ytdlp_config: dict = field(default_factory=dict)
    output_template: str | None = None
    output_template_chapter: str | None = None

    def serialize(self) -> dict:
        deprecated: tuple = (
            "thumbnail",
            "quality",
            "format",
            "ytdlp_cookies",
            "ytdlp_config",
            "output_template",
            "output_template_chapter",
        )

        if self.thumbnail and "thumbnail" not in self.extras:
            self.extras["thumbnail"] = self.thumbnail

        mapper: dict = {
            "cookies": "ytdlp_cookies",
            "config": "ytdlp_config",
            "template": "output_template",
            "template_chapter": "output_template_chapter",
        }

        for k, v in mapper.items():
            if not self.get(k) and self.get(v):
                self.__dict__[k] = self.get(v)

        dump = self.__dict__.copy()
        for f in deprecated:
            dump.pop(f, None)

        return dump

    def json(self) -> str:
        return json.dumps(self.serialize(), default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)
