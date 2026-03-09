import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.UpdateChecker import UpdateChecker
from app.routes.api.system import check_updates, system_config


class TestSystemConfigEndpoint:
    """Tests for the system configuration endpoint."""

    def setup_method(self):
        """Reset singletons before each test."""
        Config._reset_singleton()

    @pytest.mark.asyncio
    async def test_system_config_does_not_return_queue(self):
        """Test that the configuration endpoint does not include queue data."""
        config = Config.get_instance()
        encoder = Encoder()

        mock_queue = MagicMock()
        mock_queue.is_paused.return_value = False
        mock_done = AsyncMock()
        mock_done.get_total_count = AsyncMock(return_value=0)
        mock_queue.done = mock_done

        with (
            patch("app.routes.api.system.Presets") as mock_presets_cls,
            patch("app.routes.api.system.DLFields") as mock_dl_fields_cls,
            patch("app.routes.api.system.list_folders", return_value=[]),
        ):
            mock_presets_cls.get_instance.return_value.get_all.return_value = []
            mock_dl_fields_cls.get_instance.return_value.get_all_serialized = AsyncMock(return_value=[])

            response = await system_config(mock_queue, config, encoder)

            assert 200 == response.status
            body = json.loads(response.body.decode("utf-8"))
            assert "queue" not in body, "Configuration response should not include queue data"
            assert "app" in body, "Configuration response should include app data"
            assert "paused" in body, "Configuration response should include paused status"
            assert "history_count" in body, "Configuration response should include history_count"
            assert "presets" in body, "Configuration response should include presets"
            assert "dl_fields" in body, "Configuration response should include dl_fields"
            assert "folders" in body, "Configuration response should include folders"


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
    async def test_check_updates_returns_current_version(self):
        """Test check updates includes current version in response."""
        config = Config.get_instance()
        config.check_for_updates = True
        config.app_version = "v1.2.3"
        encoder = Encoder()
        update_checker = UpdateChecker.get_instance()

        with patch.object(update_checker, "check_for_updates", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (("up_to_date", None), ("up_to_date", None))
            response = await check_updates(config, encoder, update_checker)

            assert 200 == response.status, "Should return 200"
            body = response.body.decode("utf-8")
            assert "1.2.3" in body, "Response should include current version"

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

    @pytest.mark.asyncio
    async def test_check_updates_null_when_no_new_version(self):
        """Test check updates returns null for new_version when none available."""
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
            assert "null" in body.lower(), "Response should include null for new_version when not available"

    @pytest.mark.asyncio
    async def test_check_updates_error_status(self):
        """Test check updates handles error status correctly."""
        config = Config.get_instance()
        config.check_for_updates = True
        config.app_version = "v1.0.0"
        encoder = Encoder()
        update_checker = UpdateChecker.get_instance()

        with patch.object(update_checker, "check_for_updates", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (("error", None), ("error", None))
            response = await check_updates(config, encoder, update_checker)

            assert 200 == response.status, "Should return 200"
            body = response.body.decode("utf-8")
            assert "error" in body, "Response should include error status"
