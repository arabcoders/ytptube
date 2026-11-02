from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class ToolboxJobModel(Base):
    __tablename__ = "toolbox_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
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
