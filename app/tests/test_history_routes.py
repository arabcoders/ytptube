import json
from types import SimpleNamespace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web

from app.library.DataStore import StoreType
from app.library.cache import Cache
from app.library.ItemDTO import ItemDTO
from app.library.encoder import Encoder
from app.routes.api import history
from app.routes.api.history import item_rename, item_thumbnail, items_delete
from app.tests.helpers import temporary_test_dir


class _FakeRequest:
    def __init__(self, *, payload: dict[str, Any] | None = None) -> None:
        self._payload = payload or {}
        self.query: dict[str, str] = {}
        self.match_info: dict[str, str] = {}
        self.body_exists = bool(payload)

    async def json(self) -> dict[str, Any]:
        return self._payload


def _make_download(
    *,
    filename: str | None = None,
    folder: str = "",
    download_dir: str | None = None,
    status: str = "finished",
) -> SimpleNamespace:
    base_dir = download_dir or "/downloads"
    original_post_init = ItemDTO.__post_init__
    ItemDTO.__post_init__ = lambda self: None

    try:
        item = ItemDTO(
            id="test-id",
            title="Test Video",
            url="https://example.com/watch?v=test-id",
            folder=folder,
            status=status,
            filename=filename,
            download_dir=base_dir,
        )
    finally:
        ItemDTO.__post_init__ = original_post_init

    return SimpleNamespace(info=item)


@pytest.mark.asyncio
async def test_items_delete_status() -> None:
    request = _FakeRequest(payload={"type": StoreType.HISTORY.value, "status": "finished,skip", "remove_file": False})
    queue = Mock()
    queue.clear_by_status = AsyncMock(return_value={"deleted": 12})
    encoder = Encoder()

    response = await items_delete(request, queue, encoder)

    assert response.status == 200
    queue.clear_by_status.assert_awaited_once_with("finished,skip", remove_file=False)
    body = json.loads(response.body.decode("utf-8"))
    assert body == {"items": {}, "deleted": 12}


@pytest.mark.asyncio
async def test_items_delete_ids() -> None:
    request = _FakeRequest(payload={"type": StoreType.HISTORY.value, "ids": ["a", "b"], "remove_file": False})
    queue = Mock()
    queue.clear_bulk = AsyncMock(return_value={"deleted": 2})
    encoder = Encoder()

    response = await items_delete(request, queue, encoder)

    assert response.status == 200
    queue.clear_bulk.assert_awaited_once_with(["a", "b"], remove_file=False)
    body = json.loads(response.body.decode("utf-8"))
    assert body == {"items": {}, "deleted": 2}


@pytest.mark.asyncio
async def test_item_rename_needs_name() -> None:
    request = _FakeRequest(payload={})
    request.match_info["id"] = "item-1"
    queue = SimpleNamespace(
        done=SimpleNamespace(get_by_id=AsyncMock(return_value=_make_download(filename="video.mp4")))
    )
    encoder = Encoder()
    notify = Mock()
    config = SimpleNamespace(download_path="/downloads")

    response = await item_rename(request, queue, encoder, notify, config)

    assert response.status == 400
    body = json.loads(response.body.decode("utf-8"))
    assert body == {"error": "no data provided."}


@pytest.mark.asyncio
async def test_item_rename_missing() -> None:
    request = _FakeRequest(payload={"new_name": "renamed.mp4"})
    request.match_info["id"] = "missing"
    queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=None)))
    encoder = Encoder()
    notify = Mock()
    config = SimpleNamespace(download_path="/downloads")

    response = await item_rename(request, queue, encoder, notify, config)

    assert response.status == 404
    body = json.loads(response.body.decode("utf-8"))
    assert body == {"error": "item 'missing' not found."}


@pytest.mark.asyncio
async def test_item_rename_needs_file() -> None:
    request = _FakeRequest(payload={"new_name": "renamed.mp4"})
    request.match_info["id"] = "item-1"
    item = _make_download(filename="video.mp4")
    queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
    encoder = Encoder()
    notify = Mock()
    config = SimpleNamespace(download_path="/downloads")

    item.info.get_file = lambda download_path=None: None

    response = await item_rename(request, queue, encoder, notify, config)

    assert response.status == 400
    body = json.loads(response.body.decode("utf-8"))
    assert body == {"error": "item has no downloaded file."}


