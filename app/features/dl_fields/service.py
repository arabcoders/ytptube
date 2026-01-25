from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.features.dl_fields.models import DLFieldModel
from app.features.dl_fields.repository import DLFieldsRepository
from app.features.dl_fields.schemas import DLField
from app.library.Events import EventBus, Events
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from aiohttp import web

LOG: logging.Logger = logging.getLogger("feature.dl_fields")


class DLFields(metaclass=Singleton):
    def __init__(self):
        self._repo: DLFieldsRepository = DLFieldsRepository.get_instance()

    @staticmethod
    def get_instance() -> DLFields:
        return DLFields()

    async def on_shutdown(self, _: web.Application) -> None:
        pass

    def attach(self, _: web.Application) -> None:
        async def handle_event(_, __):
            await self._repo.run_migrations()

        EventBus.get_instance().subscribe(Events.STARTED, handle_event, "DLFieldsRepository.run_migrations")

    async def get_all(self) -> list[DLFieldModel]:
        return await self._repo.list()

    async def get_all_serialized(self) -> list[dict[str, Any]]:
        items = await self._repo.list()
        return [DLField.model_validate(item).model_dump() for item in items]

    async def save(self, item: DLField | dict) -> DLFieldModel:
        try:
            if not isinstance(item, DLField):
                item = DLField.model_validate(item)
        except Exception as exc:
            msg: str = f"Failed to parse item. '{exc!s}'"
            raise ValueError(msg) from exc

        try:
            repo = self._repo
            if item.id is None or 0 == item.id:
                model = await repo.create(item.model_dump(exclude_unset=True))
            else:
                model = await repo.update(item.id, item.model_dump(exclude_unset=True))
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

        return model

    async def get(self, identifier: int | str) -> DLFieldModel | None:
        return await self._repo.get(identifier)
