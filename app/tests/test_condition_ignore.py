from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.features.conditions.service import Conditions
from app.library.ItemDTO import Item
from app.library.downloads.item_adder import add
from app.library.downloads.playlist_processor import process_playlist


@pytest.fixture(autouse=True)
def reset_conditions_singleton():
    Conditions._reset_singleton()
    yield
    Conditions._reset_singleton()


class TestConditionIgnoreMatching:
    @pytest.mark.asyncio
    async def test_match_skip_name(self) -> None:
        first = SimpleNamespace(id=1, name="Primary", enabled=True, filter="duration > 0", priority=20)
        second = SimpleNamespace(id=2, name="Fallback", enabled=True, filter="duration > 0", priority=10)

        service = Conditions.get_instance()
        service._repo = Mock(list=AsyncMock(return_value=[first, second]))

        matched = await service.match(info={"duration": 60}, ignore_conditions=["Primary"])

        assert matched is second

    @pytest.mark.asyncio
    async def test_match_skip_id(self) -> None:
        first = SimpleNamespace(id=123, name="Primary", enabled=True, filter="duration > 0", priority=20)
        second = SimpleNamespace(id=124, name="Fallback", enabled=True, filter="duration > 0", priority=10)

        service = Conditions.get_instance()
        service._repo = Mock(list=AsyncMock(return_value=[first, second]))

        matched = await service.match(info={"duration": 60}, ignore_conditions=["123"])

        assert matched is second

    @pytest.mark.asyncio
    async def test_match_coerce_ids(self) -> None:
        first = SimpleNamespace(id=123, name="Primary", enabled=True, filter="duration > 0", priority=20)
        second = SimpleNamespace(id=124, name="Fallback", enabled=True, filter="duration > 0", priority=10)

        service = Conditions.get_instance()
        service._repo = Mock(list=AsyncMock(return_value=[first, second]))

        matched = await service.match(info={"duration": 60}, ignore_conditions=[123])

        assert matched is second

    @pytest.mark.asyncio
    async def test_match_wildcard(self) -> None:
        first = SimpleNamespace(id=1, name="Primary", enabled=True, filter="duration > 0", priority=20)

        service = Conditions.get_instance()
        service._repo = Mock(list=AsyncMock(return_value=[first]))

        matched = await service.match(info={"duration": 60}, ignore_conditions=["*"])

        assert matched is None


