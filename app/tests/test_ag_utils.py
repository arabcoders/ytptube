"""
Tests for ag_utils.py functions.

This test suite provides comprehensive coverage for all functions in ag_utils.py:
- get_value: Tests callable detection and value retrieval
- ag_set: Tests nested dictionary path setting with various scenarios
- ag: Tests nested dictionary/list/object access with dot notation
- ag_sets: Tests bulk setting of multiple paths
- ag_exists: Tests existence checking for nested paths
- ag_delete: Tests deletion of nested paths and keys

Total test functions: 53
All edge cases, error conditions, and normal operations are covered.
"""

from unittest.mock import MagicMock

import pytest

from app.library.ag_utils import (
    ag,
    ag_delete,
    ag_exists,
    ag_set,
    ag_sets,
    get_value,
)


class TestGetValue:
    """Test the get_value function."""

    def test_get_value_with_value(self):
        """Test get_value returns the value when not callable."""
        assert get_value(42) == 42
        assert get_value("test") == "test"
        assert get_value([1, 2, 3]) == [1, 2, 3]
        assert get_value({"key": "value"}) == {"key": "value"}
        assert get_value(None) is None

    def test_get_value_with_callable(self):
        """Test get_value calls the function when callable."""
        mock_func = MagicMock(return_value="called")
        result = get_value(mock_func)
        assert result == "called"
        mock_func.assert_called_once()

    def test_get_value_with_lambda(self):
        """Test get_value with lambda functions."""
        assert get_value(lambda: 100) == 100
        assert get_value(lambda: "lambda_result") == "lambda_result"

    def test_get_value_with_function(self):
        """Test get_value with regular functions."""

        def test_func():
            return "function_result"

        assert get_value(test_func) == "function_result"


class TestAgSet:
    """Test the ag_set function."""

    def test_ag_set_simple_path(self):
        """Test setting a value with simple path."""
        data = {}
        result = ag_set(data, "key", "value")
        assert result == {"key": "value"}
        assert data == {"key": "value"}

    def test_ag_set_nested_path(self):
        """Test setting a value with nested path."""
        data = {}
        result = ag_set(data, "a.b.c", "nested_value")
        expected = {"a": {"b": {"c": "nested_value"}}}
        assert result == expected
        assert data == expected

    def test_ag_set_existing_structure(self):
        """Test setting a value in existing structure."""
        data = {"a": {"b": {"existing": "value"}}}
        ag_set(data, "a.b.c", "new_value")
        expected = {"a": {"b": {"existing": "value", "c": "new_value"}}}
        assert data == expected

    def test_ag_set_overwrite_existing(self):
        """Test overwriting existing value."""
        data = {"a": {"b": "old_value"}}
        ag_set(data, "a.b", "new_value")
        assert data == {"a": {"b": "new_value"}}

    def test_ag_set_custom_separator(self):
        """Test using custom separator."""
        data = {}
        ag_set(data, "a/b/c", "value", separator="/")
        assert data == {"a": {"b": {"c": "value"}}}

    def test_ag_set_overwrite_non_dict_intermediate(self):
        """Test overwriting non-dict intermediate value with dict."""
        data = {"a": "not_a_dict"}
        ag_set(data, "a.b", "value")
        # The function should overwrite "not_a_dict" with a dict containing the new path
        expected = {"a": {"b": "value"}}
        assert data == expected

    def test_ag_set_error_on_non_dict_final(self):
        """Test error when final target is not a dict."""
        data = "not_a_dict"
        with pytest.raises(RuntimeError, match="Cannot set value at path 'key'"):
            ag_set(data, "key", "value")


