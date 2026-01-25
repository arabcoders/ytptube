import pytest

from app.features.tasks.definitions.handlers.twitch import TwitchHandler
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
async def test_twitch_handler_inspect(monkeypatch):
    feed = """
    <rss><channel>
      <item>
        <link>https://www.twitch.tv/videos/111</link>
        <title>First VOD</title>
      </item>
      <item>
        <link>https://www.twitch.tv/videos/222</link>
        <title>Second VOD</title>
      </item>
    </channel></rss>
    """.strip()

    async def fake_request(**kwargs):  # noqa: ARG001
        return DummyResponse(feed)

    monkeypatch.setattr(TwitchHandler, "request", staticmethod(fake_request))
    monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda self: DummyOpts({"download_archive": "/tmp/archive"}))  # noqa: ARG005

    task = HandleTask(
        id=1,
        name="Inspect",
        url="https://www.twitch.tv/testchannel",
        preset="default",
    )

    result = await TwitchHandler.extract(task)

    assert isinstance(result, TaskResult)
    assert len(result.items) == 2
    assert result.items[0].url == "https://www.twitch.tv/videos/111"
    assert result.items[0].title == "First VOD"
    assert result.metadata.get("has_entries") is True
