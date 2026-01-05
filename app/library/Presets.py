import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config
from .Events import EventBus, Events
from .Singleton import Singleton
from .Utils import arg_converter, create_cookies_file, init_class

LOG = logging.getLogger("presets")

DEFAULT_PRESETS: list[dict[int, dict[str, str | bool]]] = [
    {
        "id": "3e163c6c-64eb-4448-924f-814b629b3810",
        "name": "default",
        "default": True,
        "cli": "--socket-timeout 30 --download-archive %(archive_file)s",
        "description": "Default preset for yt-dlp. It will download whatever yt-dlp decides is the best quality for the video and audio.",
    },
    {
        "id": "441675ed-b739-40f0-a0b0-1ecfcb9dc48d",
        "name": "Mobile",
        "cli": '--socket-timeout 30 --download-archive %(archive_file)s\n-t mp4 --merge-output-format mp4 --add-chapters --remux-video mp4 \n--embed-metadata --embed-thumbnail \n--postprocessor-args "-movflags +faststart"',
        "default": True,
        "description": "This preset is designed for mobile devices. It will download the best quality video and audio in mp4 format, merge them, and add chapters, metadata, and thumbnail.",
    },
    {
        "id": "441675ed-b739-40f0-a0b0-1ecfcb9dc48b",
        "name": "1080p",
        "cli": "--socket-timeout 30 --download-archive %(archive_file)s\n-S vcodec:h264 --format 'bv[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b[ext=webm]'",
        "default": True,
        "description": "Download the best quality video and audio in mp4 format for 1080p resolution.",
    },
    {
        "id": "9719fcc3-4cf2-4d88-b1e4-74dff3dba00e",
        "name": "720p",
        "cli": "--socket-timeout 30 --download-archive %(archive_file)s\n-S vcodec:h264 --format 'bv[height<=720][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b[ext=webm]'",
        "default": True,
        "description": "Download the best quality video and audio in mp4 format for 720p resolution.",
    },
    {
        "id": "a6fd4b25-2b3e-458d-bb57-b75e41cc4330",
        "name": "Audio Only",
        "cli": "--socket-timeout 30 --download-archive %(archive_file)s\n--extract-audio --add-chapters --embed-metadata --embed-thumbnail --format 'bestaudio/best'",
        "default": True,
        "description": "This preset is designed to download only the audio of the video. It will extract the audio, add chapters, metadata, and thumbnail.",
    },
    {
        "id": "2ade2c28-cad4-4a06-b7eb-2439fdf46f60",
        "name": "Info Reader Plugin",
        "description": 'This preset generate specific filename format and metadata to work with yt-dlp info reader plugins for jellyfin/emby and plex and to make play state sync work for WatchState.\n\nThere is one more step you need to do via Other > Terminal if you have it enabled or directly from container shell\n\nyt-dlp -I0 --write-info-json --write-thumbnail --convert-thumbnails jpg --paths /downloads/youtube -o "%(channel|Unknown_title)s [%(channel_id|Unknown_id)s]/%(title).180B [%(channel_id|Unknown_id)s].%(ext)s" -- https://www.youtube.com/channel/UCClfFsWcT3N2I7VTXXyt84A\n\nChange the url to the channel you want to download.\n\nFor more information please visit \nhttps://github.com/arabcoders/watchstate/blob/master/FAQ.md#how-to-get-watchstate-working-with-youtube-contentlibrary',
        "template": "%(channel)s [%(channel_id|Unknown_id)s]/Season %(release_date>%Y,upload_date>%Y|Unknown)s/%(release_date>%Y%m%d,upload_date>%Y%m%d)s - %(title).180B [%(id)s].%(ext)s",
        "cli": "--socket-timeout 30 --download-archive %(archive_file)s\n--windows-filenames --write-info-json --embed-info-json \n--convert-thumbnails jpg --write-thumbnail --embed-metadata",
        "default": True,
    },
    {
        "id": "2ade2c28-cad4-4a06-b7eb-2439fdf46f61",
        "name": "NFO Maker TV",
        "description": "This preset generate specific filename format and metadata to work with media servers like jellyfin/emby and plex for episodes.",
        "template": "%(channel)s [%(channel_id|Unknown_id)s]/Season %(release_date>%Y,upload_date>%Y|Unknown)s/S%(release_date>%Y,upload_date>%Y)sE%(release_date>%m%d,upload_date>%m%d)s - %(title).100B [%(id)s].%(ext)s",
        "cli": '--socket-timeout 30 --download-archive %(archive_file)s\n--use-postprocessor "NFOMakerPP:when=after_move" \n--windows-filenames --convert-thumbnails jpg --write-thumbnail',
        "default": True,
    },
    {
        "id": "2ade2c28-cad4-4a06-b7eb-2439fdf46f61",
        "name": "NFO Maker Movie",
        "description": "This preset generate specific filename format and metadata to work with media servers like jellyfin/emby and plex for movies.",
        "template": "%(channel)s [%(channel_id|Unknown_id)s]/Season %(release_date>%Y,upload_date>%Y|Unknown)s/S%(release_date>%Y,upload_date>%Y)sE%(release_date>%m%d,upload_date>%m%d)s - %(title).100B [%(id)s].%(ext)s",
        "cli": '--socket-timeout 30 --download-archive %(archive_file)s\n--use-postprocessor "NFOMakerPP:when=after_move;mode=movie" \n--windows-filenames --convert-thumbnails jpg --write-thumbnail',
        "default": True,
    },
]


