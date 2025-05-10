import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from .config import Config
from .encoder import Encoder
from .Events import EventBus, Events
from .Singleton import Singleton
from .Utils import arg_converter, clean_item

LOG = logging.getLogger("presets")


@dataclass(kw_only=True)
class Preset:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """The id of the preset."""

    name: str
    """The name of the preset."""

    folder: str = ""
    """The default download folder to use if non is given."""

    template: str = ""
    """The default template to use if non is given."""

    cookies: str = ""
    """The default cookies to use if non is given."""

    cli: str = ""
    """yt-dlp cli command line arguments."""

    default: bool = False

    def serialize(self) -> dict:
        return self.__dict__

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


class Presets(metaclass=Singleton):
    """
    This class is used to manage the presets.
    """

    _items: list[Preset] = []
    """The list of presets."""

    _instance = None
    """The instance of the class."""

    _default: list[Preset] = []

    def __init__(self, file: str | None = None, config: Config | None = None):
        Presets._instance = self

        config = config or Config.get_instance()

        self._file: str = file or os.path.join(config.config_path, "presets.json")

        if os.path.exists(self._file) and "600" != oct(os.stat(self._file).st_mode)[-3:]:
            try:
                os.chmod(self._file, 0o600)
            except Exception:
                pass

        default_file = os.path.join(os.path.dirname(__file__), "presets.json")
        with open(default_file) as f:
            for i, preset in enumerate(json.load(f)):
                try:
                    self.validate(preset)
                    self._default.append(Preset(**preset))
                except Exception as e:
                    LOG.error(f"Failed to parse '{default_file}:{i}'. '{e!s}'.")
                    continue

        def event_handler(_, __):
            msg = "Not implemented"
            raise Exception(msg)

        EventBus.get_instance().subscribe(Events.PRESETS_ADD, event_handler, f"{__class__.__name__}.add")

    @staticmethod
    def get_instance() -> "Presets":
        """
        Get the instance of the class.

        Returns:
            Presets: The instance of the class

        """
        if not Presets._instance:
            Presets._instance = Presets()

        return Presets._instance

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

    def get_all(self) -> list[Preset]:
        """Return the items."""
        return self._default + self._items

    def load(self) -> "Presets":
        """
        Load the items.

        Returns:
            Presets: The current instance.

        """
        self.clear()

        if not os.path.exists(self._file) or os.path.getsize(self._file) < 10:
            return self

        LOG.info(f"Loading '{self._file}'.")
        try:
            with open(self._file) as f:
                presets = json.load(f)
        except Exception as e:
            LOG.error(f"Failed to parse '{self._file}'. '{e}'.")
            return self

        if not presets or len(presets) < 1:
            return self

        need_save = False

        for i, preset in enumerate(presets):
            try:
                if "id" not in preset:
                    preset["id"] = str(uuid.uuid4())
                    need_save = True

                preset, preset_status = clean_item(preset, keys=("args", "postprocessors"))
                if preset.get("format"):
                    if not preset.get("cli"):
                        preset.update({"cli": f"--format {preset['format']}"})
                    else:
                        preset["cli"] = f"--format '{preset['format']}'\n" + preset["cli"]

                    preset["cli"] = str(preset["cli"]).strip()

                    preset.pop("format")
                    need_save = True

                preset = Preset(**preset)

                if preset_status:
                    need_save = True

                self._items.append(preset)
            except Exception as e:
                LOG.error(f"Failed to parse '{self._file}:{i}'. '{e!s}'.")
                continue

        if need_save:
            LOG.info(f"Saving '{self._file}' due to changes.")
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
                raise ValueError(msg)  # noqa: TRY004

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
                msg = f"Invalid cli options. '{e!s}'."
                raise ValueError(msg) from e

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
                    preset = Preset(**preset)
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
            with open(self._file, "w") as f:
                json.dump(obj=[preset.serialize() for preset in items if preset.default is False], fp=f, indent=4)

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
