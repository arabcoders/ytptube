from types import SimpleNamespace
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from app.library.DataStore import StoreType
from app.library.cache import Cache
from app.library.ItemDTO import ItemDTO
from app.library.encoder import Encoder
from app.routes.api import history
from app.routes.api.history import item_rename, item_thumbnail, items_delete, items_live, items_retry
from app.tests.helpers import temporary_test_dir, url_for


async def _request(test_client, route: str, handler, method: str = "GET", *, query=None, params=None, payload=None):
    client = await test_client({route: handler})
    return await client.request(method, url_for(route, query=query, **(params or {})), json=payload)


def _make_download(
    *,
    filename: str | None = None,
    folder: str = "",
    download_dir: str | None = None,
    status: str = "finished",
) -> SimpleNamespace:
    base_dir = download_dir or "/downloads"
    original_post_init = ItemDTO.__post_init__
    cls: Any = ItemDTO
    cls.__post_init__ = lambda self: None

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
async def test_items_delete_status(test_client) -> None:
    queue = Mock()
    queue.clear_by_status = AsyncMock(return_value={"deleted": 12})
    encoder = Encoder()

    async def handler(request):
        return await items_delete(request, queue, encoder)

    response = await _request(
        test_client,
        "items_delete",
        handler,
        "DELETE",
        payload={"type": StoreType.HISTORY.value, "status": "finished,skip", "remove_file": False},
    )

    assert response.status == 200
    queue.clear_by_status.assert_awaited_once_with("finished,skip", remove_file=False)
    body = await response.json()
    assert body == {"items": {}, "deleted": 12}


@pytest.mark.asyncio
async def test_items_delete_ids(test_client) -> None:
    queue = Mock()
    queue.clear_bulk = AsyncMock(return_value={"deleted": 2})
    encoder = Encoder()

    async def handler(request):
        return await items_delete(request, queue, encoder)

    response = await _request(
        test_client,
        "items_delete",
        handler,
        "DELETE",
        payload={"type": StoreType.HISTORY.value, "ids": ["a", "b"], "remove_file": False},
    )

    assert response.status == 200
    queue.clear_bulk.assert_awaited_once_with(["a", "b"], remove_file=False)
    body = await response.json()
    assert body == {"items": {}, "deleted": 2}


@pytest.mark.asyncio
async def test_retry_ids(test_client) -> None:
    queue = Mock(retry=AsyncMock(return_value=2))

    async def handler(request):
        return await items_retry(request, queue, Encoder())

    response = await _request(test_client, "items_retry", handler, "POST", payload={"ids": ["a", "b"]})

    assert response.status == 202
    queue.retry.assert_awaited_once_with(ids=["a", "b"], status=None)


@pytest.mark.asyncio
async def test_retry_status(test_client) -> None:
    queue = Mock(retry=AsyncMock(return_value=12))

    async def handler(request):
        return await items_retry(request, queue, Encoder())

    response = await _request(test_client, "items_retry", handler, "POST", payload={"status": "!finished,!skip"})

    assert response.status == 202
    queue.retry.assert_awaited_once_with(ids=None, status="!finished,!skip")


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"ids": "a"}, {"ids": [1]}, {"ids": [" "]}, {"status": 1}])
async def test_retry_invalid(payload: dict[str, Any], test_client) -> None:
    async def handler(request):
        return await items_retry(request, Mock(), Encoder())

    response = await _request(test_client, "items_retry", handler, "POST", payload=payload)

    assert response.status == 400


@pytest.mark.asyncio
async def test_items_live_metadata(test_client) -> None:
    queue = Mock()
    queue.live_queue = Mock(
        return_value={"queue": {"a": {"title": "A"}}, "queue_count": 3, "queue_loaded": 1, "queue_limit": 1}
    )
    queue.done.get_total_count = AsyncMock(return_value=7)
    encoder = Encoder()
    config = SimpleNamespace(queue_display_limit=1)

    async def handler(request):
        return await items_live(request, queue, encoder, config)

    response = await _request(test_client, "items_live", handler)

    assert response.status == 200
    queue.live_queue.assert_called_once_with(1)
    body = await response.json()
    assert body["queue_count"] == 3
    assert body["queue_loaded"] == 1
    assert body["queue_limit"] == 1
    assert body["history_count"] == 7


