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
    def __init__(self, wait: str | None = None) -> None:
        self.wait = wait

    def preset(self, _name: str) -> _Options:
        return self

    def get_all(self) -> dict[str, Any]:
        opts: dict[str, Any] = {"noplaylist": True}
        if self.wait is not None:
            opts["extractor_args"] = {"generic": {"wait": [self.wait]}}
        return opts


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
    assert "noplaylist" not in call.kwargs["config"]
    assert call.kwargs["config"]["extract_flat"] == "in_playlist"
    assert call.kwargs["config"]["skip_download"] is True
    assert call.kwargs["config"]["extractor_args"]["generic"]["wait"] == ["10"]
    assert cache.keys[0].endswith(":entries")


@pytest.mark.asyncio
@pytest.mark.parametrize(("wait", "expected"), [("3", "3"), ("30", "10")])
async def test_info_caps_browser_wait(
    monkeypatch: pytest.MonkeyPatch,
    wait: str,
    expected: str,
) -> None:
    fetch = AsyncMock(return_value=({"title": "Playlist", "entries": []}, []))
    config = SimpleNamespace(default_preset="default", allow_internal_urls=False)

    monkeypatch.setattr(router, "validate_url", lambda *_args: True)
    monkeypatch.setattr(router.Presets, "get_instance", lambda: _Presets())
    monkeypatch.setattr(router.YTDLPOpts, "get_instance", lambda: _Options(wait))
    monkeypatch.setattr(router, "fetch_info", fetch)

    response = await router.get_info(
        _Request({"url": "https://example.com/playlist", "entries": "true"}),
        _Cache(),
        config,
    )

    assert response.status == 200
    call = fetch.await_args
    assert call is not None
    assert call.kwargs["config"]["extractor_args"]["generic"]["wait"] == [expected]
