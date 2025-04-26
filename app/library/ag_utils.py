from typing import Any


def get_value(value: Any) -> Any:
    """
    Return the result of calling `value` if it is callable, else return `value`.

    Args:
        value: A value or a callable that returns a value.

    Returns:
        The original `value` if not callable, otherwise the result of calling it.

    """
    return value() if callable(value) else value


def ag_set(data: dict[Any, Any], path: str, value: Any, separator: str = ".") -> dict[Any, Any]:
    """
    Set a value into a nested dictionary at the specified path.

    Args:
        data: The dictionary to modify.
        path: The key path (e.g., "a.b.c").
        value: The value to assign at the specified path.
        separator: The separator for splitting the path string.

    Returns:
        The modified dictionary.

    Raises:
        RuntimeError: If an intermediate value is not a dictionary.

    """
    keys = path.split(separator)
    at = data
    while keys:
        if len(keys) == 1:
            if isinstance(at, dict):
                at[keys.pop(0)] = value
            else:
                msg = f"Cannot set value at path '{path}' because '{at}' is not a dict."
                raise RuntimeError(msg)
        else:
            key = keys.pop(0)
            if key not in at or not isinstance(at[key], dict):
                at[key] = {}
            at = at[key]
    return data


def ag(
    array: dict[Any, Any] | list[Any] | object,
    path: list[str | int] | str | int | None,
    default: Any = None,
    separator: str = ".",
) -> Any:
    """
    Retrieve a value from a nested dict, list, or object using a path.

    Args:
        array: The structure to query (dict, list, or object).
        path: The lookup path. If None or empty, returns the whole structure.
            If list, tries each path in order and returns the first found.
            If str or int, navigates nested structures using `separator`.
        default: The value or callable to return if lookup fails.
        separator: The separator for nested keys in `path`.

    Returns:
        The found value, or `default()` if `default` is callable, or `default` otherwise.

    """
    if path is None or path == "":
        return array
    if not isinstance(array, dict | list):
        try:
            array = vars(array)
        except TypeError:
            return get_value(default)
    if isinstance(array, list) and isinstance(path, int):
        try:
            val = array[path]
            return val if val is not None else get_value(default)
        except (IndexError, TypeError):
            return get_value(default)
    if isinstance(path, list):
        _MISSING = object()
        for key in path:
            val = ag(array, key, default=_MISSING, separator=separator)
            if val is not _MISSING:
                return val
        return get_value(default)
    key = path
    if isinstance(array, dict) and key in array and array[key] is not None:
        return array[key]
    if not isinstance(key, str) or separator not in key:
        return get_value(default)
    current = array
    for segment in key.split(separator):
        if isinstance(current, dict) and segment in current and current[segment] is not None:
            current = current[segment]
        elif isinstance(current, list):
            try:
                idx = int(segment)
            except ValueError:
                return get_value(default)
            if 0 <= idx < len(current) and current[idx] is not None:
                current = current[idx]
            else:
                return get_value(default)
        else:
            return get_value(default)
    return current


def ag_sets(data: dict[Any, Any], path_values: dict[str, Any], separator: str = ".") -> dict[Any, Any]:
    """
    Set multiple values into a nested dictionary.

    Args:
        data: The dictionary to modify.
        path_values: A mapping of path strings to values.
        separator: The separator for splitting each path.

    Returns:
        The modified dictionary.

    """
    for path, value in path_values.items():
        ag_set(data, path, value, separator)
    return data


def ag_exists(data: dict[Any, Any] | list[Any] | object, path: str | int, separator: str = ".") -> bool:
    """
    Check if a nested key or index exists and is not None.

    Args:
        data: The structure to check (dict, list, or object).
        path: The key, index, or separator-delimited path string.
        separator: The separator for splitting the path.

    Returns:
        True if the path exists and the value is not None, False otherwise.

    """
    if not isinstance(data, dict | list):
        try:
            data = vars(data)
        except TypeError:
            return False
    if isinstance(data, dict):
        if path in data and data[path] is not None:
            return True
    elif isinstance(data, list) and isinstance(path, int):
        return 0 <= path < len(data) and data[path] is not None
    path_str = str(path)
    segments = path_str.split(separator)
    current = data
    for seg in segments:
        if isinstance(current, dict) and seg in current and current[seg] is not None:
            current = current[seg]
        elif isinstance(current, list):
            try:
                idx = int(seg)
            except ValueError:
                return False
            if 0 <= idx < len(current) and current[idx] is not None:
                current = current[idx]
            else:
                return False
        else:
            return False
    return True


