import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.routes.api.browser import path_actions


class _Request:
    def __init__(self, payload: list[dict[str, str]]) -> None:
        self.payload = payload

    async def json(self) -> list[dict[str, str]]:
        return self.payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "new_name",
    [
        "../outside.mp4",
        "sub/file.mp4",
        "sub/../file.mp4",
        "/tmp/outside.mp4",
        "file.mp4/",
        "file\x00.mp4",
        ".",
        "..",
    ],
)
async def test_rename_traversal(tmp_path: Path, new_name: str) -> None:
    media = tmp_path / "video.mp4"
    media.write_text("video")
    request = _Request([{"action": "rename", "path": "video.mp4", "new_name": new_name}])
    config = SimpleNamespace(download_path=str(tmp_path), browser_control_enabled=True)
    queue = SimpleNamespace(done=SimpleNamespace(get_item=AsyncMock(return_value=None)))

    response = await path_actions(request, config, queue, Mock())

    assert response.status == 200
    assert json.loads(response.body)[0]["status"] is False
    assert media.exists()
