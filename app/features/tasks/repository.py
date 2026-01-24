from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.features.core.deps import get_session
from app.features.tasks.models import TaskModel
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

LOG: logging.Logger = logging.getLogger(__name__)


class TasksRepository(metaclass=Singleton):
    def __init__(self, session: AsyncGenerator[AsyncSession] | None = None) -> None:
        self._migrated = False
        self.session = session or get_session

    async def run_migrations(self) -> None:
        if self._migrated:
            return

        self._migrated = True
        from app.features.tasks.migration import Migration

        await Migration(repo=self).run()

    @staticmethod
    def get_instance() -> TasksRepository:
        return TasksRepository()

    async def list(self) -> list[TaskModel]:
        async with self.session() as session:
            result: Result[tuple[TaskModel]] = await session.execute(select(TaskModel).order_by(TaskModel.name.asc()))
            return list(result.scalars().all())

    async def list_paginated(self, page: int, per_page: int) -> tuple[list[TaskModel], int, int, int]:
        async with self.session() as session:
            total: int = await self.count()
            total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

            if page > total_pages and total > 0:
                page = total_pages

            query: Select[tuple[TaskModel]] = (
                select(TaskModel).order_by(TaskModel.name.asc()).limit(per_page).offset((page - 1) * per_page)
            )
            result: Result[tuple[TaskModel]] = await session.execute(query)
            return list(result.scalars().all()), total, page, total_pages

    async def count(self) -> int:
        async with self.session() as session:
            result: Result[tuple[int]] = await session.execute(select(func.count()).select_from(TaskModel))
            return int(result.scalar_one())

    async def get(self, identifier: int | str) -> TaskModel | None:
        async with self.session() as session:
            if not identifier:
                return None

            if isinstance(identifier, int):
                clause: ColumnElement[bool] = TaskModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(TaskModel.id == int(identifier), TaskModel.name == identifier)
            else:
                clause = TaskModel.name == identifier

            result: Result[tuple[TaskModel]] = await session.execute(select(TaskModel).where(clause).limit(1))
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str, exclude_id: int | None = None) -> TaskModel | None:
        async with self.session() as session:
            query: Select[tuple[TaskModel]] = select(TaskModel).where(TaskModel.name == name)
            if exclude_id is not None:
                query = query.where(TaskModel.id != exclude_id)

            result: Result[tuple[TaskModel]] = await session.execute(query.limit(1))
            return result.scalar_one_or_none()

    async def get_all_enabled(self) -> list[TaskModel]:
        """Get all enabled tasks."""
        async with self.session() as session:
            result: Result[tuple[TaskModel]] = await session.execute(
                select(TaskModel).where(TaskModel.enabled == True).order_by(TaskModel.name.asc())  # noqa: E712
            )
            return list(result.scalars().all())

    async def get_all_with_timer(self) -> list[TaskModel]:
        """Get all tasks that have a timer configured."""
        async with self.session() as session:
            result: Result[tuple[TaskModel]] = await session.execute(
                select(TaskModel).where(TaskModel.timer != "").order_by(TaskModel.name.asc())
            )
            return list(result.scalars().all())

    async def create(self, payload: TaskModel | dict) -> TaskModel:
        async with self.session() as session:
            model: TaskModel = TaskModel(**payload) if isinstance(payload, dict) else payload
            if model.id is not None:
                model.id = None

            if await self.get_by_name(name=model.name) is not None:
                msg: str = f"Task with name '{model.name}' already exists."
                raise ValueError(msg)

            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def update(self, identifier: int | str, payload: dict[str, Any]) -> TaskModel:
        """Update an existing task."""
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = TaskModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(TaskModel.id == int(identifier), TaskModel.name == identifier)
            else:
                clause = TaskModel.name == identifier

            result: Result[tuple[TaskModel]] = await session.execute(select(TaskModel).where(clause).limit(1))
            model: TaskModel | None = result.scalar_one_or_none()

            if model is None:
                msg: str = f"Task '{identifier}' not found."
                raise KeyError(msg)

            if "name" in payload:
                existing: TaskModel | None = await self.get_by_name(name=payload["name"], exclude_id=model.id)
                if existing is not None:
                    msg = f"Task with name '{payload['name']}' already exists."
                    raise ValueError(msg)

            for key, value in payload.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            await session.commit()
            await session.refresh(model)
            return model

    async def delete(self, identifier: int | str) -> TaskModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = TaskModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(TaskModel.id == int(identifier), TaskModel.name == identifier)
            else:
                clause = TaskModel.name == identifier

            result: Result[tuple[TaskModel]] = await session.execute(select(TaskModel).where(clause).limit(1))
            model: TaskModel | None = result.scalar_one_or_none()

            if model is None:
                msg: str = f"Task '{identifier}' not found."
                raise KeyError(msg)

            await session.delete(model)
            await session.commit()
            return model
