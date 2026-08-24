from enum import Enum
from typing import Any


class Operation(str, Enum):
    EQUAL = "=="
    NOT_EQUAL = "!="
    CONTAIN = "in"
    NOT_CONTAIN = "not_in"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    STARTS_WITH = "startswith"
    ENDS_WITH = "endswith"

    def __str__(self) -> str:
        return self.value


def matches(operation: Operation | str, haystack: Any, needle: Any) -> bool:
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

        # Unknown operations default to equality.
        return haystack == needle

    except (TypeError, AttributeError):
        # Incompatible values do not match.
        return False


def matches_condition(key: str, value: tuple | str | float | bool, data: dict) -> bool:
    """Accept direct equality values and operation/value tuples, including string operations."""
    if key not in data:
        return False

    field_value: Any = data[key]

    if isinstance(value, tuple) and len(value) == 2:
        operation, compare_value = value
    else:
        operation = Operation.EQUAL
        compare_value = value

    return matches(operation, field_value, compare_value)


def matches_all(data: dict, **conditions) -> bool:
    if not conditions:
        return True

    return all(matches_condition(key, value, data) for key, value in conditions.items())


def matches_any(data: dict, **conditions) -> bool:
    if not conditions:
        return False

    return any(matches_condition(key, value, data) for key, value in conditions.items())


def filter_items(items: list[dict], **conditions) -> list[dict]:
    if not conditions:
        return items

    return [item for item in items if matches_all(item, **conditions)]


def find_first(items: list[dict], **conditions) -> dict | None:
    for item in items:
        if matches_all(item, **conditions):
            return item
    return None


def find_all(items: list[dict], **conditions) -> list[dict]:
    return filter_items(items, **conditions)
