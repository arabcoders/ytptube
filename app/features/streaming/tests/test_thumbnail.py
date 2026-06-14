from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.tests.helpers import temporary_test_dir


@pytest.mark.asyncio
async def test_pick_same_stem() -> None:
    from app.features.streaming.library.thumbnail import pick_local_thumb

    with temporary_test_dir("thumb-local") as temp_dir:
        media = temp_dir / "video.mp4"
        poster = temp_dir / "poster.jpg"
        thumb = temp_dir / "video.jpg"

        media.write_text("video")
        poster.write_text("poster")
        thumb.write_text("thumb")

        assert pick_local_thumb(media) == thumb


@pytest.mark.asyncio
async def test_singleflight(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._IN_PROCESS.clear()
    thumbnail.Cache.get_instance().clear()

    with temporary_test_dir("thumb-singleflight") as temp_dir:
        media = temp_dir / "video.mp4"
        cache_root = temp_dir / "cache"
        media.write_text("video")
        item_id = "item-1"

        calls = {"count": 0}

        async def fake_run_ffmpeg(_file: Path, output_file: Path) -> Path:
            calls["count"] += 1
            await asyncio.sleep(0.01)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text("image")
            return output_file

        monkeypatch.setattr(thumbnail, "_run_ffmpeg", fake_run_ffmpeg)

        first, second = await asyncio.gather(
            thumbnail.ensure_thumb(media, cache_root, item_id=item_id),
            thumbnail.ensure_thumb(media, cache_root, item_id=item_id),
        )

        assert first == second
        assert first is not None
        assert calls["count"] == 1
        assert thumbnail._IN_PROCESS == {}


@pytest.mark.asyncio
async def test_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._IN_PROCESS.clear()
    thumbnail.Cache.get_instance().clear()

    with temporary_test_dir("thumb-cache") as temp_dir:
        media = temp_dir / "video.mp4"
        cache_root = temp_dir / "cache"
        media.write_text("video")
        item_id = "item-1"

        cache_file = cache_root / f"{item_id}.jpg"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("image")

        async def fake_run_ffmpeg(_file: Path, _output_file: Path) -> Path:
            raise AssertionError("ffmpeg should not run when cache exists")

        monkeypatch.setattr(thumbnail, "_run_ffmpeg", fake_run_ffmpeg)

        result = await thumbnail.ensure_thumb(media, cache_root, item_id=item_id)

        assert result == cache_file


@pytest.mark.asyncio
async def test_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._IN_PROCESS.clear()
    thumbnail.Cache.get_instance().clear()

    with temporary_test_dir("thumb-disabled") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")

        monkeypatch.setattr(
            thumbnail.Config,
            "get_instance",
            staticmethod(lambda: type("Cfg", (), {"thumb_generate": False, "thumb_sidecar": False})()),
        )

        result = await thumbnail.ensure_thumb(media, temp_dir / "cache", item_id="item-1")

        assert result is None


@pytest.mark.asyncio
async def test_sidecar_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._IN_PROCESS.clear()
    thumbnail._SEM = None
    thumbnail._SEM_LIMIT = None
    thumbnail.Cache.get_instance().clear()

    with temporary_test_dir("thumb-sidecar") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")

        sidecar = media.with_name(f"{media.name}.jpg")

        monkeypatch.setattr(
            thumbnail.Config,
            "get_instance",
            staticmethod(
                lambda: type(
                    "Cfg",
                    (),
                    {"thumb_generate": True, "thumb_sidecar": True, "thumb_concurrency": 1},
                )()
            ),
        )

        async def fake_run_ffmpeg(_file: Path, out_file: Path) -> Path:
            out_file.write_text("image")
            return out_file

        monkeypatch.setattr(thumbnail, "_run_ffmpeg", fake_run_ffmpeg)

        result = await thumbnail.ensure_thumb(media, temp_dir / "cache")

        assert result == sidecar
        assert sidecar.exists()


@pytest.mark.asyncio
async def test_miss_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._IN_PROCESS.clear()
    thumbnail.Cache.get_instance().clear()

    with temporary_test_dir("thumb-miss") as temp_dir:
        media = temp_dir / "video.mp4"
        media.write_text("video")
        item_id = "item-1"

        monkeypatch.setattr(
            thumbnail.Config,
            "get_instance",
            staticmethod(
                lambda: type(
                    "Cfg",
                    (),
                    {"thumb_generate": True, "thumb_sidecar": False, "thumb_concurrency": 1},
                )()
            ),
        )

        calls = {"count": 0}

        async def fake_run_ffmpeg(_file: Path, _out_file: Path) -> Path | None:
            calls["count"] += 1
            return None

        monkeypatch.setattr(thumbnail, "_run_ffmpeg", fake_run_ffmpeg)

        first = await thumbnail.ensure_thumb(media, temp_dir / "cache", item_id=item_id)
        second = await thumbnail.ensure_thumb(media, temp_dir / "cache", item_id=item_id)

        assert first is None
        assert second is None
        assert calls["count"] == 1


def test_sem_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._SEM = None
    thumbnail._SEM_LIMIT = None

    monkeypatch.setattr(
        thumbnail.Config,
        "get_instance",
        staticmethod(
            lambda: type("Cfg", (), {"thumb_concurrency": 3, "thumb_generate": True, "thumb_sidecar": False})()
        ),
    )

    sem = thumbnail._get_semaphore()

    assert sem._value == 3
    assert thumbnail._SEM_LIMIT == 3


def test_seek_bounds() -> None:
    from app.features.streaming.library.ffprobe import FFProbeResult
    from app.features.streaming.library.thumbnail import _seek_seconds

    ff_info = FFProbeResult()
    ff_info.metadata = {"duration": "120.0"}
    assert _seek_seconds(ff_info) == 12.0

    ff_info.metadata = {"duration": "2.0"}
    assert _seek_seconds(ff_info) == 1.0

    ff_info.metadata = {"duration": "0.05"}
    assert _seek_seconds(ff_info) is None

    ff_info.metadata = {}
    assert _seek_seconds(ff_info) == 3.0


@pytest.mark.asyncio
async def test_cache_name_uses_item_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail

    thumbnail._IN_PROCESS.clear()
    thumbnail.Cache.get_instance().clear()

    with temporary_test_dir("thumb-id-name") as temp_dir:
        media = temp_dir / "video.mp4"
        cache_root = temp_dir / "cache"
        media.write_text("video")

        async def fake_run_ffmpeg(_file: Path, output_file: Path) -> Path:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text("image")
            return output_file

        monkeypatch.setattr(thumbnail, "_run_ffmpeg", fake_run_ffmpeg)

        result = await thumbnail.ensure_thumb(media, cache_root, item_id="item-1")

        assert result == cache_root / "item-1.jpg"


@pytest.mark.asyncio
async def test_retry_no_seek(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library.ffprobe import FFProbeResult
    from app.features.streaming.library import thumbnail

    with temporary_test_dir("thumb-retry") as temp_dir:
        media = temp_dir / "video.mp4"
        output = temp_dir / ".jpg"
        media.write_text("video")

        ff_info: Any = FFProbeResult()
        ff_info.metadata = {"duration": "120.0"}
        ff_info.video = [type("Video", (), {"codec_type": "video", "codec_name": "h264"})()]

        monkeypatch.setattr(thumbnail, "ffprobe", AsyncMock(return_value=ff_info))

        calls: list[list[str]] = []

        class DummyProc:
            def __init__(self, attempt: int, out_path: Path) -> None:
                self.returncode = 1 if attempt == 1 else 0
                self._out_path = out_path

            async def communicate(self) -> tuple[bytes, bytes]:
                if self.returncode == 0:
                    self._out_path.write_text("image")
                    return b"", b""
                return b"", b"seek failed"

        async def fake_create_subprocess_exec(*args, **kwargs):
            del kwargs
            calls.append([str(arg) for arg in args])
            return DummyProc(len(calls), Path(str(args[-1])))

        monkeypatch.setattr(thumbnail.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        result = await thumbnail._run_ffmpeg(media, output)

        assert result == output
        assert len(calls) == 2
        assert "-ss" in calls[0]
        assert calls[0][calls[0].index("-ss") + 1] == "12.000"
        assert "-ss" not in calls[1]
        assert calls[0][calls[0].index("-vf") + 1] == "thumbnail=200,scale=1280:-1:force_original_aspect_ratio=decrease"
        assert calls[0][-1].endswith(".tmp.jpg")


@pytest.mark.asyncio
async def test_limit_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.streaming.library import thumbnail
    from app.features.streaming.library.ffprobe import FFProbeResult

    thumbnail._SEM = None
    thumbnail._SEM_LIMIT = None
    thumbnail._IN_PROCESS.clear()
    monkeypatch.setattr(
        thumbnail.Config,
        "get_instance",
        staticmethod(
            lambda: type("Cfg", (), {"thumb_concurrency": 1, "thumb_generate": True, "thumb_sidecar": False})()
        ),
    )

    with temporary_test_dir("thumb-limit") as temp_dir:
        media1 = temp_dir / "video1.mp4"
        media2 = temp_dir / "video2.mp4"
        out1 = temp_dir / "out1.jpg"
        out2 = temp_dir / "out2.jpg"
        media1.write_text("video")
        media2.write_text("video")

        ff_info: Any = FFProbeResult()
        ff_info.metadata = {"duration": "60.0"}
        ff_info.video = [type("Video", (), {"codec_type": "video", "codec_name": "h264"})()]
        monkeypatch.setattr(thumbnail, "ffprobe", AsyncMock(return_value=ff_info))

        active = {"count": 0, "max": 0}

        class DummyProc:
            def __init__(self, out_path: Path) -> None:
                self.returncode = 0
                self._out_path = out_path

            async def communicate(self) -> tuple[bytes, bytes]:
                active["count"] += 1
                active["max"] = max(active["max"], active["count"])
                await asyncio.sleep(0.01)
                self._out_path.write_text("image")
                active["count"] -= 1
                return b"", b""

        async def fake_create_subprocess_exec(*args, **kwargs):
            del kwargs
            return DummyProc(Path(str(args[-1])))

        monkeypatch.setattr(thumbnail.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

        first, second = await asyncio.gather(
            thumbnail._run_ffmpeg(media1, out1),
            thumbnail._run_ffmpeg(media2, out2),
        )

        assert first == out1
        assert second == out2
        assert active["max"] == 1
