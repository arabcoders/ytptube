import asyncio
import sys
import struct
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError
from aiohttp.test_utils import make_mocked_request
from app.features.streaming import encoding, router, service
from app.features.streaming.library.ffprobe import FFProbeResult
from app.library.config import Config
from app.library.router import RouteType, get_routes
from app.tests.helpers import url_for


@pytest.fixture
def probe() -> AsyncMock:
    result = FFProbeResult()
    result.deserialize(
        {
            "metadata": {"duration": "13", "format_name": "matroska"},
            "audio": [{"index": 4, "codec_type": "audio"}],
            "subtitle": [
                {"index": 7, "codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"},
                {"index": 8, "codec_type": "subtitle", "codec_name": "ass"},
            ],
            "attachment": [
                {
                    "index": 9,
                    "codec_type": "attachment",
                    "tags": {"mimetype": "font/ttf", "filename": "not-the-family.ttf"},
                }
            ],
        }
    )
    return AsyncMock(return_value=result)


@pytest_asyncio.fixture
async def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: AsyncMock):
    config = Config.get_instance()
    config.download_path = str(tmp_path)
    (tmp_path / "video.mkv").write_bytes(b"source")
    monkeypatch.setattr(service, "ffprobe", probe)
    monkeypatch.setattr(service, "ffmpeg_bin", lambda: sys.executable)
    manager = service.PlayerManager(config)
    manager.root = tmp_path / "scratch"
    manager.root.mkdir()
    try:
        yield manager
    finally:
        await asyncio.wait_for(manager.shutdown(web.Application()), 5)


@pytest.mark.asyncio
async def test_reopen_resources(manager: service.PlayerManager, probe: AsyncMock) -> None:
    first = await manager.open("one", "video.mkv")
    second = await manager.open("one", "video.mkv")
    assert first.id != second.id
    assert first.resource is second.resource
    manager.select(first, 4, "e7")
    assert second.audio is None and second.subtitle is None
    assert probe.await_count == 1
    await manager.close(first.id, "one")
    await manager.close(second.id, "one")
    reopened = await manager.open("one", "video.mkv")
    assert reopened.resource is first.resource
    assert probe.await_count == 1


@pytest.mark.asyncio
async def test_stable_urls(manager: service.PlayerManager) -> None:
    first = await manager.open("one", "video.mkv")
    second = await manager.open("one", "video.mkv")
    initial = router.payload(first, manager)
    paired = router.payload(second, manager)
    assert initial["poster"] is None
    for field in ("media_url", "stream_url", "subtitles", "fonts"):
        assert initial[field] == paired[field], f"{field} must not depend on a player lease"
    assert first.id not in initial["media_url"] and "video.mkv" not in initial["media_url"]
    manager.select(first, 4, "e7")
    selected = router.payload(first, manager)
    assert selected["media_url"] == initial["media_url"]
    assert selected["stream_url"].endswith("audio=4&subtitle=e7")
    assert router.payload(second, manager)["stream_url"] == initial["stream_url"]
    await manager.close(first.id, "one")
    await manager.close(second.id, "one")
    manager._drop(first.resource)
    reopened = await manager.open("one", "video.mkv")
    assert reopened.resource is not first.resource
    assert router.payload(reopened, manager)["media_url"] == initial["media_url"]
    isolated = await manager.open("two", "video.mkv")
    assert router.payload(isolated, manager)["media_url"] != initial["media_url"]
    reopened.resource.file.write_bytes(b"replaced source")
    replaced = await manager.open("one", "video.mkv")
    assert router.payload(replaced, manager)["media_url"] != initial["media_url"]


@pytest.mark.asyncio
async def test_track_boundaries(manager: service.PlayerManager) -> None:
    player = await manager.open("one", "video.mkv")
    for audio, subtitle in [(True, None), (0, None), (4, "e4"), (None, "../subtitle")]:
        with pytest.raises(service.PlayerError):
            manager.select(player, audio, subtitle)
    with pytest.raises(service.PlayerError) as error:
        await manager.get(player.id, "two")
    assert error.value.status == 404
    with pytest.raises(service.PlayerError) as error:
        await manager.media(player.resource.id, "two")
    assert error.value.status == 404
    await manager.close(player.id, "two")
    assert await manager.get(player.id, "one") is player
    assert await manager.media(player.resource.id, "one") is player


