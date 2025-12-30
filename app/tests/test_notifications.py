import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from aiohttp import web

from app.library.BackgroundWorker import BackgroundWorker
from app.library.encoder import Encoder
from app.library.Events import Event
from app.library.ItemDTO import ItemDTO
from app.library.Notifications import (
    Notification,
    NotificationEvents,
    Target,
    TargetRequest,
    TargetRequestHeader,
)


class TestTargetRequestHeader:
    """Test the TargetRequestHeader dataclass."""

    def test_target_request_header_creation(self):
        """Test creating a TargetRequestHeader."""
        header = TargetRequestHeader(key="Authorization", value="Bearer token123")

        assert header.key == "Authorization"
        assert header.value == "Bearer token123"

    def test_target_request_header_serialize(self):
        """Test serializing a TargetRequestHeader."""
        header = TargetRequestHeader(key="Content-Type", value="application/json")
        serialized = header.serialize()

        expected = {"key": "Content-Type", "value": "application/json"}
        assert serialized == expected

    def test_target_request_header_json(self):
        """Test JSON serialization of TargetRequestHeader."""
        header = TargetRequestHeader(key="X-API-Key", value="secret123")
        json_str = header.json()

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["key"] == "X-API-Key"
        assert parsed["value"] == "secret123"

    def test_target_request_header_get(self):
        """Test get method of TargetRequestHeader."""
        header = TargetRequestHeader(key="Authorization", value="Bearer token")

        assert header.get("key") == "Authorization"
        assert header.get("value") == "Bearer token"
        assert header.get("nonexistent", "default") == "default"


class TestTargetRequest:
    """Test the TargetRequest dataclass."""

    def test_target_request_creation_defaults(self):
        """Test creating a TargetRequest with defaults."""
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")

        assert request.type == "json"
        assert request.method == "POST"
        assert request.url == "https://example.com/webhook"
        assert request.headers == []
        assert request.data_key == "data"

    def test_target_request_creation_with_headers(self):
        """Test creating a TargetRequest with headers."""
        headers = [
            TargetRequestHeader(key="Authorization", value="Bearer token"),
            TargetRequestHeader(key="Content-Type", value="application/json"),
        ]
        request = TargetRequest(
            type="json", method="POST", url="https://example.com/webhook", headers=headers, data_key="payload"
        )

        assert len(request.headers) == 2
        assert request.headers[0].key == "Authorization"
        assert request.data_key == "payload"

    def test_target_request_serialize(self):
        """Test serializing a TargetRequest."""
        headers = [TargetRequestHeader(key="X-Token", value="abc123")]
        request = TargetRequest(
            type="json", method="PUT", url="https://api.example.com/notify", headers=headers, data_key="content"
        )

        serialized = request.serialize()
        expected = {
            "type": "json",
            "method": "PUT",
            "url": "https://api.example.com/notify",
            "data_key": "content",
            "headers": [{"key": "X-Token", "value": "abc123"}],
        }
        assert serialized == expected

    def test_target_request_json(self):
        """Test JSON serialization of TargetRequest."""
        request = TargetRequest(type="form", method="POST", url="https://webhook.site/test")
        json_str = request.json()

        parsed = json.loads(json_str)
        assert parsed["type"] == "form"
        assert parsed["method"] == "POST"
        assert parsed["url"] == "https://webhook.site/test"

    def test_target_request_get(self):
        """Test get method of TargetRequest."""
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")

        assert request.get("type") == "json"
        assert request.get("method") == "POST"
        assert request.get("nonexistent", "default") == "default"


