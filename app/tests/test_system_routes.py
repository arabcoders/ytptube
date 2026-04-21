import pytest
from unittest.mock import AsyncMock, patch

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.UpdateChecker import UpdateChecker
from app.routes.api.system import check_updates


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
