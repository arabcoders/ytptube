import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web

from .config import Config
from .Emitter import Emitter
from .encoder import Encoder
from .EventsSubscriber import Event, Events, EventsSubscriber
from .Singleton import Singleton

LOG = logging.getLogger("presets")


@dataclass(kw_only=True)
class Preset:
    name: str
    """The name of the preset."""

    format: str
    """The format of the preset."""

    args: dict[str, list[str] | bool] | None = field(default_factory=dict)
    """The arguments of the preset."""

    postprocessors: list | None = field(default_factory=list)
    """The postprocessors of the preset."""

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

    _presets: list[Preset] = []
    """The list of presets."""

    _instance = None
    """The instance of the class."""

    def __init__(
        self,
        file: str | None = None,
        emitter: Emitter | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        config: Config | None = None,
    ):
        Presets._instance = self

        config = config or Config.get_instance()

        self._file: str = file or os.path.join(config.config_path, "presets.json")
        self._loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        self._emitter: Emitter = emitter or Emitter.get_instance()

        if os.path.exists(self._file) and "600" != oct(os.stat(self._file).st_mode)[-3:]:
            try:
                os.chmod(self._file, 0o600)
            except Exception:
                pass

        def handle_event(_, e: Event):
            self.save(**e.data)

        EventsSubscriber.get_instance().subscribe(Events.PRESETS_ADD, f"{__class__}.save", handle_event)

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
        Attach the work to the aiohttp application.

        Args:
            _ (web.Application): The aiohttp application.

        Returns:
            None

        """
        self.load()

    def get_all(self) -> list[Preset]:
        """Return the presets."""
        return self._presets

    def load(self) -> "Presets":
        """
        Load the Presets.

        Returns:
            Presets: The current instance.

        """
        self.clear()

        if not os.path.exists(self._file) or os.path.getsize(self._file) < 10:
            return self

        LOG.info(f"Loading presets from '{self._file}'.")
        try:
            with open(self._file) as f:
                presets = json.load(f)
        except Exception as e:
            LOG.error(f"Failed to parse presets from '{self._file}'. '{e}'.")
            return self

        if not presets or len(presets) < 1:
            LOG.info(f"No presets were defined in '{self._file}'.")
            return self

        for i, preset in enumerate(presets):
            try:
                preset = Preset(**preset)
                self._presets.append(preset)
            except Exception as e:
                LOG.error(f"Failed to parse preset at list position '{i}'. '{e!s}'.")
                continue

        return self

    def clear(self) -> "Presets":
        """
        Clear all presets

        Returns:
            Presets: The current instance.

        """
        if len(self._presets) < 1:
            return self

        self._presets.clear()

        return self

    def validate(self, preset: Preset | dict) -> bool:
        """
        Validate the preset.

        Args:
            preset (Preset|dict): The preset to validate.

        Returns:
            bool: True if the preset is valid, False otherwise.

        """
        if not isinstance(preset, dict):
            if not isinstance(preset, Preset):
                msg = "Invalid preset type."
                raise ValueError(msg)  # noqa: TRY004

            preset = preset.serialize()

        if not preset.get("name"):
            msg = "No name found."
            raise ValueError(msg)

        if not preset.get("format"):
            msg = "No format found."
            raise ValueError(msg)

        if preset.get("args") and not isinstance(preset.get("args"), dict):
            msg = "Invalid args type. expected dict."
            raise ValueError(msg)

        if preset.get("postprocessors") and not isinstance(preset.get("postprocessors"), list):
            msg = "Invalid postprocessors type. expected list."
            raise ValueError(msg)

        return True

    def save(self, presets: list[Preset | dict]) -> "Presets":
        """
        Save the presets.

        Args:
            presets (list[Preset]): The presets to save.

        Returns:
            Presets: The current instance.

        """
        for i, preset in enumerate(presets):
            try:
                if not isinstance(preset, Preset):
                    preset = Preset(**preset)
                    presets[i] = preset
            except Exception as e:
                LOG.error(f"Failed to save preset '{i}' due to parsing error. '{e!s}'.")
                continue

            try:
                self.validate(preset)
            except ValueError as e:
                LOG.error(f"Failed to validate preset '{i}: {preset.name}'. '{e}'.")
                continue

        try:
            with open(self._file, "w") as f:
                json.dump(obj=[preset.serialize() for preset in presets], fp=f, indent=4)

            LOG.info(f"Presets saved to '{self._file}'.")
        except Exception as e:
            LOG.error(f"Failed to save presets to '{self._file}'. '{e!s}'.")

        return self
