from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.features.ytdlp import router


class _Request:
    def __init__(self, query: dict[str, str]) -> None:
        self.query = query


class _Cache:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self.value: dict[str, Any] | None = None

    def hash(self, value: str) -> str:
        self.keys.append(value)
        return value

    def has(self, _key: str) -> bool:
        return False

    def set(self, *, key: str, value: dict[str, Any], ttl: int) -> None:
        self.value = value


class _Presets:
    def get(self, _name: str) -> bool:
        return True


class _Options:
    def preset(self, _name: str) -> _Options:
        return self

    def get_all(self) -> dict[str, Any]:
        return {}


@pytest.mark.asyncio
async def test_info_preserves_playlist_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    info = {
        "_type": "playlist",
        "title": "Playlist",
        "entries": [{"url": "https://example.com/video", "title": "Video"}],
    }
    fetch = AsyncMock(return_value=(info, []))
    cache = _Cache()
    config = SimpleNamespace(default_preset="default", allow_internal_urls=False)

    monkeypatch.setattr(router, "validate_url", lambda *_args: True)
    monkeypatch.setattr(router.Presets, "get_instance", lambda: _Presets())
    monkeypatch.setattr(router.YTDLPOpts, "get_instance", lambda: _Options())
    monkeypatch.setattr(router, "fetch_info", fetch)

    response = await router.get_info(
        _Request({"url": "https://example.com/playlist", "entries": "true"}),
        cache,
        config,
    )

    assert response.status == 200
    assert json.loads(response.body.decode("utf-8"))["entries"] == info["entries"]
    call = fetch.await_args
    assert call is not None
    assert call.kwargs["sanitize_info"] is False
    assert cache.keys[0].endswith(":entries")