@pytest.mark.asyncio
async def test_item_rename_sidecars() -> None:
    with temporary_test_dir("history-rename") as temp_dir:
        media = temp_dir / "video.mp4"
        subtitle = temp_dir / "video.en.srt"
        media.write_text("video")
        subtitle.write_text("subtitle")

        request = _FakeRequest(payload={"new_name": "renamed.mp4"})
        request.match_info["id"] = "item-1"
        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        item.info._id = "item-1"
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item), put=AsyncMock()))
        encoder = Encoder()
        notify = Mock()
        config = SimpleNamespace(download_path=str(temp_dir))

        response = await item_rename(request, queue, encoder, notify, config)

        assert response.status == 200
        body = json.loads(response.body.decode("utf-8"))
        assert body["filename"] == "renamed.mp4"
        assert item.info.filename == "renamed.mp4"
        assert (temp_dir / "renamed.mp4").exists()
        assert (temp_dir / "renamed.en.srt").exists()
        assert not media.exists()
        assert not subtitle.exists()
        queue.done.put.assert_awaited_once_with(item, no_notify=True)
        notify.emit.assert_called_once()


@pytest.mark.asyncio
async def test_item_rename_conflict() -> None:
    with temporary_test_dir("history-rename-conflict") as temp_dir:
        media = temp_dir / "video.mp4"
        conflict = temp_dir / "renamed.mp4"
        media.write_text("video")
        conflict.write_text("existing")

        request = _FakeRequest(payload={"new_name": "renamed.mp4"})
        request.match_info["id"] = "item-1"
        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item), put=AsyncMock()))
        encoder = Encoder()
        notify = Mock()
        config = SimpleNamespace(download_path=str(temp_dir))

        response = await item_rename(request, queue, encoder, notify, config)

        assert response.status == 409
        body = json.loads(response.body.decode("utf-8"))
        assert body == {"error": "Destination 'renamed.mp4' already exists"}
        queue.done.put.assert_not_awaited()
        notify.emit.assert_not_called()


@pytest.mark.asyncio
async def test_item_thumbnail_sidecar() -> None:
    with temporary_test_dir("history-thumb-sidecar") as temp_dir:
        media = temp_dir / "video.mp4"
        image = temp_dir / "video.jpg"
        media.write_text("video")
        image.write_text("image")

        request = _FakeRequest()
        request.match_info["id"] = "item-1"
        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
        config = SimpleNamespace(download_path=str(temp_dir), temp_path=str(temp_dir / "tmp"))

        response = await item_thumbnail(request, queue, config)

        assert isinstance(response, web.FileResponse)
        assert response.status == 200
        assert response._path == image


@pytest.mark.asyncio
async def test_item_thumbnail_generated(monkeypatch: pytest.MonkeyPatch) -> None:
    with temporary_test_dir("history-thumb-gen") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")
        cache_dir = temp_dir / "tmp"
        generated = cache_dir / "thumbnails" / "item-1.jpg"

        request = _FakeRequest()
        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        request.match_info["id"] = item.info._id
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
        config = SimpleNamespace(download_path=str(temp_dir), temp_path=str(cache_dir))

        monkeypatch.setattr(history, "pick_local_thumb", lambda _file: None)

        called = {"count": 0}

        async def fake_ensure_thumb(_file: Path, _cache_root: Path, item_id: str | None = None) -> Path:
            called["count"] += 1
            assert item_id == request.match_info["id"]
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text("generated")
            return generated

        monkeypatch.setattr(history, "ensure_thumb", fake_ensure_thumb)

        response = await item_thumbnail(request, queue, config)

        assert isinstance(response, web.FileResponse)
        assert response.status == 200
        assert response._path == generated
        assert called["count"] == 1


@pytest.mark.asyncio
async def test_item_thumbnail_no_thumb(monkeypatch: pytest.MonkeyPatch) -> None:
    with temporary_test_dir("history-thumb-miss") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")

        request = _FakeRequest()
        request.match_info["id"] = "item-1"
        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
        config = SimpleNamespace(download_path=str(temp_dir), temp_path=str(temp_dir / "tmp"))

        monkeypatch.setattr(history, "pick_local_thumb", lambda _file: None)
        monkeypatch.setattr(history, "ensure_thumb", AsyncMock(return_value=None))

        response = await item_thumbnail(request, queue, config)

        assert response.status == 404
        body = json.loads(response.body.decode("utf-8"))
        assert body == {"error": "thumbnail not found."}


@pytest.mark.asyncio
async def test_item_thumbnail_missing_cache() -> None:
    Cache.get_instance().clear()

    request = _FakeRequest()
    request.match_info["id"] = "item-1"

    item = _make_download(filename="video.mp4", download_dir="/downloads")
    seen = {"count": 0}

    def fake_get_file(download_path=None):
        del download_path
        seen["count"] += 1
        return None

    item.info.get_file = fake_get_file
    queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
    config = SimpleNamespace(download_path="/downloads", temp_path="/tmp")

    first = await item_thumbnail(request, queue, config)
    second = await item_thumbnail(request, queue, config)

    assert first.status == 404
    assert second.status == 404
    assert seen["count"] == 1
