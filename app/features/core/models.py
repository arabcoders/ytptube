from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime as SQLADateTime
from sqlalchemy import TypeDecorator
from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """
    Return current UTC time as timezone-aware datetime.

    This is the canonical way to get current UTC time for database fields.
    """
    return datetime.now(tz=UTC)


class UTCDateTime(TypeDecorator):
    impl = SQLADateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect) -> datetime | None:
        """Convert datetime to UTC before storing."""
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, _dialect) -> datetime | None:
        """Ensure datetime is timezone-aware (UTC) when loading."""
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass
