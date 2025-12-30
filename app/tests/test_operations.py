"""Tests for the generic operations module."""

from app.library.operations import (
    Operation,
    filter_items,
    find_all,
    find_first,
    matches,
    matches_all,
    matches_any,
    matches_condition,
)


class TestMatchesGeneric:
    """Test the generic matches(operation, val1, val2) function."""

    def test_matches_equal(self) -> None:
        """Test EQUAL operation."""
        assert matches(Operation.EQUAL, "test", "test") is True
        assert matches(Operation.EQUAL, 100, 100) is True
        assert matches(Operation.EQUAL, "test", "other") is False
        assert matches(Operation.EQUAL, None, None) is True

    def test_matches_not_equal(self) -> None:
        """Test NOT_EQUAL operation."""
        assert matches(Operation.NOT_EQUAL, "test", "other") is True
        assert matches(Operation.NOT_EQUAL, 100, 200) is True
        assert matches(Operation.NOT_EQUAL, "test", "test") is False

    def test_matches_contain(self) -> None:
        """Test CONTAIN operation."""
        assert matches(Operation.CONTAIN, "Python Tutorial", "Python") is True
        assert matches(Operation.CONTAIN, "Hello World", "World") is True
        assert matches(Operation.CONTAIN, "test", "xyz") is False
        assert matches(Operation.CONTAIN, None, "test") is False

    def test_matches_not_contain(self) -> None:
        """Test NOT_CONTAIN operation."""
        assert matches(Operation.NOT_CONTAIN, "Python Tutorial", "Java") is True
        assert matches(Operation.NOT_CONTAIN, "test", "test") is False
        assert matches(Operation.NOT_CONTAIN, None, "test") is True

    def test_matches_greater_than(self) -> None:
        """Test GREATER_THAN operation."""
        assert matches(Operation.GREATER_THAN, 100, 50) is True
        assert matches(Operation.GREATER_THAN, 50, 100) is False
        assert matches(Operation.GREATER_THAN, 100, 100) is False
        assert matches(Operation.GREATER_THAN, None, 50) is False
        assert matches(Operation.GREATER_THAN, 100, None) is False

    def test_matches_less_than(self) -> None:
        """Test LESS_THAN operation."""
        assert matches(Operation.LESS_THAN, 50, 100) is True
        assert matches(Operation.LESS_THAN, 100, 50) is False
        assert matches(Operation.LESS_THAN, 100, 100) is False

    def test_matches_greater_equal(self) -> None:
        """Test GREATER_EQUAL operation."""
        assert matches(Operation.GREATER_EQUAL, 100, 50) is True
        assert matches(Operation.GREATER_EQUAL, 100, 100) is True
        assert matches(Operation.GREATER_EQUAL, 50, 100) is False

    def test_matches_less_equal(self) -> None:
        """Test LESS_EQUAL operation."""
        assert matches(Operation.LESS_EQUAL, 50, 100) is True
        assert matches(Operation.LESS_EQUAL, 100, 100) is True
        assert matches(Operation.LESS_EQUAL, 100, 50) is False

    def test_matches_starts_with(self) -> None:
        """Test STARTS_WITH operation."""
        assert matches(Operation.STARTS_WITH, "Python Tutorial", "Python") is True
        assert matches(Operation.STARTS_WITH, "Tutorial", "Python") is False
        assert matches(Operation.STARTS_WITH, None, "test") is False

    def test_matches_ends_with(self) -> None:
        """Test ENDS_WITH operation."""
        assert matches(Operation.ENDS_WITH, "Learn Python", "Python") is True
        assert matches(Operation.ENDS_WITH, "Python Tutorial", "Python") is False
        assert matches(Operation.ENDS_WITH, None, "test") is False

    def test_matches_with_string_operation(self) -> None:
        """Test backward compatibility with string operations."""
        assert matches("==", "test", "test") is True
        assert matches("in", "Python Tutorial", "Python") is True
        assert matches(">", 100, 50) is True

    def test_matches_with_invalid_operation(self) -> None:
        """Test with invalid operation string defaults to EQUAL."""
        assert matches("invalid_op", "test", "test") is True
        assert matches("invalid_op", "test", "other") is False

    def test_matches_with_incompatible_types(self) -> None:
        """Test that incompatible type comparisons return False."""
        # Comparing string with number for > operation
        assert matches(Operation.GREATER_THAN, "text", 100) is False


