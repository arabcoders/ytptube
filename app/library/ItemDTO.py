from email.utils import formatdate
import json
import time
from dataclasses import dataclass, field
import uuid


@dataclass(kw_only=True)
class ItemDTO:
    _id: int = field(default_factory=lambda: str(uuid.uuid4()), init=False)

    error: str = None
    id: str
    title: str
    url: str
    quality: str
    format: str
    preset: str = "default"
    folder: str
    download_dir: str = None
    temp_dir: str = None
    status: str = None
    ytdlp_cookies: str = None
    ytdlp_config: dict = field(default_factory=dict)
    output_template: str = None
    output_template_chapter: str = None
    timestamp: float = time.time_ns()
    is_live: bool = None
    datetime: str = field(default_factory=lambda: str(formatdate(time.time())))
    live_in: str = None
    file_size: int = None
    options: dict = field(default_factory=dict)

    # yt-dlp injected fields.
    tmpfilename: str = None
    filename: str = None
    total_bytes: int = None
    total_bytes_estimate: int = None
    downloaded_bytes: int = None
    msg: str = None
    percent: int = None
    speed: str = None
    eta: str = None

    def json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