@pytest.mark.asyncio
async def test_segment_reuse(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    prepared = 0

    async def prepare(_player, _key) -> Path:
        nonlocal prepared
        prepared += 1
        output = manager._root() / f"segment-{prepared}.ts"
        output.write_bytes(b"prepared")
        return output

    monkeypatch.setattr(manager, "_prepare", prepare)
    async with manager.artifact(player, ("segment", 0, 4, None)) as artifact:
        file = artifact.file
    await manager.close(player.id, "one")
    reopened = await manager.open("one", "video.mkv")
    async with manager.artifact(reopened, ("segment", 0, 4, None)) as artifact:
        assert artifact.file == file
    assert prepared == 1
    async with manager.artifact(reopened, ("segment", 0, 4, 7)) as artifact:
        assert artifact.file != file
    assert prepared == 2


@pytest.mark.asyncio
async def test_shared_preparation(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    first = await manager.open("one", "video.mkv")
    second = await manager.open("one", "video.mkv")
    started, joined, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = 0

    async def prepare(_player, _key) -> Path:
        nonlocal calls
        calls += 1
        started.set()
        await asyncio.wait_for(release.wait(), 5)
        output = manager._root() / "shared.ts"
        output.write_bytes(b"complete")
        return output

    monkeypatch.setattr(manager, "_prepare", prepare)

    async def use(player: service.Player) -> bytes:
        if player is second:
            joined.set()
        async with manager.artifact(player, ("segment", 0, None, None)) as artifact:
            return artifact.file.read_bytes()

    tasks = [asyncio.create_task(use(first))]
    try:
        await asyncio.wait_for(started.wait(), 1)
        tasks.append(asyncio.create_task(use(second)))
        await asyncio.wait_for(joined.wait(), 1)
        await asyncio.wait_for(manager.close(first.id, "one"), 1)
        assert not first.resource.flights[("segment", 0, None, None)].task.cancelled()
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 2)
        assert isinstance(results[0], service.PlayerError)
        assert results[1] == b"complete"
        assert calls == 1
    finally:
        release.set()
        for task in tasks:
            task.cancel()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 2)


@pytest.mark.asyncio
async def test_close_cancels(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    started, stopped = asyncio.Event(), asyncio.Event()

    async def prepare(_player, _key) -> Path:
        started.set()
        try:
            await asyncio.wait_for(asyncio.Event().wait(), 5)
        finally:
            stopped.set()
        raise AssertionError

    monkeypatch.setattr(manager, "_prepare", prepare)

    async def use() -> None:
        async with manager.artifact(player, ("segment", 0, None, None)):
            raise AssertionError

    task = asyncio.create_task(use())
    try:
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(manager.close(player.id, "one"), 1)
        assert stopped.is_set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert manager.jobs == 0
    finally:
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)


