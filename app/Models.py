from typing import Optional
from pydantic import BaseModel


class ItemAddRequest(BaseModel):
    url: str
    quality: Optional[str]
    format: Optional[str]
    folder: Optional[str]
    ytdlp_cookies: Optional[str]
    ytdlp_config: Optional[str | dict]
    output_template: Optional[str]


class ItemAddRequestCollection(BaseModel):
    items: list[ItemAddRequest]


class deleteItemRequest(BaseModel):
    where: str
    ids: list[str]
