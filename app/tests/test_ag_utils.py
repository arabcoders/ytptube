from typing import Any
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
    def test_get_value_with_value(self):
        assert get_value(42) == 42
        assert get_value("test") == "test"
        assert get_value([1, 2, 3]) == [1, 2, 3]
        assert get_value({"key": "value"}) == {"key": "value"}
        assert get_value(None) is None

    def test_get_value_with_callable(self):
        mock_func = MagicMock(return_value="called")
        result = get_value(mock_func)
        assert result == "called"
        mock_func.assert_called_once()


class TestAgSet:
    def test_ag_set_simple_path(self):
        data = {}
        result = ag_set(data, "key", "value")
        assert result == {"key": "value"}
        assert data == {"key": "value"}

    def test_ag_set_nested_path(self):
        data = {}
        result = ag_set(data, "a.b.c", "nested_value")
        expected = {"a": {"b": {"c": "nested_value"}}}
        assert result == expected
        assert data == expected

    def test_ag_set_existing_structure(self):
        data = {"a": {"b": {"existing": "value"}}}
        ag_set(data, "a.b.c", "new_value")
        expected = {"a": {"b": {"existing": "value", "c": "new_value"}}}
        assert data == expected

    def test_ag_set_overwrite_existing(self):
        data = {"a": {"b": "old_value"}}
        ag_set(data, "a.b", "new_value")
        assert data == {"a": {"b": "new_value"}}

    def test_ag_set_custom_separator(self):
        data = {}
        ag_set(data, "a/b/c", "value", separator="/")
        assert data == {"a": {"b": {"c": "value"}}}

    def test_overwrite_non_dict_intermediate(self):
        data = {"a": "not_a_dict"}
        ag_set(data, "a.b", "value")
        # The function should overwrite "not_a_dict" with a dict containing the new path
        expected = {"a": {"b": "value"}}
        assert data == expected

    def test_error_non_dict_final(self):
        data: Any = "not_a_dict"
        with pytest.raises(RuntimeError, match="Cannot set value at path 'key'"):
            ag_set(data, "key", "value")


class TestAg:
    def test_ag_with_none_path(self):
        data = {"a": 1, "b": 2}
        assert ag(data, None) == data
        assert ag(data, "") == data

    def test_ag_simple_dict_access(self):
        data = {"x": 10, "y": 20}
        assert ag(data, "x") == 10
        assert ag(data, "y") == 20

    def test_ag_missing_key_default(self):
        data = {"x": 10}
        assert ag(data, "missing", default=0) == 0
        assert ag(data, "missing", default="not_found") == "not_found"

    def test_ag_nested_dict_access(self):
        data = {"a": {"b": {"c": 42}}}
        assert ag(data, "a.b.c") == 42

    def test_ag_nested_missing_key(self):
        data = {"a": {"b": 1}}
        assert ag(data, "a.missing.c", default="default") == "default"
        assert ag(data, "missing.b.c", default="default") == "default"

    def test_ag_list_access_index(self):
        data = [10, 20, 30]
        assert ag(data, 0) == 10
        assert ag(data, 1) == 20
        assert ag(data, 2) == 30

    def test_list_access_out_bounds(self):
        data = [10, 20]
        assert ag(data, 5, default="default") == "default"
        assert ag(data, -3, default="default") == "default"  # -3 is out of bounds for 2-element list

    def test_ag_list_negative_indices(self):
        data = [10, 20, 30]
        assert ag(data, -1) == 30  # Last element
        assert ag(data, -2) == 20  # Second to last
        assert ag(data, -3) == 10  # First element

    def test_mixed_dict_list_access(self):
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        assert ag(data, "items.0.name") == "item1"
        assert ag(data, "items.1.name") == "item2"

    def test_ag_list_of_paths(self):
        data = {"a": 1, "b": 2}
        assert ag(data, ["missing1", "missing2", "a"], default="default") == 1
        assert ag(data, ["missing1", "b", "a"], default="default") == 2
        assert ag(data, ["missing1", "missing2"], default="default") == "default"

    def test_ag_custom_separator(self):
        data = {"a": {"b": {"c": 100}}}
        assert ag(data, "a/b/c", separator="/") == 100

    def test_ag_with_none_values(self):
        data = {"a": None, "b": {"c": None}}
        assert ag(data, "a", default="default") == "default"
        assert ag(data, "b.c", default="default") == "default"

    def test_ag_with_callable_default(self):
        data = {}
        mock_default = MagicMock(return_value="called_default")
        result = ag(data, "missing", default=mock_default)
        assert result == "called_default"
        mock_default.assert_called_once()

    def test_ag_with_object_attributes(self):

        class TestObj:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = {"nested": "value2"}

        obj = TestObj()
        assert ag(obj, "attr1") == "value1"
        assert ag(obj, "attr2.nested") == "value2"

    def test_dict_non_list_fallback(self):

        class NoVarsObj:
            __slots__ = ["value"]

            def __init__(self):
                self.value = "test"

        obj = NoVarsObj()
        assert ag(obj, "anything", default="fallback") == "fallback"


