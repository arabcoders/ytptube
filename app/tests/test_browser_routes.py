from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import web

from app.library.encoder import Encoder
from app.routes.api.browser import get_file_info, get_ffprobe, path_actions
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


@pytest.mark.asyncio
async def test_file_info_without_ffprobe(tmp_path: Path, test_client) -> None:
    """File info must still work when ffprobe is missing, with empty probe data."""
    media = tmp_path / "video.mp4"
    media.write_text("video")
    config = SimpleNamespace(download_path=str(tmp_path))
    encoder = Encoder()
    app = Mock()

    async def handler(request):
        return await get_file_info(request, config, encoder, app)

    with patch("app.routes.api.browser.ffprobe_bin", return_value=None):
        client = await test_client({"file_info": handler})
        response = await client.get(url_for("file_info", file="video.mp4"))

    assert response.status == 200
    body = await response.json()
    assert body["ffprobe"] == {}
    assert body["mimetype"] == "video/mp4"


@pytest.mark.asyncio
async def test_ffprobe_endpoint_unavailable(tmp_path: Path, test_client) -> None:
    """The ffprobe endpoint reports a clean error when the binary is missing."""
    media = tmp_path / "video.mp4"
    media.write_text("video")
    config = SimpleNamespace(download_path=str(tmp_path))
    encoder = Encoder()
    app = Mock()

    async def handler(request):
        return await get_ffprobe(request, config, encoder, app)

    with patch("app.routes.api.browser.ffprobe_bin", return_value=None):
        client = await test_client({"ffprobe": handler})
        response = await client.get(url_for("ffprobe", file="video.mp4"))

    assert response.status == web.HTTPServiceUnavailable.status_code
    body = await response.json()
    assert body["code"] == "FFPROBE_UNAVAILABLE"
