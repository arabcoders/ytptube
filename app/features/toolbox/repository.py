from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert

from app.features.core.deps import get_session
from app.features.core.models import utcnow
from app.features.toolbox.defaults import DEFAULT_TOOLS
from app.features.toolbox.definitions import Definition, SavedDefinition
from app.features.toolbox.models import ToolboxDefinitionModel, ToolboxJobModel
from app.features.toolbox.schemas import Job


class DefinitionsRepository:
    async def seed(self) -> None:
        async with get_session() as session:
            for definition in DEFAULT_TOOLS:
                fields = definition.model_dump()
                stmt = insert(ToolboxDefinitionModel).values(default_key=definition.default_key, **fields)
                await session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=[ToolboxDefinitionModel.default_key],
                        set_=fields,
                    )
                )
            await session.commit()

    async def all(self) -> list[SavedDefinition]:
        async with get_session() as session:
            rows = await session.scalars(
                select(ToolboxDefinitionModel).order_by(
                    ToolboxDefinitionModel.default_key.is_not(None).desc(), ToolboxDefinitionModel.id
                )
            )
            return [SavedDefinition.model_validate(row, from_attributes=True) for row in rows]

    async def list_paginated(
        self, page: int, per_page: int, *, include_defaults: bool = False
    ) -> tuple[list[SavedDefinition], int, int, int]:
        clause = () if include_defaults else (ToolboxDefinitionModel.default_key.is_(None),)
        async with get_session() as session:
            total = (
                await session.execute(select(func.count()).select_from(ToolboxDefinitionModel).where(*clause))
            ).scalar_one()
            pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, pages)
            rows = await session.scalars(
                select(ToolboxDefinitionModel)
                .where(*clause)
                .order_by(ToolboxDefinitionModel.default_key.is_not(None).desc(), ToolboxDefinitionModel.id)
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            return [SavedDefinition.model_validate(row, from_attributes=True) for row in rows], total, page, pages

    async def get(self, identifier: int) -> SavedDefinition | None:
        async with get_session() as session:
            model = await session.get(ToolboxDefinitionModel, identifier)
            return SavedDefinition.model_validate(model, from_attributes=True) if model else None

    async def create(self, definition: Definition) -> SavedDefinition:
        async with get_session() as session:
            model = ToolboxDefinitionModel(**definition.model_dump())
            session.add(model)
            await session.commit()
            return SavedDefinition.model_validate(model, from_attributes=True)

    async def replace(self, identifier: int, definition: Definition) -> SavedDefinition | None:
        async with get_session() as session:
            model = await session.get(ToolboxDefinitionModel, identifier)
            if model is None:
                return None
            if model.default_key is not None:
                msg = "Shipped tools cannot be edited."
                raise ValueError(msg)
            for key, value in definition.model_dump().items():
                setattr(model, key, value)
            await session.commit()
            return SavedDefinition.model_validate(model, from_attributes=True)

    async def delete(self, identifier: int) -> bool:
        async with get_session() as session:
            model = await session.get(ToolboxDefinitionModel, identifier)
            if model is None:
                return False
            if model.default_key is not None:
                msg = "Shipped tools cannot be deleted."
                raise ValueError(msg)
            await session.delete(model)
            await session.commit()
            return True


class ToolboxRepository:
    async def create(self, payload: dict[str, Any]) -> Job:
        async with get_session() as session:
            model = ToolboxJobModel(**payload)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return Job.model_validate(model)

    async def save(self, job: Job) -> None:
        data = job.model_dump(exclude={"progress"})
        async with get_session() as session:
            await session.merge(ToolboxJobModel(**data))
            await session.commit()

    async def get(self, identifier: int) -> Job | None:
        async with get_session() as session:
            model = await session.get(ToolboxJobModel, identifier)
            return Job.model_validate(model) if model else None

    async def list_paginated(self, page: int, per_page: int, status: str | None) -> tuple[list[Job], int, int, int]:
        clause = () if status is None else (ToolboxJobModel.status == status,)
        async with get_session() as session:
            total = int(
                (await session.execute(select(func.count()).select_from(ToolboxJobModel).where(*clause))).scalar_one()
            )
            pages = max(1, (total + per_page - 1) // per_page)
            page = min(page, pages)
            rows = await session.execute(
                select(ToolboxJobModel)
                .where(*clause)
                .order_by(ToolboxJobModel.created_at.desc(), ToolboxJobModel.id.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            return [Job.model_validate(row) for row in rows.scalars()], total, page, pages

    async def interrupt(self) -> None:
        async with get_session() as session:
            await session.execute(
                update(ToolboxJobModel)
                .where(ToolboxJobModel.status.in_(("queued", "running")))
                .values(
                    status="interrupted",
                    finished_at=utcnow(),
                    message="Server stopped before the job finished.",
                    error_code="INTERRUPTED",
                )
            )
            await session.commit()

    async def delete(self, identifier: int) -> None:
        async with get_session() as session:
            await session.execute(delete(ToolboxJobModel).where(ToolboxJobModel.id == identifier))
            await session.commit()