class TestTarget:
    """Test the Target dataclass."""

    def test_target_creation_minimal(self):
        """Test creating a Target with minimal required fields."""
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=str(uuid.uuid4()), name="Test Webhook", request=request)

        assert target.name == "Test Webhook"
        assert target.on == []
        assert target.presets == []
        assert target.request == request

    def test_target_creation_full(self):
        """Test creating a Target with all fields."""
        target_id = str(uuid.uuid4())
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(
            id=target_id,
            name="Full Test Webhook",
            on=["item_completed", "item_failed"],
            presets=["default", "audio_only"],
            request=request,
        )

        assert target.id == target_id
        assert target.name == "Full Test Webhook"
        assert target.on == ["item_completed", "item_failed"]
        assert target.presets == ["default", "audio_only"]

    def test_target_serialize(self):
        """Test serializing a Target."""
        target_id = str(uuid.uuid4())
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=target_id, name="Test Target", on=["item_completed"], presets=["default"], request=request)

        serialized = target.serialize()
        assert serialized["id"] == target_id
        assert serialized["name"] == "Test Target"
        assert serialized["on"] == ["item_completed"]
        assert serialized["presets"] == ["default"]
        assert isinstance(serialized["request"], dict)

    def test_target_json(self):
        """Test JSON serialization of Target."""
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=str(uuid.uuid4()), name="JSON Test", request=request)

        json_str = target.json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "JSON Test"

    def test_target_get(self):
        """Test get method of Target."""
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=str(uuid.uuid4()), name="Get Test", request=request)

        assert target.get("name") == "Get Test"
        assert target.get("nonexistent", "default") == "default"


class TestNotificationEvents:
    """Test the NotificationEvents class."""

    def test_notification_events_constants(self):
        """Test that NotificationEvents has expected constants."""
        assert hasattr(NotificationEvents, "TEST")
        assert hasattr(NotificationEvents, "ITEM_ADDED")
        assert hasattr(NotificationEvents, "ITEM_COMPLETED")
        assert hasattr(NotificationEvents, "ITEM_CANCELLED")
        assert hasattr(NotificationEvents, "ITEM_DELETED")
        assert hasattr(NotificationEvents, "LOG_INFO")
        assert hasattr(NotificationEvents, "LOG_ERROR")

    def test_get_events(self):
        """Test get_events static method."""
        events = NotificationEvents.get_events()

        assert isinstance(events, dict)
        assert "TEST" in events
        assert "ITEM_ADDED" in events
        assert "ITEM_COMPLETED" in events

    def test_events_function(self):
        """Test events function."""
        events_list = NotificationEvents.events()

        assert isinstance(events_list, list)
        assert len(events_list) > 0

    def test_is_valid(self):
        """Test is_valid static method."""
        # Valid events
        assert NotificationEvents.is_valid("test")
        assert NotificationEvents.is_valid("item_added")
        assert NotificationEvents.is_valid("item_completed")

        # Invalid events
        assert not NotificationEvents.is_valid("invalid_event")
        assert not NotificationEvents.is_valid("")
        assert not NotificationEvents.is_valid(None)


