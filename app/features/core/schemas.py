from __future__ import annotations

from pydantic import BaseModel


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool
