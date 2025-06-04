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
from .Utils import arg_converter

LOG = logging.getLogger("presets")


@dataclass(kw_only=True)
class Condition:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """The id of the condition."""

    name: str
    """The name of the condition."""

    filter: str
    """The filter to run on info dict."""

    cli: str
    """If matched append this to the download request and re-queue."""

    def serialize(self) -> dict:
        return self.__dict__

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


class Conditions(metaclass=Singleton):
    """
    This class is used to manage the download conditions.
    """

    _items: list[Condition] = []
    """The list of items."""

    _instance = None
    """The instance of the class."""

    def __init__(self, file: str | None = None, config: Config | None = None):
        Conditions._instance = self

        config = config or Config.get_instance()

        self._file: str = file or os.path.join(config.config_path, "conditions.json")

        if os.path.exists(self._file) and "600" != oct(os.stat(self._file).st_mode)[-3:]:
            try:
                os.chmod(self._file, 0o600)
            except Exception:
                pass

        def event_handler(_, __):
            msg = "Not implemented"
            raise Exception(msg)

        EventBus.get_instance().subscribe(Events.CONDITIONS_ADD, event_handler, f"{__class__.__name__}.add")

    @staticmethod
    def get_instance() -> "Conditions":
        """
        Get the instance of the class.

        Returns:
            Conditions: The instance of the class

        """
        if not Conditions._instance:
            Conditions._instance = Conditions()

        return Conditions._instance

    async def on_shutdown(self, _: web.Application):
        pass

    def attach(self, _: web.Application):
        """
        Attach the work to the aiohttp application.

        Args:
            _ (web.Application): The aiohttp application.

        Returns:
            None

        """
        self.load()

    def get_all(self) -> list[Condition]:
        """Return the items."""
        return self._items

    def load(self) -> "Conditions":
        """
        Load the items.

        Returns:
            Conditions: The current instance.

        """
        self.clear()

        if not os.path.exists(self._file) or os.path.getsize(self._file) < 10:
            return self

        LOG.info(f"Loading '{self._file}'.")
        try:
            with open(self._file) as f:
                items = json.load(f)
        except Exception as e:
            LOG.error(f"Failed to parse '{self._file}'. '{e}'.")
            return self

        if not items or len(items) < 1:
            LOG.debug(f"No items were found in '{self._file}'.")
            return self

        need_save = False

        for i, item in enumerate(items):
            try:
                if "id" not in item:
                    item["id"] = str(uuid.uuid4())
                    need_save = True

                item = Condition(**item)

                self._items.append(item)
            except Exception as e:
                LOG.error(f"Failed to parse failure condition at list position '{i}'. '{e!s}'.")
                continue

        if need_save:
            LOG.info("Saving failure conditions due to format, or id change.")
            self.save(self._items)

        return self

    def clear(self) -> "Conditions":
        """
        Clear all items

        Returns:
            conditions: The current instance.

        """
        if len(self._items) < 1:
            return self

        self._items.clear()

        return self

    def validate(self, item: Condition | dict) -> bool:
        """
        Validate item.

        Args:
            item (Condition|dict): The item to validate.

        Returns:
            bool: True if valid, False otherwise.

        """
        from yt_dlp.utils import match_str

        if not isinstance(item, dict):
            if not isinstance(item, Condition):
                msg = f"Unexpected '{type(item).__name__}' item type."
                raise ValueError(msg)  # noqa: TRY004

            item = item.serialize()

        if not item.get("id"):
            msg = "No id found."
            raise ValueError(msg)

        if not item.get("name"):
            msg = "No name found."
            raise ValueError(msg)

        if not item.get("filter"):
            msg = "No filter found."
            raise ValueError(msg)

        try:
            match_str(item.get("filter"), {})
        except Exception as e:
            msg = f"Invalid filter. '{e!s}'."
            raise ValueError(msg) from e

        if not item.get("cli"):
            msg = "No command options for yt-dlp were found."
            raise ValueError(msg)

        try:
            arg_converter(args=item.get("cli"))
        except Exception as e:
            msg = f"Invalid command options for yt-dlp. '{e!s}'."
            raise ValueError(msg) from e

        return True

    def save(self, items: list[Condition | dict]) -> "Conditions":
        """
        Save the items.

        Args:
            items (list[Condition]): The items to save.

        Returns:
            Conditions: The current instance.

        """
        for i, item in enumerate(items):
            try:
                if not isinstance(item, Condition):
                    item = Condition(**item)
                    items[i] = item
            except Exception as e:
                LOG.error(f"Failed to save '{i}' due to parsing error. '{e!s}'.")
                continue

            try:
                self.validate(item)
            except ValueError as e:
                LOG.error(f"Failed to validate '{i}: {item.name}'. '{e!s}'.")
                continue

        try:
            with open(self._file, "w") as f:
                json.dump(obj=[item.serialize() for item in items], fp=f, indent=4)

            LOG.info(f"Updated '{self._file}'.")
        except Exception as e:
            LOG.error(f"Failed to save '{self._file}'. '{e!s}'.")

        return self

    def has(self, id_or_name: str) -> bool:
        """
        Check if the item exists by id or name.

        Args:
            id_or_name (str): The id or name of the preset.

        Returns:
            bool: True if the item exists, False otherwise.

        """
        return self.get(id_or_name) is not None

    def get(self, id_or_name: str) -> Condition | None:
        """
        Get the item by id or name.

        Args:
            id_or_name (str): The id or name of the preset.

        Returns:
            Condition|None: The item if found, None otherwise.

        """
        if not id_or_name:
            return None

        for condition in self.get_all():
            if id_or_name not in (condition.id, condition.name):
                continue

            return condition

        return None

    def match(self, info: dict) -> Condition | None:
        """
        Check if any condition matches the info dict.

        Args:
            info (dict): The info dict to check.

        Returns:
            Condition|None: The condition if found, None otherwise.

        """
        if len(self._items) < 1 or not info or not isinstance(info, dict) or len(info) < 1:
            return None

        from yt_dlp.utils import match_str

        for item in self.get_all():
            if not item.filter:
                LOG.error(f"Filter is empty for '{item.name}'.")
                continue

            try:
                if match_str(item.filter, info):
                    LOG.debug(f"Matched '{item.name}' with filter '{item.filter}'.")

                    return item
            except Exception as e:
                LOG.error(f"Failed to evaluate '{item.name}'. '{e!s}'.")
                continue

        return None

    def single_match(self, name: str, info: dict) -> Condition | None:
        """
        Check if condition matches the info dict.

        Args:
            name (str): The condition name to check.
            info (dict): The info dict to check.

        Returns:
            Condition|None: The condition if found, None otherwise.

        """
        if len(self._items) < 1 or not info or not isinstance(info, dict) or len(info) < 1:
            return None

        item = self.get(name)
        if not item or not item.filter:
            return None

        from yt_dlp.utils import match_str

        return item if match_str(item.filter, info) else None
