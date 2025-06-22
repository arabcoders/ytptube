import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from email.utils import formatdate
from typing import Any

from app.library.Utils import clean_item

LOG = logging.getLogger("ItemDTO")


@dataclass(kw_only=True)
class Item:
    """
    This class represents a single download request for data transfer purposes.
    """

    url: str
    """The URL of the item to be downloaded."""

    preset: str = field(default_factory=lambda: Item._default_preset())
    """The preset to be used for this download."""

    folder: str = ""
    """The folder to save the download to."""

    cookies: str = ""
    """The cookies to be used for this download."""

    template: str = ""
    """The template to be used for this download."""

    cli: str = ""
    """The command options for yt-dlp to be used for this download."""

    extras: dict = field(default_factory=dict)
    """Extra data to be added to the download."""

    requeued: bool = False
    """If the item has been retried already via conditions."""

    def serialize(self) -> dict:
        return self.__dict__.copy()

    def json(self) -> str:
        return json.dumps(self.serialize(), default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def has_extras(self) -> bool:
        """
        Check if the item has any extras data associated with it.

        Returns:
            bool: True if the item has extras, False otherwise.

        """
        return self.extras and len(self.extras) > 0

    def has_cli(self) -> bool:
        """
        Check if the item has any command options for yt-dlp associated with it.

        Returns:
            bool: True if the item has command options for yt, False otherwise.

        """
        return self.cli and len(self.cli) > 2

    @staticmethod
    def _default_preset() -> str:
        from .config import Config

        return Config.get_instance().default_preset

    def new_with(self, **kwargs) -> "Item":
        """
        Create a new instance of Item with the given parameters.

        Args:
            **kwargs: The parameters to be used for creating the new instance.

        Returns:
            Item: A new instance of Item with the given parameters.

        """
        return Item.format({**self.serialize(), **kwargs})

    def __repr__(self):
        from .config import Config
        from .Utils import calc_download_path, strip_newline

        data = {}
        for k, v in self.serialize().items():
            if not v:
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

        items = "".join(f'{k}="{v}", ' for k, v in data.items() if v)
        return f"Item({items.strip(', ')})"

    @staticmethod
    def format(item: dict) -> "Item":
        """
        Format the item to be added to the download queue.

        Args:
            item (dict): The item to be formatted.

        Raises:
            ValueError: If the url is not provided.
            ValueError: If the command options for yt-cli are invalid.

        Returns:
            Item: The formatted item.

        """
        url: str = item.get("url")

        if not url or not isinstance(url, str):
            msg = "url param is required."
            raise ValueError(msg)

        data = {
            "url": url,
        }

        preset = item.get("preset")
        if preset and isinstance(preset, str) and preset != Item._default_preset():
            from .Presets import Presets

            if not Presets.get_instance().has(preset):
                msg = f"Preset '{preset}' does not exist."
                raise ValueError(msg)

            data["preset"] = preset

        if item.get("folder") and isinstance(item.get("folder"), str):
            data["folder"] = item.get("folder")

        if item.get("cookies") and isinstance(item.get("cookies"), str):
            data["cookies"] = item.get("cookies")

        if item.get("template") and isinstance(item.get("template"), str):
            data["template"] = item.get("template")

        extras = item.get("extras")
        if extras and isinstance(extras, dict) and len(extras) > 0:
            data["extras"] = extras

        if item.get("requeued") and isinstance(item.get("requeued"), bool):
            data["requeued"] = item.get("requeued")

        cli = item.get("cli")
        if cli and len(cli) > 2:
            from .Utils import arg_converter

            try:
                removed_options = []
                arg_converter(args=cli, level=True, removed_options=removed_options)
                if len(removed_options) > 0:
                    LOG.warning("Removed the following options '%s' for '%s'.", ", ".join(removed_options), url)

                data["cli"] = cli
            except Exception as e:
                msg = f"Failed to parse command options for yt-dlp. {e!s}"
                raise ValueError(msg) from e

        return Item(**data)


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
    template: str | None = None
    template_chapter: str | None = None
    timestamp: float = field(default_factory=lambda: time.time_ns())
    is_live: bool | None = None
    datetime: str = field(default_factory=lambda: str(formatdate(time.time())))
    live_in: str | None = None
    file_size: int | None = None
    options: dict = field(default_factory=dict)
    extras: dict = field(default_factory=dict)
    cli: str = ""

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

    def serialize(self) -> dict:
        item, _ = clean_item(self.__dict__.copy(), ItemDTO.removed_fields())
        return item

    def json(self) -> str:
        return json.dumps(self.serialize(), default=lambda o: o.__dict__, sort_keys=True, indent=4)

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def get_id(self) -> str:
        return self._id

    def name(self) -> str:
        return f'id="{self.id}",  title="{self.title}"'

    @staticmethod
    def removed_fields() -> tuple:
        """Fields that once existed but are no longer used."""
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
        )
