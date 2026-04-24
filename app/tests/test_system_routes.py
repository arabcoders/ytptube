import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.UpdateChecker import UpdateChecker
from app.routes.api.system import check_updates, system_limits


@dataclass
class DummyInfo:
    extractor: str | None

    def get_extractor(self) -> str | None:
        return self.extractor


@dataclass
class DummyDownload:
    info: DummyInfo
    is_live: bool = False
    _started: bool = False

    def started(self) -> bool:
        return self._started


class DummyPool:
    def __init__(self, active: dict[str, DummyDownload] | None = None, paused: bool = False):
        self._active = active or {}
        self._paused = paused

    def get_active_downloads(self) -> dict[str, DummyDownload]:
        return self._active.copy()

    def is_paused(self) -> bool:
        return self._paused


class DummyStore:
    def __init__(self, items: dict[str, DummyDownload] | None = None):
        self._items = items or {}

    def items(self):
        return self._items.items()


class DummyQueue:
    def __init__(self, active: dict[str, DummyDownload] | None = None, queued: dict[str, DummyDownload] | None = None):
        self.pool = DummyPool(active=active)
        self.queue = DummyStore(items=queued)

    def is_paused(self) -> bool:
        return self.pool.is_paused()


class TestCheckUpdatesEndpoint:
    """Tests for the check updates endpoint."""

    def setup_method(self):
        """Reset singletons before each test."""
        Config._reset_singleton()
        UpdateChecker._reset_singleton()

    @pytest.mark.asyncio
    async def test_check_updates_disabled(self):
        """Test check updates returns error when disabled in config."""
        config = Config.get_instance()
        config.check_for_updates = False
        encoder = Encoder()
        update_checker = UpdateChecker.get_instance()

        response = await check_updates(config, encoder, update_checker)

        assert 200 == response.status, "Should work even if disabled as it's manual check."
        body = response.body
        assert b"disabled" in body.lower(), "Response should mention update checking is disabled"

    @pytest.mark.asyncio
    async def test_check_updates_up_to_date(self):
        """Test check updates returns up_to_date status."""
        config = Config.get_instance()
        config.check_for_updates = True
        config.app_version = "v1.0.0"
        encoder = Encoder()
        update_checker = UpdateChecker.get_instance()

        with patch.object(update_checker, "check_for_updates", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (("up_to_date", None), ("up_to_date", None))
            response = await check_updates(config, encoder, update_checker)

            assert 200 == response.status, "Should return 200"
            body = response.body.decode("utf-8")
            assert "up_to_date" in body, "Response should include up_to_date status"
            assert mock_check.called, "Should have called check_for_updates"

    @pytest.mark.asyncio
    async def test_check_updates_update_available(self):
        """Test check updates returns update_available status with new version."""
        config = Config.get_instance()
        config.check_for_updates = True
        config.app_version = "v1.0.0"
        encoder = Encoder()
        update_checker = UpdateChecker.get_instance()

        with patch.object(update_checker, "check_for_updates", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (("update_available", "v1.0.5"), ("up_to_date", None))
            response = await check_updates(config, encoder, update_checker)

            assert 200 == response.status, "Should return 200"
            body = response.body.decode("utf-8")
            assert "v1.0.5" in body, "Response should include new version"
            assert "update_available" in body, "Response should include update_available status"


class TestSystemLimitsEndpoint:
    def setup_method(self):
        Config._reset_singleton()

    @pytest.mark.asyncio
    async def test_system_limits_returns_user_facing_limits(self):
        config = Config.get_instance()
        config.max_workers = 10
        config.max_workers_per_extractor = 3
        config.extract_info_concurrency = 4
        config.extract_info_timeout = 70
        config.download_info_expires = 10800
        config.prevent_live_premiere = True
        config.live_premiere_buffer = 7
        config.default_pagination = 50

        active = {
            "a": DummyDownload(info=DummyInfo("youtube"), is_live=False, _started=True),
            "b": DummyDownload(info=DummyInfo("youtube"), is_live=False, _started=True),
            "c": DummyDownload(info=DummyInfo("twitch"), is_live=True, _started=True),
        }
        queued = {
            "q1": DummyDownload(info=DummyInfo("youtube"), is_live=False, _started=False),
            "q2": DummyDownload(info=DummyInfo("vimeo"), is_live=False, _started=False),
        }
        queue = DummyQueue(active=active, queued=queued)
        encoder = Encoder()

        with patch.dict("os.environ", {"YTP_MAX_WORKERS_FOR_YOUTUBE": "2"}, clear=False):
            response = await system_limits(queue, config, encoder)

        assert 200 == response.status

        body = json.loads(response.body.decode("utf-8"))
        assert body["downloads"]["paused"] is False
        assert body["downloads"]["live_bypasses_limits"] is True
        assert body["downloads"]["global"] == {
            "limit": 10,
            "active": 2,
            "available": 8,
            "live_active": 1,
            "queued": 2,
        }
        assert body["extraction"] == {
            "concurrency": 4,
            "timeout_seconds": 70,
            "info_cache_ttl_seconds": 10800,
        }
        assert body["live"] == {
            "prevent_premiere": True,
            "premiere_buffer_minutes": 7,
        }

        per_extractor = {item["name"]: item for item in body["downloads"]["per_extractor"]["items"]}
        assert body["downloads"]["per_extractor"]["default_limit"] == 3
        assert per_extractor["youtube"] == {
            "name": "youtube",
            "limit": 2,
            "source": "env_override",
            "active": 2,
            "queued": 1,
            "available": 0,
        }
        assert per_extractor["vimeo"] == {
            "name": "vimeo",
            "limit": 3,
            "source": "default",
            "active": 0,
            "queued": 1,
            "available": 3,
        }

    def test_config_reads_prevent_live_premiere_boolean_env(self):
        with patch.dict("os.environ", {"YTP_PREVENT_LIVE_PREMIERE": "false"}, clear=False):
            Config._reset_singleton()
            config = Config.get_instance()

        assert config.prevent_live_premiere is False
