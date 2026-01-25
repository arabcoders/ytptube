from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class ConditionModel(Base):
    __tablename__: str = "conditions"
    __table_args__: tuple[Index, ...] = (
        Index("ix_conditions_name", "name"),
        Index("ix_conditions_enabled", "enabled"),
        Index("ix_conditions_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    filter: Mapped[str] = mapped_column(Text, nullable=False)
    cli: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extras: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
