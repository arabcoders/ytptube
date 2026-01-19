from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import JSON, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class DLFieldModel(Base):
    __tablename__: str = "dl_fields"
    __table_args__: tuple[Index, ...] = (
        Index("ix_dl_fields_name", "name"),
        Index("ix_dl_fields_order", "order"),
        Index("ix_dl_fields_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    field: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    icon: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extras: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
