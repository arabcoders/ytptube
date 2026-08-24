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
    def test_matches_equal(self) -> None:
        assert matches(Operation.EQUAL, "test", "test") is True
        assert matches(Operation.EQUAL, 100, 100) is True
        assert matches(Operation.EQUAL, "test", "other") is False
        assert matches(Operation.EQUAL, None, None) is True

    def test_matches_not_equal(self) -> None:
        assert matches(Operation.NOT_EQUAL, "test", "other") is True
        assert matches(Operation.NOT_EQUAL, 100, 200) is True
        assert matches(Operation.NOT_EQUAL, "test", "test") is False

    def test_matches_contain(self) -> None:
        assert matches(Operation.CONTAIN, "Python Tutorial", "Python") is True
        assert matches(Operation.CONTAIN, "Hello World", "World") is True
        assert matches(Operation.CONTAIN, "test", "xyz") is False
        assert matches(Operation.CONTAIN, None, "test") is False

    def test_matches_not_contain(self) -> None:
        assert matches(Operation.NOT_CONTAIN, "Python Tutorial", "Java") is True
        assert matches(Operation.NOT_CONTAIN, "test", "test") is False
        assert matches(Operation.NOT_CONTAIN, None, "test") is True

    def test_matches_greater_than(self) -> None:
        assert matches(Operation.GREATER_THAN, 100, 50) is True
        assert matches(Operation.GREATER_THAN, 50, 100) is False
        assert matches(Operation.GREATER_THAN, 100, 100) is False
        assert matches(Operation.GREATER_THAN, None, 50) is False
        assert matches(Operation.GREATER_THAN, 100, None) is False

    def test_matches_less_than(self) -> None:
        assert matches(Operation.LESS_THAN, 50, 100) is True
        assert matches(Operation.LESS_THAN, 100, 50) is False
        assert matches(Operation.LESS_THAN, 100, 100) is False

    def test_matches_greater_equal(self) -> None:
        assert matches(Operation.GREATER_EQUAL, 100, 50) is True
        assert matches(Operation.GREATER_EQUAL, 100, 100) is True
        assert matches(Operation.GREATER_EQUAL, 50, 100) is False

    def test_matches_less_equal(self) -> None:
        assert matches(Operation.LESS_EQUAL, 50, 100) is True
        assert matches(Operation.LESS_EQUAL, 100, 100) is True
        assert matches(Operation.LESS_EQUAL, 100, 50) is False

    def test_matches_starts_with(self) -> None:
        assert matches(Operation.STARTS_WITH, "Python Tutorial", "Python") is True
        assert matches(Operation.STARTS_WITH, "Tutorial", "Python") is False
        assert matches(Operation.STARTS_WITH, None, "test") is False

    def test_matches_ends_with(self) -> None:
        assert matches(Operation.ENDS_WITH, "Learn Python", "Python") is True
        assert matches(Operation.ENDS_WITH, "Python Tutorial", "Python") is False
        assert matches(Operation.ENDS_WITH, None, "test") is False

    def test_matches_with_string_operation(self) -> None:
        assert matches("==", "test", "test") is True
        assert matches("in", "Python Tutorial", "Python") is True
        assert matches(">", 100, 50) is True

    def test_matches_with_invalid_operation(self) -> None:
        assert matches("invalid_op", "test", "test") is True
        assert matches("invalid_op", "test", "other") is False

    def test_matches_with_incompatible_types(self) -> None:
        assert matches(Operation.GREATER_THAN, "text", 100) is False


class TestMatchesCondition:
    def test_matches_condition_simple_value(self) -> None:
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_condition("title", "Python Tutorial", data) is True
        assert matches_condition("title", "Other", data) is False

    def test_matches_condition_with_operation(self) -> None:
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_condition("title", (Operation.CONTAIN, "Python"), data) is True
        assert matches_condition("size", (Operation.GREATER_THAN, 500), data) is True

    def test_matches_condition_missing_key(self) -> None:
        data = {"title": "Python Tutorial"}
        assert matches_condition("missing", "value", data) is False


class TestMatchesAll:
    def test_matches_all_true(self) -> None:
        data = {"title": "Python Tutorial", "size": 1000, "status": "active"}
        assert matches_all(data, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 500)) is True

    def test_matches_all_false(self) -> None:
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_all(data, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 2000)) is False

    def test_matches_all_empty_conditions(self) -> None:
        data = {"title": "Python Tutorial"}
        assert matches_all(data) is True


class TestMatchesAny:
    def test_matches_any_true(self) -> None:
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_any(data, title=(Operation.CONTAIN, "Java"), size=(Operation.GREATER_THAN, 500)) is True

    def test_matches_any_false(self) -> None:
        data = {"title": "Python Tutorial", "size": 1000}
        assert matches_any(data, title="Wrong", status="Wrong") is False

    def test_matches_any_empty_conditions(self) -> None:
        data = {"title": "Python Tutorial"}
        assert matches_any(data) is False


class TestFilterItems:
    def test_filter_items_basic(self) -> None:
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
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "Python Advanced", "size": 2000},
            {"title": "JavaScript Course", "size": 1500},
        ]

        result = filter_items(items, title=(Operation.CONTAIN, "Python"), size=(Operation.GREATER_THAN, 1200))
        assert len(result) == 1
        assert result[0]["title"] == "Python Advanced"

    def test_filter_items_no_conditions(self) -> None:
        items = [{"title": "Test 1"}, {"title": "Test 2"}]
        result = filter_items(items)
        assert len(result) == 2


class TestFindFirst:
    def test_find_first_match(self) -> None:
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "Python Advanced", "size": 2000},
        ]

        result = find_first(items, title=(Operation.CONTAIN, "Python"))
        assert result is not None
        assert result["title"] == "Python Tutorial"

    def test_find_first_no_match(self) -> None:
        items = [{"title": "Python Tutorial"}]
        result = find_first(items, title="Nonexistent")
        assert result is None


class TestFindAll:
    def test_find_all(self) -> None:
        items = [
            {"title": "Python Tutorial", "size": 1000},
            {"title": "JavaScript Course", "size": 2000},
        ]

        result = find_all(items, title=(Operation.CONTAIN, "Python"))
        assert len(result) == 1
        assert result[0]["title"] == "Python Tutorial"
