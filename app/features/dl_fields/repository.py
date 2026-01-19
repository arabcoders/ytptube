from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, func, or_, select

from app.features.core.deps import get_session
from app.features.dl_fields.migration import Migration
from app.features.dl_fields.models import DLFieldModel
from app.library.Singleton import Singleton

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable

    from sqlalchemy.engine.result import Result
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement
    from sqlalchemy.sql.selectable import Select

LOG: logging.Logger = logging.getLogger(__name__)


class DLFieldsRepository(metaclass=Singleton):
    def __init__(self, session: AsyncGenerator[AsyncSession] | None = None) -> None:
        self._migrated = False
        self.session: AsyncGenerator[AsyncSession] = session or get_session

    async def run_migrations(self) -> None:
        if self._migrated:
            return

        self._migrated = True
        await Migration(repo=self).run()

    @staticmethod
    def get_instance() -> DLFieldsRepository:
        return DLFieldsRepository()

    async def list(self) -> list[DLFieldModel]:
        async with self.session() as session:
            result: Result[tuple[DLFieldModel]] = await session.execute(
                select(DLFieldModel).order_by(DLFieldModel.order.asc(), DLFieldModel.name.asc())
            )
            return list(result.scalars().all())

    async def list_paginated(self, page: int, per_page: int) -> tuple[list[DLFieldModel], int, int, int]:
        async with self.session() as session:
            total: int = await self.count()
            total_pages: int = (total + per_page - 1) // per_page if total > 0 else 1

            if page > total_pages and total > 0:
                page = total_pages

            query: Select[tuple[DLFieldModel]] = (
                select(DLFieldModel)
                .order_by(DLFieldModel.order.asc(), DLFieldModel.name.asc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            result: Result[tuple[DLFieldModel]] = await session.execute(query)
            return list(result.scalars().all()), total, page, total_pages

    async def count(self) -> int:
        async with self.session() as session:
            result: Result[tuple[int]] = await session.execute(select(func.count()).select_from(DLFieldModel))
            return int(result.scalar_one())

    async def get(self, identifier: int | str) -> DLFieldModel | None:
        async with self.session() as session:
            if not identifier:
                return None

            if isinstance(identifier, int):
                clause: ColumnElement[bool] = DLFieldModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(DLFieldModel.id == int(identifier), DLFieldModel.name == identifier)
            else:
                clause = DLFieldModel.name == identifier

            result: Result[tuple[DLFieldModel]] = await session.execute(select(DLFieldModel).where(clause).limit(1))
            return result.scalar_one_or_none()

    async def get_by_name(self, name: str, exclude_id: int | None = None) -> DLFieldModel | None:
        async with self.session() as session:
            query: Select[tuple[DLFieldModel]] = select(DLFieldModel).where(DLFieldModel.name == name)
            if exclude_id is not None:
                query = query.where(DLFieldModel.id != exclude_id)

            result: Result[tuple[DLFieldModel]] = await session.execute(query.limit(1))
            return result.scalar_one_or_none()

    async def create(self, payload: DLFieldModel | dict) -> DLFieldModel:
        async with self.session() as session:
            model: DLFieldModel = DLFieldModel(**payload) if isinstance(payload, dict) else payload

            if await self.get_by_name(name=model.name) is not None:
                msg: str = f"DL field with name '{model.name}' already exists."
                raise ValueError(msg)

            session.add(model)
            await session.commit()
            await session.refresh(model)
            return model

    async def update(self, identifier: int | str, payload: dict[str, Any]) -> DLFieldModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = DLFieldModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(DLFieldModel.id == int(identifier), DLFieldModel.name == identifier)
            else:
                clause = DLFieldModel.name == identifier

            result: Result[tuple[DLFieldModel]] = await session.execute(select(DLFieldModel).where(clause).limit(1))
            model: DLFieldModel | None = result.scalar_one_or_none()

            if not model:
                msg: str = f"DL field '{identifier}' not found."
                raise KeyError(msg)

            payload.pop("id", None)

            if "name" in payload and await self.get_by_name(name=payload["name"], exclude_id=model.id) is not None:
                msg = f"DL field with name '{payload['name']}' already exists."
                raise ValueError(msg)

            for key, value in payload.items():
                if hasattr(model, key):
                    setattr(model, key, value)

            await session.commit()
            await session.refresh(model)
            return model

    async def delete(self, identifier: int | str) -> DLFieldModel:
        async with self.session() as session:
            if isinstance(identifier, int):
                clause: ColumnElement[bool] = DLFieldModel.id == identifier
            elif isinstance(identifier, str) and identifier.isdigit():
                clause = or_(DLFieldModel.id == int(identifier), DLFieldModel.name == identifier)
            else:
                clause = DLFieldModel.name == identifier

            result: Result[tuple[DLFieldModel]] = await session.execute(select(DLFieldModel).where(clause).limit(1))
            model = result.scalar_one_or_none()

            if not model:
                msg: str = f"DL field '{identifier}' not found."
                raise KeyError(msg)

            await session.delete(model)
            await session.commit()
            return model

    async def replace_all(self, items: Iterable[dict | DLFieldModel]) -> list[DLFieldModel]:
        async with self.session() as session:
            try:
                await session.execute(delete(DLFieldModel))
                models: list[DLFieldModel] = [
                    DLFieldModel(**item) if isinstance(item, dict) else item for item in items
                ]
                session.add_all(models)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return models
