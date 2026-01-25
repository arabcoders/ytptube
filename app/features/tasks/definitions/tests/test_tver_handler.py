import pytest

from app.features.tasks.definitions.handlers.tver import TverHandler
from app.features.tasks.definitions.results import TaskResult
from app.features.tasks.definitions.results import HandleTask


class DummyResponse:
    def __init__(self, data: dict):
        self.data = data

    def json(self):
        return self.data

    def raise_for_status(self) -> None:
        return None


class DummyOpts:
    def __init__(self, data):
        self._data = data

    def get_all(self):
        return self._data


@pytest.mark.asyncio
async def test_tver_handler_extract(monkeypatch):
    """Test tver handler extraction of episodes from series."""
    session_response = {
        "result": {
            "platform_uid": "test_uid_123",
            "platform_token": "test_token_456",
        }
    }

    episodes_response = {
        "result": {
            "contents": [
                {
                    "seasonTitle": "本編",
                    "hasNext": False,
                    "contents": [
                        {
                            "type": "episode",
                            "content": {
                                "id": "eppcxhym1e",
                                "version": 12,
                                "title": "木村拓哉がタクシー 運転手！目黒蓮が木村と二人旅",
                                "seriesID": "sr1jg44pbb",
                                "endAt": 1766404799,
                                "broadcastDateLabel": "11月24日(月)放送 分",
                                "isNHKContent": False,
                                "isSubtitle": False,
                                "ribbonID": 0,
                                "seriesTitle": "ウルトラタクシー",
                                "isAvailable": True,
                                "broadcasterName": "TBS",
                                "productionProviderName": "TBS",
                                "isEndingSoon": False,
                                "thumbnailPath": "/images/content/thumbnail/episode/xlarge/eppcxhym1e.jpg?v=84b0ee80",
                            },
                            "resume": {"lastViewedDuration": 0, "contentDuration": 3796, "completed": False},
                            "isFavorite": False,
                            "isGood": False,
                            "isLater": False,
                            "goodCount": 5553,
                        },
                        {
                            "type": "episode",
                            "content": {
                                "id": "epejwb9mvx",
                                "version": 9,
                                "title": "木村拓哉がタクシー運転手！蒼井優＆上戸彩高校の同級生コンビがディズニーリゾートを大満喫！",
                                "seriesID": "sr1jg44pbb",
                                "endAt": 1764590399,
                                "broadcastDateLabel": "11月24日(月)放送分",
                                "isNHKContent": False,
                                "isSubtitle": False,
                                "ribbonID": 0,
                                "seriesTitle": "ウルトラタクシー",
                                "isAvailable": True,
                                "broadcasterName": "TBS",
                                "productionProviderName": "TBS",
                                "isEndingSoon": False,
                                "thumbnailPath": "/images/content/thumbnail/episode/xlarge/epejwb9mvx.jpg?v=ab478281",
                            },
                            "resume": {"lastViewedDuration": 0, "contentDuration": 1896, "completed": False},
                            "isFavorite": False,
                            "isGood": False,
                            "isLater": False,
                            "goodCount": 1298,
                        },
                    ],
                }
            ],
            "seasons": [
                {
                    "type": "season",
                    "content": {"id": "sshbu1ycq8", "version": 2, "title": "本編", "season_extended": None},
                }
            ],
        }
    }

    call_count = 0

    async def fake_request(url: str, **kwargs):  # noqa: ARG001
        nonlocal call_count
        call_count += 1

        if "browser/create" in url:
            return DummyResponse(session_response)

        if "callSeriesEpisodes" in url:
            return DummyResponse(episodes_response)

        msg = f"Unexpected URL: {url}"
        raise RuntimeError(msg)

    monkeypatch.setattr(TverHandler, "request", staticmethod(fake_request))
    monkeypatch.setattr(HandleTask, "get_ytdlp_opts", lambda _: DummyOpts({"download_archive": "/tmp/archive"}))

    task = HandleTask(id=1, name="Test Tver Series", url="https://tver.jp/series/sr8sb9pnhc", preset="default")

    result = await TverHandler.extract(task)

    assert isinstance(result, TaskResult)
    assert len(result.items) == 2
    assert result.items[0].url == "https://tver.jp/episodes/eppcxhym1e"
    assert "木村拓哉がタクシー 運転手！目黒蓮が木村と二人旅" == result.items[0].title

    assert result.items[1].url == "https://tver.jp/episodes/epejwb9mvx"
    assert (
        "木村拓哉がタクシー運転手！蒼井優＆上戸彩高校の同級生コンビがディズニーリゾートを大満喫！"
        == result.items[1].title
    )

    assert result.metadata.get("has_entries") is True
    assert "callSeriesEpisodes" in result.metadata.get("feed_url", "")
    assert call_count == 2


@pytest.mark.parametrize(("url", "should_match"), TverHandler.tests())
def test_tver_handler_parse(url: str, should_match: bool):
    """Test tver URL parsing."""
    result = TverHandler.parse(url)
    if should_match:
        assert result is not None
        assert result.startswith("sr")
    else:
        assert result is None


@pytest.mark.asyncio
async def test_tver_handler_can_handle():
    """Test tver handler can_handle method."""
    task_valid = HandleTask(id=1, name="Test", url="https://tver.jp/series/sr8sb9pnhc", preset="default")
    task_invalid = HandleTask(id=2, name="Test", url="https://youtube.com/watch?v=123", preset="default")
    assert await TverHandler.can_handle(task_valid) is True
    assert await TverHandler.can_handle(task_invalid) is False