class TestConditionIgnorePropagation:
    @pytest.mark.asyncio
    async def test_add_passes_ignore(self, tmp_path: Path) -> None:
        queue = Mock()
        queue.config = Mock(temp_path=str(tmp_path), ignore_archived_items=False, ytdlp_debug=False)
        queue._notify = Mock()

        item = Item(
            url="https://example.com/watch?v=test",
            preset="default",
            extras={"ignore_conditions": [" 123 ", "Primary", "", " * "]},
        )
        item.get_ytdlp_opts = Mock(return_value=Mock(get_all=Mock(return_value={})))
        item.get_archive_id = Mock(return_value=None)
        item.get_archive_file = Mock(return_value=None)
        item.is_archived = Mock(return_value=False)

        matcher = Mock(match=AsyncMock(return_value=None))
        entry = {"id": "video-1", "duration": 60}

        with (
            patch(
                "app.library.downloads.item_adder.Presets.get_instance", return_value=Mock(get=Mock(return_value=None))
            ),
            patch("app.library.downloads.item_adder.Conditions.get_instance", return_value=matcher),
            patch("app.library.downloads.item_adder.ytdlp_reject", return_value=(True, "")),
            patch(
                "app.library.downloads.item_adder.add_item", new=AsyncMock(return_value={"status": "ok"})
            ) as add_item_mock,
        ):
            result = await add(queue=queue, item=item, entry=entry)

        matcher.match.assert_awaited_once_with(info=entry, ignore_conditions=["123", "Primary", "*"])
        add_item_mock.assert_awaited_once()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_add_coerces_ignore(self, tmp_path: Path) -> None:
        queue = Mock()
        queue.config = Mock(temp_path=str(tmp_path), ignore_archived_items=False, ytdlp_debug=False)
        queue._notify = Mock()

        item = Item(
            url="https://example.com/watch?v=test",
            preset="default",
            extras={"ignore_conditions": [123, "Primary", True, " * "]},
        )
        item.get_ytdlp_opts = Mock(return_value=Mock(get_all=Mock(return_value={})))
        item.get_archive_id = Mock(return_value=None)
        item.get_archive_file = Mock(return_value=None)
        item.is_archived = Mock(return_value=False)

        matcher = Mock(match=AsyncMock(return_value=None))
        entry = {"id": "video-1", "duration": 60}

        with (
            patch(
                "app.library.downloads.item_adder.Presets.get_instance", return_value=Mock(get=Mock(return_value=None))
            ),
            patch("app.library.downloads.item_adder.Conditions.get_instance", return_value=matcher),
            patch("app.library.downloads.item_adder.ytdlp_reject", return_value=(True, "")),
            patch("app.library.downloads.item_adder.add_item", new=AsyncMock(return_value={"status": "ok"})),
        ):
            await add(queue=queue, item=item, entry=entry)

        matcher.match.assert_awaited_once_with(info=entry, ignore_conditions=["123", "Primary", "*"])

    @pytest.mark.asyncio
    async def test_playlist_keeps_parent_ignore(self) -> None:
        captured: dict[str, object] = {}

        class FakeItem:
            def __init__(self) -> None:
                self.extras = {"ignore_conditions": ["*", "Primary"], "source_name": "Manual"}

            def get_ytdlp_opts(self):
                return Mock(get_all=Mock(return_value={}))

            def new_with(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(extras=kwargs["extras"], url=kwargs["url"])

        queue = Mock(add=AsyncMock(return_value={"status": "ok"}))
        entry = {
            "_type": "playlist",
            "id": "playlist-1",
            "title": "Playlist",
            "extractor": "youtube",
            "entries": [{"_type": "video", "id": "video-1", "title": "Video 1", "url": "https://example.com/v/1"}],
        }

        with patch("app.library.downloads.playlist_processor.ytdlp_reject", return_value=(True, "")):
            result = await process_playlist(queue=queue, entry=entry, item=FakeItem())

        assert result == {"status": "ok"}
        assert captured["url"] == "https://example.com/v/1"
        assert captured["extras"]["ignore_conditions"] == ["*", "Primary"]
        assert captured["extras"]["playlist"] == "Playlist"
        assert "source_name" not in captured["extras"]
        queue.add.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_playlist_keeps_child_urls(self) -> None:
        class FakeItem:
            def __init__(self) -> None:
                self.extras = {}

            def get_ytdlp_opts(self):
                return Mock(get_all=Mock(return_value={}))

            def new_with(self, **kwargs):
                return SimpleNamespace(extras=kwargs["extras"], url=kwargs["url"])

        queue = Mock(add=AsyncMock(return_value={"status": "ok"}))
        entry = {
            "_type": "playlist",
            "id": "playlist-1",
            "title": "Playlist",
            "webpage_url": "https://example.com/page",
            "original_url": "https://example.com/page",
            "entries": [
                {
                    "_type": "video",
                    "id": "video-1",
                    "title": "Video 1",
                    "url": "https://cdn.example/1.mp3",
                    "webpage_url": "https://cdn.example/1.mp3",
                    "original_url": "https://cdn.example/1.mp3",
                    "formats": [{"url": "https://cdn.example/1.mp3", "ext": "mp3"}],
                },
                {
                    "_type": "video",
                    "id": "video-2",
                    "title": "Video 2",
                    "url": "https://cdn.example/2.mp3",
                    "webpage_url": "https://cdn.example/2.mp3",
                    "original_url": "https://cdn.example/2.mp3",
                    "formats": [{"url": "https://cdn.example/2.mp3", "ext": "mp3"}],
                },
            ],
        }

        with patch("app.library.downloads.playlist_processor.ytdlp_reject", return_value=(True, "")):
            result = await process_playlist(queue=queue, entry=entry, item=FakeItem())

        assert result == {"status": "ok"}
        assert queue.add.await_count == 2
        assert [call.kwargs["item"].url for call in queue.add.await_args_list] == [
            "https://cdn.example/1.mp3",
            "https://cdn.example/2.mp3",
        ]
        assert [call.kwargs["entry"]["webpage_url"] for call in queue.add.await_args_list] == [
            "https://cdn.example/1.mp3",
            "https://cdn.example/2.mp3",
        ]
        assert [call.kwargs["entry"]["original_url"] for call in queue.add.await_args_list] == [
            "https://cdn.example/1.mp3",
            "https://cdn.example/2.mp3",
        ]