@pytest.mark.asyncio
async def test_items_live_limit_query(test_client) -> None:
    queue = Mock()
    queue.live_queue = Mock(return_value={"queue": {}, "queue_count": 0, "queue_loaded": 0, "queue_limit": 25})
    queue.done.get_total_count = AsyncMock(return_value=0)
    encoder = Encoder()
    config = SimpleNamespace(queue_display_limit=1)

    async def handler(request):
        return await items_live(request, queue, encoder, config)

    response = await _request(test_client, "items_live", handler, query={"limit": "25"})

    assert response.status == 200
    queue.live_queue.assert_called_once_with(25)


@pytest.mark.asyncio
async def test_items_live_bad_limit(test_client) -> None:
    queue = Mock()
    queue.live_queue = Mock()
    encoder = Encoder()
    config = SimpleNamespace(queue_display_limit=1)

    async def handler(request):
        return await items_live(request, queue, encoder, config)

    response = await _request(test_client, "items_live", handler, query={"limit": "many"})

    assert response.status == 400
    queue.live_queue.assert_not_called()


@pytest.mark.asyncio
async def test_item_rename_needs_name(test_client) -> None:
    queue = SimpleNamespace(
        done=SimpleNamespace(get_by_id=AsyncMock(return_value=_make_download(filename="video.mp4")))
    )
    encoder = Encoder()
    notify = Mock()
    config = SimpleNamespace(download_path="/downloads")

    async def handler(request):
        return await item_rename(request, queue, encoder, notify, config)

    response = await _request(test_client, "history.item.rename", handler, "POST", params={"id": "item-1"}, payload={})

    assert response.status == 400
    body = await response.json()
    assert body["error"] == "no data provided."


@pytest.mark.asyncio
async def test_item_rename_missing(test_client) -> None:
    queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=None)))
    encoder = Encoder()
    notify = Mock()
    config = SimpleNamespace(download_path="/downloads")

    async def handler(request):
        return await item_rename(request, queue, encoder, notify, config)

    response = await _request(
        test_client,
        "history.item.rename",
        handler,
        "POST",
        params={"id": "missing"},
        payload={"new_name": "renamed.mp4"},
    )

    assert response.status == 404
    body = await response.json()
    assert body["error"] == "item 'missing' not found."


@pytest.mark.asyncio
async def test_item_rename_needs_file(test_client) -> None:
    item = _make_download(filename="video.mp4")
    queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
    encoder = Encoder()
    notify = Mock()
    config = SimpleNamespace(download_path="/downloads")

    item.info.get_file = lambda download_path=None: None

    async def handler(request):
        return await item_rename(request, queue, encoder, notify, config)

    response = await _request(
        test_client,
        "history.item.rename",
        handler,
        "POST",
        params={"id": "item-1"},
        payload={"new_name": "renamed.mp4"},
    )

    assert response.status == 400
    body = await response.json()
    assert body["error"] == "item has no downloaded file."


@pytest.mark.asyncio
async def test_item_rename_sidecars(test_client) -> None:
    with temporary_test_dir("history-rename") as temp_dir:
        media = temp_dir / "video.mp4"
        subtitle = temp_dir / "video.en.srt"
        media.write_text("video")
        subtitle.write_text("subtitle")

        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        item.info._id = "item-1"
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item), put=AsyncMock()))
        encoder = Encoder()
        notify = Mock()
        config = SimpleNamespace(download_path=str(temp_dir))

        async def handler(request):
            return await item_rename(request, queue, encoder, notify, config)

        response = await _request(
            test_client,
            "history.item.rename",
            handler,
            "POST",
            params={"id": "item-1"},
            payload={"new_name": "renamed.mp4"},
        )

        assert response.status == 200
        body = await response.json()
        assert body["filename"] == "renamed.mp4"
        assert item.info.filename == "renamed.mp4"
        assert (temp_dir / "renamed.mp4").exists()
        assert (temp_dir / "renamed.en.srt").exists()
        assert not media.exists()
        assert not subtitle.exists()
        queue.done.put.assert_awaited_once_with(item, no_notify=True)
        notify.emit.assert_called_once()


@pytest.mark.asyncio
async def test_item_rename_conflict(test_client) -> None:
    with temporary_test_dir("history-rename-conflict") as temp_dir:
        media = temp_dir / "video.mp4"
        conflict = temp_dir / "renamed.mp4"
        media.write_text("video")
        conflict.write_text("existing")

        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item), put=AsyncMock()))
        encoder = Encoder()
        notify = Mock()
        config = SimpleNamespace(download_path=str(temp_dir))

        async def handler(request):
            return await item_rename(request, queue, encoder, notify, config)

        response = await _request(
            test_client,
            "history.item.rename",
            handler,
            "POST",
            params={"id": "item-1"},
            payload={"new_name": "renamed.mp4"},
        )

    assert response.status == 409
    body = await response.json()
    assert body["error"] == "Destination 'renamed.mp4' already exists"
    queue.done.put.assert_not_awaited()
    notify.emit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("new_name", ["../outside.mp4", "sub/file.mp4", "/tmp/outside.mp4", "video\x00.mp4"])
