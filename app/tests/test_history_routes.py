import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from app.library.encoder import Encoder
from app.library.DataStore import StoreType
from app.routes.api.history import items_delete


class _FakeRequest:
    def __init__(self, *, payload: dict[str, Any] | None = None) -> None:
        self._payload = payload or {}
        self.query: dict[str, str] = {}
        self.match_info: dict[str, str] = {}

    async def json(self) -> dict[str, Any]:
        return self._payload


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