class TestAgSets:
    def test_ag_sets_multiple_paths(self):
        data = {}
        path_values = {"a.b.c": "value1", "a.b.d": "value2", "x.y": "value3"}
        result = ag_sets(data, path_values)

        expected = {"a": {"b": {"c": "value1", "d": "value2"}}, "x": {"y": "value3"}}
        assert result == expected
        assert data == expected

    def test_ag_sets_custom_separator(self):
        data = {}
        path_values = {"a/b/c": "value1", "x/y": "value2"}
        ag_sets(data, path_values, separator="/")

        expected = {"a": {"b": {"c": "value1"}}, "x": {"y": "value2"}}
        assert data == expected

    def test_ag_sets_existing_structure(self):
        data = {"a": {"existing": "value"}}
        path_values = {"a.b.c": "new_value", "d": "another_value"}
        ag_sets(data, path_values)

        expected = {"a": {"existing": "value", "b": {"c": "new_value"}}, "d": "another_value"}
        assert data == expected

    def test_ag_sets_empty_dict(self):
        data = {"existing": "data"}
        original = data.copy()
        ag_sets(data, {})
        assert data == original


class TestAgExists:
    def test_exists_simple_dict_key(self):
        data = {"a": "value", "b": None, "c": 0}
        assert ag_exists(data, "a") is True
        assert ag_exists(data, "b") is False  # None values return False
        assert ag_exists(data, "c") is True  # 0 is not None
        assert ag_exists(data, "missing") is False

    def test_ag_exists_nested_path(self):
        data = {"a": {"b": {"c": "value", "d": None}}}
        assert ag_exists(data, "a.b.c") is True
        assert ag_exists(data, "a.b.d") is False  # None value
        assert ag_exists(data, "a.b.missing") is False
        assert ag_exists(data, "a.missing.c") is False

    def test_ag_exists_list_indices(self):
        data = [10, None, 30]
        assert ag_exists(data, 0) is True
        assert ag_exists(data, 1) is False  # None value
        assert ag_exists(data, 2) is True
        assert ag_exists(data, 5) is False  # Out of bounds

    def test_ag_exists_mixed_structure(self):
        data = {"items": [{"name": "item1"}, None, {"name": "item3"}]}
        assert ag_exists(data, "items.0.name") is True
        assert ag_exists(data, "items.1.name") is False  # items[1] is None
        assert ag_exists(data, "items.2.name") is True
        assert ag_exists(data, "items.5.name") is False  # Out of bounds

    def test_ag_exists_custom_separator(self):
        data = {"a": {"b": {"c": "value"}}}
        assert ag_exists(data, "a/b/c", separator="/") is True
        assert ag_exists(data, "a/b/missing", separator="/") is False

    def test_ag_exists_with_object(self):

        class TestObj:
            def __init__(self):
                self.attr = "value"
                self.nested = {"key": "value"}

        obj = TestObj()
        assert ag_exists(obj, "attr") is True
        assert ag_exists(obj, "nested.key") is True
        assert ag_exists(obj, "missing") is False

    def test_exists_non_vars_object(self):

        class NoVarsObj:
            __slots__ = []

        obj = NoVarsObj()
        assert ag_exists(obj, "anything") is False


