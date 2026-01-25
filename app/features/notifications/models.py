from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import JSON, Boolean, Index, Integer, String, Text
from sqlalchemy import Enum as SQLAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow
from app.features.notifications.schemas import NotificationRequestMethod, NotificationRequestType


class NotificationModel(Base):
    __tablename__: str = "notifications"
    __table_args__: tuple[Index, ...] = (
        Index("ix_notifications_name", "name"),
        Index("ix_notifications_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    on: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    presets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    request_url: Mapped[str] = mapped_column(Text, nullable=False)
    request_method: Mapped[NotificationRequestMethod] = mapped_column(
        SQLAEnum(NotificationRequestMethod, name="notification_request_method", native_enum=False),
        nullable=False,
        default=NotificationRequestMethod.POST,
    )
    request_type: Mapped[NotificationRequestType] = mapped_column(
        SQLAEnum(NotificationRequestType, name="notification_request_type", native_enum=False),
        nullable=False,
        default=NotificationRequestType.JSON,
    )
    request_data_key: Mapped[str] = mapped_column(String(255), nullable=False, default="data")
    request_headers: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
