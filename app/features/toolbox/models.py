from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class ToolboxDefinitionModel(Base):
    __tablename__ = "toolbox_definitions"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    default_key: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_extension: Mapped[str] = mapped_column(Text, nullable=False)
    supports_overwrite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    command: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    env: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    params: Mapped[dict[str, dict[str, Any]]] = mapped_column(JSON, nullable=False, default=dict)
    extras: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ToolboxJobModel(Base):
    __tablename__ = "toolbox_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool: Mapped[int] = mapped_column(Integer, nullable=False)
    file: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    log: Mapped[str] = mapped_column(Text, default="", nullable=False)
