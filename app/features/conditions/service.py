from collections.abc import Iterable

from aiohttp import web

from app.features.conditions.models import ConditionModel
from app.features.conditions.repository import ConditionsRepository
from app.features.conditions.schemas import Condition
from app.features.ytdlp.mini_filter import MiniFilter, match_str
from app.features.ytdlp.utils import get_archive_id, get_ytdlp
from app.library.Events import EventBus, Events
from app.library.logging import get_logger
from app.library.Singleton import Singleton

LOG = get_logger()


def _ignored_identifiers(ignore_conditions: Iterable[str | int | float] | None) -> tuple[set[str], bool]:
    ignored: set[str] = set()
    ignore_all = False

    if not ignore_conditions:
        return ignored, ignore_all

    for value in ignore_conditions:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
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
        return await self._repo.all()

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
                model = await repo.update(item.id, Condition.model_validate(item).model_dump())
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

    async def match_url(
        self, url: str, ignore_conditions: Iterable[str | int | float] | None = None
    ) -> ConditionModel | None:
        info = {"url": url, "webpage_url": url, "original_url": url}
        identity = get_archive_id(url)
        if entry_id := identity.get("id"):
            info["id"] = entry_id
        if key := identity.get("ie_key"):
            info.update(extractor_key=key, ie_key=key, extractor=get_ytdlp()._ies[key].IE_NAME)

        return await self.match(info, ignore_conditions=ignore_conditions, incomplete=True)

    async def match(
        self, info: dict, ignore_conditions: Iterable[str | int | float] | None = None, *, incomplete: bool = False
    ) -> ConditionModel | None:
        """Match the highest-priority rule, deferring unknown fields when metadata is incomplete."""
        if not info or not isinstance(info, dict) or len(info) < 1:
            return None

        ignored_identifiers, ignore_all = _ignored_identifiers(ignore_conditions)
        if ignore_all:
            return None

        repo = self._repo
        items: list[ConditionModel] = await repo.all()
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
                if not MiniFilter(item.filter).evaluate(info, incomplete=incomplete):
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

        if not (item := await self.get(str(identifier))) or not item.enabled or not item.filter:
            return None

        return item if match_str(item.filter, info) else None