def ag_delete(
    data: dict[Any, Any] | list[Any] | object, path: str | int | list[str | int], separator: str = "."
) -> dict[Any, Any] | list[Any]:
    """
    Delete one or more keys or indices from a nested structure.

    Args:
        data: The structure to modify (dict, list, or object).
        path: A key/index, a separator-delimited string path, or a list of such paths.
        separator: The separator for splitting the path.

    Returns:
        The modified structure.

    """
    if isinstance(path, list | tuple):
        for p in path:
            ag_delete(data, p, separator)
        return data
    if not isinstance(data, dict | list):
        try:
            data = vars(data)
        except TypeError:
            return data  # type: ignore
    if isinstance(data, dict) and path in data:
        del data[path]
        return data
    if isinstance(data, list) and isinstance(path, int):
        if 0 <= path < len(data):
            data.pop(path)
        return data
    path_str = str(path)
    segments = path_str.split(separator)
    last = segments.pop()
    current = data
    for seg in segments:
        if isinstance(current, dict) and seg in current:
            current = current[seg]
        elif isinstance(current, list):
            try:
                idx = int(seg)
            except ValueError:
                current = None
                break
            if 0 <= idx < len(current):
                current = current[idx]
            else:
                current = None
                break
        else:
            current = None
            break
    if current is None:
        return data
    if isinstance(current, dict) and last in current:
        del current[last]
    elif isinstance(current, list):
        try:
            idx = int(last)
            if 0 <= idx < len(current):
                current.pop(idx)
        except (ValueError, IndexError):
            pass
    return data


def run_tests():
    def test_ag_set_basic():
        d = {"a": {"b": 1}}
        assert ag_set(d, "a.c.d", 42) == {"a": {"b": 1, "c": {"d": 42}}}

    def test_ag_set_overwrite_error():
        try:
            ag_set({"a": 1}, "a.b", 2)
        except RuntimeError as e:
            assert "Cannot set value at path" in str(e)  # noqa: PT017

    def test_ag_get_value_callable_and_value():
        assert get_value(5) == 5
        assert get_value(lambda: 7) == 7

    def test_ag_simple_dict():
        d = {"x": 10}
        assert ag(d, "x") == 10
        assert ag(d, "y", default=0) == 0

    def test_ag_nested():
        d = {"a": {"b": {"c": 3}}}
        assert ag(d, "a.b.c") == 3
        assert ag(d, "a.b.x", default="no") == "no"

    def test_ag_list_index():
        lst = [1, 2, None]
        assert ag(lst, 1) == 2
        assert ag(lst, 2, default=0) == 0

    def test_ag_list_of_paths():
        d = {"a": 1}
        assert ag(d, ["x", "a"], default=9) == 1

    def test_ag_sets():
        d = {}
        ag_sets(d, {"u.v": 5, "u.w": 6, "z": 7})
        assert d == {"u": {"v": 5, "w": 6}, "z": 7}

    def test_ag_exists():
        d = {"a": {"b": None, "c": 2}, "lst": [0, None]}
        assert not ag_exists(d, "a.b")
        assert ag_exists(d, "a.c")
        assert not ag_exists(d, "a.x")
        assert ag_exists(d, "lst.0")
        assert not ag_exists(d, "lst.1")

    def test_ag_delete_basic():
        d = {"a": {"b": 1, "c": 2}, "x": 5}
        ag_delete(d, "a.b")
        assert d == {"a": {"c": 2}, "x": 5}

    def test_ag_delete_list_and_multiple():
        lst = [10, 20, {"n": [1, 2, 3]}]
        ag_delete(lst, 1)
        assert lst == [10, {"n": [1, 2, 3]}]
        ag_delete(lst, "1.n.2")
        assert lst == [10, {"n": [1, 2]}]

    def test_ag_delete_multiple_paths():
        data = {"u": {"v": 100}, "w": 200}
        ag_delete(data, ["u.v", "w"])
        assert data == {"u": {}}

    for test in [
        test_ag_set_basic,
        test_ag_set_overwrite_error,
        test_ag_get_value_callable_and_value,
        test_ag_simple_dict,
        test_ag_nested,
        test_ag_list_index,
        test_ag_list_of_paths,
        test_ag_sets,
        test_ag_exists,
        test_ag_delete_basic,
        test_ag_delete_list_and_multiple,
        test_ag_delete_multiple_paths,
    ]:
        try:
            test()
            print(f"PASS: {test.__name__}")  # noqa: T201
        except AssertionError:
            print(f"FAIL {test.__name__}")  # noqa: T201


if __name__ == "__main__":
    run_tests()
