import asyncio
import logging
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from app.features.tasks.definitions.handlers.rss import RssGenericHandler
from app.features.tasks.definitions.results import TaskResult
from app.features.tasks.definitions.results import HandleTask
from app.features.tasks.definitions.utils import ARCHIVE_ID_TTL, archive_key


class DummyResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


class DummyOpts:
    def __init__(self, data):
        self._data = data

    def get_all(self):
        return self._data


def _opts(tmp_path: Path) -> DummyOpts:
    return DummyOpts({"download_archive": str(tmp_path / "archive.txt")})


class TestRssHandlerParsing:
    """Test URL parsing for RSS/Atom feeds using the tests() method."""

    @pytest.mark.parametrize(("url", "expected"), RssGenericHandler.tests())
    def test_url_parsing(self, url: str, expected: bool):
        result = RssGenericHandler.parse(url)
        assert (result is not None) == expected
        if expected:
            assert result is not None
            assert result["url"] == url


class TestRssHandlerExtraction:
    """Test RSS feed extraction and parsing."""

    @pytest.mark.asyncio
    async def test_podcast_enclosure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        podcast = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>My Podcast</title>
    <itunes:image href="https://example.com/cover.jpg" />
    <item>
      <title>Episode 1</title>
      <description>Our first episode.</description>
      <pubDate>Sun, 23 Aug 2026 10:00:00 +0000</pubDate>
      <guid isPermaLink="false">episode-001</guid>
      <enclosure url="https://example.com/audio/episode-001.mp3" length="42512345" type="audio/mpeg" />
      <itunes:duration>42:15</itunes:duration>
    </item>
  </channel>
</rss>"""

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(podcast)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))

        _, items, count = await RssGenericHandler._get(
            HandleTask(id=None, name="Podcast", url="https://example.com/feed.rss"),
            {},
            {"url": "https://example.com/feed.rss"},
        )

        assert count == 1
        assert items == [
            {
                "url": "https://example.com/audio/episode-001.mp3",
                "title": "Episode 1",
                "description": "Our first episode.",
                "published": "Sun, 23 Aug 2026 10:00:00 +0000",
                "thumbnail": "",
            }
        ]

    @pytest.mark.asyncio
    async def test_rss_atom_feed_extraction(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test extraction from Atom feed."""
        atom_feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
  <title>Example Feed</title>
  <entry>
    <title>Video 1</title>
    <link href="https://www.youtube.com/watch?v=abc123" rel="alternate" />
    <summary>Atom summary</summary>
    <media:group><media:description>YouTube description</media:description></media:group>
    <media:thumbnail url="https://example.com/video-1.jpg" />
    <published>2024-01-01T00:00:00Z</published>
  </entry>
  <entry>
    <title>Video 2</title>
    <link href="https://www.youtube.com/watch?v=def456" rel="alternate" />
    <published>2024-01-02T00:00:00Z</published>
  </entry>
