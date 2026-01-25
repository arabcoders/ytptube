from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from app.features.core.deps import get_session
from app.features.notifications.migration import Migration
from app.features.notifications.models import NotificationModel
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

LOG: logging.Logger = logging.getLogger(__name__)


class NotificationsRepository(metaclass=Singleton):
    def __init__(self, session: AsyncGenerator[AsyncSession] | None = None) -> None:
        self._migrated = False
        self.session: AsyncGenerator[AsyncSession] = session or get_session

    async def run_migrations(self) -> None:
        if self._migrated:
            return

        self._migrated = True
        await Migration(repo=self, config=None).run()

    @staticmethod
    def get_instance() -> NotificationsRepository:
        return NotificationsRepository()

    async def list(self) -> list[NotificationModel]:
        async with self.session() as session:
            result: Result[tuple[NotificationModel]] = await session.execute(
                select(NotificationModel).order_by(NotificationModel.name.asc())
            )
            return list(result.scalars().all())

    async def list_paginated(self, page: int, per_page: int) -> tuple[list[NotificationModel], int, int, int]:
        async with self.session() as session:
            total: int = await self.count()
            total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

            if page > total_pages and total > 0:
                page = total_pages

            query: Select[tuple[NotificationModel]] = (
                select(NotificationModel)
                .order_by(NotificationModel.name.asc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            result: Result[tuple[NotificationModel]] = await session.execute(query)
            return list(result.scalars().all()), total, page, total_pages

    async def count(self) -> int:
        async with self.session() as session:
            result: Result[tuple[int]] = await session.execute(select(func.count()).select_from(NotificationModel))
            return int(result.scalar_one())

    async def get(self, identifier: int | str) -> NotificationModel | None:
        async with self.session() as session:
            if not identifier:
                return None

            if isinstance(identifier, int):
                clause: ColumnElement[bool] = NotificationModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(NotificationModel.id == int(identifier), NotificationModel.name == identifier)
            else:
                clause = NotificationModel.name == identifier

            result: Result[tuple[NotificationModel]] = await session.execute(
                select(NotificationModel).where(clause).limit(1)
            )
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str, exclude_id: int | None = None) -> NotificationModel | None:
        async with self.session() as session:
            query: Select[tuple[NotificationModel]] = select(NotificationModel).where(NotificationModel.name == name)
            if exclude_id is not None:
                query = query.where(NotificationModel.id != exclude_id)

            result: Result[tuple[NotificationModel]] = await session.execute(query.limit(1))
            return result.scalar_one_or_none()

    async def create(self, payload: NotificationModel | dict) -> NotificationModel:
        async with self.session() as session:
            model: NotificationModel = NotificationModel(**payload) if isinstance(payload, dict) else payload
            if model.id is not None:
                model.id = None

            if await self.get_by_name(name=model.name) is not None:
                msg: str = f"Notification target with name '{model.name}' already exists."
                raise ValueError(msg)

            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def update(self, identifier: int | str, payload: dict[str, Any]) -> NotificationModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = NotificationModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(NotificationModel.id == int(identifier), NotificationModel.name == identifier)
            else:
                clause = NotificationModel.name == identifier

            result: Result[tuple[NotificationModel]] = await session.execute(
                select(NotificationModel).where(clause).limit(1)
            )
            model: NotificationModel | None = result.scalar_one_or_none()

            if not model:
                msg: str = f"Notification target '{identifier}' not found."
                raise KeyError(msg)

            payload.pop("id", None)

            if "name" in payload and await self.get_by_name(name=payload["name"], exclude_id=model.id) is not None:
                msg = f"Notification target with name '{payload['name']}' already exists."
                raise ValueError(msg)

            for key, value in payload.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            await session.commit()
            await session.refresh(model)
            return model

    async def delete(self, identifier: int | str) -> NotificationModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = NotificationModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(NotificationModel.id == int(identifier), NotificationModel.name == identifier)
            else:
                clause = NotificationModel.name == identifier

            result: Result[tuple[NotificationModel]] = await session.execute(
                select(NotificationModel).where(clause).limit(1)
            )
            model = result.scalar_one_or_none()

            if not model:
                msg: str = f"Notification target '{identifier}' not found."
                raise KeyError(msg)

            await session.delete(model)
            await session.commit()
            return model
