import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestUpdateChecker:
    """Test UpdateChecker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        from app.library.cache import Cache
        from app.library.config import Config
        from app.library.Events import EventBus
        from app.library.Scheduler import Scheduler
        from app.library.UpdateChecker import UpdateChecker

        Config._reset_singleton()
        Scheduler._reset_singleton()
        UpdateChecker._reset_singleton()
        EventBus._reset_singleton()
        Cache._reset_singleton()

    def test_singleton_pattern(self):
        """Test that UpdateChecker follows singleton pattern."""
        from app.library.UpdateChecker import UpdateChecker

        instance1 = UpdateChecker.get_instance()
        instance2 = UpdateChecker.get_instance()

        assert instance1 is instance2, "Should return same instance"

    def test_initialization_with_defaults(self):
        """Test UpdateChecker initializes with default config and scheduler."""
        from app.library.UpdateChecker import UpdateChecker

        checker = UpdateChecker.get_instance()

        assert checker._config is not None, "Should have config instance"
        assert checker._scheduler is not None, "Should have scheduler instance"
        assert checker._notify is not None, "Should have EventBus instance"
        assert checker._job_id is None, "Should have no job ID initially"

    def test_attach_schedules_check_when_enabled(self):
        """Test that attach schedules update check when config.check_for_updates is True."""
        import asyncio

        from app.library.config import Config
        from app.library.Events import EventBus
        from app.library.Scheduler import Scheduler
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True

        loop = asyncio.new_event_loop()
        scheduler = Scheduler.get_instance(loop=loop)
        notify = EventBus.get_instance()

        with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
            checker = UpdateChecker.get_instance(config=config, scheduler=scheduler)
            app_mock = MagicMock()

            try:
                checker.attach(app_mock)
                assert checker._job_id is not None, "Should have scheduled a job"
                assert "UpdateChecker.check_for_updates" == checker._job_id, "Job ID should be 'update_checker'"
            finally:
                if checker._job_id:
                    scheduler.remove(checker._job_id)
                loop.close()

    def test_attach_skips_scheduling_when_disabled(self):
        """Test that attach skips scheduling when config.check_for_updates is False."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = False

        checker = UpdateChecker.get_instance(config=config)
        app_mock = MagicMock()

        checker.attach(app_mock)

        assert checker._job_id is None, "Should not have scheduled a job when disabled"

    def test_attach_skips_scheduling_for_dev_version(self):
        """Test that attach skips scheduling when running dev version."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True

        with patch("app.library.UpdateChecker.APP_VERSION", "dev-master"):
            checker = UpdateChecker.get_instance(config=config)
            app_mock = MagicMock()

            checker.attach(app_mock)

            assert checker._job_id is None, "Should not schedule job for dev version"

    @pytest.mark.asyncio
    async def test_on_shutdown_removes_scheduled_job(self):
        """Test that on_shutdown removes the scheduled job."""
        import asyncio

        from app.library.config import Config
        from app.library.Events import EventBus
        from app.library.Scheduler import Scheduler
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True

        loop = asyncio.new_event_loop()
        scheduler = Scheduler.get_instance(loop=loop)
        notify = EventBus.get_instance()

        with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
            checker = UpdateChecker.get_instance(config=config, scheduler=scheduler)
            app_mock = MagicMock()
            try:
                checker.attach(app_mock)
                initial_job_id = checker._job_id
                assert initial_job_id is not None, "Should have job ID before shutdown"
                await checker.on_shutdown(app_mock)
                assert checker._job_id is None, "Should clear job ID after shutdown"
            finally:
                loop.close()

    @pytest.mark.asyncio
    async def test_check_for_updates_skips_when_disabled(self):
        """Test that check_for_updates skips when config.check_for_updates is False."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = False
        config.new_version = ""
        config.yt_new_version = ""

        checker = UpdateChecker.get_instance(config=config)

        (app_status, app_version), (ytdlp_status, ytdlp_version) = await checker.check_for_updates()

        assert "disabled" == app_status, "Should return disabled status for app"
        assert app_version is None, "Should return None for app new_version when disabled"
        assert "disabled" == ytdlp_status, "Should return disabled status for yt-dlp"
        assert ytdlp_version is None, "Should return None for yt-dlp new_version when disabled"
        assert "" == config.new_version, "Should not update new_version when disabled"
        assert "" == config.yt_new_version, "Should not update yt_new_version when disabled"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_finds_newer_version(self, mock_client):
        """Test that check_for_updates detects when a newer version is available."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""
        config.yt_new_version = ""

        mock_app_response = MagicMock()
        mock_app_response.status_code = 200
        mock_app_response.json.return_value = {"tag_name": "v99.0.0"}

        mock_ytdlp_response = MagicMock()
        mock_ytdlp_response.status_code = 200
        mock_ytdlp_response.json.return_value = {"tag_name": "9999.12.31"}

        mock_get = AsyncMock(side_effect=[mock_app_response, mock_ytdlp_response])
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = mock_get
        mock_client.return_value = mock_context

        with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
            checker = UpdateChecker.get_instance(config=config)
            (app_status, app_version), (ytdlp_status, ytdlp_version) = await checker.check_for_updates()

        assert "update_available" == app_status, "Should return update_available status for app"
        assert "v99.0.0" == app_version, "Should return new app version tag"
        assert "v99.0.0" == config.new_version, "Should store new app version tag"
        assert "update_available" == ytdlp_status, "Should return update_available status for yt-dlp"
        assert "9999.12.31" == ytdlp_version, "Should return new yt-dlp version tag"
        assert "9999.12.31" == config.yt_new_version, "Should store new yt-dlp version tag"
        assert checker._job_id is None, "Should stop scheduled task after finding app update"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_no_update_available(self, mock_client):
        """Test that check_for_updates correctly handles when no update is available."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""
        config.yt_new_version = ""

        mock_app_response = MagicMock()
        mock_app_response.status_code = 200
        mock_app_response.json.return_value = {"tag_name": "v1.0.0"}

        mock_ytdlp_response = MagicMock()
        mock_ytdlp_response.status_code = 200
        mock_ytdlp_response.json.return_value = {"tag_name": "2020.01.01"}

        mock_get = AsyncMock(side_effect=[mock_app_response, mock_ytdlp_response])
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = mock_get
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)
        checker._job_id = "test-job"

        (app_status, app_version), (ytdlp_status, ytdlp_version) = await checker.check_for_updates()

        assert "up_to_date" == app_status, "Should return up_to_date status for app"
        assert app_version is None, "Should return None for app new_version"
        assert "" == config.new_version, "Should clear new_version when no app update available"
        assert "up_to_date" == ytdlp_status, "Should return up_to_date status for yt-dlp"
        assert ytdlp_version is None, "Should return None for yt-dlp new_version"
        assert "" == config.yt_new_version, "Should clear yt_new_version when no yt-dlp update available"
        assert "test-job" == checker._job_id, "Should keep scheduled task running"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_handles_http_error(self, mock_client):
        """Test that check_for_updates handles HTTP errors gracefully."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""
        config.yt_new_version = ""

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)

        (app_status, app_version), (ytdlp_status, ytdlp_version) = await checker.check_for_updates()

        assert "error" == app_status, "Should return error status for app"
        assert app_version is None, "Should return None for app new_version on error"
        assert "" == config.new_version, "Should not set new_version on HTTP error"
        assert "error" == ytdlp_status, "Should return error status for yt-dlp"
        assert ytdlp_version is None, "Should return None for yt-dlp new_version on error"
        assert "" == config.yt_new_version, "Should not set yt_new_version on HTTP error"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_handles_exception(self, mock_client):
        """Test that check_for_updates handles exceptions gracefully."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""
        config.yt_new_version = ""

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)

        (app_status, app_version), (ytdlp_status, ytdlp_version) = await checker.check_for_updates()

        assert "error" == app_status, "Should return error status on exception for app"
        assert app_version is None, "Should return None for app new_version on exception"
        assert "" == config.new_version, "Should not set new_version on exception"
        assert "error" == ytdlp_status, "Should return error status on exception for yt-dlp"
        assert ytdlp_version is None, "Should return None for yt-dlp new_version on exception"
        assert "" == config.yt_new_version, "Should not set yt_new_version on exception"

    def test_compare_versions_newer_available(self):
        """Test version comparison detects newer version."""
        from app.library.UpdateChecker import UpdateChecker

        checker = UpdateChecker.get_instance()

        assert checker._compare_versions("1.0.0", "2.0.0") is True, "Should detect 2.0.0 > 1.0.0"
        assert checker._compare_versions("1.0.0", "1.1.0") is True, "Should detect 1.1.0 > 1.0.0"
        assert checker._compare_versions("1.0.0", "1.0.1") is True, "Should detect 1.0.1 > 1.0.0"

    def test_compare_versions_same_version(self):
        """Test version comparison with same version."""
        from app.library.UpdateChecker import UpdateChecker

        checker = UpdateChecker.get_instance()

        assert checker._compare_versions("1.0.0", "1.0.0") is False, "Should detect versions are equal"

    def test_compare_versions_older_version(self):
        """Test version comparison with older version."""
        from app.library.UpdateChecker import UpdateChecker

        checker = UpdateChecker.get_instance()

        assert checker._compare_versions("2.0.0", "1.0.0") is False, "Should detect 1.0.0 is not newer than 2.0.0"

    def test_github_api_url_constant(self):
        """Test that GitHub API URL is correctly defined."""
        from app.library.UpdateChecker import UpdateChecker

        expected_url = "https://api.github.com/repos/arabcoders/ytptube/releases/latest"
        assert UpdateChecker.GITHUB_API_URL == expected_url, "GitHub API URL should be correct"

    @pytest.mark.asyncio
    async def test_check_for_updates_stores_tag_name(self):
        """Test that check_for_updates stores the tag_name when update found."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""
        config.yt_new_version = ""

        mock_app_response = MagicMock()
        mock_app_response.status_code = 200
        mock_app_response.json.return_value = {"tag_name": "v2.0.0"}

        mock_ytdlp_response = MagicMock()
        mock_ytdlp_response.status_code = 200
        mock_ytdlp_response.json.return_value = {"tag_name": "2026.01.01"}

        mock_get = AsyncMock(side_effect=[mock_app_response, mock_ytdlp_response])
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = mock_get

        with patch("app.library.UpdateChecker.async_client", return_value=mock_context):
            with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
                checker = UpdateChecker.get_instance(config=config)
                await checker.check_for_updates()

        assert "v2.0.0" == config.new_version, "Should store full tag_name including 'v' prefix"
        assert "2026.01.01" == config.yt_new_version, "Should store yt-dlp tag_name"

    def test_subscribe_to_started_event(self):
        """Test that attach subscribes to Events.STARTED."""
        import asyncio

        from app.library.config import Config
        from app.library.Events import EventBus
        from app.library.Scheduler import Scheduler
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True

        loop = asyncio.new_event_loop()
        scheduler = Scheduler.get_instance(loop=loop)
        notify = EventBus.get_instance()

        checker = None
        try:
            with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
                checker = UpdateChecker.get_instance(config=config, scheduler=scheduler)
                app_mock = MagicMock()

                checker.attach(app_mock)

                subscriptions = notify._listeners.get("started", [])
                assert len(subscriptions) > 0, "Should have subscribed to STARTED event"
                assert any("UpdateChecker.attach" in name for name, _ in subscriptions), (
                    "Should have UpdateChecker.attach subscription"
                )
        finally:
            if checker and checker._job_id:
                scheduler.remove(checker._job_id)
            loop.close()

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_ytdlp_version_finds_newer_version(self, mock_client):
        """Test that yt-dlp check detects when a newer version is available."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.yt_new_version = ""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "9999.12.31"}

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)
        status, new_version = await checker._check_ytdlp_version()

        assert "update_available" == status, "Should return update_available status for yt-dlp"
        assert "9999.12.31" == new_version, "Should return new yt-dlp version tag"
        assert "9999.12.31" == config.yt_new_version, "Should store new yt-dlp version tag"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_ytdlp_version_no_update_available(self, mock_client):
        """Test that yt-dlp check correctly handles when no update is available."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.yt_new_version = ""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "2020.01.01"}

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)
        status, new_version = await checker._check_ytdlp_version()

        assert "up_to_date" == status, "Should return up_to_date status for yt-dlp"
        assert new_version is None, "Should return None for yt-dlp new_version"
        assert "" == config.yt_new_version, "Should clear yt_new_version when no update available"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_ytdlp_version_handles_http_error(self, mock_client):
        """Test that yt-dlp check handles HTTP errors gracefully."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.yt_new_version = ""

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)
        status, new_version = await checker._check_ytdlp_version()

        assert "error" == status, "Should return error status for yt-dlp on HTTP error"
        assert new_version is None, "Should return None for yt-dlp new_version on error"
        assert "" == config.yt_new_version, "Should not set yt_new_version on HTTP error"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_caches_separately(self, mock_client):
        """Test that app and yt-dlp checks are cached separately."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""
        config.yt_new_version = ""

        mock_app_response = MagicMock()
        mock_app_response.status_code = 200
        mock_app_response.json.return_value = {"tag_name": "v2.0.0"}

        mock_ytdlp_response = MagicMock()
        mock_ytdlp_response.status_code = 200
        mock_ytdlp_response.json.return_value = {"tag_name": "2026.01.01"}

        mock_get = AsyncMock(side_effect=[mock_app_response, mock_ytdlp_response])
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = mock_get
        mock_client.return_value = mock_context

        with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
            checker = UpdateChecker.get_instance(config=config)
            (app_status1, app_version1), (ytdlp_status1, ytdlp_version1) = await checker.check_for_updates()

        assert "update_available" == app_status1, "Should find app update on first call"
        assert "update_available" == ytdlp_status1, "Should find yt-dlp update on first call"

        (app_status2, app_version2), (ytdlp_status2, ytdlp_version2) = await checker.check_for_updates()

        assert "update_available" == app_status2, "Should return cached app result"
        assert "update_available" == ytdlp_status2, "Should return cached yt-dlp result"
        assert app_version1 == app_version2, "App versions should match from cache"
        assert ytdlp_version1 == ytdlp_version2, "yt-dlp versions should match from cache"
