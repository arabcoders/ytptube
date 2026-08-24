import copy
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import formatdate
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.features.ytdlp.utils import archive_add, archive_delete, archive_read, get_archive_id
from app.features.ytdlp.ytdlp_opts import YTDLPOpts
from app.library.encoder import Encoder
from app.library.logging import get_logger
from app.library.Utils import clean_item, get_file, get_file_sidecar

if TYPE_CHECKING:
    from app.features.downloads.models import DownloadModel
    from app.features.presets.schemas import Preset

LOG = get_logger()


@dataclass(kw_only=True)
class Item:
    url: str
    preset: str = field(default_factory=lambda: Item._default_preset())
    folder: str = ""
    cookies: str = ""
    template: str = ""
    cli: str = ""
    extras: dict = field(default_factory=dict)
    # Prevent condition-triggered retries from being requeued indefinitely.
    requeued: bool = False
    auto_start: bool = True
    # Starts this item even when the scheduler's worker limit is reached.
    force_start: bool = False

    def serialize(self) -> dict:
        return self.__dict__.copy()

    def json(self) -> str:
        return Encoder(sort_keys=True, indent=4).encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def has_extras(self) -> bool:
        return bool(self.extras and len(self.extras) > 0)

    def add_extras(self, key: str, value: Any) -> None:
        if not self.extras:
            self.extras = {}

        self.extras[key] = value

    def has_cli(self) -> bool:
        return bool(self.cli and len(self.cli) > 2)

    @staticmethod
    def _default_preset() -> str:
        from app.library.config import Config

        return Config.get_instance().default_preset

    def new_with(self, **kwargs) -> "Item":
        return Item.format({**self.serialize(), **kwargs})

    @staticmethod
    def format(item: dict) -> "Item":
        url = item.get("url")

        if not url or not isinstance(url, str):
            msg = "url param is required."
            raise ValueError(msg)

        url = url.strip()

        # Accept bare YouTube video IDs as download URLs.
        if len(url) >= 11 and re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
            url = f"https://www.youtube.com/watch?v={url}"

        data: dict[str, Any] = {"url": url}

        preset: str | None = item.get("preset")
        if preset and isinstance(preset, str) and preset != Item._default_preset():
            from app.features.presets.service import Presets

            if not Presets.get_instance().has(preset):
                msg: str = f"Preset '{preset}' does not exist."
                raise ValueError(msg)

            data["preset"] = preset

        folder = item.get("folder")
        if isinstance(folder, str) and folder:
            data["folder"] = folder

        cookies = item.get("cookies")
        if isinstance(cookies, str) and cookies:
            data["cookies"] = cookies

        template = item.get("template")
        if isinstance(template, str) and template:
            data["template"] = template

        if isinstance(item.get("auto_start"), bool):
            data["auto_start"] = item["auto_start"]

        if isinstance(item.get("force_start"), bool):
            data["force_start"] = item["force_start"]

        extras: dict | None = item.get("extras")
        if isinstance(extras, dict) and len(extras) > 0:
            data["extras"] = extras

        requeued = item.get("requeued")
        if isinstance(requeued, bool):
            data["requeued"] = requeued

        cli: str | None = item.get("cli")
        if cli and len(cli) > 2:
            try:
                from app.features.ytdlp.utils import arg_converter

                arg_converter(args=cli, level=True)
                data["cli"] = cli
            except Exception as e:
                msg = f"Failed to parse command options for yt-dlp. {e!s}"
                raise ValueError(msg) from e

        return Item(**data)

    def get_preset(self) -> "Preset | None":
        from app.features.presets.service import Presets

        return Presets.get_instance().get(self.preset or self._default_preset())

    def get_archive_id(self) -> str | None:
        return get_archive_id(self.url).get("archive_id") if self.url else None

    def get_extractor(self) -> str | None:
        return get_archive_id(self.url).get("ie_key") if self.url else None

    def get_ytdlp_opts(self) -> YTDLPOpts:
        params: YTDLPOpts = YTDLPOpts.get_instance()

        if self.preset:
            params = params.preset(name=self.preset)

        if self.cli:
            params = params.add_cli(self.cli, from_user=True)

        return params

    def get_archive_file(self) -> str | None:
        return self.get_ytdlp_opts().get_all().get("download_archive")

    def is_archived(self) -> bool:
        archive_id: str | None = self.get_archive_id()
        archive_file: str | None = self.get_archive_file()
        return len(archive_read(archive_file, [archive_id])) > 0 if archive_file and archive_id else False

    def __repr__(self) -> str:
        from app.library.config import Config
        from app.library.Utils import calc_download_path, strip_newline

        data: dict = {}
        for k, v in self.serialize().items():
            if not v and k not in ("auto_start"):
                continue

            if k == "cli":
                data[k] = strip_newline(v)
            elif k == "extras":
                data[k] = f"{len(v)} items"
            elif k == "cookies":
                data[k] = f"{len(v)}/chars"
            elif k == "folder":
                data[k] = calc_download_path(base_path=Config.get_instance().download_path, folder=v)
            else:
                data[k] = v

        items: str = "".join(f'{k}="{v}", ' for k, v in data.items() if v is not None)
        return f"Item({items.strip(', ')})"


