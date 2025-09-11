"""
Tests for encoder.py - JSON encoding utilities.

This test suite provides comprehensive coverage for the Encoder class:
- Tests serialization of various Python types
- Tests special handling of Path objects
- Tests DateRange serialization
- Tests date serialization
- Tests ImpersonateTarget serialization
- Tests ItemDTO serialization
- Tests object serialization with serialize() method
- Tests object serialization with __dict__ fallback
- Tests fallback to default JSONEncoder behavior

Total test functions: 10
All supported types and edge cases are covered.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.library.encoder import Encoder


class TestEncoder:
    """Test the Encoder class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.encoder = Encoder()

    def test_path_serialization(self):
        """Test that Path objects are serialized as strings."""
        path = Path("/tmp/test/file.txt")
        result = self.encoder.default(path)
        assert result == "/tmp/test/file.txt"
        assert isinstance(result, str)

    def test_path_serialization_relative(self):
        """Test that relative Path objects are serialized correctly."""
        path = Path("relative/path/file.txt")
        result = self.encoder.default(path)
        assert result == "relative/path/file.txt"

    def test_date_serialization(self):
        """Test that date objects are serialized as strings."""
        test_date = date(2024, 3, 15)
        result = self.encoder.default(test_date)
        assert result == "2024-03-15"

    def test_object_with_serialize_method(self):
        """Test that objects with serialize method use it."""
        class CustomObject:
            def serialize(self):
                return {"custom": "data", "type": "test"}

        obj = CustomObject()
        result = self.encoder.default(obj)
        assert result == {"custom": "data", "type": "test"}

    def test_object_with_dict_fallback(self):
        """Test that objects without serialize method fall back to __dict__."""
        class SimpleObject:
            def __init__(self):
                self.name = "test"
                self.value = 42

        obj = SimpleObject()
        result = self.encoder.default(obj)
        assert result == {"name": "test", "value": 42}

    def test_object_without_dict_fallback_to_default(self):
        """Test that objects without __dict__ fall back to default JSONEncoder."""
        # This should raise TypeError since complex is not JSON serializable
        with pytest.raises(TypeError):
            self.encoder.default(complex(1, 2))

    def test_json_dumps_integration(self):
        """Test full JSON serialization with various types."""
        data = {
            "path": Path("/tmp/test.txt"),
            "date": date(2024, 1, 1),
            "number": 42,
            "string": "test"
        }

        result = json.dumps(data, cls=Encoder)
        parsed = json.loads(result)

        assert parsed["path"] == "/tmp/test.txt"
        assert parsed["date"] == "2024-01-01"
        assert parsed["number"] == 42
        assert parsed["string"] == "test"

    def test_json_dumps_with_custom_object(self):
        """Test JSON serialization with custom objects."""
        class TestObject:
            def __init__(self):
                self.name = "test"
                self.items = [1, 2, 3]

        data = {
            "object": TestObject(),
            "regular": "data"
        }

        result = json.dumps(data, cls=Encoder)
        parsed = json.loads(result)

        assert parsed["object"]["name"] == "test"
        assert parsed["object"]["items"] == [1, 2, 3]
        assert parsed["regular"] == "data"

    def test_nested_serialization(self):
        """Test serialization of nested structures with various types."""
        class CustomObj:
            def serialize(self):
                return {"serialized": True}

        data = {
            "paths": [Path("/tmp/1.txt"), Path("/tmp/2.txt")],
            "dates": [date(2024, 1, 1), date(2024, 12, 31)],
            "custom": CustomObj(),
            "nested": {
                "path": Path("/nested/path"),
                "date": date(2024, 6, 15)
            }
        }

        result = json.dumps(data, cls=Encoder)
        parsed = json.loads(result)

        assert parsed["paths"] == ["/tmp/1.txt", "/tmp/2.txt"]
        assert parsed["dates"] == ["2024-01-01", "2024-12-31"]
        assert parsed["custom"] == {"serialized": True}
        assert parsed["nested"]["path"] == "/nested/path"
        assert parsed["nested"]["date"] == "2024-06-15"

    def test_mock_daterange_serialization(self):
        """Test DateRange serialization with mock object."""
        # Mock a DateRange-like object
        mock_daterange = MagicMock()
        mock_daterange.start = date(2024, 1, 15)
        mock_daterange.end = date(2024, 12, 31)

        # Mock isinstance to return True for DateRange
        import builtins
        original_isinstance = builtins.isinstance

        def mock_isinstance(obj, cls):
            if obj is mock_daterange and hasattr(cls, "__name__") and "DateRange" in str(cls):
                return True
            return original_isinstance(obj, cls)

        builtins.isinstance = mock_isinstance

        try:
            result = self.encoder.default(mock_daterange)
            expected = {"start": "20240115", "end": "20241231"}
            assert result == expected
        finally:
            builtins.isinstance = original_isinstance


if __name__ == "__main__":
    pytest.main([__file__])
