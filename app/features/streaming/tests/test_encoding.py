import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiohttp import web

from app.features.streaming import encoding, service
from app.features.streaming.encoding import read_ranges
from app.features.streaming.library.ffprobe import FFProbeResult
from app.features.streaming.types import StreamingError
from app.features.streaming.utils import ENCODE_AHEAD, SEGMENT_DURATION
from app.library.config import Config

MEDIA_DURATION = 49.0


def segment_bytes(index: int) -> bytes:
    return f"<segment:{index}>".encode() * 8


def playlist(count: int, start: int = 0, *, endlist: bool = True) -> list[bytes]:
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:6",
        "#EXT-X-TARGETDURATION:6",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:VOD",
    ]
    snapshots = []
    offset = 0
    for position in range(count):
        index = start + position
        length = len(segment_bytes(index))
        lines += [
            f"#EXTINF:{min(SEGMENT_DURATION, MEDIA_DURATION - index * SEGMENT_DURATION):.6f},",
            f"#EXT-X-BYTERANGE:{length}@{offset}",
            "pipe:1",
        ]
        snapshots.append(("\n".join(lines) + "\n").encode())
        offset += length
    if endlist and snapshots:
        snapshots[-1] += b"#EXT-X-ENDLIST\n"
    return snapshots


class FakeChild:
    def __init__(self, stdout: list[bytes], stderr: list[bytes], *, code: int | None = 0):
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        for chunk in stdout:
            self.stdout.feed_data(chunk)
        for snapshot in stderr:
            self.stderr.feed_data(snapshot)
        self.returncode: int | None = None
        self.signals: list[int] = []
        self._exited = asyncio.Event()
        if code is not None:
            self.exit(code)

    def exit(self, code: int) -> None:
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        if self.returncode is None:
            self.returncode = code
        self._exited.set()

    async def wait(self) -> int:
        await self._exited.wait()
        assert self.returncode is not None
        return self.returncode

    def terminate(self) -> None:
        self.exit(-15)

    def kill(self) -> None:
        self.exit(-9)

    def send_signal(self, sig: int) -> None:
        self.signals.append(int(sig))


def media_child(start: int, count: int, *, live: bool = False) -> FakeChild:
    stdout = [segment_bytes(start + position) for position in range(count)]
    return FakeChild(stdout, playlist(count, start, endlist=not live), code=None if live else 0)


class Spawner:
    def __init__(self, *children: FakeChild):
        self.children = list(children)
        self.args: list[list[str]] = []

    async def __call__(self, _binary: str, args: list[str]) -> FakeChild:
        self.args.append(args)
        if not self.children:
            msg = f"unexpected ffmpeg spawn #{len(self.args)}"
            raise AssertionError(msg)
        return self.children.pop(0)


def patch_spawn(monkeypatch: pytest.MonkeyPatch, spawner: Spawner) -> None:
    monkeypatch.setattr(encoding, "spawn", spawner)


def published(resource: service.Resource) -> set[int]:
    return {key[1] for key in resource.artifacts if key[0] == "segment"}


async def quiesce(turns: int = 100) -> None:
    # Buffered fake output drains through deterministic loop turns instead of wall-clock waits.
    for _ in range(turns):
        await asyncio.sleep(0)


async def drained(snapshots: list[str]) -> list[tuple[int, float]]:
    reader = asyncio.StreamReader()
    for snapshot in snapshots:
        reader.feed_data(snapshot.encode())
    reader.feed_eof()
    ranges: asyncio.Queue[tuple[int, float]] = asyncio.Queue()
    await asyncio.wait_for(read_ranges(reader, ranges), 2)
    collected = []
    while not ranges.empty():
        collected.append(ranges.get_nowait())
    return collected


@pytest.fixture
def probe() -> AsyncMock:
    result = FFProbeResult()
    result.deserialize(
        {
            "metadata": {"duration": "49", "format_name": "matroska"},
            "video": [{"index": 1, "codec_type": "video", "codec_name": "h264"}],
            "audio": [{"index": 4, "codec_type": "audio"}],
            "subtitle": [{"index": 7, "codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"}],
        }
    )
    return AsyncMock(return_value=result)


async def select_configured(configured: str) -> str:
    return configured or "libx264"


@pytest_asyncio.fixture
async def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: AsyncMock):
    config = Config.get_instance()
    config.download_path = str(tmp_path)
    (tmp_path / "video.mkv").write_bytes(b"source")
    monkeypatch.setattr(service, "ffprobe", probe)
    monkeypatch.setattr(service, "ffmpeg_bin", lambda: sys.executable)
    monkeypatch.setattr(encoding, "ffmpeg_bin", lambda: sys.executable)
    monkeypatch.setattr(encoding, "select_encoder", select_configured)
    monkeypatch.setattr(encoding.Segments, "_encoders", {})
    manager = service.PlayerManager(config)
    manager.root = tmp_path / "scratch"
    manager.root.mkdir()
    try:
        yield manager
    finally:
        await asyncio.wait_for(manager.shutdown(web.Application()), 5)