@dataclass(kw_only=True)
class ItemDTO:
    """
    ItemDTO is a data transfer object that represents a single item in the queue.
    It contains all the required information for both the frontend and the backend to process the item.
    """

    _id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
    """ Unique identifier for the item. """
    error: str | None = None
    """ Error message if the item failed. """
    id: str
    """ The ID of the item yt-dlp """
    title: str
    """ The title of the item. """
    description: str = ""
    """ The description of the item. """
    url: str
    """ The URL of the item. """
    preset: str = "default"
    """ The preset to be used for the item. """
    folder: str
    """ The folder to save the item to. """
    download_dir: str | None = None
    """ The full path to the download directory. """
    temp_dir: str | None = None
    """ The full path to the temporary directory. """
    status: str | None = None
    """ The status of the item. """
    cookies: str | None = None
    """ The cookies to be used for the item. """
    template: str | None = None
    """ The output template to be used for the item. """
    template_chapter: str | None = None
    """ The output template for chapters to be used for the item. """
    timestamp: float = field(default_factory=lambda: time.time_ns())
    """ The timestamp of the item. """
    is_live: bool | None = None
    """ If the item is a live stream. """
    datetime: str = field(default_factory=lambda: str(formatdate(time.time())))
    """ The datetime of the item. """
    live_in: str | None = None
    """ The time until the live stream starts. """
    file_size: int | None = None
    """ The file size of the item. """
    options: dict = field(default_factory=dict)
    """ The options used for the item. """
    extras: dict = field(default_factory=dict)
    """ Extra data associated with the item. """
    cli: str = ""
    """ The command options for yt-dlp to be used for this download. """
    auto_start: bool = True
    """ If the item should be started automatically. """

    force_start: bool = False
    """ If the scheduler should bypass worker limits for this item. """

    queue_position: int | None = None
    """ Persisted position used to order queued items. """
    is_archivable: bool | None = None
    """ If the item can be archived. """
    is_archived: bool | None = None
    """ If the item has been archived. """
    archive_id: str | None = None
    """ The archive ID of the item. """
    sidecar: dict = field(default_factory=dict)
    """ Sidecar data associated with the item. """
    download_skipped: bool = False
    """ True when yt-dlp intentionally skips the primary media download. """

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
    postprocessor: str | None = None

    _recomputed: bool = False
    _archive_file: str | None = None

    def serialize(self) -> dict:
        """
        Serialize the item to a dictionary.

        Returns:
            dict: The serialized item.

        """
        if "finished" == self.status and not self._recomputed:
            self.archive_status()

        item, _ = clean_item(self.__dict__.copy(), ItemDTO.removed_fields())
        return item

    def json(self) -> str:
        """
        Convert the item to a JSON string.

        Returns:
            str: The JSON string representation of the item.

        """
        return Encoder(sort_keys=True, indent=4).encode(self.serialize())

    def to_download_model(self, type_value: str) -> "DownloadModel":
        """Convert this in-memory item to its persisted representation."""
        from app.features.downloads.models import DownloadModel

        stored = copy.deepcopy(self)
        stored_data = stored.serialize()
        stored_data.pop("datetime", None)
        if stored.status == "finished":
            stored_data.pop("live_in", None)

        return DownloadModel(
            id=stored._id,
            type=type_value,
            url=stored.url,
            data=json.loads(Encoder(sort_keys=True).encode(stored_data)),
            created_at=datetime.now(UTC).replace(microsecond=0),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def get_id(self) -> str:
        return self._id

    def name(self) -> str:
        """
        Get a short string representation of the item.

        Returns:
            str: A short string representation of the item.

        """
        return f'id="{self.id}", title="{self.title}"'

    def get_file(self, download_path: Path | None = None) -> Path | None:
        """
        Get the file path of the downloaded item.

        Args:
            download_path (Path | None): The base download path. If None, it will be taken from the config.

        Returns:
            Path | None: The file path of the downloaded item, or None if not available.

        """
        if not self.filename:
            return None

        if not download_path:
            from app.library.config import Config

            base_path = Path(Config.get_instance().download_path)
        else:
            base_path = download_path if isinstance(download_path, Path) else Path(download_path)

        filename = base_path

        if self.folder:
            filename: Path = filename / self.folder

        filename = filename / self.filename

        try:
            realFile, status = get_file(download_path=base_path, file=str(filename.relative_to(base_path)))
        except Exception:
            return None

        return Path(realFile) if status in (200, 302) else None

    def get_archive_id(self) -> str | None:
        """
        Get the archive ID for the download URL.

        Returns:
        str | None: The archive ID if available, None otherwise.

        """
        if self.archive_id:
            return self.archive_id

        if not self.url:
            return None

        idDict: dict = get_archive_id(self.url)
        self.archive_id = idDict.get("archive_id")

        return self.archive_id

    def get_extractor(self) -> str | None:
        """
        Get the extractor key for the download URL.

        Returns:
            str | None: The extractor key if available, None otherwise.

        """
        if self.archive_id:
            return self.archive_id.split(" ")[0]

        idDict: dict[str, str | None] = get_archive_id(self.url)
        self.archive_id = idDict.get("archive_id")

        return idDict.get("ie_key") if self.url else None

    def get_ytdlp_opts(self) -> YTDLPOpts:
        params: YTDLPOpts = YTDLPOpts.get_instance()

        if self.preset:
            params = params.preset(name=self.preset)

        if self.cli:
            params = params.add_cli(self.cli, from_user=True)

        return params

    def get_preset(self) -> "Preset | None":
        """
        Get the preset for the item.

        Returns:
            Preset | None: The preset for the item. If not found, None.

        """
        from app.features.presets.service import Presets

        return Presets.get_instance().get(self.preset or "default")

    def archive_status(self, force: bool = False) -> None:
        """
        Recompute the archive status of the item.

        Args:
            force (bool): If True, force recomputation even if already computed.

        """
        if not force and (self._recomputed or not self.archive_id):
            return

        if "finished" == self.status:
            self._recomputed = True

        self.is_archivable = bool(self._archive_file)
        if not self.is_archivable:
            self.is_archived = False
        elif self.archive_id and self._archive_file:
            self.is_archived = len(archive_read(self._archive_file, [self.archive_id])) > 0
        else:
            self.is_archived = False

    def get_archive_file(self) -> str | None:
        """
        Get the archive file path from the yt-dlp options.

        Returns:
            str | None: The archive file path if available, None otherwise.

        """
        if self._archive_file or self._recomputed or not self.archive_id:
            return self._archive_file

        self._archive_file = self.get_ytdlp_opts().get_all().get("download_archive")
        if self._archive_file:
            self._archive_file = self._archive_file.strip()

        return self._archive_file

    def archive_add(self) -> bool:
        """
        Archive the item by adding its archive ID to the download archive file.

        Returns:
            bool: True if the item was archived, False otherwise.

        """
        if self.is_archived or not self.is_archivable or not self.archive_id or not self._archive_file:
            return False

        self.is_archived = archive_add(self._archive_file, [self.archive_id])

        return self.is_archived

    def archive_delete(self) -> bool:
        """
        Remove the item's archive ID from the download archive file.

        Returns:
            bool: True if the item was removed from the archive, False otherwise.

        """
        if not self.is_archivable or not self.is_archived or not self.archive_id or not self._archive_file:
            return False

        archive_delete(self._archive_file, [self.archive_id])
        self.is_archived = False

        return True

    def get_file_sidecar(self) -> dict:
        """
        Get sidecar files associated with the item.

        Returns:
            dict: A dictionary with sidecar files categorized by type.

        """
        if filename := self.get_file():
            self.sidecar = get_file_sidecar(filename)

        return self.sidecar

    @staticmethod
    def removed_fields() -> tuple:
        """
        Fields that once existed but are no longer used.

        Returns:
            tuple: A tuple of field names that are no longer used.

        """
        return (
            "thumbnail",
            "quality",
            "format",
            "ytdlp_cookies",
            "ytdlp_config",
            "output_template",
            "output_template_chapter",
            "config",
            "temp_path",
            "_recomputed",
            "_archive_file",
        )

    def __post_init__(self):
        """
        Post-initialization to compute archive status if applicable.
        """
        self.get_archive_id()
        self.get_archive_file()
        self.archive_status()
