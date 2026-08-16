from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.routes.api.browser import path_actions
from app.tests.helpers import url_for


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
async def test_rename_traversal(tmp_path: Path, new_name: str, test_client) -> None:
    media = tmp_path / "video.mp4"
    media.write_text("video")
    config = SimpleNamespace(download_path=str(tmp_path), browser_control_enabled=True)
    queue = SimpleNamespace(done=SimpleNamespace(get_item=AsyncMock(return_value=None)))

    async def handler(request):
        return await path_actions(request, config, queue, Mock())

    client = await test_client({"browser.file.actions": handler})
    response = await client.post(
        url_for("browser.file.actions"),
        json=[{"action": "rename", "path": "video.mp4", "new_name": new_name}],
    )

    assert response.status == 200
    assert (await response.json())[0]["status"] is False
    assert media.exists()
