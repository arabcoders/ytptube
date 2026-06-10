import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.library.config import Config
from app.library.cache import Cache
from app.library.encoder import Encoder
from app.library.UpdateChecker import UpdateChecker
from app.routes.api.system import check_updates, system_config, system_diagnostics, system_folders, system_limits


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
    async def test_system_limits_public(self):
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

    def test_config_reads_live_premiere(self):
        with patch.dict("os.environ", {"YTP_PREVENT_LIVE_PREMIERE": "false"}, clear=False):
            Config._reset_singleton()
            config = Config.get_instance()

        assert config.prevent_live_premiere is False


class TestSystemDiagnosticsEndpoint:
    def setup_method(self):
        Config._reset_singleton()
        Cache.get_instance().clear()

    @pytest.mark.asyncio
    async def test_diagnostics_always_200(self, tmp_path: Path):
        config = Config.get_instance()
        config.config_path = str(tmp_path / "config")
        config.download_path = str(tmp_path / "downloads")
        config.temp_path = str(tmp_path / "tmp")
        config.db_file = str(tmp_path / "config" / "ytptube.db")
        config.console_enabled = False

        Path(config.config_path).mkdir(parents=True)
        Path(config.download_path).mkdir(parents=True)
        Path(config.temp_path).mkdir(parents=True)
        Path(config.db_file).touch()

        encoder = Encoder()

        with (
            patch("app.library.diagnostics.Config._ytdlp_version", return_value="2026.01.01"),
            patch("app.library.diagnostics.shutil.which") as mock_which,
            patch("app.library.diagnostics._run_command", new_callable=AsyncMock) as mock_run,
        ):
            mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd in {"ffmpeg", "ffprobe", "deno"} else None
            mock_run.side_effect = [
                (0, "ffmpeg version 7.0", ""),
                (0, "ffprobe version 7.0", ""),
                (0, "deno 2.3.0", ""),
            ]

            response = await system_diagnostics(config, encoder)

        assert 200 == response.status
        body = json.loads(response.body.decode("utf-8"))
        assert body["status"] == "ok"
        assert body["summary"]["required_failed"] == 0

        checks = {item["id"]: item for item in body["checks"]}
        assert checks["deno"]["status"] == "pass"
        assert checks["deno"]["details"]["version"] == "2.3.0"
        assert checks["yt_dlp_cli"]["status"] == "skip"

    @pytest.mark.asyncio
    async def test_diagnostics_error_payload(self):
        config = Config.get_instance()
        encoder = Encoder()

        with patch("app.routes.api.system.collect_diagnostics", new_callable=AsyncMock) as mock_collect:
            mock_collect.side_effect = RuntimeError("boom")

            response = await system_diagnostics(config, encoder)

        assert 200 == response.status
        body = json.loads(response.body.decode("utf-8"))
        assert body["status"] == "error"
        assert body["summary"]["required_failed"] >= 1
        assert len(body["checks"]) == 1
        assert body["checks"][0]["status"] == "fail"

    def test_distribution_package_detection(self):
        from app.library.diagnostics import _check_pot_provider_package

        with patch("app.library.diagnostics._package_version", return_value="1.3.1"):
            check = _check_pot_provider_package()

        assert check.status == "pass"
        assert check.details["version"] == "1.3.1"
        assert "description" not in check.details

    def test_safe_details(self):
        from app.library.diagnostics import _safe_url

        assert _safe_url("https://user:pass@example.test/token/path?x=1#frag") == (
            "https://***:***@example.test/***?***#***"
        )

    @pytest.mark.asyncio
    async def test_binary_timeout(self):
        from app.library.diagnostics import _check_binary

        with (
            patch("app.library.diagnostics.shutil.which", return_value="/usr/local/bin/deno"),
            patch("app.library.diagnostics._run_command", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.side_effect = TimeoutError

            check = await _check_binary("deno", check_id="deno", label="deno", required=True)

        assert check.status == "fail"
        assert check.details["command"] == "deno"

    @pytest.mark.asyncio
    async def test_diagnostics_marks_required_missing(self, tmp_path: Path):
        config = Config.get_instance()
        config.config_path = str(tmp_path / "config")
        config.download_path = str(tmp_path / "downloads")
        config.temp_path = str(tmp_path / "tmp")
        config.db_file = str(tmp_path / "config" / "ytptube.db")
        config.console_enabled = True

        Path(config.config_path).mkdir(parents=True)
        Path(config.download_path).mkdir(parents=True)
        Path(config.temp_path).mkdir(parents=True)
        Path(config.db_file).touch()

        encoder = Encoder()

        with (
            patch("app.library.diagnostics.Config._ytdlp_version", return_value="2026.01.01"),
            patch("app.library.diagnostics.shutil.which") as mock_which,
            patch("app.library.diagnostics._run_command", new_callable=AsyncMock) as mock_run,
        ):
            mock_which.side_effect = lambda cmd: (
                "/usr/bin/ffprobe" if cmd == "ffprobe" else "/usr/bin/yt-dlp" if cmd == "yt-dlp" else None
            )
            mock_run.side_effect = [
                (0, "ffprobe version 7.0", ""),
                (0, "yt-dlp 2026.01.01", ""),
            ]

            response = await system_diagnostics(config, encoder)

        assert 200 == response.status
        body = json.loads(response.body.decode("utf-8"))
        assert body["status"] == "error"
        assert body["summary"]["required_failed"] >= 1

        checks = {item["id"]: item for item in body["checks"]}
        assert checks["ffmpeg"]["status"] == "fail"
        assert checks["deno"]["status"] == "fail"
        assert checks["yt_dlp_cli"]["status"] == "pass"
        assert checks["aria2c"]["status"] == "skip"
        assert checks["mkvpropedit"]["status"] == "skip"
        assert checks["mkvextract"]["status"] == "skip"
        assert checks["mp4box"]["status"] == "skip"

    @pytest.mark.asyncio
    async def test_alias_fallback_mp4box(self):
        from app.library.diagnostics import _check_binary

        with (
            patch("app.library.diagnostics.shutil.which") as mock_which,
            patch("app.library.diagnostics._run_command", new_callable=AsyncMock) as mock_run,
        ):
            mock_which.side_effect = lambda cmd: "/usr/bin/mp4box" if cmd == "mp4box" else None
            mock_run.return_value = (0, "MP4Box 2.2.1", "")

            check = await _check_binary(
                "MP4Box",
                check_id="mp4box",
                label="MP4Box",
                required=False,
                missing_status="skip",
                aliases=("mp4box",),
            )

        assert check.status == "pass"
        assert check.details["command"] == "mp4box"
        assert check.details["version"] == "MP4Box 2.2.1"

    @pytest.mark.asyncio
    async def test_optional_binary_present(self):
        from app.library.diagnostics import _check_binary

        with (
            patch("app.library.diagnostics.shutil.which", return_value="/usr/bin/aria2c"),
            patch("app.library.diagnostics._run_command", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = (0, "aria2 version 1.37.0", "")

            check = await _check_binary(
                "aria2c",
                check_id="aria2c",
                label="aria2c",
                required=False,
                missing_status="skip",
            )

        assert check.status == "pass"
        assert check.details["version"] == "1.37.0"

    @pytest.mark.asyncio
    async def test_optional_binary_missing_skip(self):
        from app.library.diagnostics import _check_binary

        with patch("app.library.diagnostics.shutil.which", return_value=None):
            check = await _check_binary(
                "mkvpropedit",
                check_id="mkvpropedit",
                label="mkvpropedit",
                required=False,
                missing_status="skip",
            )

        assert check.status == "skip"


class TestSystemFoldersEndpoint:
    def setup_method(self):
        Config._reset_singleton()

    @pytest.mark.asyncio
    async def test_system_folders_returns_folder_list(self, tmp_path: Path) -> None:
        """GET /api/system/folders returns the folders list."""
        config = Config.get_instance()
        config.download_path = str(tmp_path)
        config.download_path_depth = 1
        encoder = Encoder()

        response = await system_folders(config, encoder)

        assert response.status == 200
        data = json.loads(response.body.decode("utf-8"))
        assert "folders" in data
        assert isinstance(data["folders"], list)


class TestSystemConfigEndpoint:
    def setup_method(self):
        Config._reset_singleton()

    @pytest.mark.asyncio
    async def test_system_configuration_excludes_queue_and_folders(self, tmp_path: Path) -> None:
        """GET /api/system/configuration no longer includes queue or folders."""
        config = Config.get_instance()
        config.download_path = str(tmp_path)
        config.download_path_depth = 1
        encoder = Encoder()

        done_mock = MagicMock()
        done_mock.get_total_count = AsyncMock(return_value=0)
        queue = DummyQueue()
        queue.done = done_mock

        with patch("app.features.dl_fields.service.DLFields.get_instance") as mock_dlfields, \
             patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_dlfields_instance = MagicMock()
            mock_dlfields_instance.get_all_serialized = AsyncMock(return_value=[])
            mock_dlfields.return_value = mock_dlfields_instance

            mock_presets_instance = MagicMock()
            mock_presets_instance.get_all.return_value = []
            mock_presets.return_value = mock_presets_instance

            response = await system_config(queue, config, encoder)

        assert response.status == 200
        data = json.loads(response.body.decode("utf-8"))
        assert "queue" not in data, "queue should be removed from config response"
        assert "folders" not in data, "folders should be moved to /api/system/folders"
