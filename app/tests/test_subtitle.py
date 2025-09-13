from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.library.Subtitle import Subtitle, ms_to_timestamp


class TestMsToTimestamp:
    def test_ms_to_timestamp_basic(self) -> None:
        assert ms_to_timestamp(0) == "0:00:00.00"
        assert ms_to_timestamp(9) == "0:00:00.00"
        assert ms_to_timestamp(10) == "0:00:00.01"
        assert ms_to_timestamp(12345) == "0:00:12.34"
        # 1 hour, 2 minutes, 3 seconds
        assert ms_to_timestamp(3600000 + 120000 + 3000) == "1:02:03.00"
        # Over 10 hours (SubStation limit is < 10h, our override must exceed)
        assert ms_to_timestamp(12 * 3600000 + 34 * 60000 + 56 * 1000 + 780) == "12:34:56.78"
        # Well over 36 hours to ensure no clamping at 9:59:59.99
        assert ms_to_timestamp(37 * 3600000 + 12 * 60000 + 34 * 1000 + 560) == "37:12:34.56"


@pytest.mark.asyncio
async def test_make_unsupported_extension(tmp_path: Path) -> None:
    srt = tmp_path / "sub.txt"
    srt.write_text("not a subtitle")

    sub = Subtitle()
    with pytest.raises(Exception, match="subtitle type is not supported"):
        await sub.make(srt)


@pytest.mark.asyncio
async def test_make_vtt_reads_file(tmp_path: Path) -> None:
    vtt = tmp_path / "file.vtt"
    content = "WEBVTT\n\n00:00:00.00 --> 00:00:01.00\nHello"
    vtt.write_text(content)

    sub = Subtitle()
    out = await sub.make(vtt)
    assert out == content


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

    with patch("app.library.Subtitle.pysubs2.load") as mock_load:
        mock_load.return_value = _DummySubs(events=[])
        sub = Subtitle()
        with pytest.raises(Exception, match="No subtitle events were found"):
            await sub.make(srt)


@pytest.mark.asyncio
async def test_make_single_event_returns_vtt(tmp_path: Path) -> None:
    srt = tmp_path / "sub.ass"
    srt.write_text("dummy")

    single = SimpleNamespace(end=1000)
    d = _DummySubs(events=[single])

    with patch("app.library.Subtitle.pysubs2.load", return_value=d):
        sub = Subtitle()
        out = await sub.make(srt)
        assert out == "OUT"
        # Snapshot should contain the single event
        assert d.snapshot == [1000]


@pytest.mark.asyncio
async def test_make_two_events_pop_first_when_ends_equal(tmp_path: Path) -> None:
    srt = tmp_path / "sub.srt"
    srt.write_text("dummy")

    e1 = SimpleNamespace(end=5000)
    e2 = SimpleNamespace(end=5000)
    d = _DummySubs(events=[e1, e2])

    with patch("app.library.Subtitle.pysubs2.load", return_value=d):
        sub = Subtitle()
        out = await sub.make(srt)
        assert out == "OUT"
        # Since ends are equal, first should be popped => only last remains
        assert d.snapshot == [5000]


@pytest.mark.asyncio
async def test_make_two_events_no_pop_when_different(tmp_path: Path) -> None:
    srt = tmp_path / "sub.srt"
    srt.write_text("dummy")

    e1 = SimpleNamespace(end=5000)
    e2 = SimpleNamespace(end=6000)
    d = _DummySubs(events=[e1, e2])

    with patch("app.library.Subtitle.pysubs2.load", return_value=d):
        sub = Subtitle()
        out = await sub.make(srt)
        assert out == "OUT"
        # Both remain since ends differ
        assert d.snapshot == [5000, 6000]
