import pytest

from app.features.tasks.definitions.handlers.rss import RssGenericHandler
from app.features.tasks.definitions.results import TaskResult
from app.features.tasks.definitions.results import HandleTask


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


class TestRssHandlerParsing:
    """Test URL parsing for RSS/Atom feeds using the tests() method."""

    @pytest.mark.parametrize(("url", "expected"), RssGenericHandler.tests())
    def test_url_parsing(self, url: str, expected: bool):
        """Test URL parsing against all defined test cases."""
        result = RssGenericHandler.parse(url)
        is_matched = result is not None
        assert is_matched == expected, f"URL '{url}' expected {expected}, got {is_matched}"

    @pytest.mark.parametrize(("url", "expected"), RssGenericHandler.tests())
    def test_returns_url_dict_on_match(self, url: str, expected: bool):
        """Test that parse returns dict with 'url' key for valid feeds."""
        result = RssGenericHandler.parse(url)
        if expected:
            assert result is not None
            assert "url" in result
            assert result["url"] == url
        else:
            assert result is None


class TestRssHandlerExtraction:
    """Test RSS feed extraction and parsing."""

    @pytest.mark.asyncio
    async def test_rss_atom_feed_extraction(self, monkeypatch):
        """Test extraction from Atom feed."""
        atom_feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example Feed</title>
  <entry>
    <title>Video 1</title>
    <link href="https://www.youtube.com/watch?v=abc123" rel="alternate" />
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
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

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
        assert result.items[1].title == "Video 2"
        assert result.items[1].url == "https://www.youtube.com/watch?v=def456"
        assert result.metadata["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_rss_feed_extraction(self, monkeypatch):
        """Test extraction from RSS feed."""
        rss_feed = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Channel</title>
    <item>
      <title>Video 1</title>
      <link>https://www.youtube.com/watch?v=abc123</link>
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
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

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
        assert result.items[1].title == "Video 2"
        assert result.items[1].url == "https://www.youtube.com/watch?v=def456"
        assert result.metadata["entry_count"] == 2

    @pytest.mark.asyncio
    async def test_can_handle(self, monkeypatch):
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
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

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


class TestRssHandlerEdgeCases:
    """Test edge cases in RSS handling."""

    @pytest.mark.asyncio
    async def test_empty_feed(self, monkeypatch):
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
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

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
    async def test_invalid_feed_url(self, monkeypatch):
        """Test handling of invalid feed URL."""
        from app.features.tasks.definitions.results import TaskFailure

        async def fake_request(**kwargs):  # noqa: ARG001
            msg = "Network error"
            raise Exception(msg)

        monkeypatch.setattr(RssGenericHandler, "request", staticmethod(fake_request))
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

        task = HandleTask(
            id=1,
            name="Invalid Feed",
            url="https://example.com/feed.rss",
            preset="default",
        )

        result = await RssGenericHandler.extract(task)

        assert isinstance(result, TaskFailure)

    @pytest.mark.asyncio
    async def test_missing_urls_in_feed(self, monkeypatch):
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
        monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

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
