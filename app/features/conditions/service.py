from collections.abc import Iterable
from numbers import Number

from aiohttp import web

from app.features.conditions.models import ConditionModel
from app.features.conditions.repository import ConditionsRepository
from app.features.ytdlp.mini_filter import match_str
from app.library.Events import EventBus, Events
from app.library.log import get_logger
from app.library.Singleton import Singleton

LOG = get_logger()


def _ignored_identifiers(ignore_conditions: Iterable[str | Number] | None) -> tuple[set[str], bool]:
    ignored: set[str] = set()
    ignore_all = False

    if not ignore_conditions:
        return ignored, ignore_all

    for value in ignore_conditions:
        if isinstance(value, bool) or not isinstance(value, (str, Number)):
            continue

        identifier = str(value).strip()
        if not identifier:
            continue

        if "*" == identifier:
            ignore_all = True
            continue

        ignored.add(identifier)

    return ignored, ignore_all


class Conditions(metaclass=Singleton):
    def __init__(self):
        self._repo: ConditionsRepository = ConditionsRepository.get_instance()

    @staticmethod
    def get_instance() -> "Conditions":
        return Conditions()

    async def on_shutdown(self, _: web.Application):
        pass

    def attach(self, _: web.Application):
        async def handle_event(_, __):
            await self._repo.run_migrations()

        EventBus.get_instance().subscribe(Events.STARTED, handle_event, "ConditionsRepository.run_migrations")

    async def get_all(self) -> list[ConditionModel]:
        return await self._repo.list()

    async def save(self, item: ConditionModel | dict) -> ConditionModel:
        """
        Save the item.

        Args:
            item (Condition|dict): The items to save.

        Returns:
            ConditionModel: The current instance.

        """
        try:
            if not isinstance(item, ConditionModel):
                item: ConditionModel = ConditionModel(**item)
        except Exception as exc:
            msg: str = f"Failed to parse item. '{exc!s}'"
            raise ValueError(msg) from exc

        try:
            repo = self._repo
            if item.id is None or 0 == item.id:
                model = await repo.create(item)
            else:
                model = await repo.update(item.id, item.serialize())
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

        return model

    async def has(self, identifier: str) -> bool:
        """
        Check if the item exists by id or name.

        Args:
            identifier (str): The id or name of the preset.

        Returns:
            bool: True if the item exists, False otherwise.

        """
        return await self.get(identifier) is not None

    async def get(self, identifier: str) -> ConditionModel | None:
        """
        Get the item by id or name.

        Args:
            identifier (str): The id or name of the preset.

        Returns:
            ConditionModel|None: The item if found, None otherwise.

        """
        repo = self._repo
        return await repo.get(identifier)

    async def match(self, info: dict, ignore_conditions: Iterable[str | Number] | None = None) -> ConditionModel | None:
        """
        Check if any condition matches the info dict.

        Args:
            info (dict): The info dict to check.
            ignore_conditions (Iterable[str | Number] | None): Condition ids or names to skip for this match.

        Returns:
            Condition|None: The condition if found, None otherwise.

        """
        if not info or not isinstance(info, dict) or len(info) < 1:
            return None

        ignored_identifiers, ignore_all = _ignored_identifiers(ignore_conditions)
        if ignore_all:
            return None

        repo = self._repo
        items: list[ConditionModel] = await repo.list()
        if len(items) < 1:
            return None

        for item in sorted(items, key=lambda x: x.priority, reverse=True):
            if not item.enabled:
                continue

            if str(item.id) in ignored_identifiers or item.name in ignored_identifiers:
                continue

            if not item.filter:
                LOG.error(
                    "Filter is empty for '%s'.", item.name, extra={"condition_id": item.id, "condition_name": item.name}
                )
                continue

            try:
                if not match_str(item.filter, info):
                    continue

                LOG.debug(
                    "Matched '%s: %s' with filter '%s'.",
                    item.id,
                    item.name,
                    item.filter,
                    extra={"condition_id": item.id, "condition_name": item.name, "filter": item.filter},
                )
                return item
            except Exception as e:
                LOG.exception(
                    "Failed to evaluate condition '%s'.",
                    item.name,
                    extra={"condition_id": item.id, "condition_name": item.name, "exception_type": type(e).__name__},
                )
                continue

        return None

    async def single_match(self, identifier: int | str, info: dict) -> ConditionModel | None:
        """
        Check if condition matches the info dict.

        Args:
            identifier (int|str): The id or name of the item.
            info (dict): The info dict to check.

        Returns:
            ConditionModel|None: The condition if found, None otherwise.

        """
        if not info or not isinstance(info, dict) or len(info) < 1:
            return None

        if not (item := await self.get(identifier)) or not item.enabled or not item.filter:
            return None

        return item if match_str(item.filter, info) else None