async def test_item_rename_traversal(new_name: str, test_client) -> None:
    with temporary_test_dir("history-rename-traversal") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")
        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item), put=AsyncMock()))
        notify = Mock()

        config = SimpleNamespace(download_path=str(temp_dir))

        async def handler(request):
            return await item_rename(request, queue, Encoder(), notify, config)

        response = await _request(
            test_client, "history.item.rename", handler, "POST", params={"id": "item-1"}, payload={"new_name": new_name}
        )

        assert response.status == 400
        assert (await response.json())["code"] == "INVALID"
        assert media.exists()
        queue.done.put.assert_not_awaited()
        notify.emit.assert_not_called()


@pytest.mark.asyncio
async def test_item_thumbnail_sidecar(test_client) -> None:
    with temporary_test_dir("history-thumb-sidecar") as temp_dir:
        media = temp_dir / "video.mp4"
        image = temp_dir / "video.jpg"
        media.write_text("video")
        image.write_text("image")

        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
        config = SimpleNamespace(download_path=str(temp_dir), temp_path=str(temp_dir / "tmp"))

        async def handler(request):
            return await item_thumbnail(request, queue, config)

        response = await _request(test_client, "history.item.thumbnail", handler, params={"id": "item-1"})

        assert response.status == 200
        assert await response.text() == "image"


@pytest.mark.asyncio
async def test_item_thumbnail_generated(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    with temporary_test_dir("history-thumb-gen") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")
        cache_dir = temp_dir / "tmp"
        generated = cache_dir / "thumbnails" / "item-1.jpg"

        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
        config = SimpleNamespace(download_path=str(temp_dir), temp_path=str(cache_dir))

        monkeypatch.setattr(history, "pick_local_thumb", lambda _file: None)

        called = {"count": 0}

        async def fake_ensure_thumb(_file: Path, _cache_root: Path, item_id: str | None = None) -> Path:
            called["count"] += 1
            assert item_id == item.info._id
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text("generated")
            return generated

        monkeypatch.setattr(history, "ensure_thumb", fake_ensure_thumb)

        async def handler(request):
            return await item_thumbnail(request, queue, config)

        response = await _request(test_client, "history.item.thumbnail", handler, params={"id": item.info._id})

        assert response.status == 200
        assert await response.text() == "generated"
        assert called["count"] == 1


@pytest.mark.asyncio
async def test_item_thumbnail_no_thumb(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    with temporary_test_dir("history-thumb-miss") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")

        item = _make_download(filename="video.mp4", download_dir=str(temp_dir))
        queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
        config = SimpleNamespace(download_path=str(temp_dir), temp_path=str(temp_dir / "tmp"))

        monkeypatch.setattr(history, "pick_local_thumb", lambda _file: None)
        monkeypatch.setattr(history, "ensure_thumb", AsyncMock(return_value=None))

        async def handler(request):
            return await item_thumbnail(request, queue, config)

        response = await _request(test_client, "history.item.thumbnail", handler, params={"id": "item-1"})

    assert response.status == 404
    body = await response.json()
    assert body["error"] == "thumbnail not found."


@pytest.mark.asyncio
async def test_item_thumbnail_missing_cache(test_client) -> None:
    Cache.get_instance().clear()

    item = _make_download(filename="video.mp4", download_dir="/downloads")
    seen = {"count": 0}

    def fake_get_file(download_path=None):
        del download_path
        seen["count"] += 1
        return None

    item.info.get_file = fake_get_file
    queue = SimpleNamespace(done=SimpleNamespace(get_by_id=AsyncMock(return_value=item)))
    config = SimpleNamespace(download_path="/downloads", temp_path="/tmp")

    async def handler(request):
        return await item_thumbnail(request, queue, config)

    client = await test_client({"history.item.thumbnail": handler})
    path = url_for("history.item.thumbnail", id="item-1")
    first = await client.get(path)
    second = await client.get(path)

    assert first.status == 404
    assert second.status == 404
    assert seen["count"] == 1
