from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohttp.web import Request
    from pydantic import ValidationError


def parse_int(value: Any, *, field: str, minimum: int | None = None) -> int:
    try:
        parsed = int(value)
    except Exception as exc:
        msg = f"{field} must be an integer."
        raise ValueError(msg) from exc

    if minimum is not None and parsed < minimum:
        msg = f"{field} must be >= {minimum}."
        raise ValueError(msg)

    return parsed


def normalize_pagination(request: Request, page: int | None = None, per_page: int | None = None) -> tuple[int, int]:
    if page is None:
        page = int(request.query.get("page", 1))

    if per_page is None:
        per_page = int(request.query.get("per_page", 0))

    if 0 == per_page:
        from app.library.config import Config

        items_per_page: int = int(Config.get_instance().default_pagination)
        per_page = items_per_page // 2 if items_per_page > 50 else items_per_page

    if page < 1:
        msg = "page must be >= 1."
        raise ValueError(msg)

    if per_page < 1 or per_page > 1000:
        msg = "per_page must be between 1 and 1000."
        raise ValueError(msg)

    return int(page), int(per_page)


def build_pagination(total: int, page: int, per_page: int, total_pages: int) -> dict:
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def format_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """
    Format Pydantic ValidationError.

    Args:
        exc: The ValidationError from Pydantic

    Returns:
        List of dicts with loc, msg, and type

    """
    return [
        {
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", "Validation error"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]


def gen_random(length: int = 16) -> str:
    import secrets

    return "".join(secrets.token_urlsafe(length)[:length])
