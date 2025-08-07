import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import Config
from .encoder import Encoder
from .Events import EventBus, Events
from .Singleton import Singleton
from .Utils import init_class

LOG = logging.getLogger("DLFields")


class FieldType(str, Enum):
    STRING = "string"
    TEXT = "text"
    BOOL = "bool"

    @classmethod
    def all(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def from_value(cls, value: str) -> "FieldType":
        """
        Returns the FieldType enum member corresponding to the given value.

        Args:
            value (str): The value to match against the enum members.

        Returns:
            StoreType: The enum member that matches the value.

        Raises:
            ValueError: If the value does not match any member.

        """
        for member in cls:
            if member.value == value:
                return member

        msg = f"Invalid StoreType value: {value}"
        raise ValueError(msg)

    def __str__(self) -> str:
        return self.value


@dataclass(kw_only=True)
class DLField:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """The id of the field."""

    name: str
    """The name of the preset."""

    description: str
    """The description of the preset."""

    field: str
    """The yt-dlp field to use in long format."""

    kind: FieldType = FieldType.TEXT
    """The kind of the field. i.e. string, bool"""

    icon: str = ""
    """The icon of the field, it can be a font-awesome icon"""

    order: int = 0
    """The order of the field, used to sort the fields in the UI."""

    value: str = ""
    """The default value of the field, It's currently unused."""

    extras: dict = field(default_factory=dict)
    """Additional options for the field."""

    def serialize(self) -> dict:
        dct = self.__dict__
        dct["kind"] = str(self.kind)
        dct["extras"] = {k: v for k, v in self.extras.items() if v is not None}
        return dct

    def json(self) -> str:
        return Encoder().encode(self.serialize())

    def get(self, key: str, default: Any = None) -> Any:
        return self.serialize().get(key, default)


class DLFields(metaclass=Singleton):
    """
    This class is used to manage the DLFields.
    """

    _items: list[DLField] = []
    """The list of items."""

    _instance = None
    """The instance of the class."""

    _config: Config = None
    """The config instance."""

    def __init__(self, file: str | Path | None = None, config: Config | None = None):
        DLFields._instance = self

        self._config = config or Config.get_instance()

        self._file: Path = Path(file) if file else Path(self._config.config_path).joinpath("dl_fields.json")

        if self._file.exists() and "600" != self._file.stat().st_mode:
            try:
                self._file.chmod(0o600)
            except Exception:
                pass

        def event_handler(_, __):
            msg = "Not implemented"
            raise Exception(msg)

        EventBus.get_instance().subscribe(Events.DLFIELDS_ADD, event_handler, f"{__class__.__name__}.add")

    @staticmethod
    def get_instance() -> "DLFields":
        """
        Get the instance of the class.

        Returns:
            DLFields: The instance of the class

        """
        if not DLFields._instance:
            DLFields._instance = DLFields()

        return DLFields._instance

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

    def get_all(self) -> list[DLField]:
        """Return the items."""
        return self._items

    def load(self) -> "DLFields":
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
            items: dict = json.loads(self._file.read_text())
        except Exception as e:
            LOG.error(f"Failed to parse '{self._file}'. '{e}'.")
            return self

        if not items or len(items) < 1:
            return self

        need_save = False

        for i, item in enumerate(items):
            try:
                if "id" not in item:
                    item["id"] = str(uuid.uuid4())
                    need_save = True

                item: DLField = init_class(DLField, item)

                self._items.append(item)
            except Exception as e:
                LOG.error(f"Failed to parse '{self._file}:{i}'. '{e!s}'.")
                continue

        if need_save:
            LOG.info(f"Saving '{self._file}'.")
            self.save(self._items)

        return self

    def clear(self) -> "DLFields":
        """
        Clear all items.

        Returns:
            DLFields: The current instance.

        """
        if len(self._items) < 1:
            return self

        self._items.clear()

        return self

    def validate(self, item: DLField | dict) -> bool:
        """
        Validate the item.

        Args:
            item (DLField|dict): The item to validate.

        Returns:
            bool: True if valid

        Raises:
            ValueError: If the item is not valid.

        """
        if not isinstance(item, dict):
            if not isinstance(item, DLField):
                msg = f"Unexpected '{type(item).__name__}' type was given."
                raise ValueError(msg)  # noqa: TRY004

            item = item.serialize()

        for key in ["id", "name", "description", "field", "kind"]:
            if key not in item:
                msg = f"Missing required key '{key}'."
                raise ValueError(msg)

        if item.get("kind") not in FieldType.all():
            msg = f"Invalid field type '{item.get('kind')}'."
            raise ValueError(msg)

        if item.get("extras") and not isinstance(item.get("extras"), dict):
            msg = "Extras must be a dictionary."
            raise ValueError(msg)

        if item.get("value") and not isinstance(item.get("value"), str):
            msg = "Value must be a string."
            raise ValueError(msg)

        if item.get("order") is not None and not isinstance(item.get("order"), int):
            msg = "Order must be an integer."
            raise ValueError(msg)

        if not isinstance(item.get("extras", {}), dict):
            msg = "Extras must be a dictionary."
            raise ValueError(msg)  # noqa: TRY004

        if re.match(r"^--[a-zA-Z0-9\-]+$", item.get("field", "").strip()) is None:
            msg = "Invalid yt-dlp option field it must starts with '--' and contain only alphanumeric characters."
            raise ValueError(msg)

        return True

    def save(self, items: list[DLField | dict]) -> "DLFields":
        """
        Save the items.

        Args:
            items (list[DLField]): The items to save.

        Returns:
            Presets: The current instance.

        """
        for i, item in enumerate(items):
            try:
                if not isinstance(item, DLField):
                    item: DLField = init_class(DLField, item)
                    items[i] = item
            except Exception as e:
                LOG.error(f"Failed to save item '{i}' due to parsing error. '{e!s}'.")
                continue

            try:
                self.validate(item)
            except ValueError as e:
                LOG.error(f"Failed to validate item '{i}: {item.name}'. '{e}'.")
                continue

        try:
            self._file.write_text(json.dumps(obj=[item.serialize() for item in items], indent=4))
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

    def get(self, id_or_name: str) -> DLField | None:
        """
        Get the item by id or name.

        Args:
            id_or_name (str): The id or name of the item.

        Returns:
            Preset|None: The item if found, None otherwise.

        """
        if not id_or_name:
            return None

        for item in self.get_all():
            if id_or_name not in (item.id, item.name):
                continue

            return item

        return None
