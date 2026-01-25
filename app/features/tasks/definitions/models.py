from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import JSON, Boolean, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class TaskDefinitionModel(Base):
    __tablename__: str = "task_definitions"
    __table_args__: tuple[Index, ...] = (
        Index("ix_task_definitions_name", "name"),
        Index("ix_task_definitions_priority", "priority"),
        Index("ix_task_definitions_match_url", "match_url"),
        Index("ix_task_definitions_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    match_url: Mapped[list] = mapped_column(JSON, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