@pytest.mark.asyncio
async def test_sequential_reuse(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    spawner = Spawner(media_child(0, 3, live=True))
    patch_spawn(monkeypatch, spawner)
    for index in range(3):
        async with asyncio.timeout(5):
            async with manager.artifact(player, ("segment", index, 4, None)) as artifact:
                assert artifact.content_type == "video/mpegts"
                assert artifact.size == len(segment_bytes(index))
                assert artifact.file.read_bytes() == segment_bytes(index)
    assert len(spawner.args) == 1
    assert published(player.resource) == {0, 1, 2}
    assert list(player.resource.encodings) == [(4, None)]
    assert all(artifact.pins == 0 for artifact in player.resource.artifacts.values())


@pytest.mark.asyncio
async def test_seek_restarts(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    first = media_child(2, 1, live=True)
    spawner = Spawner(first, media_child(0, 1, live=True))
    patch_spawn(monkeypatch, spawner)
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 2, 4, None)) as artifact:
            assert artifact.file.read_bytes() == segment_bytes(2)
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 0, 4, None)) as artifact:
            assert artifact.file.read_bytes() == segment_bytes(0)
    assert len(spawner.args) == 2
    assert spawner.args[0][spawner.args[0].index("-ss") + 1] == "12.000000"
    assert spawner.args[1][spawner.args[1].index("-ss") + 1] == "0.000000"
    assert first.returncode == -15, "the superseded child must be stopped before the new one is used"


@pytest.mark.asyncio
async def test_bounded_read_ahead(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    child = media_child(0, 6, live=True)
    spawner = Spawner(child)
    patch_spawn(monkeypatch, spawner)
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 0, 4, None)):
            pass
    await quiesce()
    assert published(player.resource) == set(range(ENCODE_AHEAD + 1))
    assert child.returncode is None, "read-ahead must pause the child instead of draining it"


@pytest.mark.asyncio
async def test_fallback_before_publish(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    monkeypatch.setattr(config, "streamer_vcodec", "h264_nvenc")
    player = await manager.open("one", "video.mkv")
    spawner = Spawner(FakeChild([], [], code=1), media_child(0, 1))
    patch_spawn(monkeypatch, spawner)
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 0, 4, None)) as artifact:
            assert artifact.file.read_bytes() == segment_bytes(0)
    assert len(spawner.args) == 2
    assert "h264_nvenc" in spawner.args[0]
    assert "libx264" in spawner.args[1]


@pytest.mark.asyncio
async def test_published_no_fallback(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config.get_instance()
    monkeypatch.setattr(config, "streamer_vcodec", "h264_vaapi")
    player = await manager.open("one", "video.mkv")
    crashed = media_child(0, 1, live=True)
    spawner = Spawner(crashed, media_child(1, 1, live=True))
    patch_spawn(monkeypatch, spawner)
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 0, 4, None)) as artifact:
            assert artifact.file.read_bytes() == segment_bytes(0)
    assert "h264_vaapi" in spawner.args[0]
    crashed.exit(1)
    await quiesce()
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 1, 4, None)) as artifact:
            assert artifact.file.read_bytes() == segment_bytes(1)
    assert len(spawner.args) == 2
    assert "h264_vaapi" in spawner.args[1], "a post-publication restart must keep the codec"
    assert all("libx264" not in args for args in spawner.args)


@pytest.mark.asyncio
async def test_close_stops_child(manager: service.PlayerManager, monkeypatch: pytest.MonkeyPatch) -> None:
    player = await manager.open("one", "video.mkv")
    child = media_child(0, 3, live=True)
    spawner = Spawner(child)
    patch_spawn(monkeypatch, spawner)
    async with asyncio.timeout(5):
        async with manager.artifact(player, ("segment", 0, 4, None)):
            pass
    await quiesce()
    assert published(player.resource) == {0, 1, 2}
    await asyncio.wait_for(manager.close(player.id, "one"), 5)
    assert child.returncode == -15, "closing playback must stop the live child"
    assert not player.resource.encodings
    assert manager.jobs == 0 and manager.pending == 0
    assert len(spawner.args) == 1
    assert all(artifact.file.exists() for artifact in player.resource.artifacts.values())
    with pytest.raises(service.PlayerError) as error:
        async with asyncio.timeout(5):
            async with manager.artifact(player, ("segment", 3, 4, None)):
                raise AssertionError
    assert error.value.status == 410


@pytest.mark.asyncio
async def test_repeated_snapshots() -> None:
    header = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXT-X-MEDIA-SEQUENCE:0\n"

    def entry(index: int, offset: int) -> str:
        length = len(segment_bytes(index))
        return f"#EXTINF:{SEGMENT_DURATION:.6f},\n#EXT-X-BYTERANGE:{length}@{offset}\npipe:1\n"

    first = entry(0, 0)
    second = entry(1, len(segment_bytes(0)))
    snapshots = [header + first, header + first + second, header + first + second]
    expected = [(len(segment_bytes(0)), SEGMENT_DURATION), (len(segment_bytes(1)), SEGMENT_DURATION)]
    assert await drained(snapshots) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entry",
    [
        "#EXTINF:later,\n#EXT-X-BYTERANGE:88@0\npipe:1\n",
        "#EXTINF:0.000000,\n#EXT-X-BYTERANGE:88@0\npipe:1\n",
        "#EXTINF:nan,\n#EXT-X-BYTERANGE:88@0\npipe:1\n",
        "#EXTINF:6.000000,\n#EXT-X-BYTERANGE:88@88\npipe:1\n",
        "#EXTINF:6.000000,\n#EXT-X-BYTERANGE:0@88\npipe:1\n",
    ],
)
async def test_invalid_ranges(entry: str) -> None:
    header = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n"
    with pytest.raises(ValueError):
        await drained([header + entry])
