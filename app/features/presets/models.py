from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class PresetModel(Base):
    __tablename__: str = "presets"
    __table_args__: tuple[Index, ...] = (
        Index("ix_presets_name", "name"),
        Index("ix_presets_is_default", "is_default"),
        Index("ix_presets_priority", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    folder: Mapped[str] = mapped_column(Text, nullable=False, default="")
    template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cookies: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cli: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default: Mapped[bool] = mapped_column("is_default", Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