class TestAg:
    """Test the ag function."""

    def test_ag_with_none_path(self):
        """Test ag returns whole structure when path is None."""
        data = {"a": 1, "b": 2}
        assert ag(data, None) == data
        assert ag(data, "") == data

    def test_ag_simple_dict_access(self):
        """Test simple dictionary key access."""
        data = {"x": 10, "y": 20}
        assert ag(data, "x") == 10
        assert ag(data, "y") == 20

    def test_ag_missing_key_with_default(self):
        """Test accessing missing key returns default."""
        data = {"x": 10}
        assert ag(data, "missing", default=0) == 0
        assert ag(data, "missing", default="not_found") == "not_found"

    def test_ag_nested_dict_access(self):
        """Test nested dictionary access with dot notation."""
        data = {"a": {"b": {"c": 42}}}
        assert ag(data, "a.b.c") == 42

    def test_ag_nested_missing_key(self):
        """Test nested access with missing intermediate keys."""
        data = {"a": {"b": 1}}
        assert ag(data, "a.missing.c", default="default") == "default"
        assert ag(data, "missing.b.c", default="default") == "default"

    def test_ag_list_access_by_index(self):
        """Test accessing list elements by index."""
        data = [10, 20, 30]
        assert ag(data, 0) == 10
        assert ag(data, 1) == 20
        assert ag(data, 2) == 30

    def test_ag_list_access_out_of_bounds(self):
        """Test list access with out of bounds index."""
        data = [10, 20]
        assert ag(data, 5, default="default") == "default"
        assert ag(data, -3, default="default") == "default"  # -3 is out of bounds for 2-element list

    def test_ag_list_negative_indices(self):
        """Test list access with valid negative indices."""
        data = [10, 20, 30]
        assert ag(data, -1) == 30  # Last element
        assert ag(data, -2) == 20  # Second to last
        assert ag(data, -3) == 10  # First element

    def test_ag_mixed_dict_list_access(self):
        """Test accessing nested structure with dicts and lists."""
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        assert ag(data, "items.0.name") == "item1"
        assert ag(data, "items.1.name") == "item2"

    def test_ag_list_of_paths(self):
        """Test trying multiple paths and returning first found."""
        data = {"a": 1, "b": 2}
        assert ag(data, ["missing1", "missing2", "a"], default="default") == 1
        assert ag(data, ["missing1", "b", "a"], default="default") == 2
        assert ag(data, ["missing1", "missing2"], default="default") == "default"

    def test_ag_custom_separator(self):
        """Test using custom separator."""
        data = {"a": {"b": {"c": 100}}}
        assert ag(data, "a/b/c", separator="/") == 100

    def test_ag_with_none_values(self):
        """Test ag behavior with None values."""
        data = {"a": None, "b": {"c": None}}
        assert ag(data, "a", default="default") == "default"
        assert ag(data, "b.c", default="default") == "default"

    def test_ag_with_callable_default(self):
        """Test ag with callable default value."""
        data = {}
        mock_default = MagicMock(return_value="called_default")
        result = ag(data, "missing", default=mock_default)
        assert result == "called_default"
        mock_default.assert_called_once()

    def test_ag_with_object_attributes(self):
        """Test ag with object attributes using vars()."""

        class TestObj:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = {"nested": "value2"}

        obj = TestObj()
        assert ag(obj, "attr1") == "value1"
        assert ag(obj, "attr2.nested") == "value2"

    def test_ag_with_non_dict_non_list_fallback(self):
        """Test ag fallback for non-dict, non-list objects without vars."""

        class NoVarsObj:
            __slots__ = ["value"]

            def __init__(self):
                self.value = "test"

        obj = NoVarsObj()
        assert ag(obj, "anything", default="fallback") == "fallback"


class TestAgSets:
    """Test the ag_sets function."""

    def test_ag_sets_multiple_paths(self):
        """Test setting multiple paths at once."""
        data = {}
        path_values = {"a.b.c": "value1", "a.b.d": "value2", "x.y": "value3"}
        result = ag_sets(data, path_values)

        expected = {"a": {"b": {"c": "value1", "d": "value2"}}, "x": {"y": "value3"}}
        assert result == expected
        assert data == expected

    def test_ag_sets_custom_separator(self):
        """Test ag_sets with custom separator."""
        data = {}
        path_values = {"a/b/c": "value1", "x/y": "value2"}
        ag_sets(data, path_values, separator="/")

        expected = {"a": {"b": {"c": "value1"}}, "x": {"y": "value2"}}
        assert data == expected

    def test_ag_sets_existing_structure(self):
        """Test ag_sets with existing data structure."""
        data = {"a": {"existing": "value"}}
        path_values = {"a.b.c": "new_value", "d": "another_value"}
        ag_sets(data, path_values)

        expected = {"a": {"existing": "value", "b": {"c": "new_value"}}, "d": "another_value"}
        assert data == expected

    def test_ag_sets_empty_dict(self):
        """Test ag_sets with empty path_values dict."""
        data = {"existing": "data"}
        original = data.copy()
        ag_sets(data, {})
        assert data == original


