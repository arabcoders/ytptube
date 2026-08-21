from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from datetime import datetime  # noqa: TC003
from email.utils import formatdate
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Index, String, column, func
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.models import Base, UTCDateTime, utcnow
from app.library.Utils import init_class

if TYPE_CHECKING:
    from app.features.downloads.items import ItemDTO


JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]


class DownloadModel(Base):
    __tablename__ = "history"
    __table_args__ = (
        Index("history_type", "type"),
        Index("history_url", "url", unique=True),
        Index("history_status", func.json_extract(column("data"), "$.status")),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[dict[str, JSONValue]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    def to_item(self) -> ItemDTO:
        from app.features.downloads.items import ItemDTO

        item_data = deepcopy(self.data)
        item_data.pop("_id", None)
        item_fields = {field.name for field in fields(ItemDTO)}
        item = init_class(ItemDTO, item_data, item_fields)
        item._id = self.id
        item.datetime = formatdate(self.created_at.timestamp())
        return item