@pytest.mark.asyncio
async def test_unstarted_close(manager: service.PlayerManager) -> None:
    player = await manager.open("one", "video.mkv")
    encoding = service.Encoding(manager, player.resource, None, None)

    async def pending() -> None:
        await asyncio.wait_for(asyncio.Event().wait(), 5)

    task = encoding.task = asyncio.create_task(pending())
    try:
        async with asyncio.timeout(1):
            await encoding.close()
        assert task.cancelled() and encoding.task is None
        await asyncio.wait_for(encoding.close(), 1)
    finally:
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["empty", "spawn"])
async def test_encoder_fallback(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    player = await manager.open("one", "video.mkv")
    stream = service.Encoding(manager, player.resource, None, None)
    player.resource.encodings[(None, None)] = stream
    monkeypatch.setattr(encoding, "ffmpeg_bin", lambda: sys.executable)
    monkeypatch.setattr(encoding, "select_encoder", AsyncMock(return_value="h264_nvenc"))
    monkeypatch.setattr(encoding.Segments, "_encoders", {})
    monkeypatch.setattr(service, "MAX_JOBS", 1)
    attempts = []

    async def encode(_binary: str, codec: str, _validate) -> None:
        attempts.append(codec)
        if codec == "h264_nvenc":
            if failure == "spawn":
                raise OSError("encoder unavailable")
            return
        file = manager._root() / "fallback.ts"
        file.write_bytes(b"complete")
        player.resource.artifacts[("segment", 0, None, None)] = service.Artifact(
            file=file, content_type="video/mpegts", size=8, touched=0
        )
        stream.next_index += 1

    monkeypatch.setattr(stream, "encode", encode)
    async with asyncio.timeout(2), manager.artifact(player, ("segment", 0, None, None)) as artifact:
        assert artifact.file.read_bytes() == b"complete"
    assert attempts == ["h264_nvenc", "libx264"]
    assert manager.jobs == 0 and manager.pending == 0


@pytest.mark.asyncio
async def test_shutdown_encoders(manager: service.PlayerManager) -> None:
    first = await manager.open("one", "video.mkv")
    second = await manager.open("two", "video.mkv")
    failed = AsyncMock(spec=service.Encoding)
    failed.close.side_effect = service.ProcessExitError("Child exit was not confirmed.")
    sibling = AsyncMock(spec=service.Encoding)
    other = AsyncMock(spec=service.Encoding)
    first.resource.encodings.update({(None, None): failed, (4, None): sibling})
    second.resource.encodings[(None, None)] = other
    try:
        with pytest.raises(service.ProcessExitError):
            await asyncio.wait_for(manager.shutdown(web.Application()), 2)
        sibling.close.assert_awaited_once()
        other.close.assert_awaited_once()
        assert manager.closed and first.resource.encodings == {(None, None): failed}
        assert not second.resource.encodings
    finally:
        first.resource.encodings.clear()


@pytest.mark.asyncio
async def test_truncated_segment(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    stdout, stderr = asyncio.StreamReader(), asyncio.StreamReader()
    stdout.feed_data(b"short")
    stdout.feed_eof()
    stderr.feed_data(b"#EXTM3U\n#EXTINF:6,\n#EXT-X-BYTERANGE:9@0\npipe:1\n")
    stderr.feed_eof()
    child = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)
    release = AsyncMock()
    monkeypatch.setattr(encoding, "spawn", AsyncMock(return_value=child))
    monkeypatch.setattr(encoding, "release", release)
    monkeypatch.setattr(encoding, "select_encoder", AsyncMock(return_value="libx264"))
    monkeypatch.setattr(encoding.Segments, "_encoders", {})
    async with asyncio.timeout(2):
        with pytest.raises(service.StreamingError, match="Unable to prepare"):
            async with manager.artifact(player, ("segment", 0, None, None)):
                raise AssertionError("truncated muxer output must not be delivered")
    release.assert_awaited_once_with(child)
    assert manager.jobs == 0 and not player.resource.artifacts


@pytest.mark.asyncio
async def test_expiry_generation(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr(service, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    player = await manager.open("one", "video.mkv")
    await manager.close(player.id, "one")
    clock[0] += service.IDLE_TTL
    await manager.expire()
    assert not manager.resources
    await manager.open("one", "video.mkv")
    clock[0] += service.PLAYER_TTL
    await manager.expire()
    assert not manager.players and manager.resources
    player = await manager.open("one", "video.mkv")
    player.resource.file.write_bytes(b"replaced-source")
    with pytest.raises(service.PlayerError) as error:
        await manager.get(player.id, "one")
    assert error.value.status == 409
    assert not manager.players and not manager.resources


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["source", "sidecar", "settings"])
async def test_resource_changes(
    manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch, probe: AsyncMock, change: str
) -> None:
    sidecar = Path(manager.config.download_path) / "video.en.vtt"
    sidecar.write_text("WEBVTT\n", encoding="utf-8")
    player = await manager.open("one", "video.mkv")
    if change == "settings":
        monkeypatch.setattr(manager.config, "streamer_acodec", "changed")
    else:
        file = player.resource.file if change == "source" else sidecar
        file.write_bytes(b"replaced")
    with pytest.raises(service.PlayerError) as error:
        await manager.get(player.id, "one")
    assert error.value.status == 409
    reopened = await manager.open("one", "video.mkv")
    assert reopened.resource is not player.resource
    assert probe.await_count == 2


@pytest.mark.asyncio
async def test_extracted_resources(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    family = "Declared Family".encode("utf-16-be")
    table = struct.pack(">HHH", 0, 1, 18) + struct.pack(">HHHHHH", 3, 1, 0x409, 1, len(family), 0) + family
    font = (
        b"\x00\x01\x00\x00"
        + struct.pack(">HHHH", 1, 0, 0, 0)
        + struct.pack(">4sIII", b"name", 0, 28, len(table))
        + table
    )
    calls = []

    async def run(_binary: str, args: list[str], *, output: Path, max_bytes: int, **_kwargs) -> tuple[int, bytes, str]:
        calls.append(args)
        if "-dump_attachment:9" in args:
            assert max_bytes == service.FONT_MAX_BYTES
            output.write_bytes(font)
        else:
            assert "0:8" in args and "copy" in args
            output.write_bytes(b"[Script Info]\nTitle: Embedded\n")
        return 0, b"", ""

    monkeypatch.setattr(service, "run", run)
    player = await manager.open("one", "video.mkv")
    for _ in range(2):
        async with manager.artifact(player, ("font", "f9")) as artifact:
            assert artifact.metadata == {"families": ["Declared Family"], "weight": "400", "style": "normal"}
        async with manager.artifact(player, ("subtitle", "e8")) as artifact:
            assert artifact.content_type == "text/x-ssa"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_pinned_capacity(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    monkeypatch.setattr(service, "MAX_CACHE_BYTES", service.SEGMENT_MAX_BYTES)

    async def prepare(_player, key: tuple) -> Path:
        file = manager._root() / f"segment-{key[1]}.ts"
        file.write_bytes(b"prepared")
        return file

    monkeypatch.setattr(manager, "_prepare", prepare)
    async with manager.artifact(player, ("segment", 0, None, None)) as artifact:
        first = artifact.file
        with pytest.raises(service.PlayerError) as error:
            async with manager.artifact(player, ("segment", 1, None, None)):
                raise AssertionError
        assert error.value.status == 503
        assert first.exists()
    async with manager.artifact(player, ("segment", 1, None, None)) as artifact:
        assert artifact.file.exists() and not first.exists()


@pytest.mark.asyncio
async def test_player_routes(manager: service.PlayerManager, test_client) -> None:
    (Path(manager.config.download_path) / "video.jpg").write_bytes(b"artwork")
    handlers = {
        name: partial(route.handler, players=manager)
        for name, route in get_routes(RouteType.HTTP).items()
        if route.handler.__module__ == router.__name__ and route.path.startswith("api/player/")
    }
    client = await test_client(handlers)
    async with asyncio.timeout(5):
        response = await client.post(url_for("player_open", file="video.mkv"))
        assert response.status == 200
        body = await response.json()
        assert body["title"] == "video"
        assert body["mimetype"] == "video/x-matroska"
        assert body["poster"] == "video.jpg"
        assert body["ffprobe"]["metadata"]["format_name"] == "matroska"
        id = body["player_id"]
        assert body["media_url"].endswith(f"/media/{manager.players[id].resource.id}/file")
        assert body["audio_tracks"][0]["stream_index"] == 4
        assert body["subtitles"][0]["renderer"] == "bitmap"
        response = await client.get(body["media_url"], headers={"Range": "bytes=1-3"})
        assert response.status == 206 and await response.read() == b"our"
        assert response.headers["Cache-Control"] == "private, max-age=300"
        etag = response.headers["ETag"]
        response = await client.get(body["media_url"], headers={"If-None-Match": etag})
        assert response.status == 304 and await response.read() == b""
        response = await client.head(body["media_url"])
        assert response.status == 200 and response.headers["Content-Length"] == "6"
        assert await response.read() == b""
        response = await client.put(
            url_for("player_refresh", id=id), json={"audio_stream_index": 4, "subtitle_track_id": "e7"}
        )
        assert response.status == 200
        selected = await response.json()
        response = await client.get(selected["stream_url"])
        playlist = await response.text()
        assert response.status == 200
        assert playlist.splitlines()[:5] == [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            "#EXT-X-TARGETDURATION:6",
            "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD",
        ]
        assert "#EXTINF:1.000000" in playlist and playlist.endswith("#EXT-X-ENDLIST")
        assert "segments/2.ts?audio=4&subtitle=e7" in playlist
        response = await client.get(url_for("player_segment", media=manager.players[id].resource.id, index="3"))
        assert response.status == 404
        response = await client.put(url_for("player_refresh", id=id), json={"audio_stream_index": True})
        assert response.status == 400
        manager.players[id].resource.file.write_bytes(b"replacement")
        response = await client.get(body["media_url"])
        assert response.status == 409
        for _ in range(2):
            response = await client.delete(url_for("player_close", id=id))
            assert response.status == 204


@pytest.mark.asyncio
async def test_sidecar_delivery(manager: service.PlayerManager, test_client) -> None:
    root = Path(manager.config.download_path)
    sources = {
        "vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nEnglish\n",
        "srt": "1\n00:00:00,000 --> 00:00:01,000\nEnglish\n",
        "ass": "[Script Info]\nTitle: Demo\n",
    }
    for fmt, text in sources.items():
        (root / f"video.en.{fmt}").write_text(text, encoding="utf-8")
    handlers: dict[str, Callable[[web.Request], Awaitable[web.StreamResponse]]] = {
        name: partial(route.handler, players=manager)
        for name, route in get_routes(RouteType.HTTP).items()
        if route.handler.__module__ == router.__name__ and route.path.startswith("api/player/")
    }
    finished = asyncio.Event()

    async def deliver(request: web.Request) -> web.StreamResponse:
        try:
            return await router.player_artifact(request, manager)
        finally:
            finished.set()

    handlers["player_subtitle"] = deliver
    client = await test_client(handlers)
    async with asyncio.timeout(5):
        response = await client.post(url_for("player_open", file="video.mkv"))
        assert response.status == 200
        body = await response.json()
        tracks = [track for track in body["subtitles"] if track["id"].startswith("x")]
        assert [track["source_format"] for track in tracks] == ["vtt", "srt", "ass"]
        for track in tracks:
            finished.clear()
            try:
                response = await client.get(track["url"])
                assert response.status == 200
                text = await response.text()
                if track["source_format"] == "ass":
                    assert response.content_type == "text/x-ssa" and track["renderer"] == "assjs"
                    assert text == sources["ass"]
                else:
                    assert response.content_type == "text/vtt" and track["renderer"] == "native"
                    assert text.startswith("WEBVTT") and "English" in text
            finally:
                await asyncio.wait_for(finished.wait(), 2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change,shared",
    [("close", False), ("expiry", False), ("generation", False), ("disconnect", False), ("disconnect", True)],
)
async def test_delivery_guard(
    manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch, change: str, shared: bool
) -> None:
    player = await manager.open("shared", "video.mkv")
    if shared:
        await manager.open("shared", "video.mkv")
    encoding = AsyncMock(spec=service.Encoding)
    player.resource.encodings[(None, None)] = encoding
    file = manager._root() / "prepared.ts"
    file.write_bytes(b"x" * 131072)
    monkeypatch.setattr(manager, "_prepare", AsyncMock(return_value=file))
    chunks: list[bytes] = []
    request = make_mocked_request("GET", "/", match_info={"media": player.resource.id, "index": "0"})

    class Response:
        def __init__(self, **_kwargs):
            self.closed = False

        async def prepare(self, _request) -> None:
            pass

        async def write(self, chunk: bytes) -> None:
            if change == "disconnect":
                raise ClientConnectionResetError("Cannot write to closing transport")
            chunks.append(chunk)
            if change == "close":
                await manager.close(player.id, player.owner)
            elif change == "expiry":
                player.expires = 0
            else:
                player.resource.file.write_bytes(b"replacement")

        async def write_eof(self) -> None:
            raise AssertionError("interrupted delivery must not report a complete response")

        def force_close(self) -> None:
            self.closed = True

    monkeypatch.setattr(router.web, "StreamResponse", Response)
    response = await asyncio.wait_for(router.player_artifact(request, manager), 2)
    assert response.closed
    assert len(chunks) == (0 if change == "disconnect" else 1)
    assert all(artifact.pins == 0 for artifact in player.resource.artifacts.values())
    if shared:
        encoding.close.assert_not_awaited()
    else:
        encoding.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_media_ownership(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    first = await manager.open("one", "video.mkv")
    second = await manager.open("one", "video.mkv")
    started, release = asyncio.Event(), asyncio.Event()

    async def prepare(_player, _key) -> Path:
        started.set()
        await asyncio.wait_for(release.wait(), 3)
        file = manager._root() / "shared.ts"
        file.write_bytes(b"complete")
        return file

    async def use(player: service.Player, index: int) -> bytes:
        async with manager.artifact(player, ("segment", index, None, None), shared=True) as artifact:
            return artifact.file.read_bytes()

    monkeypatch.setattr(manager, "_prepare", prepare)
    task = asyncio.create_task(use(first, 0))
    try:
        await asyncio.wait_for(started.wait(), 1)
        first.expires = 0
        assert await manager.media(first.resource.id, "one") is second
        await asyncio.wait_for(manager.close(first.id, "one"), 1)
        assert not first.resource.flights[("segment", 0, None, None)].task.cancelled()
        assert await manager.media(first.resource.id, "one") is second
        release.set()
        assert await asyncio.wait_for(task, 2) == b"complete"
        started.clear()
        release.clear()
        task = asyncio.create_task(use(second, 1))
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.wait_for(manager.close(second.id, "one"), 1)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert manager.jobs == 0 and not first.resource.flights
    finally:
        release.set()
        task.cancel()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 2)
