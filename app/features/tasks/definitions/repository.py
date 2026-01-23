from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.features.core.deps import get_session
from app.features.core.schemas import CEFeature, ConfigEvent
from app.features.tasks.definitions.migration import Migration
from app.features.tasks.definitions.models import TaskDefinitionModel
from app.library.Events import Event, EventBus, Events
from app.library.Services import Services
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

LOG: logging.Logger = logging.getLogger(__name__)


class TaskDefinitionsRepository(metaclass=Singleton):
    def __init__(self, session: AsyncGenerator[AsyncSession] | None = None) -> None:
        self._migrated = False
        self.session: AsyncGenerator[AsyncSession] = session or get_session

    async def run_migrations(self) -> None:
        if self._migrated:
            return

        self._migrated = True
        await Migration(repo=self).run()

    @staticmethod
    def get_instance() -> TaskDefinitionsRepository:
        return TaskDefinitionsRepository()

    def attach(self, _: Any) -> None:
        async def handle_event(_, __):
            await self.run_migrations()

        async def handler(e: Event, __):
            from app.features.tasks.definitions.handlers.generic import GenericTaskHandler

            if isinstance(e.data, ConfigEvent) and CEFeature.TASKS_DEFINITIONS == e.data.feature:
                LOG.debug("Refreshing task definitions due to configuration update.")
                await GenericTaskHandler.refresh_definitions(force=True)

        Services.get_instance().add(__class__.__name__, self)
        EventBus.get_instance().subscribe(
            Events.STARTED, handle_event, f"{__class__.__name__}.run_migrations"
        ).subscribe(Events.CONFIG_UPDATE, handler, "GenericTaskHandler.refresh_definitions")

    async def list(self) -> list[TaskDefinitionModel]:
        async with self.session() as session:
            result: Result[tuple[TaskDefinitionModel]] = await session.execute(
                select(TaskDefinitionModel).order_by(TaskDefinitionModel.priority.asc(), TaskDefinitionModel.name.asc())
            )
            return list(result.scalars().all())

    async def list_paginated(self, page: int, per_page: int) -> tuple[list[TaskDefinitionModel], int, int, int]:
        async with self.session() as session:
            total: int = await self.count()
            total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

            if page > total_pages and total > 0:
                page = total_pages

            query: Select[tuple[TaskDefinitionModel]] = (
                select(TaskDefinitionModel)
                .order_by(TaskDefinitionModel.priority.asc(), TaskDefinitionModel.name.asc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            result: Result[tuple[TaskDefinitionModel]] = await session.execute(query)
            return list(result.scalars().all()), total, page, total_pages

    async def count(self) -> int:
        async with self.session() as session:
            result: Result[tuple[int]] = await session.execute(select(func.count()).select_from(TaskDefinitionModel))
            return int(result.scalar_one())

    async def get(self, identifier: int | str) -> TaskDefinitionModel | None:
        async with self.session() as session:
            if not identifier:
                return None

            if isinstance(identifier, int):
                clause: ColumnElement[bool] = TaskDefinitionModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(TaskDefinitionModel.id == int(identifier), TaskDefinitionModel.name == identifier)
            else:
                clause = TaskDefinitionModel.name == identifier

            result: Result[tuple[TaskDefinitionModel]] = await session.execute(
                select(TaskDefinitionModel).where(clause).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str, exclude_id: int | None = None) -> TaskDefinitionModel | None:
        async with self.session() as session:
            query: Select[tuple[TaskDefinitionModel]] = select(TaskDefinitionModel).where(
                TaskDefinitionModel.name == name
            )
            if exclude_id is not None:
                query = query.where(TaskDefinitionModel.id != exclude_id)

            result: Result[tuple[TaskDefinitionModel]] = await session.execute(query.limit(1))
            return result.scalar_one_or_none()

    async def create(self, payload: dict[str, Any]) -> TaskDefinitionModel:
        async with self.session() as session:
            model: TaskDefinitionModel = TaskDefinitionModel(**payload) if isinstance(payload, dict) else payload
            if model.id is not None:
                model.id = None

            if await self.get_by_name(name=model.name) is not None:
                msg: str = f"Task definition with name '{model.name}' already exists."
                raise ValueError(msg)

            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def update(self, identifier: int | str, payload: dict[str, Any]) -> TaskDefinitionModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = TaskDefinitionModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(TaskDefinitionModel.id == int(identifier), TaskDefinitionModel.name == identifier)
            else:
                clause = TaskDefinitionModel.name == identifier

            result: Result[tuple[TaskDefinitionModel]] = await session.execute(
                select(TaskDefinitionModel).where(clause).limit(1)
            )
            model: TaskDefinitionModel | None = result.scalar_one_or_none()

            if not model:
                msg: str = f"Task definition '{identifier}' not found."
                raise KeyError(msg)

            payload.pop("id", None)
            payload.pop("created_at", None)
            payload.pop("updated_at", None)

            if "name" in payload and await self.get_by_name(name=payload["name"], exclude_id=model.id) is not None:
                msg = f"Task definition with name '{payload['name']}' already exists."
                raise ValueError(msg)

            for key, value in payload.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            await session.commit()
            await session.refresh(model)
            return model

    async def delete(self, identifier: int | str) -> TaskDefinitionModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = TaskDefinitionModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(TaskDefinitionModel.id == int(identifier), TaskDefinitionModel.name == identifier)
            else:
                clause = TaskDefinitionModel.name == identifier

            result: Result[tuple[TaskDefinitionModel]] = await session.execute(
                select(TaskDefinitionModel).where(clause).limit(1)
            )

            if not (model := result.scalar_one_or_none()):
                msg: str = f"Task definition '{identifier}' not found."
                raise KeyError(msg)

            await session.delete(model)
            await session.commit()
            return model
