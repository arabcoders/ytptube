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
    from collections.abc import AsyncGenerator

    from aiohttp import web
    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

LOG: logging.Logger = logging.getLogger(__name__)


class PresetsRepository(metaclass=Singleton):
    def __init__(self, session: AsyncGenerator[AsyncSession] | None = None) -> None:
        self._migrated = False
        self.session: AsyncGenerator[AsyncSession] = session or get_session

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

    async def list_paginated(self, page: int, per_page: int) -> tuple[list[PresetModel], int, int, int]:
        async with self.session() as session:
            total: int = await self.count()
            total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

            if page > total_pages and total > 0:
                page = total_pages

            query: Select[tuple[PresetModel]] = (
                select(PresetModel)
                .order_by(PresetModel.priority.desc(), PresetModel.name.asc())
                .limit(per_page)
                .offset((page - 1) * per_page)
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
            model: PresetModel = PresetModel(**payload) if isinstance(payload, dict) else payload
            if model.id is not None:
                model.id = None

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

            if None is model:
                msg: str = f"Preset '{identifier}' not found."
                raise KeyError(msg)

            assert None is not model

            payload.pop("id", None)
            payload.pop("created_at", None)
            payload.pop("updated_at", None)

            for key, value in payload.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            model.name = preset_name(model.name)
            if await self.get_by_name(name=model.name, exclude_id=model.id) is not None:
                msg = f"Preset with name '{model.name}' already exists."
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
            if not (model := result.scalar_one_or_none()):
                msg: str = f"Preset '{identifier}' not found."
                raise KeyError(msg)

            assert None is not model

            await session.delete(model)
            await session.commit()
            return model