@dataclass(kw_only=True)
class Preset:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """The id of the preset."""

    name: str
    """The name of the preset."""

    description: str = ""
    """The description of the preset."""

    folder: str = ""
    """The default download folder to use if non is given."""

    template: str = ""
    """The default template to use if non is given."""

    cookies: str = ""
    """The default cookies to use if non is given."""

    cli: str = ""
    """command options for yt-dlp."""

    default: bool = False
    """If True, the preset is a default preset."""

    priority: int = 0
    """Priority of the preset."""

    _cookies_file: Path | None = field(init=False, default=None)
    """The path to the cookies file."""

    def serialize(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def json(self) -> str:
        from .encoder import Encoder

        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def get_cookies_file(self, config: Config | None = None) -> Path | None:
        """
        Get the path to the cookies file.

        Args:
            config (Config|None): The config instance.

        Returns:
            Path|None: The path to the cookies file.

        """
        if self._cookies_file:
            return self._cookies_file

        if not self.cookies or not self.id:
            return None

        if not config:
            config = Config.get_instance()

        self._cookies_file = create_cookies_file(self.cookies, Path(config.config_path) / "cookies" / f"{self.id}.txt")

        return self._cookies_file


class Presets(metaclass=Singleton):
    """
    This class is used to manage the presets.
    """

    def __init__(self, file: str | Path | None = None, config: Config | None = None):
        self._items: list[Preset] = []
        "The list of presets."

        self._config: Config = None
        "The config instance."

        self._default: list[Preset] = []
        "The list of default presets."

        self._config = config or Config.get_instance()

        self._file: Path = Path(file) if file else Path(self._config.config_path).joinpath("presets.json")
        "The path to the presets file."

        if self._file.exists() and "600" != self._file.stat().st_mode:
            try:
                self._file.chmod(0o600)
            except Exception:
                pass

        for i, preset in enumerate(DEFAULT_PRESETS):
            try:
                self.validate(preset)
                self._default.append(init_class(Preset, preset))
            except Exception as e:
                LOG.error(f"Failed to parse default preset ':{i}'. '{e!s}'.")
                continue

    @staticmethod
    def get_instance(file: str | Path | None = None, config: Config | None = None) -> "Presets":
        """
        Get the instance of the class.

        Args:
            file (str|Path|None): The path to the presets file.
            config (Config|None): The config instance.

        Returns:
            Presets: The instance of the class

        """
        return Presets(file=file, config=config)

    async def on_shutdown(self, _: web.Application):
        pass

    def attach(self, _: web.Application):
        """
        Attach the class to the aiohttp application.

        Args:
            _ (web.Application): The aiohttp application.

        Returns:
            None

        """
        self.load()

        if not self.get(self._config.default_preset):
            LOG.error(f"Default preset '{self._config.default_preset}' not found, using 'default' preset.")
            self._config.default_preset = "default"

        async def event_handler(_, __):
            msg = "Not implemented"
            raise Exception(msg)

        EventBus.get_instance().subscribe(Events.PRESETS_ADD, event_handler, f"{__class__.__name__}.add")

    def get_all(self) -> list[Preset]:
        """Return the items."""
        return sorted(self._default + self._items, key=lambda x: x.priority, reverse=True)

    def load(self) -> "Presets":
        """
        Load the items.

        Returns:
            Presets: The current instance.

        """
        has: int = len(self._items)
        self.clear()

        if not self._file.exists() or self._file.stat().st_size < 10:
            return self

        try:
            LOG.info(f"{'Reloading' if has else 'Loading'} '{self._file}'.")
            presets: dict = json.loads(self._file.read_text())
        except Exception as e:
            LOG.error(f"Failed to parse '{self._file}'. '{e}'.")
            return self

        if not presets or len(presets) < 1:
            return self

        need_save = False

        for i, preset in enumerate(presets):
            try:
                if "priority" not in preset:
                    preset["priority"] = 0
                    need_save = True

                if "id" not in preset:
                    preset["id"] = str(uuid.uuid4())
                    need_save = True

                if preset.get("format"):
                    if not preset.get("cli"):
                        preset.update({"cli": f"--format {preset['format']}"})
                    else:
                        preset["cli"] = f"--format '{preset['format']}'\n" + preset["cli"]

                    preset["cli"] = str(preset["cli"]).strip()

                    preset.pop("format")
                    need_save = True

                preset: Preset = init_class(Preset, preset)

                self._items.append(preset)
            except Exception as e:
                LOG.error(f"Failed to parse '{self._file}:{i}'. '{e!s}'.")
                continue

        if need_save:
            LOG.warning("Saving presets due to schema changes.")
            self.save(self._items)

        return self

    def clear(self) -> "Presets":
        """
        Clear all items.

        Returns:
            Presets: The current instance.

        """
        if len(self._items) < 1:
            return self

        self._items.clear()

        return self

    def validate(self, item: Preset | dict) -> bool:
        """
        Validate the item.

        Args:
            item (Preset|dict): The item to validate.

        Returns:
            bool: True if valid

        Raises:
            ValueError: If the item is not valid.

        """
        if not isinstance(item, dict):
            if not isinstance(item, Preset):
                msg = f"Unexpected '{type(item).__name__}' type was given."
                raise ValueError(msg)

            item = item.serialize()

        if not item.get("id"):
            msg = "No id found."
            raise ValueError(msg)

        if not item.get("name"):
            msg = "No name found."
            raise ValueError(msg)

        if item.get("cli"):
            try:
                arg_converter(args=item.get("cli"))
            except Exception as e:
                msg = f"Invalid command options for yt-dlp. '{e!s}'."
                raise ValueError(msg) from e

        if item.get("priority") is not None:
            priority = item.get("priority")
            if not isinstance(priority, int):
                msg = "Priority must be an integer."
                raise ValueError(msg)
            if priority < 0:
                msg = "Priority must be >= 0."
                raise ValueError(msg)

        return True

    def save(self, items: list[Preset | dict]) -> "Presets":
        """
        Save the items.

        Args:
            items (list[Preset]): The items to save.

        Returns:
            Presets: The current instance.

        """
        for i, preset in enumerate(items):
            try:
                if not isinstance(preset, Preset):
                    preset: Preset = init_class(Preset, preset)
                    items[i] = preset
            except Exception as e:
                LOG.error(f"Failed to save item '{i}' due to parsing error. '{e!s}'.")
                continue

            try:
                self.validate(preset)
            except ValueError as e:
                LOG.error(f"Failed to validate item '{i}: {preset.name}'. '{e}'.")
                continue

        try:
            self._file.write_text(
                json.dumps(obj=[preset.serialize() for preset in items if preset.default is False], indent=4)
            )

            LOG.info(f"Saved '{self._file}'.")
        except Exception as e:
            LOG.error(f"Failed to save '{self._file}'. '{e!s}'.")

        return self

    def has(self, id_or_name: str) -> bool:
        """
        Check if the item exists by id or name.

        Args:
            id_or_name (str): The id or name of the item.

        Returns:
            bool: True if exists, False otherwise.

        """
        return self.get(id_or_name) is not None

    def get(self, id_or_name: str) -> Preset | None:
        """
        Get the item by id or name.

        Args:
            id_or_name (str): The id or name of the item.

        Returns:
            Preset|None: The item if found, None otherwise.

        """
        if not id_or_name:
            return None

        for preset in self.get_all():
            if id_or_name not in (preset.id, preset.name):
                continue

            return preset

        return None
