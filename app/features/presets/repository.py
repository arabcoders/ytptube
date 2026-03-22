from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.features.core.deps import get_session
from app.features.core.schemas import CEFeature, ConfigEvent
from app.features.presets.migration import Migration
from app.features.presets.models import PresetModel
from app.features.presets.utils import preset_name, seed_defaults
from app.library.config import Config
from app.library.Events import Event, EventBus, Events
from app.library.Services import Services
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager

    from aiohttp import web
    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

    SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

LOG: logging.Logger = logging.getLogger(__name__)


class PresetsRepository(metaclass=Singleton):
    SORT_FIELDS: dict[str, Any] = {
        "id": PresetModel.id,
        "name": PresetModel.name,
        "priority": PresetModel.priority,
        "default": PresetModel.default,
        "created_at": PresetModel.created_at,
        "updated_at": PresetModel.updated_at,
    }
    SORT_DIRECTIONS: tuple[str, str] = ("asc", "desc")
    DEFAULT_SORT_ORDER: tuple[tuple[str, str], ...] = (("priority", "desc"), ("name", "asc"))
    FIELD_DEFAULT_DIRECTIONS: dict[str, str] = {
        "id": "asc",
        "name": "asc",
        "priority": "desc",
        "default": "desc",
        "created_at": "desc",
        "updated_at": "desc",
    }

    def __init__(self, session: SessionFactory | None = None) -> None:
        self._migrated = False
        self.session: SessionFactory = session or get_session

    async def run_migrations(self) -> None:
        if self._migrated:
            return

        self._migrated = True
        await Migration(repo=self).run()

    def attach(self, _: web.Application) -> None:
        async def handle_event(_, __):
            await seed_defaults(self)
            await self.run_migrations()
            await self._update_cache()
            await self._ensure_default_preset()

        async def handler(e: Event, __):
            if isinstance(e.data, ConfigEvent) and CEFeature.PRESETS == e.data.feature:
                LOG.debug("Refreshing presets cache due to configuration update.")
                await self._update_cache()

        Services.get_instance().add(__class__.__name__, self)
        EventBus.get_instance().subscribe(
            Events.STARTED, handle_event, f"{__class__.__name__}.run_migrations"
        ).subscribe(Events.CONFIG_UPDATE, handler, "Presets.refresh_cache")

    async def _update_cache(self) -> None:
        from app.features.presets.service import Presets

        await Presets.get_instance().refresh_cache(await self.list())

    @staticmethod
    def get_instance() -> PresetsRepository:
        return PresetsRepository()

    async def _ensure_default_preset(self) -> None:
        config = Config.get_instance()
        if not (default_name := preset_name(config.default_preset)):
            config.default_preset = "default"
            default_name = config.default_preset

        if await self.get_by_name(default_name) is None:
            LOG.error("Default preset '%s' not found, using 'default' preset.", default_name)
            config.default_preset = "default"

    async def list(self) -> list[PresetModel]:
        async with self.session() as session:
            result: Result[tuple[PresetModel]] = await session.execute(
                select(PresetModel).order_by(PresetModel.priority.desc(), PresetModel.name.asc())
            )
            return list(result.scalars().all())

    @classmethod
    def parse_sorting(cls, sort: str | None = None, order: str | None = None) -> tuple[tuple[str, str], ...]:
        sort_value = (sort or "").strip()
        order_value = (order or "").strip()

        if not sort_value and not order_value:
            return cls.DEFAULT_SORT_ORDER

        if order_value and not sort_value:
            msg = "sort is required when order is provided."
            raise ValueError(msg)

        fields: list[str] = []
        for raw_field in sort_value.split(","):
            field = raw_field.strip().lower()
            if not field:
                continue
            if field not in cls.SORT_FIELDS:
                msg = f"sort must use supported fields: {', '.join(cls.SORT_FIELDS)}."
                raise ValueError(msg)
            if field not in fields:
                fields.append(field)

        if not fields:
            msg = "sort must include at least one field."
            raise ValueError(msg)

        directions: list[str] = []
        if order_value:
            for raw_direction in order_value.split(","):
                direction = raw_direction.strip().lower()
                if not direction:
                    continue
                if direction not in cls.SORT_DIRECTIONS:
                    msg = "order must be 'asc' or 'desc'."
                    raise ValueError(msg)
                directions.append(direction)

            if not directions:
                msg = "order must include at least one direction."
                raise ValueError(msg)

            if len(directions) not in {1, len(fields)}:
                msg = "order must provide one direction or match the number of sort fields."
                raise ValueError(msg)

        if not directions:
            return tuple((field, cls.FIELD_DEFAULT_DIRECTIONS.get(field, "asc")) for field in fields)

        if len(directions) == 1:
            return tuple((field, directions[0]) for field in fields)

        return tuple((field, directions[index]) for index, field in enumerate(fields))

    @classmethod
    def _apply_sort_direction(cls, field: str, direction: str) -> Any:
        column = cls.SORT_FIELDS[field]
        return column.asc() if direction == "asc" else column.desc()

    @classmethod
    def _build_order_by(cls, sort: str | None = None, order: str | None = None) -> list[Any]:
        sorting = cls.parse_sorting(sort, order)

        order_by: list[Any] = [cls._apply_sort_direction(field, direction) for field, direction in sorting]

        if all(field != "id" for field, _ in sorting):
            order_by.append(PresetModel.id.asc())

        return order_by

    async def list_paginated(
        self,
        page: int,
        per_page: int,
        sort: str | None = None,
        order: str | None = None,
    ) -> tuple[list[PresetModel], int, int, int]:
        order_by = self._build_order_by(sort, order)

        async with self.session() as session:
            total: int = await self.count()
            total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

            if page > total_pages and total > 0:
                page = total_pages

            query: Select[tuple[PresetModel]] = (
                select(PresetModel).order_by(*order_by).limit(per_page).offset((page - 1) * per_page)
            )
            result: Result[tuple[PresetModel]] = await session.execute(query)
            return list(result.scalars().all()), total, page, total_pages

    async def count(self) -> int:
        async with self.session() as session:
            result: Result[tuple[int]] = await session.execute(select(func.count()).select_from(PresetModel))
            return int(result.scalar_one())

    async def get(self, identifier: int | str) -> PresetModel | None:
        async with self.session() as session:
            if not identifier:
                return None

            if isinstance(identifier, int):
                clause: ColumnElement[bool] = PresetModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(PresetModel.id == int(identifier), PresetModel.name == identifier)
            else:
                name = preset_name(identifier) if isinstance(identifier, str) else identifier
                if not name:
                    return None
                clause = PresetModel.name == name

            result: Result[tuple[PresetModel]] = await session.execute(select(PresetModel).where(clause).limit(1))
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str, exclude_id: int | None = None) -> PresetModel | None:
        async with self.session() as session:
            if not (name := preset_name(name)):
                return None

            query: Select[tuple[PresetModel]] = select(PresetModel).where(PresetModel.name == name)
            if None is not exclude_id:
                query = query.where(PresetModel.id != exclude_id)

            result: Result[tuple[PresetModel]] = await session.execute(query.limit(1))
            return result.scalar_one_or_none()

    async def create(self, payload: PresetModel | dict) -> PresetModel:
        async with self.session() as session:
            data: dict[str, Any]
            if isinstance(payload, dict):
                data = dict(payload)
            else:
                data = {
                    "name": payload.name,
                    "description": payload.description,
                    "folder": payload.folder,
                    "template": payload.template,
                    "cookies": payload.cookies,
                    "cli": payload.cli,
                    "default": payload.default,
                    "priority": payload.priority,
                    "created_at": payload.created_at,
                    "updated_at": payload.updated_at,
                }

            data.pop("id", None)
            model = PresetModel(**data)

            model.name = preset_name(model.name)

            if await self.get_by_name(name=model.name) is not None:
                msg: str = f"Preset with name '{model.name}' already exists."
                raise ValueError(msg)

            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def update(self, identifier: int | str, payload: dict[str, Any]) -> PresetModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = PresetModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(PresetModel.id == int(identifier), PresetModel.name == identifier)
            else:
                clause = PresetModel.name == identifier

            result: Result[tuple[PresetModel]] = await session.execute(select(PresetModel).where(clause).limit(1))
            model: PresetModel | None = result.scalar_one_or_none()

            if model is None:
                msg: str = f"Preset '{identifier}' not found."
                raise KeyError(msg)

            payload.pop("id", None)
            payload.pop("created_at", None)
            payload.pop("updated_at", None)

            for key, value in payload.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            normalized_name = preset_name(model.name)
            model.name = normalized_name
            if await self.get_by_name(name=normalized_name, exclude_id=model.id) is not None:
                msg = f"Preset with name '{normalized_name}' already exists."
                raise ValueError(msg)

            await session.commit()
            await session.refresh(model)
            return model

    async def delete(self, identifier: int | str) -> PresetModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = PresetModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(PresetModel.id == int(identifier), PresetModel.name == identifier)
            else:
                clause = PresetModel.name == preset_name(identifier)

            result: Result[tuple[PresetModel]] = await session.execute(select(PresetModel).where(clause).limit(1))
            model: PresetModel | None = result.scalar_one_or_none()
            if model is None:
                msg: str = f"Preset '{identifier}' not found."
                raise KeyError(msg)

            await session.delete(model)
            await session.commit()
            return model
