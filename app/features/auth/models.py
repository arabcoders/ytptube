from __future__ import annotations

from datetime import datetime  # noqa: TC003

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow


class UserModel(Base):
    __tablename__: str = "users"
    __table_args__: tuple[Index, ...] = (Index("ix_users_username", "username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)


class SessionModel(Base):
    __tablename__: str = "sessions"
    __table_args__: tuple[Index, ...] = (Index("ix_sessions_token_digest", "token_digest"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_digest: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(Text)


class ApiKeyModel(Base):
    __tablename__: str = "api_keys"
    __table_args__: tuple[Index, ...] = (
        Index("ix_api_keys_key_digest", "key_digest"),
        Index("ix_api_keys_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_digest: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    hint: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
