from enum import Enum
from typing import Any


class Operation(str, Enum):
    """Comparison operations for filtering items."""

    EQUAL = "=="
    """Exact equality comparison."""
    NOT_EQUAL = "!="
    """Not equal comparison."""
    CONTAIN = "in"
    """Check if value is contained in the field (substring match)."""
    NOT_CONTAIN = "not_in"
    """Check if value is not contained in the field."""
    GREATER_THAN = ">"
    """Greater than comparison."""
    LESS_THAN = "<"
    """Less than comparison."""
    GREATER_EQUAL = ">="
    """Greater than or equal comparison."""
    LESS_EQUAL = "<="
    """Less than or equal comparison."""
    STARTS_WITH = "startswith"
    """Check if field starts with value."""
    ENDS_WITH = "endswith"
    """Check if field ends with value."""

    def __str__(self) -> str:
        return self.value


def matches(operation: Operation | str, haystack: Any, needle: Any) -> bool:
    """
    Generic comparison function that compares two values using the specified operation.

    Args:
        operation: The comparison operation to perform (Operation enum or string)
        haystack: The first value (usually the field value from data)
        needle: The second value (usually the comparison value)

    Returns:
        bool: True if the comparison matches, False otherwise

    Examples:
        >>> matches(Operation.EQUAL, "test", "test")
        True
        >>> matches(Operation.CONTAIN, "Python Tutorial", "Python")
        True
        >>> matches(Operation.GREATER_THAN, 100, 50)
        True
        >>> matches("==", "test", "test")
        True

    """
    # Parse operation if it's a string
    if isinstance(operation, str):
        try:
            operation = Operation(operation)
        except ValueError:
            operation = Operation.EQUAL

    try:
        if Operation.EQUAL == operation:
            return haystack == needle

        if Operation.NOT_EQUAL == operation:
            return haystack != needle

        if Operation.CONTAIN == operation:
            return str(needle) in str(haystack) if haystack is not None else False

        if Operation.NOT_CONTAIN == operation:
            return str(needle) not in str(haystack) if haystack is not None else True

        if Operation.GREATER_THAN == operation:
            if haystack is None or needle is None:
                return False
            return haystack > needle

        if Operation.LESS_THAN == operation:
            if haystack is None or needle is None:
                return False
            return haystack < needle

        if Operation.GREATER_EQUAL == operation:
            if haystack is None or needle is None:
                return False
            return haystack >= needle

        if Operation.LESS_EQUAL == operation:
            if haystack is None or needle is None:
                return False
            return haystack <= needle

        if Operation.STARTS_WITH == operation:
            return str(haystack).startswith(str(needle)) if haystack is not None else False

        if Operation.ENDS_WITH == operation:
            return str(haystack).endswith(str(needle)) if haystack is not None else False

        # Unknown operation, default to equality
        return haystack == needle

    except (TypeError, AttributeError):
        # Comparison failed (e.g., comparing incompatible types)
        return False


def matches_condition(key: str, value: tuple | str | float | bool, data: dict) -> bool:
    """
    Check if a field in a dictionary matches the given condition.

    This is a helper function that extracts values from a dictionary and uses the generic
    matches() function to perform the comparison.

    Args:
        key: The field name to check in the data dictionary
        value: Either:
            - A direct value for equality check: "test"
            - A tuple of (Operation, value): (Operation.CONTAIN, "test")
            - A tuple of (str, value): ("in", "test") for backward compatibility
        data: Dictionary containing the data to check against

    Returns:
        bool: True if the condition matches, False otherwise

    Examples:
        >>> data = {"title": "Python Tutorial", "size": 1000}
        >>> matches_condition("title", "Python Tutorial", data)
        True
        >>> matches_condition("title", (Operation.CONTAIN, "Python"), data)
        True
        >>> matches_condition("size", (Operation.GREATER_THAN, 500), data)
        True
        >>> matches_condition("missing", "value", data)
        False

    """
    if key not in data:
        return False

    field_value: Any = data[key]

    # Parse value to extract operation and comparison value
    if isinstance(value, tuple) and len(value) == 2:
        operation, compare_value = value
    else:
        operation = Operation.EQUAL
        compare_value = value

    return matches(operation, field_value, compare_value)


def matches_all(data: dict, **conditions) -> bool:
    """
    Check if all conditions match (AND logic).

    Args:
        data: Dictionary containing the data to check against
        **conditions: Keyword arguments representing conditions to check

    Returns:
        bool: True if all conditions match, False otherwise

    Examples:
        >>> data = {"title": "Python Tutorial", "size": 1000, "status": "active"}
        >>> matches_all(data, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 500))
        True
        >>> matches_all(data, title="Python Tutorial", status="active")
        True

    """
    if not conditions:
        return True

    return all(matches_condition(key, value, data) for key, value in conditions.items())


def matches_any(data: dict, **conditions) -> bool:
    """
    Check if any condition matches (OR logic).

    Args:
        data: Dictionary containing the data to check against
        **conditions: Keyword arguments representing conditions to check

    Returns:
        bool: True if any condition matches, False if none match

    Examples:
        >>> data = {"title": "Python Tutorial", "size": 1000}
        >>> matches_any(data, title=(Operation.CONTAIN, "Java"), size=(Operation.GREATER_THAN, 500))
        True
        >>> matches_any(data, title="Wrong", status="Wrong")
        False

    """
    if not conditions:
        return False

    return any(matches_condition(key, value, data) for key, value in conditions.items())


def filter_items(items: list[dict], **conditions) -> list[dict]:
    """
    Filter a list of dictionaries based on conditions (AND logic).

    Args:
        items: List of dictionaries to filter
        **conditions: Keyword arguments representing conditions to check

    Returns:
        list[dict]: Filtered list of dictionaries that match all conditions

    Examples:
        >>> items = [
        ...     {"title": "Python Tutorial", "size": 1000},
        ...     {"title": "JavaScript Course", "size": 2000},
        ...     {"title": "Python Advanced", "size": 1500}
        ... ]
        >>> filter_items(items, title=(Operation.CONTAIN, "Python"))
        [{"title": "Python Tutorial", "size": 1000}, {"title": "Python Advanced", "size": 1500}]
        >>> filter_items(items, size=(Operation.GREATER_THAN, 1200))
        [{"title": "JavaScript Course", "size": 2000}, {"title": "Python Advanced", "size": 1500}]

    """
    if not conditions:
        return items

    return [item for item in items if matches_all(item, **conditions)]


def find_first(items: list[dict], **conditions) -> dict | None:
    """
    Find the first dictionary that matches all conditions (AND logic).

    Args:
        items: List of dictionaries to search
        **conditions: Keyword arguments representing conditions to check

    Returns:
        dict | None: First matching dictionary or None if no match found

    Examples:
        >>> items = [
        ...     {"title": "Python Tutorial", "size": 1000},
        ...     {"title": "JavaScript Course", "size": 2000}
        ... ]
        >>> find_first(items, title=(Operation.CONTAIN, "Python"))
        {"title": "Python Tutorial", "size": 1000}
        >>> find_first(items, title="Nonexistent")
        None

    """
    for item in items:
        if matches_all(item, **conditions):
            return item
    return None


def find_all(items: list[dict], **conditions) -> list[dict]:
    """
    Alias for filter_items() - find all dictionaries matching conditions.

    Args:
        items: List of dictionaries to search
        **conditions: Keyword arguments representing conditions to check

    Returns:
        list[dict]: List of matching dictionaries

    """
    return filter_items(items, **conditions)