class TestNotification:
    """Test the Notification singleton class."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Reset singleton instance to ensure clean state
        Notification._reset_singleton()

    def teardown_method(self):
        """Clean up after each test."""
        # Reset singleton instance to prevent test pollution
        Notification._reset_singleton()

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    def test_notification_singleton(self, mock_background_worker, mock_config):
        """Test that Notification follows singleton pattern."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_background_worker.get_instance.return_value = Mock()

        instance1 = Notification.get_instance()
        instance2 = Notification.get_instance()

        assert instance1 is instance2
        assert isinstance(instance1, Notification)

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    def test_notification_init_default_params(self, mock_background_worker, mock_config):
        """Test Notification initialization with default parameters."""
        mock_config_instance = Mock(debug=False, config_path="/tmp/test", app_version="1.0.0")
        mock_config.get_instance.return_value = mock_config_instance
        mock_background_worker.get_instance.return_value = Mock()

        with patch("pathlib.Path.exists", return_value=False):
            notification = Notification.get_instance()

            assert notification._debug is False
            assert notification._version == "1.0.0"
            assert isinstance(notification._targets, list)
            assert len(notification._targets) == 0

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    def test_notification_init_custom_params(self, mock_background_worker, mock_config):
        """Test Notification initialization with custom parameters."""
        _ = mock_background_worker, mock_config  # Suppress unused variable warnings
        mock_config_instance = Mock(debug=True, config_path="/custom/path", app_version="2.0.0")
        mock_client = Mock(spec=httpx.AsyncClient)
        mock_encoder = Mock(spec=Encoder)
        mock_worker = Mock(spec=BackgroundWorker)

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

        notification = Notification.get_instance(
            file=temp_path,
            client=mock_client,
            encoder=mock_encoder,
            config=mock_config_instance,
            background_worker=mock_worker,
        )

        assert notification._debug is True
        assert notification._version == "2.0.0"
        assert notification._client == mock_client
        assert notification._encoder == mock_encoder
        assert notification._offload == mock_worker

    def test_get_targets_empty(self):
        """Test get_targets when no targets are loaded."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()
            targets = notification.get_targets()

            assert isinstance(targets, list)
            assert len(targets) == 0

    def test_clear_targets(self):
        """Test clearing notification targets."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()

            # Add a dummy target
            notification._targets = ["dummy_target"]
            assert len(notification._targets) == 1

            # Clear targets
            result = notification.clear()

            assert result == notification  # Should return self
            assert len(notification._targets) == 0

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    def test_save_targets(self, mock_worker, mock_config):
        """Test saving targets to file."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_path = temp_file.name

        # Create a test target
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=str(uuid.uuid4()), name="Test Target", request=request)

        notification = Notification.get_instance(file=temp_path)
        result = notification.save([target])

        assert result == notification  # Should return self

        # Verify file was written
        with open(temp_path) as f:
            saved_data = json.load(f)

        assert isinstance(saved_data, list)
        assert len(saved_data) == 1
        assert saved_data[0]["name"] == "Test Target"

        # Clean up
        Path(temp_path).unlink()

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    def test_load_targets_empty_file(self, mock_worker, mock_config):
        """Test loading targets from empty file."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("")  # Empty file
            temp_path = temp_file.name

        notification = Notification.get_instance(file=temp_path)
        result = notification.load()

        assert result == notification  # Should return self
        assert len(notification._targets) == 0

        # Clean up
        Path(temp_path).unlink()

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    @patch("app.library.Notifications.Presets")
    def test_load_targets_valid_file(self, mock_presets, mock_worker, mock_config):
        """Test loading targets from valid file."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()

        # Mock preset with name attribute
        mock_preset = Mock()
        mock_preset.name = "default"
        mock_presets.get_instance.return_value.get_all.return_value = [mock_preset]

        target_data = [
            {
                "id": str(uuid.uuid4()),
                "name": "Test Webhook",
                "on": ["item_completed"],
                "presets": ["default"],
                "request": {
                    "type": "json",
                    "method": "POST",
                    "url": "https://example.com/webhook",
                    "data_key": "data",
                    "headers": [],
                },
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            json.dump(target_data, temp_file)
            temp_path = temp_file.name

        notification = Notification.get_instance(file=temp_path)
        result = notification.load()

        assert result == notification  # Should return self
        assert len(notification._targets) == 1
        assert notification._targets[0].name == "Test Webhook"

        # Clean up
        Path(temp_path).unlink()

    def test_make_target(self):
        """Test make_target method."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()

            target_dict = {
                "id": str(uuid.uuid4()),
                "name": "Test Target",
                "on": ["item_completed"],
                "presets": ["default"],
                "request": {
                    "type": "json",
                    "method": "POST",
                    "url": "https://example.com/webhook",
                    "data_key": "payload",
                    "headers": [{"key": "Authorization", "value": "Bearer token"}],
                },
            }

            target = notification.make_target(target_dict)

            assert isinstance(target, Target)
            assert target.name == "Test Target"
            assert target.on == ["item_completed"]
            assert target.presets == ["default"]
            assert target.request.url == "https://example.com/webhook"
            assert target.request.data_key == "payload"
            assert len(target.request.headers) == 1
            assert target.request.headers[0].key == "Authorization"

    def test_validate_target_valid(self):
        """Test validate method with valid target."""
        target_dict = {
            "id": str(uuid.uuid4()),
            "name": "Valid Target",
            "request": {"url": "https://example.com/webhook"},
        }

        with (
            patch("app.library.Notifications.NotificationEvents.get_events") as mock_events,
            patch("app.library.Notifications.Presets") as mock_presets,
        ):
            mock_events.return_value.values.return_value = ["item_completed"]
            mock_presets.get_instance.return_value.get_all.return_value = []

            result = Notification.validate(target_dict)
            assert result is True

    def test_validate_target_missing_id(self):
        """Test validate method with missing ID."""
        target_dict = {"name": "Missing ID Target", "request": {"url": "https://example.com/webhook"}}

        with pytest.raises(ValueError, match=r"Invalid notification target\. No ID found\."):
            Notification.validate(target_dict)

    def test_validate_target_invalid_id(self):
        """Test validate method with invalid UUID."""
        target_dict = {
            "id": "invalid-uuid",
            "name": "Invalid ID Target",
            "request": {"url": "https://example.com/webhook"},
        }

        with pytest.raises(ValueError, match=r"Invalid notification target\. No ID found\."):
            Notification.validate(target_dict)

    def test_validate_target_missing_name(self):
        """Test validate method with missing name."""
        target_dict = {"id": str(uuid.uuid4()), "request": {"url": "https://example.com/webhook"}}

        with pytest.raises(ValueError, match=r"Invalid notification target\. No name found\."):
            Notification.validate(target_dict)

    def test_validate_target_missing_request(self):
        """Test validate method with missing request."""
        target_dict = {"id": str(uuid.uuid4()), "name": "Missing Request Target"}

        with pytest.raises(ValueError, match=r"Invalid notification target\. No request details found\."):
            Notification.validate(target_dict)

    def test_validate_target_missing_url(self):
        """Test validate method with missing URL."""
        target_dict = {"id": str(uuid.uuid4()), "name": "Missing URL Target", "request": {}}

        with pytest.raises(ValueError, match=r"Invalid notification target\. No URL found\."):
            Notification.validate(target_dict)

    def test_validate_target_invalid_method(self):
        """Test validate method with invalid HTTP method."""
        target_dict = {
            "id": str(uuid.uuid4()),
            "name": "Invalid Method Target",
            "request": {
                "url": "https://example.com/webhook",
                "method": "GET",  # Only POST and PUT are allowed
            },
        }

        with pytest.raises(ValueError, match=r"Invalid notification target\. Invalid method found\."):
            Notification.validate(target_dict)

    def test_validate_target_invalid_type(self):
        """Test validate method with invalid request type."""
        target_dict = {
            "id": str(uuid.uuid4()),
            "name": "Invalid Type Target",
            "request": {
                "url": "https://example.com/webhook",
                "type": "xml",  # Only json and form are allowed
            },
        }

        with pytest.raises(ValueError, match=r"Invalid notification target\. Invalid type found\."):
            Notification.validate(target_dict)

    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    @patch("app.library.Notifications.EventBus")
    def test_attach(self, mock_eventbus, mock_worker, mock_config):
        """Test attach method."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance

        notification = Notification.get_instance()
        app = Mock(spec=web.Application)

        with patch.object(notification, "load") as mock_load:
            notification.attach(app)

            mock_load.assert_called_once()
            mock_eventbus_instance.subscribe.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    async def test_send_no_targets(self, mock_worker, mock_config):
        """Test send method with no targets."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()

        notification = Notification.get_instance()
        event = Event(event="test", data={"test": "data"})

        result = await notification.send(event)
        assert result == []

    @pytest.mark.asyncio
    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    async def test_send_invalid_event_data(self, mock_worker, mock_config):
        """Test send method with invalid event data."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()

        notification = Notification.get_instance()
        # Add a target
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=str(uuid.uuid4()), name="Test Target", request=request)
        notification._targets = [target]

        event = Event(
            event="test",
            data="invalid_string_data",  # Should be ItemDTO or dict
        )

        result = await notification.send(event)
        assert result == []

    @pytest.mark.asyncio
    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    async def test_send_with_http_target(self, mock_worker, mock_config):
        """Test send method with HTTP target."""
        mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
        mock_worker.get_instance.return_value = Mock()

        # Mock HTTP client
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)

        notification = Notification.get_instance(client=mock_client)

        # Add HTTP target
        request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
        target = Target(id=str(uuid.uuid4()), name="Test HTTP Target", request=request)
        notification._targets = [target]

        # Create test event
        item_dto = ItemDTO(
            id="test_id", url="https://youtube.com/watch?v=test", title="Test Video", folder="/downloads"
        )
        event = Event(event="item_completed", data=item_dto)

        result = await notification.send(event)

        assert len(result) == 1
        assert result[0]["status"] == 200
        assert result[0]["text"] == "OK"
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.library.Notifications.Config")
    @patch("app.library.Notifications.BackgroundWorker")
    async def test_send_with_apprise_target(self, mock_worker, mock_config):
        """Test send method with Apprise target."""
        mock_config.get_instance.return_value = Mock(
            debug=False, config_path="/tmp", app_version="1.0.0", apprise_config="/tmp/apprise.conf"
        )
        mock_worker.get_instance.return_value = Mock()

        notification = Notification.get_instance()

        # Add Apprise target (non-HTTP URL)
        request = TargetRequest(type="json", method="POST", url="discord://webhook_id/webhook_token")
        target = Target(id=str(uuid.uuid4()), name="Test Discord Target", request=request)
        notification._targets = [target]

        # Create test event
        event = Event(event="item_completed", data={"test": "data"})

        with patch("app.library.Notifications.Path") as mock_path, patch("builtins.__import__") as mock_import:
            # Mock apprise config file doesn't exist
            mock_path.return_value.exists.return_value = False

            # Mock apprise import
            mock_apprise = Mock()
            mock_notify = Mock()
            # Mock async_notify as an AsyncMock that returns True
            mock_notify.async_notify = AsyncMock(return_value=True)
            mock_apprise.Apprise.return_value = mock_notify
            mock_import.return_value = mock_apprise

            result = await notification.send(event)

            # Should return empty dict from _apprise method
            assert len(result) == 1
            assert result[0] == {}

    def test_check_preset_no_presets(self):
        """Test _check_preset method with target having no preset filters."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()

            request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
            target = Target(
                id=str(uuid.uuid4()),
                name="No Preset Filter",
                presets=[],  # No preset filter
                request=request,
            )

            event = Event(event="item_completed", data={"preset": "default"})

            result = notification._check_preset(target, event)
            assert result is True  # Should pass when no preset filter

    def test_check_preset_with_matching_preset(self):
        """Test _check_preset method with matching preset."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()

            request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
            target = Target(
                id=str(uuid.uuid4()), name="Preset Filter", presets=["default", "audio_only"], request=request
            )

            # Test with ItemDTO
            item_dto = ItemDTO(
                id="test_id", url="https://youtube.com/test", title="Test Video", folder="/downloads", preset="default"
            )
            event = Event(event="item_completed", data=item_dto)

            result = notification._check_preset(target, event)
            assert result is True

    def test_check_preset_with_non_matching_preset(self):
        """Test _check_preset method with non-matching preset."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()

            request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
            target = Target(id=str(uuid.uuid4()), name="Preset Filter", presets=["audio_only"], request=request)

            event = Event(
                event="item_completed",
                data={"preset": "video_only"},  # Different preset
            )

            result = notification._check_preset(target, event)
            assert result is False

    def test_emit_invalid_event(self):
        """Test emit method with invalid event."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker_instance = Mock()
            mock_worker.get_instance.return_value = mock_worker_instance

            notification = Notification.get_instance()

            # Add a target
            request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
            target = Target(id=str(uuid.uuid4()), name="Test Target", request=request)
            notification._targets = [target]

            # Create invalid event
            event = Event(event="invalid_event", data={"test": "data"})

            with patch("app.library.Notifications.NotificationEvents.is_valid", return_value=False):
                result = notification.emit(event, None)

                # Should return None and not submit to background worker
                assert result is None
                mock_worker_instance.submit.assert_not_called()

    def test_emit_valid_event(self):
        """Test emit method with valid event."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker_instance = Mock()
            mock_worker.get_instance.return_value = mock_worker_instance

            notification = Notification.get_instance()

            # Add a target
            request = TargetRequest(type="json", method="POST", url="https://example.com/webhook")
            target = Target(id=str(uuid.uuid4()), name="Test Target", request=request)
            notification._targets = [target]

            # Create valid event
            event = Event(event="item_completed", data={"test": "data"})

            with patch("app.library.Notifications.NotificationEvents.is_valid", return_value=True):
                result = notification.emit(event, None)

                # Should return None but submit to background worker
                assert result is None
                mock_worker_instance.submit.assert_called_once_with(notification.send, event)

    @pytest.mark.asyncio
    async def test_noop(self):
        """Test noop method."""
        with (
            patch("app.library.Notifications.Config") as mock_config,
            patch("app.library.Notifications.BackgroundWorker") as mock_worker,
        ):
            mock_config.get_instance.return_value = Mock(debug=False, config_path="/tmp", app_version="1.0.0")
            mock_worker.get_instance.return_value = Mock()

            notification = Notification.get_instance()
            result = await notification.noop()

            assert result is None