class TestAgDelete:
    def test_delete_simple_dict_key(self):
        data = {"a": 1, "b": 2, "c": 3}
        result = ag_delete(data, "b")
        assert result == {"a": 1, "c": 3}
        assert data == {"a": 1, "c": 3}

    def test_ag_delete_nested_path(self):
        data = {"a": {"b": {"c": 1, "d": 2}, "e": 3}}
        ag_delete(data, "a.b.c")
        expected = {"a": {"b": {"d": 2}, "e": 3}}
        assert data == expected

    def test_ag_delete_list_index(self):
        data = [10, 20, 30, 40]
        ag_delete(data, 1)
        assert data == [10, 30, 40]

    def test_ag_delete_mixed_structure(self):
        data = {"items": [{"name": "item1"}, {"name": "item2", "value": 100}]}
        ag_delete(data, "items.1.value")
        expected = {"items": [{"name": "item1"}, {"name": "item2"}]}
        assert data == expected

    def test_ag_delete_multiple_paths(self):
        data = {"a": {"b": 1, "c": 2}, "d": 3, "e": 4}
        ag_delete(data, ["a.b", "d"])
        expected = {"a": {"c": 2}, "e": 4}
        assert data == expected

    def test_ag_delete_custom_separator(self):
        data = {"a": {"b": {"c": 1}}}
        ag_delete(data, "a/b/c", separator="/")
        assert data == {"a": {"b": {}}}

    def test_ag_delete_missing_key(self):
        data = {"a": {"b": 1}}
        original = {"a": {"b": 1}}

        ag_delete(data, "missing")
        ag_delete(data, "a.missing")
        ag_delete(data, "a.b.c")

        assert data == original

    def test_delete_out_bounds_list(self):
        data = [1, 2, 3]
        original = [1, 2, 3]

        ag_delete(data, 10)  # Out of bounds
        ag_delete(data, -1)  # Negative index

        assert data == original

    def test_ag_delete_with_object(self):

        class TestObj:
            def __init__(self):
                self.attr1 = "value1"
                self.attr2 = {"nested": "value2"}

        obj = TestObj()
        ag_delete(obj, "attr1")

        # Check that attr1 was deleted
        assert not hasattr(obj, "attr1")
        assert hasattr(obj, "attr2")

    def test_invalid_list_string_index(self):
        data = {"items": [1, 2, 3]}
        original_items = [1, 2, 3]

        ag_delete(data, "items.invalid_index")

        assert data["items"] == original_items

    def test_delete_path_through_none(self):
        data = {"a": {"b": None}}
        original = {"a": {"b": None}}

        ag_delete(data, "a.b.c")  # Can't traverse through None

        assert data == original


class TestEdgeCases:
    def test_empty_data_structures(self):
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
        # Create 10-level deep structure
        data = {}
        current = data
        for i in range(10):
            current[f"level{i}"] = {}
            current = current[f"level{i}"]
        current["value"] = "deep_value"

        path = ".".join(f"level{i}" for i in range(10)) + ".value"

        assert ag(data, path) == "deep_value"

        assert ag_exists(data, path) is True

        ag_set(data, path.replace(".value", ".new_value"), "new_deep_value")
        new_path = ".".join(f"level{i}" for i in range(10)) + ".new_value"
        assert ag(data, new_path) == "new_deep_value"

    def test_special_characters_in_keys(self):
        data = {"key with spaces": "value1", "key.with.dots": "value2", "key/with/slashes": "value3"}

        # These should work with direct key access
        assert ag(data, "key with spaces") == "value1"
        assert ag(data, "key.with.dots") == "value2"
        assert ag(data, "key/with/slashes") == "value3"

        assert ag_exists(data, "key with spaces") is True
        assert ag_exists(data, "key.with.dots") is True

        ag_delete(data, "key with spaces")
        assert "key with spaces" not in data

    def test_type_consistency(self):
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
