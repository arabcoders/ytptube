"""
Tests for dl_fields.py - Download fields management.

This test suite provides comprehensive coverage for the dl_fields module:
- Tests FieldType enum functionality
- Tests DLField dataclass functionality
- Tests DLFields singleton class behavior
- Tests field loading, saving, and validation
- Tests field CRUD operations
- Tests error handling and edge cases

Total test functions: 25+
All dl_fields management functionality and edge cases are covered.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.library.dl_fields import DLField, DLFields, FieldType


class TestFieldType:
    """Test the FieldType enum."""

    def test_field_type_values(self):
        """Test FieldType enum values."""
        assert FieldType.STRING == "string"
        assert FieldType.TEXT == "text"
        assert FieldType.BOOL == "bool"

    def test_field_type_all(self):
        """Test FieldType.all() method."""
        all_types = FieldType.all()
        expected = ["string", "text", "bool"]
        assert all_types == expected
        assert len(all_types) == 3

    def test_field_type_from_value_valid(self):
        """Test FieldType.from_value() with valid values."""
        assert FieldType.from_value("string") == FieldType.STRING
        assert FieldType.from_value("text") == FieldType.TEXT
        assert FieldType.from_value("bool") == FieldType.BOOL

    def test_field_type_from_value_invalid(self):
        """Test FieldType.from_value() with invalid values."""
        with pytest.raises(ValueError, match="Invalid StoreType value"):
            FieldType.from_value("invalid")

        with pytest.raises(ValueError, match="Invalid StoreType value"):
            FieldType.from_value("number")

        with pytest.raises(ValueError, match="Invalid StoreType value"):
            FieldType.from_value("")

    def test_field_type_str(self):
        """Test FieldType string conversion."""
        assert str(FieldType.STRING) == "string"
        assert str(FieldType.TEXT) == "text"
        assert str(FieldType.BOOL) == "bool"


class TestDLField:
    """Test the DLField dataclass."""

    def test_dl_field_creation_with_defaults(self):
        """Test creating a DLField with default values."""
        field = DLField(name="test_field", description="Test description", field="--test-option")

        # Check that ID is generated
        assert field.id
        assert isinstance(field.id, str)

        # Check required fields
        assert field.name == "test_field"
        assert field.description == "Test description"
        assert field.field == "--test-option"

        # Check defaults
        assert field.kind == FieldType.TEXT
        assert field.icon == ""
        assert field.order == 0
        assert field.value == ""
        assert field.extras == {}

    def test_dl_field_creation_with_all_fields(self):
        """Test creating a DLField with all fields specified."""
        test_id = str(uuid.uuid4())
        extras = {"key": "value", "number": 42}

        field = DLField(
            id=test_id,
            name="custom_field",
            description="Custom description",
            field="--custom-option",
            kind=FieldType.BOOL,
            icon="fa-check",
            order=5,
            value="default_value",
            extras=extras,
        )

        assert field.id == test_id
        assert field.name == "custom_field"
        assert field.description == "Custom description"
        assert field.field == "--custom-option"
        assert field.kind == FieldType.BOOL
        assert field.icon == "fa-check"
        assert field.order == 5
        assert field.value == "default_value"
        assert field.extras == extras

    def test_dl_field_serialize(self):
        """Test DLField serialization."""
        extras = {"key": "value", "none_value": None}
        field = DLField(name="test", description="Test field", field="--test", kind=FieldType.STRING, extras=extras)

        serialized = field.serialize()

        assert serialized["name"] == "test"
        assert serialized["description"] == "Test field"
        assert serialized["field"] == "--test"
        assert serialized["kind"] == "string"
        assert serialized["extras"] == {"key": "value"}  # None values filtered out

    def test_dl_field_json(self):
        """Test DLField JSON encoding."""
        field = DLField(name="json_test", description="JSON test field", field="--json-test")

        json_str = field.json()
        assert isinstance(json_str, str)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["name"] == "json_test"
        assert parsed["description"] == "JSON test field"
        assert parsed["field"] == "--json-test"

    def test_dl_field_get_method(self):
        """Test DLField get method."""
        field = DLField(name="get_test", description="Get test field", field="--get-test", order=3)

        assert field.get("name") == "get_test"
        assert field.get("order") == 3
        assert field.get("nonexistent") is None
        assert field.get("nonexistent", "default") == "default"


class TestDLFields:
    """Test the DLFields class."""

    def setup_method(self):
        """Set up test fixtures."""
        DLFields._reset_singleton()

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)
        yield temp_path
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def sample_fields_data(self):
        """Sample field data for testing."""
        return [
            {
                "id": str(uuid.uuid4()),
                "name": "quality",
                "description": "Video quality setting",
                "field": "--format",
                "kind": "string",
                "icon": "fa-video",
                "order": 1,
                "value": "best",
                "extras": {"options": ["best", "worst", "720p"]},
            },
            {
                "id": str(uuid.uuid4()),
                "name": "audio_only",
                "description": "Extract audio only",
                "field": "--extract-audio",
                "kind": "bool",
                "icon": "fa-music",
                "order": 2,
                "value": "",
                "extras": {},
            },
        ]

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_singleton_behavior(self, mock_config):
        """Test that DLFields follows singleton pattern."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields1 = DLFields()
        fields2 = DLFields()
        assert fields1 is fields2

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_get_instance(self, mock_config):
        """Test DLFields.get_instance() method."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields1 = DLFields.get_instance()
        fields2 = DLFields.get_instance()
        assert fields1 is fields2

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_initialization(self, mock_config):
        """Test DLFields initialization."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / "test_fields.json"

            fields = DLFields(file=str(temp_file))

            assert fields._file == temp_file

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_load_empty_file(self, mock_config, temp_file):
        """Test loading from empty/non-existent file."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields(file=str(temp_file))
        result = fields.load()

        assert result is fields
        assert fields.get_all() == []

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_load_valid_file(self, mock_config, temp_file, sample_fields_data):
        """Test loading from valid JSON file."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        # Write sample data to temp file
        temp_file.write_text(json.dumps(sample_fields_data, indent=2))

        fields = DLFields(file=str(temp_file))
        fields.load()

        loaded_fields = fields.get_all()
        assert len(loaded_fields) == 2

        # Check first field
        field1 = loaded_fields[0]
        assert field1.name == "quality"
        assert field1.description == "Video quality setting"
        assert field1.field == "--format"
        assert field1.kind == FieldType.STRING

        # Check second field
        field2 = loaded_fields[1]
        assert field2.name == "audio_only"
        assert field2.kind == FieldType.BOOL

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_load_invalid_json(self, mock_config, temp_file):
        """Test loading from invalid JSON file."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        # Write invalid JSON
        temp_file.write_text("invalid json content")

        fields = DLFields(file=str(temp_file))
        fields.load()

        # Should handle error gracefully and return empty list
        assert fields.get_all() == []

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_load_missing_id_auto_generation(self, mock_config, temp_file):
        """Test that missing IDs are auto-generated during load."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        # Sample data without IDs
        data_without_ids = [
            {"name": "test_field", "description": "Test description", "field": "--test", "kind": "string"}
        ]

        temp_file.write_text(json.dumps(data_without_ids))

        with patch.object(DLFields, "save") as mock_save:
            fields = DLFields(file=str(temp_file))
            fields.load()

            # Should auto-generate ID and trigger save
            loaded_fields = fields.get_all()
            assert len(loaded_fields) == 1
            assert loaded_fields[0].id is not None
            mock_save.assert_called_once()

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_clear(self, mock_config):
        """Test clearing all fields."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        # Add some fields manually
        fields._items = [
            DLField(name="test1", description="Test 1", field="--test1"),
            DLField(name="test2", description="Test 2", field="--test2"),
        ]

        assert len(fields.get_all()) == 2

        result = fields.clear()
        assert result is fields
        assert len(fields.get_all()) == 0

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_clear_empty(self, mock_config):
        """Test clearing when already empty."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()
        assert len(fields.get_all()) == 0

        result = fields.clear()
        assert result is fields
        assert len(fields.get_all()) == 0

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_valid_field(self, mock_config):
        """Test validation with valid DLField."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        valid_field = DLField(
            name="valid_field", description="Valid description", field="--valid-option", kind=FieldType.STRING
        )

        assert fields.validate(valid_field) is True

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_valid_dict(self, mock_config):
        """Test validation with valid dictionary."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        valid_dict = {
            "id": str(uuid.uuid4()),
            "name": "test_field",
            "description": "Test description",
            "field": "--test-field",
            "kind": "text",
        }

        assert fields.validate(valid_dict) is True

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_missing_required_fields(self, mock_config):
        """Test validation with missing required fields."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        # Missing name
        invalid_dict = {
            "id": str(uuid.uuid4()),
            "description": "Test description",
            "field": "--test-field",
            "kind": "text",
        }

        with pytest.raises(ValueError, match="Missing required key 'name'"):
            fields.validate(invalid_dict)

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_invalid_field_type(self, mock_config):
        """Test validation with invalid field type."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        invalid_dict = {
            "id": str(uuid.uuid4()),
            "name": "test_field",
            "description": "Test description",
            "field": "--test-field",
            "kind": "invalid_type",
        }

        with pytest.raises(ValueError, match="Invalid field type"):
            fields.validate(invalid_dict)

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_invalid_yt_dlp_field(self, mock_config):
        """Test validation with invalid yt-dlp field format."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        invalid_dict = {
            "id": str(uuid.uuid4()),
            "name": "test_field",
            "description": "Test description",
            "field": "invalid-field",  # Missing --
            "kind": "text",
        }

        with pytest.raises(ValueError, match="Invalid yt-dlp option field"):
            fields.validate(invalid_dict)

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_invalid_extras_type(self, mock_config):
        """Test validation with invalid extras type."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        invalid_dict = {
            "id": str(uuid.uuid4()),
            "name": "test_field",
            "description": "Test description",
            "field": "--test-field",
            "kind": "text",
            "extras": "not_a_dict",
        }

        with pytest.raises(ValueError, match="Extras must be a dictionary"):
            fields.validate(invalid_dict)

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_invalid_value_type(self, mock_config):
        """Test validation with invalid value type."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        invalid_dict = {
            "id": str(uuid.uuid4()),
            "name": "test_field",
            "description": "Test description",
            "field": "--test-field",
            "kind": "text",
            "value": 123,  # Should be string
        }

        with pytest.raises(ValueError, match="Value must be a string"):
            fields.validate(invalid_dict)

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_invalid_order_type(self, mock_config):
        """Test validation with invalid order type."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        invalid_dict = {
            "id": str(uuid.uuid4()),
            "name": "test_field",
            "description": "Test description",
            "field": "--test-field",
            "kind": "text",
            "order": "not_an_int",
        }

        with pytest.raises(ValueError, match="Order must be an integer"):
            fields.validate(invalid_dict)

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_validate_unexpected_type(self, mock_config):
        """Test validation with unexpected item type."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        with pytest.raises(ValueError, match="Unexpected 'str' type was given"):
            fields.validate("not_a_field_or_dict")

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_save_valid_fields(self, mock_config, temp_file):
        """Test saving valid fields."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields(file=str(temp_file))

        test_fields = [DLField(name="test_field", description="Test description", field="--test-option")]

        fields.save(test_fields)

        # Verify file was written
        assert temp_file.exists()

        # Verify content
        saved_data = json.loads(temp_file.read_text())
        assert len(saved_data) == 1
        assert saved_data[0]["name"] == "test_field"

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_save_mixed_types(self, mock_config, temp_file):
        """Test saving mix of DLField objects and dicts."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields(file=str(temp_file))

        test_items = [
            DLField(name="field1", description="Field 1", field="--field1"),
            {"id": str(uuid.uuid4()), "name": "field2", "description": "Field 2", "field": "--field2", "kind": "text"},
        ]

        fields.save(test_items)

        # Verify both items were saved
        saved_data = json.loads(temp_file.read_text())
        assert len(saved_data) == 2

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_get_by_id(self, mock_config):
        """Test getting field by ID."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        test_id = str(uuid.uuid4())
        test_field = DLField(id=test_id, name="test_field", description="Test description", field="--test-option")

        fields._items = [test_field]

        result = fields.get(test_id)
        assert result is test_field

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_get_by_name(self, mock_config):
        """Test getting field by name."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        test_field = DLField(name="test_field", description="Test description", field="--test-option")

        fields._items = [test_field]

        result = fields.get("test_field")
        assert result is test_field

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_get_not_found(self, mock_config):
        """Test getting non-existent field."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        result = fields.get("nonexistent")
        assert result is None

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_get_empty_string(self, mock_config):
        """Test getting with empty string."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        result = fields.get("")
        assert result is None

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_has_by_id(self, mock_config):
        """Test checking field existence by ID."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        test_id = str(uuid.uuid4())
        test_field = DLField(id=test_id, name="test_field", description="Test description", field="--test-option")

        fields._items = [test_field]

        assert fields.has(test_id) is True
        assert fields.has("nonexistent") is False

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_has_by_name(self, mock_config):
        """Test checking field existence by name."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        test_field = DLField(name="test_field", description="Test description", field="--test-option")

        fields._items = [test_field]

        assert fields.has("test_field") is True
        assert fields.has("nonexistent") is False

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_attach_method(self, mock_config):
        """Test attach method calls load."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()

        with patch.object(fields, "load") as mock_load:
            mock_app = MagicMock()
            fields.attach(mock_app)
            mock_load.assert_called_once()

    @patch("app.library.dl_fields.Config")
    def test_dl_fields_on_shutdown(self, mock_config):
        """Test on_shutdown method."""
        mock_config.get_instance.return_value.config_path = "/tmp"

        fields = DLFields()
        mock_app = MagicMock()

        # Should not raise any exceptions
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fields.on_shutdown(mock_app))
        finally:
            loop.close()