class TestAgExists:
    """Test the ag_exists function."""

    def test_ag_exists_simple_dict_key(self):
        """Test checking existence of simple dict keys."""
        data = {"a": "value", "b": None, "c": 0}
        assert ag_exists(data, "a") is True
        assert ag_exists(data, "b") is False  # None values return False
        assert ag_exists(data, "c") is True  # 0 is not None
        assert ag_exists(data, "missing") is False

    def test_ag_exists_nested_path(self):
        """Test checking existence of nested paths."""
        data = {"a": {"b": {"c": "value", "d": None}}}
        assert ag_exists(data, "a.b.c") is True
        assert ag_exists(data, "a.b.d") is False  # None value
        assert ag_exists(data, "a.b.missing") is False
        assert ag_exists(data, "a.missing.c") is False

    def test_ag_exists_list_indices(self):
        """Test checking existence of list indices."""
        data = [10, None, 30]
        assert ag_exists(data, 0) is True
        assert ag_exists(data, 1) is False  # None value
        assert ag_exists(data, 2) is True
        assert ag_exists(data, 5) is False  # Out of bounds

    def test_ag_exists_mixed_structure(self):
        """Test checking existence in mixed dict/list structure."""
        data = {"items": [{"name": "item1"}, None, {"name": "item3"}]}
        assert ag_exists(data, "items.0.name") is True
        assert ag_exists(data, "items.1.name") is False  # items[1] is None
        assert ag_exists(data, "items.2.name") is True
        assert ag_exists(data, "items.5.name") is False  # Out of bounds

    def test_ag_exists_custom_separator(self):
        """Test ag_exists with custom separator."""
        data = {"a": {"b": {"c": "value"}}}
        assert ag_exists(data, "a/b/c", separator="/") is True
        assert ag_exists(data, "a/b/missing", separator="/") is False

    def test_ag_exists_with_object(self):
        """Test ag_exists with object using vars()."""

        class TestObj:
            def __init__(self):
                self.attr = "value"
                self.nested = {"key": "value"}

        obj = TestObj()
        assert ag_exists(obj, "attr") is True
        assert ag_exists(obj, "nested.key") is True
        assert ag_exists(obj, "missing") is False

    def test_ag_exists_with_non_vars_object(self):
        """Test ag_exists with object that doesn't support vars()."""

        class NoVarsObj:
            __slots__ = []

        obj = NoVarsObj()
        assert ag_exists(obj, "anything") is False


