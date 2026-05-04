import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from app.library.DataStore import StoreType
from app.library.ItemDTO import ItemDTO
from app.library.encoder import Encoder
from app.routes.api.history import item_rename, items_delete
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
async def test_items_delete_uses_bulk_history_status_clear() -> None:
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
async def test_items_delete_uses_bulk_history_id_clear() -> None:
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
async def test_item_rename_requires_new_name() -> None:
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
async def test_item_rename_returns_not_found_when_item_missing() -> None:
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
async def test_item_rename_requires_existing_downloaded_file() -> None:
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
async def test_item_rename_renames_file_and_sidecars() -> None:
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
async def test_item_rename_returns_conflict_on_collision() -> None:
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
