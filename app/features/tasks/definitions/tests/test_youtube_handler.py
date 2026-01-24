import pytest

from app.features.tasks.definitions.handlers.youtube import YoutubeHandler
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


@pytest.mark.asyncio
async def test_youtube_handler_inspect(monkeypatch):
    feed = """
    <feed xmlns='http://www.w3.org/2005/Atom' xmlns:yt='http://www.youtube.com/xml/schemas/2015'>
      <entry>
        <yt:videoId>abc123</yt:videoId>
        <title>First Video</title>
        <published>2024-01-01T00:00:00Z</published>
      </entry>
      <entry>
        <yt:videoId>def456</yt:videoId>
        <title>Second Video</title>
        <published>2024-01-02T00:00:00Z</published>
      </entry>
    </feed>
    """.strip()

    async def fake_request(**kwargs):  # noqa: ARG001
        return DummyResponse(feed)

    monkeypatch.setattr(YoutubeHandler, "request", staticmethod(fake_request))
    monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

    task = HandleTask(
        id=1,
        name="Inspect",
        url="https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv",
        preset="default",
    )

    result = await YoutubeHandler.extract(task)

    assert isinstance(result, TaskResult)
    assert len(result.items) == 2
    first = result.items[0]
    assert first.url == "https://www.youtube.com/watch?v=abc123"
    assert first.title == "First Video"
    assert first.metadata.get("published") == "2024-01-01T00:00:00Z"
    assert result.metadata.get("entry_count") == 2