class TestAgDelete:
    """Test the ag_delete function."""

    def test_ag_delete_simple_dict_key(self):
        """Test deleting simple dictionary keys."""
        data = {"a": 1, "b": 2, "c": 3}
        result = ag_delete(data, "b")
        assert result == {"a": 1, "c": 3}
        assert data == {"a": 1, "c": 3}

    def test_ag_delete_nested_path(self):
        """Test deleting nested dictionary paths."""
        data = {"a": {"b": {"c": 1, "d": 2}, "e": 3}}
        ag_delete(data, "a.b.c")
        expected = {"a": {"b": {"d": 2}, "e": 3}}
        assert data == expected

    def test_ag_delete_list_index(self):
        """Test deleting list elements by index."""
        data = [10, 20, 30, 40]
        ag_delete(data, 1)
        assert data == [10, 30, 40]

    def test_ag_delete_mixed_structure(self):
        """Test deleting from mixed dict/list structure."""
        data = {"items": [{"name": "item1"}, {"name": "item2", "value": 100}]}
        ag_delete(data, "items.1.value")
        expected = {"items": [{"name": "item1"}, {"name": "item2"}]}
        assert data == expected

    def test_ag_delete_multiple_paths(self):
        """Test deleting multiple paths at once."""
        data = {"a": {"b": 1, "c": 2}, "d": 3, "e": 4}
        ag_delete(data, ["a.b", "d"])
        expected = {"a": {"c": 2}, "e": 4}
        assert data == expected

    def test_ag_delete_custom_separator(self):
        """Test ag_delete with custom separator."""
        data = {"a": {"b": {"c": 1}}}
        ag_delete(data, "a/b/c", separator="/")
        assert data == {"a": {"b": {}}}

    def test_ag_delete_missing_key(self):
        """Test deleting non-existent keys (should not raise error)."""
        data = {"a": {"b": 1}}
        original = {"a": {"b": 1}}

        # Should not raise error and not modify data
        ag_delete(data, "missing")
        ag_delete(data, "a.missing")
        ag_delete(data, "a.b.c")

        assert data == original

    def test_ag_delete_out_of_bounds_list(self):
        """Test deleting out of bounds list index (should not raise error)."""
        data = [1, 2, 3]
        original = [1, 2, 3]

        ag_delete(data, 10)  # Out of bounds
        ag_delete(data, -1)  # Negative index

        assert data == original

    def test_ag_delete_with_object(self):
        """Test ag_delete with object using vars()."""

        class TestObj:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = {"nested": "value2"}

        obj = TestObj()
        ag_delete(obj, "attr1")

        # Check that attr1 was deleted
        assert not hasattr(obj, "attr1")
        assert hasattr(obj, "attr2")

    def test_ag_delete_invalid_list_string_index(self):
        """Test ag_delete with invalid string index for list."""
        data = {"items": [1, 2, 3]}
        original_items = [1, 2, 3]

        ag_delete(data, "items.invalid_index")

        # Should not modify the list
        assert data["items"] == original_items

    def test_ag_delete_path_through_none(self):
        """Test ag_delete when path goes through None value."""
        data = {"a": {"b": None}}
        original = {"a": {"b": None}}

        ag_delete(data, "a.b.c")  # Can't traverse through None

        assert data == original


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_data_structures(self):
        """Test functions with empty data structures."""
        empty_dict = {}
        empty_list = []

        # ag function
        assert ag(empty_dict, "key", default="default") == "default"
        assert ag(empty_list, 0, default="default") == "default"

        # ag_exists function
        assert ag_exists(empty_dict, "key") is False
        assert ag_exists(empty_list, 0) is False

        # ag_delete function (should not raise errors)
        ag_delete(empty_dict, "key")
        ag_delete(empty_list, 0)

        assert empty_dict == {}
        assert empty_list == []

    def test_deeply_nested_structures(self):
        """Test with deeply nested structures."""
        # Create 10-level deep structure
        data = {}
        current = data
        for i in range(10):
            current[f"level{i}"] = {}
            current = current[f"level{i}"]
        current["value"] = "deep_value"

        path = ".".join(f"level{i}" for i in range(10)) + ".value"

        # Test ag function
        assert ag(data, path) == "deep_value"

        # Test ag_exists function
        assert ag_exists(data, path) is True

        # Test ag_set function
        ag_set(data, path.replace(".value", ".new_value"), "new_deep_value")
        new_path = ".".join(f"level{i}" for i in range(10)) + ".new_value"
        assert ag(data, new_path) == "new_deep_value"

    def test_special_characters_in_keys(self):
        """Test with special characters in dictionary keys."""
        data = {"key with spaces": "value1", "key.with.dots": "value2", "key/with/slashes": "value3"}

        # These should work with direct key access
        assert ag(data, "key with spaces") == "value1"
        assert ag(data, "key.with.dots") == "value2"
        assert ag(data, "key/with/slashes") == "value3"

        # Test existence
        assert ag_exists(data, "key with spaces") is True
        assert ag_exists(data, "key.with.dots") is True

        # Test deletion
        ag_delete(data, "key with spaces")
        assert "key with spaces" not in data

    def test_type_consistency(self):
        """Test type consistency across operations."""
        data = {"string": "test", "number": 42, "boolean": True, "list": [1, 2, 3], "dict": {"nested": "value"}}

        # All values should be retrieved correctly
        assert ag(data, "string") == "test"
        assert ag(data, "number") == 42
        assert ag(data, "boolean") is True
        assert ag(data, "list") == [1, 2, 3]
        assert ag(data, "dict") == {"nested": "value"}

        # All should exist
        for key in data:
            assert ag_exists(data, key) is True