class TestMatchesCondition:
    """Test the matches_condition helper function."""

    def test_matches_condition_simple_value(self) -> None:
        """Test with simple value (defaults to EQUAL)."""
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_condition("title", "Python Tutorial", data) is True
        assert matches_condition("title", "Other", data) is False

    def test_matches_condition_with_operation(self) -> None:
        """Test with tuple (operation, value)."""
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_condition("title", (Operation.CONTAIN, "Python"), data) is True
        assert matches_condition("size", (Operation.GREATER_THAN, 500), data) is True

    def test_matches_condition_missing_key(self) -> None:
        """Test with non-existent key."""
        data = {"title": "Python Tutorial"}
        assert matches_condition("missing", "value", data) is False


class TestMatchesAll:
    """Test matches_all function (AND logic)."""

    def test_matches_all_true(self) -> None:
        """Test when all conditions match."""
        data = {"title": "Python Tutorial", "size": 1000, "status": "active"}
        assert matches_all(data, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 500)) is True

    def test_matches_all_false(self) -> None:
        """Test when any condition fails."""
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_all(data, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 2000)) is False

    def test_matches_all_empty_conditions(self) -> None:
        """Test with no conditions returns True."""
        data = {"title": "Python Tutorial"}
        assert matches_all(data) is True


class TestMatchesAny:
    """Test matches_any function (OR logic)."""

    def test_matches_any_true(self) -> None:
        """Test when at least one condition matches."""
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_any(data, title=(Operation.CONTAIN, "Java"), size=(Operation.GREATER_THAN, 500)) is True

    def test_matches_any_false(self) -> None:
        """Test when no conditions match."""
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_any(data, title="Wrong", status="Wrong") is False

    def test_matches_any_empty_conditions(self) -> None:
        """Test with no conditions returns False."""
        data = {"title": "Python Tutorial"}
        assert matches_any(data) is False


class TestFilterItems:
    """Test filter_items function."""

    def test_filter_items_basic(self) -> None:
        """Test basic filtering."""
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "JavaScript Course", "size": 2000},
            {"title": "Python Advanced", "size": 1500},
        ]

        result = filter_items(items, title=(Operation.CONTAIN, "Python"))
        assert len(result) == 2
        assert result[0]["title"] == "Python Tutorial"
        assert result[1]["title"] == "Python Advanced"

    def test_filter_items_multiple_conditions(self) -> None:
        """Test filtering with multiple conditions (AND logic)."""
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "Python Advanced", "size": 2000},
            {"title": "JavaScript Course", "size": 1500},
        ]

        result = filter_items(items, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 1200))
        assert len(result) == 1
        assert result[0]["title"] == "Python Advanced"

    def test_filter_items_no_conditions(self) -> None:
        """Test that no conditions returns all items."""
        items = [{"title": "Test 1"}, {"title": "Test 2"}]
        result = filter_items(items)
        assert len(result) == 2


class TestFindFirst:
    """Test find_first function."""

    def test_find_first_match(self) -> None:
        """Test finding first match."""
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "Python Advanced", "size": 2000},
        ]

        result = find_first(items, title=(Operation.CONTAIN, "Python"))
        assert result is not None
        assert result["title"] == "Python Tutorial"

    def test_find_first_no_match(self) -> None:
        """Test when no match is found."""
        items = [{"title": "Python Tutorial"}]
        result = find_first(items, title="Nonexistent")
        assert result is None


class TestFindAll:
    """Test find_all function (alias for filter_items)."""

    def test_find_all(self) -> None:
        """Test find_all is an alias for filter_items."""
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "JavaScript Course", "size": 2000},
        ]

        result = find_all(items, title=(Operation.CONTAIN, "Python"))
        assert len(result) == 1
        assert result[0]["title"] == "Python Tutorial"


class TestOperationEnum:
    """Test Operation enum."""

    def test_operation_values(self) -> None:
        """Test operation enum values."""
        assert Operation.EQUAL.value == "=="
        assert Operation.NOT_EQUAL.value == "!="
        assert Operation.CONTAIN.value == "in"
        assert Operation.GREATER_THAN.value == ">"
        assert Operation.STARTS_WITH.value == "startswith"

    def test_operation_str(self) -> None:
        """Test operation string representation."""
        assert str(Operation.EQUAL) == "=="
        assert str(Operation.CONTAIN) == "in"
