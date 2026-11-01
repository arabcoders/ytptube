from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, update

from app.features.core.deps import get_session
from app.features.core.models import utcnow
from app.features.toolbox.models import ToolboxJobModel
from app.features.toolbox.schemas import Job


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
