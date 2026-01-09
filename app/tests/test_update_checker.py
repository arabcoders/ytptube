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

        # Create scheduler with a fresh event loop
        loop = asyncio.new_event_loop()
        scheduler = Scheduler.get_instance(loop=loop)
        notify = EventBus.get_instance()

        # Mock APP_VERSION to be a release version
        with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
            checker = UpdateChecker.get_instance(config=config, scheduler=scheduler)
            app_mock = MagicMock()

            try:
                checker.attach(app_mock)

                assert checker._job_id is not None, "Should have scheduled a job"
                assert "update_checker" == checker._job_id, "Job ID should be 'update_checker'"
            finally:
                # Clean up
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

        # Create scheduler with a fresh event loop
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

        checker = UpdateChecker.get_instance(config=config)

        # Should return disabled status
        status, new_version = await checker.check_for_updates()

        assert "disabled" == status, "Should return disabled status"
        assert new_version is None, "Should return None for new_version when disabled"
        assert "" == config.new_version, "Should not update new_version when disabled"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_finds_newer_version(self, mock_client):
        """Test that check_for_updates detects when a newer version is available."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v99.0.0"}

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        # Mock current version to be older
        with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
            checker = UpdateChecker.get_instance(config=config)
            status, new_version = await checker.check_for_updates()

        assert "update_available" == status, "Should return update_available status"
        assert "v99.0.0" == new_version, "Should return new version tag"
        assert "v99.0.0" == config.new_version, "Should store new version tag"
        assert checker._job_id is None, "Should stop scheduled task after finding update"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_no_update_available(self, mock_client):
        """Test that check_for_updates correctly handles when no update is available."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""

        # Mock HTTP response with older version (current is hardcoded as 1.0.14 in the code)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v1.0.0"}

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)
        checker._job_id = "test-job"  # Set a job ID to verify it's not removed

        status, new_version = await checker.check_for_updates()

        assert "up_to_date" == status, "Should return up_to_date status"
        assert new_version is None, "Should return None for new_version"
        assert "" == config.new_version, "Should clear new_version when no update available"
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

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)

        status, new_version = await checker.check_for_updates()

        assert "error" == status, "Should return error status"
        assert new_version is None, "Should return None for new_version on error"
        assert "" == config.new_version, "Should not set new_version on HTTP error"

    @pytest.mark.asyncio
    @patch("app.library.UpdateChecker.async_client")
    async def test_check_for_updates_handles_exception(self, mock_client):
        """Test that check_for_updates handles exceptions gracefully."""
        from app.library.config import Config
        from app.library.UpdateChecker import UpdateChecker

        config = Config.get_instance()
        config.check_for_updates = True
        config.new_version = ""

        # Mock exception during HTTP request
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.return_value = mock_context

        checker = UpdateChecker.get_instance(config=config)

        status, new_version = await checker.check_for_updates()

        assert "error" == status, "Should return error status on exception"
        assert new_version is None, "Should return None for new_version on exception"
        assert "" == config.new_version, "Should not set new_version on exception"

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

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tag_name": "v2.0.0"}

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        with patch("app.library.UpdateChecker.async_client", return_value=mock_context):
            with patch("app.library.UpdateChecker.APP_VERSION", "v1.0.0"):
                checker = UpdateChecker.get_instance(config=config)
                await checker.check_for_updates()

        assert "v2.0.0" == config.new_version, "Should store full tag_name including 'v' prefix"

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

                # Verify subscription was created
                subscriptions = notify._listeners.get("started", {})
                assert len(subscriptions) > 0, "Should have subscribed to STARTED event"
                assert any("UpdateChecker.attach" in name for name in subscriptions.keys()), (
                    "Should have UpdateChecker.attach subscription"
                )
        finally:
            if checker and checker._job_id:
                scheduler.remove(checker._job_id)
            loop.close()
