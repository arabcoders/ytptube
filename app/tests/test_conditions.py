"""
Tests for conditions.py - Download conditions management.

This test suite provides comprehensive coverage for the conditions module:
- Tests Condition dataclass functionality
- Tests Conditions singleton class behavior
- Tests condition loading, saving, and validation
- Tests condition matching against info dicts
- Tests error handling and edge cases

Total test functions: 15+
All condition management functionality and edge cases are covered.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.library.conditions import Condition, Conditions


class TestCondition:
    """Test the Condition dataclass."""

    def test_condition_creation_with_defaults(self):
        """Test creating a condition with default values."""
        condition = Condition(name="test", filter="duration > 60")

        # Check that ID is generated
        assert condition.id
        assert isinstance(condition.id, str)

        # Check required fields
        assert condition.name == "test"
        assert condition.filter == "duration > 60"

        # Check defaults
        assert condition.cli == ""
        assert condition.extras == {}

    def test_condition_creation_with_all_fields(self):
        """Test creating a condition with all fields specified."""
        test_id = str(uuid.uuid4())
        extras = {"key": "value", "number": 42}

        condition = Condition(
            id=test_id, name="full_test", filter="uploader = 'test'", cli="--format best", extras=extras
        )

        assert condition.id == test_id
        assert condition.name == "full_test"
        assert condition.filter == "uploader = 'test'"
        assert condition.cli == "--format best"
        assert condition.extras == extras

    def test_condition_serialize(self):
        """Test condition serialization to dict."""
        condition = Condition(
            name="serialize_test", filter="title ~= 'test'", cli="--audio-quality 0", extras={"tag": "music"}
        )

        serialized = condition.serialize()

        assert isinstance(serialized, dict)
        assert serialized["name"] == "serialize_test"
        assert serialized["filter"] == "title ~= 'test'"
        assert serialized["cli"] == "--audio-quality 0"
        assert serialized["extras"] == {"tag": "music"}
        assert "id" in serialized

    def test_condition_json(self):
        """Test condition JSON serialization."""
        condition = Condition(name="json_test", filter="duration < 300")

        json_str = condition.json()

        assert isinstance(json_str, str)
        # Should be valid JSON
        data = json.loads(json_str)
        assert data["name"] == "json_test"
        assert data["filter"] == "duration < 300"

    def test_condition_get_method(self):
        """Test condition get method for accessing fields."""
        condition = Condition(name="get_test", filter="view_count > 1000", extras={"category": "popular"})

        assert condition.get("name") == "get_test"
        assert condition.get("filter") == "view_count > 1000"
        assert condition.get("extras") == {"category": "popular"}
        assert condition.get("nonexistent") is None
        assert condition.get("nonexistent", "default") == "default"


class TestConditions:
    """Test the Conditions singleton class."""

    def setup_method(self):
        """Set up test fixtures by clearing singleton instances."""
        Conditions._reset_singleton()

    def test_conditions_singleton(self):
        """Test that Conditions follows singleton pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_conditions.json"

            instance1 = Conditions(file=file_path)
            instance2 = Conditions.get_instance()

            assert instance1 is instance2

    def test_conditions_initialization(self):
        """Test Conditions initialization with file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_conditions.json"

            conditions = Conditions(file=file_path)

            assert conditions._file == file_path
            assert isinstance(conditions._items, list)

    @patch("app.library.conditions.Config.get_instance")
    def test_conditions_default_file_path(self, mock_config):
        """Test Conditions uses default config path when no file specified."""
        mock_config_instance = MagicMock()
        mock_config_instance.config_path = "/test/config"
        mock_config.return_value = mock_config_instance

        conditions = Conditions()

        expected_path = Path("/test/config") / "conditions.json"
        assert conditions._file == expected_path

    def test_get_all_empty(self):
        """Test get_all returns empty list when no conditions loaded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "empty_conditions.json"
            conditions = Conditions(file=file_path)

            result = conditions.get_all()

            assert isinstance(result, list)
            assert len(result) == 0

    def test_clear(self):
        """Test clearing all conditions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "clear_test.json"
            conditions = Conditions(file=file_path)

            # Add some test conditions
            conditions._items = [
                Condition(name="test1", filter="duration > 60"),
                Condition(name="test2", filter="uploader = 'test'"),
            ]

            result = conditions.clear()

            assert result is conditions  # Should return self
            assert len(conditions._items) == 0

    def test_clear_when_already_empty(self):
        """Test clearing when conditions list is already empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "already_empty.json"
            conditions = Conditions(file=file_path)

            result = conditions.clear()

            assert result is conditions
            assert len(conditions._items) == 0

    def test_load_nonexistent_file(self):
        """Test loading from non-existent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nonexistent.json"
            conditions = Conditions(file=file_path)

            result = conditions.load()

            assert result is conditions
            assert len(conditions._items) == 0

    def test_load_empty_file(self):
        """Test loading from empty file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "empty.json"
            file_path.touch()  # Create empty file

            conditions = Conditions(file=file_path)
            result = conditions.load()

            assert result is conditions
            assert len(conditions._items) == 0

    def test_load_valid_conditions(self):
        """Test loading valid conditions from file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "valid_conditions.json"

            # Create test data
            test_data = [
                {
                    "id": str(uuid.uuid4()),
                    "name": "short_videos",
                    "filter": "duration < 300",
                    "cli": "--format worst",
                    "extras": {"category": "short"},
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "music_videos",
                    "filter": "title ~= 'music'",
                    "cli": "--audio-quality 0",
                    "extras": {"type": "audio"},
                },
            ]

            file_path.write_text(json.dumps(test_data, indent=4))

            conditions = Conditions(file=file_path)
            result = conditions.load()

            assert result is conditions
            assert len(conditions._items) == 2

            # Check first condition
            assert conditions._items[0].name == "short_videos"
            assert conditions._items[0].filter == "duration < 300"
            assert conditions._items[0].cli == "--format worst"
            assert conditions._items[0].extras == {"category": "short"}

            # Check second condition
            assert conditions._items[1].name == "music_videos"
            assert conditions._items[1].filter == "title ~= 'music'"

    def test_load_conditions_without_id(self):
        """Test loading conditions that don't have ID (should generate ID)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_id_conditions.json"

            # Create test data without ID
            test_data = [{"name": "no_id_test", "filter": "duration > 120"}]

            file_path.write_text(json.dumps(test_data))

            with patch.object(Conditions, "save") as mock_save:
                conditions = Conditions(file=file_path)
                conditions.load()

                # Should have generated ID
                assert len(conditions._items) == 1
                assert conditions._items[0].id
                assert conditions._items[0].name == "no_id_test"

                # Should call save due to changes
                mock_save.assert_called_once()

    def test_load_conditions_without_extras(self):
        """Test loading conditions that don't have extras field."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_extras_conditions.json"

            test_data = [{"id": str(uuid.uuid4()), "name": "no_extras_test", "filter": "uploader = 'test'"}]

            file_path.write_text(json.dumps(test_data))

            with patch.object(Conditions, "save") as mock_save:
                conditions = Conditions(file=file_path)
                conditions.load()

                # Should have generated empty extras
                assert len(conditions._items) == 1
                assert conditions._items[0].extras == {}

                # Should call save due to changes
                mock_save.assert_called_once()

    def test_load_invalid_json(self):
        """Test loading file with invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid.json"
            file_path.write_text("invalid json content")

            conditions = Conditions(file=file_path)
            result = conditions.load()

            assert result is conditions
            assert len(conditions._items) == 0

    def test_load_invalid_condition_data(self):
        """Test loading file with invalid condition data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_data.json"

            # Missing required fields
            test_data = [
                {"id": "valid", "name": "valid", "filter": "duration > 60"},
                {"invalid": "data"},  # Missing required fields
            ]

            file_path.write_text(json.dumps(test_data))

            conditions = Conditions(file=file_path)
            result = conditions.load()

            # Should load only valid conditions
            assert result is conditions
            assert len(conditions._items) == 1
            assert conditions._items[0].name == "valid"

    def test_validate_valid_condition_dict(self):
        """Test validating a valid condition dictionary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "validate_test.json"
            conditions = Conditions(file=file_path)

            valid_condition = {
                "id": str(uuid.uuid4()),
                "name": "valid_test",
                "filter": "duration > 60",
                "cli": "--format best",
                "extras": {"key": "value"},
            }

            result = conditions.validate(valid_condition)
            assert result is True

    def test_validate_valid_condition_object(self):
        """Test validating a valid Condition object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "validate_obj_test.json"
            conditions = Conditions(file=file_path)

            valid_condition = Condition(name="valid_obj_test", filter="uploader = 'test'")

            result = conditions.validate(valid_condition)
            assert result is True

    def test_validate_missing_id(self):
        """Test validating condition without ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_id_validate.json"
            conditions = Conditions(file=file_path)

            invalid_condition = {"name": "no_id_test", "filter": "duration > 60"}

            with pytest.raises(ValueError, match="No id found"):
                conditions.validate(invalid_condition)

    def test_validate_missing_name(self):
        """Test validating condition without name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_name_validate.json"
            conditions = Conditions(file=file_path)

            invalid_condition = {"id": str(uuid.uuid4()), "filter": "duration > 60"}

            with pytest.raises(ValueError, match="No name found"):
                conditions.validate(invalid_condition)

    def test_validate_missing_filter(self):
        """Test validating condition without filter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_filter_validate.json"
            conditions = Conditions(file=file_path)

            invalid_condition = {"id": str(uuid.uuid4()), "name": "no_filter_test"}

            with pytest.raises(ValueError, match="No filter found"):
                conditions.validate(invalid_condition)

    def test_validate_invalid_filter(self):
        """Test validating condition with invalid filter syntax."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_filter.json"
            conditions = Conditions(file=file_path)

            # Use a filter that will cause a syntax error in the parser
            invalid_condition = {
                "id": str(uuid.uuid4()),
                "name": "invalid_filter_test",
                "filter": "duration > & < 60",  # Invalid syntax with consecutive operators
                "cli": "",
                "extras": {},
            }

            with pytest.raises(ValueError, match="Invalid filter"):
                conditions.validate(invalid_condition)

    def test_validate_invalid_cli(self):
        """Test validating condition with invalid CLI options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_cli.json"
            conditions = Conditions(file=file_path)

            invalid_condition = {
                "id": str(uuid.uuid4()),
                "name": "invalid_cli_test",
                "filter": "duration > 60",
                "cli": "--invalid-option-that-does-not-exist",
            }

            with pytest.raises(ValueError, match="Invalid command options"):
                conditions.validate(invalid_condition)

    def test_validate_invalid_extras_type(self):
        """Test validating condition with non-dict extras."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_extras.json"
            conditions = Conditions(file=file_path)

            invalid_condition = {
                "id": str(uuid.uuid4()),
                "name": "invalid_extras_test",
                "filter": "duration > 60",
                "extras": "not a dict",
            }

            with pytest.raises(ValueError, match="Extras must be a dictionary"):
                conditions.validate(invalid_condition)

    def test_validate_invalid_item_type(self):
        """Test validating invalid item type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_type.json"
            conditions = Conditions(file=file_path)

            with pytest.raises(ValueError, match=r"Unexpected.*item type"):
                conditions.validate("invalid type")

    def test_save_conditions(self):
        """Test saving conditions to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "save_test.json"
            conditions = Conditions(file=file_path)

            test_conditions = [
                Condition(name="save_test1", filter="duration > 60"),
                Condition(name="save_test2", filter="uploader = 'test'"),
            ]

            result = conditions.save(test_conditions)

            assert result is conditions
            assert file_path.exists()

            # Verify file content
            saved_data = json.loads(file_path.read_text())
            assert len(saved_data) == 2
            assert saved_data[0]["name"] == "save_test1"
            assert saved_data[1]["name"] == "save_test2"

    def test_save_conditions_dict_format(self):
        """Test saving conditions in dictionary format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "save_dict_test.json"
            conditions = Conditions(file=file_path)

            test_conditions = [
                {"id": str(uuid.uuid4()), "name": "dict_test", "filter": "duration < 300", "cli": "", "extras": {}}
            ]

            conditions.save(test_conditions)

            assert file_path.exists()
            saved_data = json.loads(file_path.read_text())
            assert len(saved_data) == 1
            assert saved_data[0]["name"] == "dict_test"

    def test_has_condition_by_id(self):
        """Test checking if condition exists by ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "has_test.json"
            conditions = Conditions(file=file_path)

            test_id = str(uuid.uuid4())
            test_condition = Condition(id=test_id, name="has_test", filter="duration > 60")
            conditions._items = [test_condition]

            assert conditions.has(test_id) is True
            assert conditions.has("nonexistent") is False

    def test_has_condition_by_name(self):
        """Test checking if condition exists by name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "has_name_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="has_name_test", filter="uploader = 'test'")
            conditions._items = [test_condition]

            assert conditions.has("has_name_test") is True
            assert conditions.has("nonexistent_name") is False

    def test_get_condition_by_id(self):
        """Test getting condition by ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "get_id_test.json"
            conditions = Conditions(file=file_path)

            test_id = str(uuid.uuid4())
            test_condition = Condition(id=test_id, name="get_id_test", filter="duration > 120")
            conditions._items = [test_condition]

            result = conditions.get(test_id)
            assert result is test_condition

            assert conditions.get("nonexistent") is None

    def test_get_condition_by_name(self):
        """Test getting condition by name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "get_name_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="get_name_test", filter="title ~= 'music'")
            conditions._items = [test_condition]

            result = conditions.get("get_name_test")
            assert result is test_condition

    def test_get_condition_empty_id_or_name(self):
        """Test getting condition with empty ID or name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "empty_get_test.json"
            conditions = Conditions(file=file_path)

            assert conditions.get("") is None
            assert conditions.get(None) is None

    @patch("app.library.conditions.match_str")
    def test_match_condition_found(self, mock_match_str):
        """Test matching condition against info dict."""
        mock_match_str.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "match_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="match_test", filter="duration > 60")
            conditions._items = [test_condition]

            info_dict = {"duration": 120, "title": "Test Video"}
            result = conditions.match(info_dict)

            assert result is test_condition
            mock_match_str.assert_called_once_with("duration > 60", info_dict)

    @patch("app.library.conditions.match_str")
    def test_match_condition_not_found(self, mock_match_str):
        """Test matching when no condition matches."""
        mock_match_str.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_match_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="no_match_test", filter="duration > 300")
            conditions._items = [test_condition]

            info_dict = {"duration": 60, "title": "Short Video"}
            result = conditions.match(info_dict)

            assert result is None

    def test_match_empty_conditions(self):
        """Test matching with empty conditions list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "empty_match_test.json"
            conditions = Conditions(file=file_path)

            info_dict = {"duration": 120}
            result = conditions.match(info_dict)

            assert result is None

    def test_match_invalid_info_dict(self):
        """Test matching with invalid info dict."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_info_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="test", filter="duration > 60")
            conditions._items = [test_condition]

            # Test with None
            assert conditions.match(None) is None

            # Test with empty dict
            assert conditions.match({}) is None

            # Test with non-dict
            assert conditions.match("not a dict") is None

    @patch("app.library.conditions.match_str")
    def test_match_filter_evaluation_error(self, mock_match_str):
        """Test matching when filter evaluation raises exception."""
        mock_match_str.side_effect = Exception("Filter error")

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "filter_error_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="error_test", filter="invalid filter")
            conditions._items = [test_condition]

            info_dict = {"duration": 120}
            result = conditions.match(info_dict)

            assert result is None

    def test_match_empty_filter(self):
        """Test matching with condition that has empty filter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "empty_filter_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="empty_filter", filter="")
            conditions._items = [test_condition]

            info_dict = {"duration": 120}
            result = conditions.match(info_dict)

            assert result is None

    @patch("app.library.conditions.match_str")
    def test_single_match_found(self, mock_match_str):
        """Test single condition matching."""
        mock_match_str.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "single_match_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="single_test", filter="uploader = 'test'")
            conditions._items = [test_condition]

            info_dict = {"uploader": "test", "title": "Test Video"}
            result = conditions.single_match("single_test", info_dict)

            assert result is test_condition
            mock_match_str.assert_called_once_with("uploader = 'test'", info_dict)

    @patch("app.library.conditions.match_str")
    def test_single_match_not_found(self, mock_match_str):
        """Test single condition matching when condition doesn't match."""
        mock_match_str.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "single_no_match_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="single_no_match", filter="uploader = 'other'")
            conditions._items = [test_condition]

            info_dict = {"uploader": "test", "title": "Test Video"}
            result = conditions.single_match("single_no_match", info_dict)

            assert result is None

    def test_single_match_nonexistent_condition(self):
        """Test single matching with non-existent condition name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "nonexistent_single_test.json"
            conditions = Conditions(file=file_path)

            info_dict = {"duration": 120}
            result = conditions.single_match("nonexistent", info_dict)

            assert result is None

    def test_single_match_condition_no_filter(self):
        """Test single matching with condition that has no filter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "no_filter_single_test.json"
            conditions = Conditions(file=file_path)

            test_condition = Condition(name="no_filter_single", filter="")
            conditions._items = [test_condition]

            info_dict = {"duration": 120}
            result = conditions.single_match("no_filter_single", info_dict)

            assert result is None

    def test_single_match_invalid_inputs(self):
        """Test single matching with invalid inputs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "invalid_single_test.json"
            conditions = Conditions(file=file_path)

            # Test with empty conditions
            assert conditions.single_match("test", {"duration": 120}) is None

            # Test with None info
            assert conditions.single_match("test", None) is None

            # Test with empty info dict
            assert conditions.single_match("test", {}) is None

            # Test with non-dict info
            assert conditions.single_match("test", "not a dict") is None
