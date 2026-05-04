from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.features.streaming.library.subtitle import Subtitle, get_subtitle_tracks, ms_to_timestamp


class TestMsToTimestamp:
    def test_ms_to_timestamp_basic(self) -> None:
        assert ms_to_timestamp(0) == "0:00:00.00"
        assert ms_to_timestamp(9) == "0:00:00.00"
        assert ms_to_timestamp(10) == "0:00:00.01"
        assert ms_to_timestamp(12345) == "0:00:12.34"
        assert ms_to_timestamp(3600000 + 120000 + 3000) == "1:02:03.00", "1 hour, 2 minutes, 3 seconds"
        assert ms_to_timestamp(12 * 3600000 + 34 * 60000 + 56 * 1000 + 780) == "12:34:56.78", (
            "Over 10 hours (SubStation limit is < 10h, our override must exceed)"
        )
        assert ms_to_timestamp(37 * 3600000 + 12 * 60000 + 34 * 1000 + 560) == "37:12:34.56", (
            "Well over 36 hours to ensure no clamping at 9:59:59.99"
        )


@pytest.mark.asyncio
async def test_make_unsupported_extension(tmp_path: Path) -> None:
    file = tmp_path / "sub.txt"
    file.write_text("not a subtitle")

    subtitle = Subtitle()
    with pytest.raises(Exception, match="subtitle type is not supported"):
        await subtitle.make(file)


@pytest.mark.asyncio
async def test_make_vtt_reads_file(tmp_path: Path) -> None:
    vtt = tmp_path / "file.vtt"
    content = "WEBVTT\n\n00:00:00.00 --> 00:00:01.00\nHello"
    vtt.write_text(content)

    subtitle = Subtitle()
    out = await subtitle.make(vtt)
    assert out == content


@pytest.mark.asyncio
async def test_make_delivery_ass(tmp_path: Path) -> None:
    ass = tmp_path / "file.ass"
    content = "[Script Info]\nTitle: Demo\n"
    ass.write_text(content, encoding="utf-8")

    subtitle = Subtitle()
    out, media_type = await subtitle.make_delivery(ass)
    assert out == content
    assert media_type == "text/x-ssa; charset=UTF-8"


def test_tracks_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media = tmp_path / "video.mkv"
    media.write_text("x", encoding="utf-8")
    ass_file = tmp_path / "video.ass"
    ass_file.write_text("ass", encoding="utf-8")
    vtt_file = tmp_path / "video.vtt"
    vtt_file.write_text("WEBVTT\n\n", encoding="utf-8")
    srt_file = tmp_path / "video.en.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.features.streaming.library.subtitle.get_file_sidecar",
        lambda _file: {
            "subtitle": [
                {"file": ass_file, "lang": "en", "name": "ASS"},
                {"file": srt_file, "lang": "en", "name": "SRT"},
                {"file": vtt_file, "lang": "en", "name": "VTT"},
            ]
        },
    )

    tracks = get_subtitle_tracks(media)

    assert [track.source_format for track in tracks] == ["vtt", "srt", "ass"]
    assert [track.delivery_format for track in tracks] == ["vtt", "vtt", "ass"]
    assert [track.renderer for track in tracks] == ["native", "native", "assjs"]


class _DummySubs:
    def __init__(self, events):
        self.events = events
        self.snapshot = None

    def to_string(self, fmt: str) -> str:  # noqa: ARG002
        # Record end times to verify pop behavior
        self.snapshot = [e.end for e in self.events]
        return "OUT"


@pytest.mark.asyncio
async def test_make_no_events_raises(tmp_path: Path) -> None:
    srt = tmp_path / "sub.srt"
    srt.write_text("dummy")

    with patch("app.features.streaming.library.subtitle.pysubs2.load") as mock_load:
        mock_load.return_value = _DummySubs(events=[])
        subtitle = Subtitle()
        with pytest.raises(Exception, match="No subtitle events were found"):
            await subtitle.make(srt)


@pytest.mark.asyncio
async def test_make_single_vtt(tmp_path: Path) -> None:
    srt = tmp_path / "sub.ass"
    srt.write_text("dummy")

    single = SimpleNamespace(end=1000)
    d = _DummySubs(events=[single])

    with patch("app.features.streaming.library.subtitle.pysubs2.load", return_value=d):
        subtitle = Subtitle()
        out = await subtitle.make(srt)
        assert out == "OUT"
        assert d.snapshot == [1000], "Snapshot should contain the single event"


@pytest.mark.asyncio
async def test_make_two_events_same_end(tmp_path: Path) -> None:
    srt = tmp_path / "sub.srt"
    srt.write_text("dummy")

    e1 = SimpleNamespace(end=5000)
    e2 = SimpleNamespace(end=5000)
    d = _DummySubs(events=[e1, e2])

    with patch("app.features.streaming.library.subtitle.pysubs2.load", return_value=d):
        subtitle = Subtitle()
        out = await subtitle.make(srt)
        assert out == "OUT"
        assert d.snapshot == [5000], "Since ends are equal, first should be popped => only last remains"


@pytest.mark.asyncio
async def test_make_two_events_keep_both(tmp_path: Path) -> None:
    srt = tmp_path / "sub.srt"
    srt.write_text("dummy")

    e1 = SimpleNamespace(end=5000)
    e2 = SimpleNamespace(end=6000)
    d = _DummySubs(events=[e1, e2])

    with patch("app.features.streaming.library.subtitle.pysubs2.load", return_value=d):
        subtitle = Subtitle()
        out = await subtitle.make(srt)
        assert out == "OUT"
        assert d.snapshot == [5000, 6000], "Both remain since ends differ"
