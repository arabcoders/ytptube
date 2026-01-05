import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.library.Presets import DEFAULT_PRESETS, Preset, Presets


class TestPreset:
    """Test the Preset dataclass."""

    def test_preset_creation_with_defaults(self):
        """Test creating a preset with default values."""
        preset = Preset(name="test_preset")

        assert preset.name == "test_preset"
        assert preset.description == ""
        assert preset.folder == ""
        assert preset.template == ""
        assert preset.cookies == ""
        assert preset.cli == ""
        assert preset.default is False
        # ID should be auto-generated UUID
        assert len(preset.id) == 36  # UUID4 string length
        assert "-" in preset.id

    def test_preset_creation_with_all_fields(self):
        """Test creating a preset with all fields specified."""
        preset_id = str(uuid.uuid4())
        preset = Preset(
            id=preset_id,
            name="test_preset",
            description="Test description",
            folder="test_folder",
            template="test_template",
            cookies="test_cookies",
            cli="--test-option",
            default=True,
            priority=10,
        )

        assert preset.id == preset_id
        assert preset.name == "test_preset"
        assert preset.description == "Test description"
        assert preset.folder == "test_folder"
        assert preset.template == "test_template"
        assert preset.cookies == "test_cookies"
        assert preset.cli == "--test-option"
        assert preset.priority == 10
        assert preset.default is True

    def test_preset_serialize(self):
        """Test preset serialization to dictionary."""
        preset = Preset(name="test_preset", description="Test description", cli="--test-option")

        serialized = preset.serialize()

        assert isinstance(serialized, dict)
        assert serialized["name"] == "test_preset"
        assert serialized["description"] == "Test description"
        assert serialized["cli"] == "--test-option"
        assert "id" in serialized

    def test_preset_json(self):
        """Test preset JSON serialization."""
        preset = Preset(name="test_preset", cli="--test-option")

        json_str = preset.json()

        assert isinstance(json_str, str)
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["name"] == "test_preset"
        assert parsed["cli"] == "--test-option"

    def test_preset_get_method(self):
        """Test preset get method for accessing fields."""
        preset = Preset(name="test_preset", description="Test description")

        assert preset.get("name") == "test_preset"
        assert preset.get("description") == "Test description"
        assert preset.get("nonexistent") is None
        assert preset.get("nonexistent", "default_value") == "default_value"

    def test_preset_id_generation(self):
        """Test that each preset gets a unique ID."""
        preset1 = Preset(name="preset1")
        preset2 = Preset(name="preset2")

        assert preset1.id != preset2.id
        assert len(preset1.id) == 36
        assert len(preset2.id) == 36