</feed>
        """.strip()

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(atom_feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Test Atom Feed",
            url="https://example.com/feed.atom",
            preset="default",
        )

        result = await RssGenericHandler.extract(task)

        assert isinstance(result, TaskResult)
        assert len(result.items) == 2
        assert result.items[0].title == "Video 1"
        assert result.items[0].url == "https://www.youtube.com/watch?v=abc123"
        assert result.items[0].thumbnail == "https://example.com/video-1.jpg"
        assert result.items[0].description == "YouTube description"
        assert result.items[1].title == "Video 2"
        assert result.items[1].url == "https://www.youtube.com/watch?v=def456"
        assert result.metadata["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_accepts_unqualified_atom_feed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        atom_feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Video</title>
    <link href="https://www.youtube.com/watch?v=abc123" />
  </entry>
</feed>
        """.strip()

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(atom_feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(id=None, name="Inspector", url="https://example.com/content", preset="default")

        result = await RssGenericHandler.extract(task)

        assert isinstance(result, TaskResult)
        assert len(result.items) == 1
        assert result.items[0].title == "Video"

    @pytest.mark.asyncio
    async def test_rss_feed_extraction(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test extraction from RSS feed."""
        rss_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Channel</title>
    <item>
      <title>Video 1</title>
      <link>https://www.youtube.com/watch?v=abc123</link>
      <description>RSS description</description>
      <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Video 2</title>
      <link>https://www.youtube.com/watch?v=def456</link>
      <pubDate>Tue, 02 Jan 2024 00:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
        """.strip()

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(rss_feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Test RSS Feed",
            url="https://example.com/feed.rss",
            preset="default",
        )

        result = await RssGenericHandler.extract(task)

        assert isinstance(result, TaskResult)
        assert len(result.items) == 2
        assert result.items[0].title == "Video 1"
        assert result.items[0].url == "https://www.youtube.com/watch?v=abc123"
        assert result.items[0].description == "RSS description"
        assert result.items[1].title == "Video 2"
        assert result.items[1].url == "https://www.youtube.com/watch?v=def456"
        assert result.metadata["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_archive_error_logged(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><item>
  <title>Unsupported</title>
  <link>https://example.com/rss-missing-media</link>
</item></channel></rss>
        """.strip()
        call: dict = {}

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(feed)

        async def fake_fetch(**kwargs):
            call.update(kwargs)
            return None, ["Invalid browser URL."]

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005
        monkeypatch.setattr(
            "app.features.tasks.definitions.handlers.rss.get_archive_id",
            lambda url: {"archive_id": None},
        )
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.fetch_info", fake_fetch)

        with caplog.at_level(logging.WARNING, logger="ytptube"):
            result = await RssGenericHandler.extract(
                HandleTask(id=None, name="Archive Error", url="https://example.com/feed.rss")
            )

        assert isinstance(result, TaskResult)
        assert result.items == []
        assert "required yt-dlp archive ID fallback for 1 item(s)" in caplog.text
        assert "yt-dlp: Invalid browser URL." in caplog.text
        assert call["capture_logs"] == logging.ERROR

    @pytest.mark.asyncio
    async def test_rss_cache_success(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        feed = """<?xml version="1.0"?><rss><channel><item>
          <link>https://example.com/rss-video</link>
        </item></channel></rss>"""

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005
        monkeypatch.setattr(
            "app.features.tasks.definitions.handlers.rss.get_archive_id", lambda **_kwargs: {"archive_id": None}
        )
        monkeypatch.setattr(
            "app.features.tasks.definitions.handlers.rss.fetch_info",
            AsyncMock(return_value=({"id": "42", "extractor_key": "Example"}, [])),
        )
        cache = Mock()
        cache.has.return_value = False
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.CACHE", cache)

        result = await RssGenericHandler.extract(HandleTask(id=None, name="RSS", url="https://example.com/feed.rss"))

        assert isinstance(result, TaskResult)
        cache.set.assert_called_once_with(
            archive_key("https://example.com/rss-video"), "example 42", ttl=ARCHIVE_ID_TTL, persist=True
        )
        cache.delete.assert_called_once_with(f"{archive_key('https://example.com/rss-video')}:f")

    @pytest.mark.asyncio
    async def test_parallel_archive_lookup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        items = [
            {"url": "https://example.com/first", "title": "First"},
            {"url": "https://example.com/second", "title": "Second"},
            {"url": "https://example.com/first", "title": "Again"},
        ]
        monkeypatch.setattr(
            RssGenericHandler,
            "_get",
            staticmethod(AsyncMock(return_value=("https://example.com/feed.rss", items, 3))),
        )
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005
        monkeypatch.setattr(
            "app.features.tasks.definitions.handlers.rss.get_archive_id", lambda **_kwargs: {"archive_id": None}
        )
        cache = Mock()
        cache.has.return_value = False
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.CACHE", cache)
        active = 0
        peak = 0

        async def fake_fetch(config, url, **kwargs):  # noqa: ARG001
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return {"id": url.rsplit("/", 1)[-1], "extractor_key": "Example"}, []

        fetch = AsyncMock(side_effect=fake_fetch)
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.fetch_info", fetch)

        result = await RssGenericHandler.extract(HandleTask(id=None, name="RSS", url="https://example.com/feed.rss"))

        assert isinstance(result, TaskResult)
        assert [item.url for item in result.items] == [entry["url"] for entry in items]
        assert [item.archive_id for item in result.items] == ["example first", "example second", "example first"]
        assert peak == 2
        assert [call.kwargs["url"] for call in fetch.await_args_list] == [
            "https://example.com/first",
            "https://example.com/second",
        ]

    @pytest.mark.asyncio
    async def test_inspection_skips_lookup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        items = [{"url": "https://example.com/item", "title": "Item"}]
        monkeypatch.setattr(
            RssGenericHandler,
            "_get",
            staticmethod(AsyncMock(return_value=("https://example.com/feed.rss", items, 1))),
        )
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005
        monkeypatch.setattr(
            "app.features.tasks.definitions.handlers.rss.get_archive_id", lambda **_kwargs: {"archive_id": None}
        )
        cache = Mock()
        cache.has.return_value = False
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.CACHE", cache)
        fetch = AsyncMock()
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.fetch_info", fetch)

        result = await RssGenericHandler.inspect(
            HandleTask(id=None, name="Inspector", url="https://example.com/feed.rss"),
            resolve_ids=False,
        )

        assert isinstance(result, TaskResult)
        assert result.items[0].archive_id is None
        fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_inspection_zero_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        items = [{"url": "https://example.com/item", "title": "Item"}]
        monkeypatch.setattr(
            RssGenericHandler,
            "_get",
            staticmethod(AsyncMock(return_value=("https://example.com/feed.rss", items, 1))),
        )
        monkeypatch.setattr(
            HandleTask,
            "get_ytdlp_opts",
            lambda self: DummyOpts({"extractor_args": {"youtube": {"player_client": ["web"]}}}),  # noqa: ARG005
        )
        monkeypatch.setattr(
            "app.features.tasks.definitions.handlers.rss.get_archive_id", lambda **_kwargs: {"archive_id": None}
        )
        cache = Mock()
        cache.has.return_value = False
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.CACHE", cache)
        fetch = AsyncMock(return_value=({"id": "42", "extractor_key": "Example"}, []))
        monkeypatch.setattr("app.features.tasks.definitions.handlers.rss.fetch_info", fetch)

        result = await RssGenericHandler.inspect(
            HandleTask(id=None, name="Inspector", url="https://example.com/feed.rss")
        )

        assert isinstance(result, TaskResult)
        call = fetch.await_args_list[0].kwargs
        assert call["config"]["extractor_args"] == {
            "youtube": {"player_client": ["web"]},
            "generic": {"wait": ["0"]},
        }
        assert "generic_args" not in call

    @pytest.mark.asyncio
    async def test_can_handle(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test can_handle method."""
        atom_feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link href="https://www.youtube.com/watch?v=abc123" />
  </entry>
</feed>
        """.strip()

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(atom_feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Test rss Feed",
            url="https://example.com/feed.atom",
            preset="default",
        )

        assert await RssGenericHandler.can_handle(task) is True

        non_feed_task = HandleTask(
            id=1,
            name="YouTube Video",
            url="https://www.youtube.com/watch?v=abc123",
            preset="default",
        )

        assert await RssGenericHandler.can_handle(non_feed_task) is False

        unqualified_task = HandleTask(id=3, name="Inspector", url="https://example.com/content", preset="default")
        assert await RssGenericHandler.can_handle(unqualified_task) is False


class TestRssHandlerEdgeCases:
    """Test edge cases in RSS handling."""

    @pytest.mark.asyncio
    async def test_empty_feed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test handling of empty feed."""
        empty_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Channel</title>
  </channel>
</rss>
        """.strip()

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(empty_feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Empty Feed",
            url="https://example.com/feed.rss",
            preset="default",
        )

        result = await RssGenericHandler.extract(task)

        assert isinstance(result, TaskResult)
        assert len(result.items) == 0
        assert result.metadata["entry_count"] == 0

    @pytest.mark.asyncio
    async def test_invalid_feed_url(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test handling of invalid feed URL."""
        from app.features.tasks.definitions.results import TaskFailure

        async def fake_request(**kwargs):  # noqa: ARG001
            msg = "Network error"
            raise Exception(msg)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Invalid Feed",
            url="https://example.com/feed.rss",
            preset="default",
        )

        result = await RssGenericHandler.extract(task)

        assert isinstance(result, TaskFailure)

    @pytest.mark.asyncio
    async def test_missing_urls_in_feed(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Test handling of entries missing URLs."""
        feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>No URL Item</title>
    </item>
    <item>
      <title>Valid Item</title>
      <link>https://www.youtube.com/watch?v=abc123</link>
    </item>
  </channel>
</rss>
        """.strip()

        async def fake_request(**kwargs):  # noqa: ARG001
            return DummyResponse(feed)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: _opts(tmp_path))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Feed with Missing URLs",
            url="https://example.com/feed.rss",
            preset="default",
        )

        result = await RssGenericHandler.extract(task)

        # Should only include the item with URL
        assert isinstance(result, TaskResult)
        assert len(result.items) == 1
        assert result.items[0].title == "Valid Item"
