from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class TaskModel(Base):
    __tablename__: str = "tasks"
    __table_args__: tuple[Index, ...] = (
        Index("ix_tasks_name", "name"),
        Index("ix_tasks_enabled", "enabled"),
        Index("ix_tasks_timer", "timer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    folder: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    preset: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    timer: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    template: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    cli: Mapped[str] = mapped_column(Text, nullable=False, default="")
    auto_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    handler_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