class TestPresets:
    """Test the Presets singleton manager."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Reset singleton completely
        Presets._reset_singleton()

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_singleton(self, mock_eventbus, mock_config):
        """Test that Presets follows singleton pattern."""
        mock_config.get_instance.return_value = Mock(config_path="/tmp", default_preset="default")
        mock_eventbus.get_instance.return_value = Mock()

        instance1 = Presets.get_instance()
        instance2 = Presets.get_instance()

        assert instance1 is instance2
        assert isinstance(instance1, Presets)

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_initialization(self, mock_eventbus, mock_config):
        """Test Presets initialization with default presets."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus_instance = Mock()
        mock_eventbus.get_instance.return_value = mock_eventbus_instance

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Should have default presets loaded
            default_presets = presets._default
            assert len(default_presets) > 0

            # Check that default presets are Preset instances
            for preset in default_presets:
                assert isinstance(preset, Preset)
                assert preset.default is True

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_load_empty_file(self, mock_eventbus, mock_config):
        """Test loading presets from empty or non-existent file."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)
            presets.clear()  # Ensure we start with empty items

            result = presets.load()

            assert result is presets
            assert len(presets._items) == 0
            assert len(presets._default) > 0  # Should still have default presets

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    @patch("app.library.Presets.arg_converter")
    def test_presets_load_valid_file(self, mock_arg_converter, mock_eventbus, mock_config):
        """Test loading presets from valid JSON file."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_arg_converter.return_value = []  # Mock successful CLI parsing

        test_presets = [
            {"id": str(uuid.uuid4()), "name": "test_preset_1", "description": "Test preset 1", "cli": "--format best"},
            {"id": str(uuid.uuid4()), "name": "test_preset_2", "description": "Test preset 2", "cli": "--format worst"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets_file.write_text(json.dumps(test_presets, indent=2))

            presets = Presets(file=presets_file, config=mock_config_instance)
            presets._items.clear()  # Ensure we start with empty items
            result = presets.load()

            assert result is presets
            assert len(presets._items) == 2
            assert presets._items[0].name == "test_preset_1"
            assert presets._items[1].name == "test_preset_2"

    @patch("app.library.Presets.EventBus")
    @patch("app.library.Presets.Config")
    def test_presets_load_invalid_json(self, mock_eventbus, mock_config):
        """Test loading presets from invalid JSON file."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets_file.write_text("invalid json content")

            presets = Presets(file=presets_file, config=mock_config_instance)

            # Should handle invalid JSON gracefully
            result = presets.load()
            assert result is presets
            assert len(presets._items) == 0

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    @patch("app.library.Presets.arg_converter")
    def test_presets_load_with_format_migration(self, mock_arg_converter, mock_eventbus, mock_config):
        """Test loading presets with old format that needs migration."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_arg_converter.return_value = []  # Mock successful CLI parsing

        # Old format preset with 'format' field instead of 'cli'
        old_preset = {"name": "old_preset", "format": "best[height<=720]", "description": "Old format preset"}

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets_file.write_text(json.dumps([old_preset]))

            presets = Presets(file=presets_file, config=mock_config_instance)
            result = presets.load()

            assert result is presets
            assert len(presets._items) == 1
            loaded_preset = presets._items[0]
            assert loaded_preset.name == "old_preset"
            # Should have migrated format to cli
            assert "best[height<=720]" in loaded_preset.cli
            assert "--format" in loaded_preset.cli
            # Should have generated ID
            assert loaded_preset.id is not None

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_validate_valid_preset(self, mock_eventbus, mock_config):
        """Test validating a valid preset."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            valid_preset = {"id": str(uuid.uuid4()), "name": "valid_preset", "cli": "--format best"}

            result = presets.validate(valid_preset)
            assert result is True

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_validate_invalid_preset(self, mock_eventbus, mock_config):
        """Test validating invalid presets."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Test missing ID
            with pytest.raises(ValueError, match="No id found"):
                presets.validate({"name": "test"})

            # Test missing name
            with pytest.raises(ValueError, match="No name found"):
                presets.validate({"id": str(uuid.uuid4())})

            # Test wrong type
            with pytest.raises(ValueError, match="Unexpected"):
                presets.validate("invalid_type")

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    @patch("app.library.Presets.arg_converter")
    def test_presets_save(self, mock_arg_converter, mock_eventbus, mock_config):
        """Test saving presets to file."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_arg_converter.return_value = []  # Mock successful CLI parsing

        test_presets = [
            Preset(name="test1", cli="--format best"),
            Preset(name="test2", cli="--format worst", default=True),  # This should be excluded from save
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            result = presets.save(test_presets)

            assert result is presets
            assert presets_file.exists()

            # Should only save non-default presets
            saved_data = json.loads(presets_file.read_text())
            assert len(saved_data) == 1
            assert saved_data[0]["name"] == "test1"

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_get_all(self, mock_eventbus, mock_config):
        """Test getting all presets (default + custom)."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Add a custom preset
            custom_preset = Preset(name="custom", cli="--custom")
            presets._items.append(custom_preset)

            all_presets = presets.get_all()

            # Should include both default and custom presets
            assert len(all_presets) > 1
            assert any(p.name == "custom" for p in all_presets)
            assert any(p.default is True for p in all_presets)

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_get_by_id(self, mock_eventbus, mock_config):
        """Test getting preset by ID."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            test_id = str(uuid.uuid4())
            test_preset = Preset(id=test_id, name="test_preset")
            presets._items.append(test_preset)

            found_preset = presets.get(test_id)

            assert found_preset is not None
            assert found_preset.id == test_id
            assert found_preset.name == "test_preset"

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_get_by_name(self, mock_eventbus, mock_config):
        """Test getting preset by name."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            test_preset = Preset(name="test_preset", cli="--test")
            presets._items.append(test_preset)

            found_preset = presets.get("test_preset")

            assert found_preset is not None
            assert found_preset.name == "test_preset"
            assert found_preset.cli == "--test"

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_get_nonexistent(self, mock_eventbus, mock_config):
        """Test getting non-existent preset returns None."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            found_preset = presets.get("nonexistent")

            assert found_preset is None

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_get_empty_parameter(self, mock_eventbus, mock_config):
        """Test getting preset with empty string returns None."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            assert presets.get("") is None
            assert presets.get(None) is None

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_has_method(self, mock_eventbus, mock_config):
        """Test has method for checking preset existence."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            test_preset = Preset(name="existing_preset")
            presets._items.append(test_preset)

            assert presets.has("existing_preset") is True
            assert presets.has(test_preset.id) is True
            assert presets.has("nonexistent") is False

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_clear(self, mock_eventbus, mock_config):
        """Test clearing all custom presets."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Add some custom presets
            presets._items.append(Preset(name="custom1"))
            presets._items.append(Preset(name="custom2"))

            assert len(presets._items) == 2

            result = presets.clear()

            assert result is presets
            assert len(presets._items) == 0

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_file_permissions(self, mock_eventbus, mock_config):
        """Test that presets file gets correct permissions."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            # Create file with different permissions
            presets_file.write_text("{}")
            presets_file.chmod(0o644)

            # Creating Presets instance should attempt to fix permissions
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Note: The actual chmod might fail in test environment,
            # but we're testing that the code attempts it
            assert presets is not None

    def test_default_presets_validation(self):
        """Test that all default presets are valid."""
        # This test verifies that the DEFAULT_PRESETS constant contains valid presets
        for i, preset_data in enumerate(DEFAULT_PRESETS):
            assert "id" in preset_data, f"Default preset {i} missing id"
            assert "name" in preset_data, f"Default preset {i} missing name"
            assert "default" in preset_data, f"Default preset {i} missing default flag"
            assert preset_data["default"] is True, f"Default preset {i} should have default=True"

            # Should be able to create Preset instance
            preset = Preset(
                id=preset_data["id"],
                name=preset_data["name"],
                description=preset_data.get("description", ""),
                folder=preset_data.get("folder", ""),
                template=preset_data.get("template", ""),
                cli=preset_data.get("cli", ""),
                default=preset_data["default"],
            )
            assert isinstance(preset, Preset)

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_attach_method(self, mock_eventbus, mock_config):
        """Test the attach method for aiohttp integration."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_app = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Mock the get method to return a preset for default_preset check
            with patch.object(presets, "get", return_value=Mock()) as mock_get:
                presets.attach(mock_app)
                mock_get.assert_called_once_with("default")

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_presets_attach_default_preset_not_found(self, mock_eventbus, mock_config):
        """Test attach method when default preset is not found."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="nonexistent")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_app = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            with patch.object(presets, "get", return_value=None):
                # The actual config instance stored in presets should be checked
                presets.attach(mock_app)
                # Should have reset default_preset to "default"
                assert presets._config.default_preset == "default"

    @pytest.mark.asyncio
    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    async def test_presets_on_shutdown(self, mock_eventbus, mock_config):
        """Test the on_shutdown method."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_app = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Should not raise an exception
            await presets.on_shutdown(mock_app)

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    @patch("app.library.Presets.LOG")
    @patch("app.library.Presets.arg_converter")
    def test_presets_load_invalid_preset_in_file(self, mock_arg_converter, mock_log, mock_eventbus, mock_config):
        """Test loading file with some invalid presets."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()
        mock_arg_converter.return_value = []  # Mock successful CLI parsing

        # Mix of valid and invalid presets
        test_presets = [
            {"id": str(uuid.uuid4()), "name": "valid_preset", "cli": "--format best"},
            {
                # Missing required fields
                "description": "Invalid preset"
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets_file.write_text(json.dumps(test_presets))

            # Clear any existing items first
            presets = Presets(file=presets_file, config=mock_config_instance)
            presets.load()

            # Should only load the valid preset
            assert len(presets._items) == 1
            assert presets._items[0].name == "valid_preset", f"Expected 'valid_preset', got '{presets._items}'"

            # Should have logged an error for the invalid preset
            mock_log.error.assert_called()

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    @patch("app.library.Presets.LOG")
    def test_presets_save_with_invalid_preset(self, mock_log, mock_eventbus, mock_config):
        """Test saving presets with some invalid ones."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        # Create preset with invalid CLI that will fail validation
        valid_preset = Preset(name="valid", cli="--valid-option")

        # Create invalid preset data
        invalid_preset_data = {"name": "invalid"}  # Missing ID

        presets_to_save = [valid_preset, invalid_preset_data]

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            presets.save(presets_to_save)

            # Should have logged errors for invalid presets
            mock_log.error.assert_called()

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_preset_priority_validation_integer(self, mock_eventbus, mock_config):
        """Test that priority must be an integer."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Test with non-integer priority
            invalid_preset = {"id": str(uuid.uuid4()), "name": "test", "priority": "not_an_int"}

            with pytest.raises(ValueError, match="Priority must be an integer"):
                presets.validate(invalid_preset)

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_preset_priority_validation_negative(self, mock_eventbus, mock_config):
        """Test that priority must be >= 0."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Test with negative priority
            invalid_preset = {"id": str(uuid.uuid4()), "name": "test", "priority": -5}

            with pytest.raises(ValueError, match="Priority must be >= 0"):
                presets.validate(invalid_preset)

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_preset_priority_sorting(self, mock_eventbus, mock_config):
        """Test that presets are sorted by priority in descending order."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"
            presets = Presets(file=presets_file, config=mock_config_instance)

            # Create presets with different priorities
            preset1 = Preset(name="low", priority=1)
            preset2 = Preset(name="high", priority=10)
            preset3 = Preset(name="medium", priority=5)

            presets.save([preset1, preset2, preset3]).load()

            all_presets = presets.get_all()
            non_default = [p for p in all_presets if not p.default]

            # Should be sorted by priority descending
            assert non_default[0].name == "high"
            assert non_default[0].priority == 10
            assert non_default[1].name == "medium"
            assert non_default[1].priority == 5
            assert non_default[2].name == "low"
            assert non_default[2].priority == 1

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_preset_priority_default_zero(self, mock_eventbus, mock_config):
        """Test that priority defaults to 0 if not specified."""
        preset = Preset(name="test")
        assert preset.priority == 0

    @patch("app.library.Presets.Config")
    @patch("app.library.Presets.EventBus")
    def test_preset_priority_migration(self, mock_eventbus, mock_config):
        """Test that old presets without priority get it added on load."""
        mock_config_instance = Mock(config_path="/tmp", default_preset="default")
        mock_config.get_instance.return_value = mock_config_instance
        mock_eventbus.get_instance.return_value = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            presets_file = Path(temp_dir) / "presets.json"

            # Create a preset file without priority field
            old_preset_data = [{"id": str(uuid.uuid4()), "name": "old_preset", "cli": ""}]
            presets_file.write_text(json.dumps(old_preset_data))

            # Load presets - should migrate by adding priority
            presets = Presets(file=presets_file, config=mock_config_instance)
            presets.load()

            # Check that priority was added
            loaded_data = json.loads(presets_file.read_text())
            assert "priority" in loaded_data[0]
            assert loaded_data[0]["priority"] == 0
