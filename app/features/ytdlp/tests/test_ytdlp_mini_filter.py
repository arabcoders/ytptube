import unittest
from typing import Any

from app.features.ytdlp.mini_filter import MiniFilter


class TestMiniFilter(unittest.TestCase):
    @staticmethod
    def _normalize(filters) -> set[str]:
        """
        Normalize AND order so 'a&b' == 'b&a'

        Args:
            filters (list[str]): List of filter strings

        Returns:
            set[str]: Set of normalized filter strings

        """
        return {"&".join(sorted(p.split("&"))) for p in filters}

    def _test(
        self, expr: str, test_data: dict, *, expected_result: bool, test_name: str = "", skip_ytdlp: bool = False
    ):
        """
        Test both our implementation and yt-dlp's implementation to ensure they give the same result.

        This method:
        1. Tests our implementation directly on the full expression (supports OR, grouping)
        2. Exports our expression to yt-dlp compatible format (flattens OR/grouping to multiple AND-only filters)
        3. Tests yt-dlp on each exported filter (OR logic: any filter match = True)
        4. Verifies both implementations agree

        Args:
            expr: Filter expression string (may contain OR, parentheses)
            test_data: Dictionary to test against
            expected_result: Expected boolean result (keyword-only)
            test_name: Optional test name for better error messages
            skip_ytdlp: Skip yt-dlp comparison due to known bugs (keyword-only)

        """
        from yt_dlp.utils import match_str

        # Step 1: Test our implementation directly
        parser = MiniFilter(expr)
        our_result = parser.evaluate(test_data)

        # Step 2: Export to yt-dlp compatible format
        # Our export() method flattens OR/grouping into multiple AND-only strings
        exported_filters: list[str] = parser.export()

        # Step 3: Test yt-dlp implementation (unless skipped)
        if not skip_ytdlp:
            # Since yt-dlp doesn't support OR, we test each exported filter separately
            # The overall result is True if ANY exported filter matches (OR logic)
            ytdlp_result = any(match_str(filter_part, test_data) for filter_part in exported_filters)

            # Step 4b: Verify yt-dlp gives the expected result
            assert ytdlp_result == expected_result, (
                f"{test_name}: yt-dlp impl failed - expr: '{expr}' -> {exported_filters}, expected: {expected_result}, got: {ytdlp_result}"
            )

            # Step 5: Verify both implementations agree with each other
            assert our_result == ytdlp_result, (
                f"{test_name}: Implementations disagree - expr: '{expr}', our: {our_result}, yt-dlp: {ytdlp_result}, "
                f"exported: {exported_filters}"
            )

        # Step 4a: Verify our implementation gives the expected result
        assert our_result == expected_result, (
            f"{test_name}: Our impl failed - expr: '{expr}', expected: {expected_result}, got: {our_result}"
        )

        return our_result

    def test_simple_and(self):
        expr = "filesize>1MB & duration<10m"
        parser = MiniFilter(expr)
        assert TestMiniFilter._normalize(parser.export()) == TestMiniFilter._normalize(["filesize>1MB&duration<10m"]), (
            "Failed export check"
        )

        self._test(expr, {"filesize": 2000000, "duration": 200}, expected_result=True, test_name="simple_and_positive")
        self._test(expr, {"filesize": 500000, "duration": 200}, expected_result=False, test_name="simple_and_negative")

    def test_or(self):
        expr = "uploader='BBC' || uploader='NHK'"
        parser = MiniFilter(expr)
        assert TestMiniFilter._normalize(parser.export()) == TestMiniFilter._normalize(
            ["uploader='BBC'", "uploader='NHK'"]
        ), "Failed export check"

        self._test(expr, {"uploader": "BBC"}, expected_result=True, test_name="or_bbc")
        self._test(expr, {"uploader": "NHK"}, expected_result=True, test_name="or_nhk")
        self._test(expr, {"uploader": "CNN"}, expected_result=False, test_name="or_cnn")

    def test_grouping(self):
        expr = "(filesize>1MB & duration<10m) || uploader='BBC'"
        parser = MiniFilter(expr)
        assert TestMiniFilter._normalize(parser.export()) == TestMiniFilter._normalize(
            ["filesize>1MB&duration<10m", "uploader='BBC'"]
        ), "Failed export check"

        self._test(
            expr, {"filesize": 2000000, "duration": 200}, expected_result=True, test_name="grouping_filesize_match"
        )
        self._test(expr, {"uploader": "BBC"}, expected_result=True, test_name="grouping_uploader_match")
        self._test(
            expr,
            {"filesize": 500000, "duration": 200, "uploader": "CNN"},
            expected_result=False,
            test_name="grouping_no_match",
        )

    def test_unary_presence(self):
        # Test duration presence
        self._test("duration", {"duration": 100}, expected_result=True, test_name="unary_duration_present")
        self._test("duration", {}, expected_result=False, test_name="unary_duration_absent")

        # Test duration absence
        self._test("!duration", {}, expected_result=True, test_name="unary_not_duration_absent")
        self._test("!duration", {"duration": 100}, expected_result=False, test_name="unary_not_duration_present")

    def test_duration_units(self):
        # Test with numeric duration values to avoid yt-dlp's inconsistent unit parsing
        # Using 120 seconds = 2 minutes
        self._test("duration<120", {"duration": 30}, expected_result=True, test_name="duration_120_positive")
        self._test("duration<120", {"duration": 200}, expected_result=False, test_name="duration_120_negative")

        # Test 90 seconds
        self._test("duration<90", {"duration": 30}, expected_result=True, test_name="duration_90_positive")
        self._test("duration<90", {"duration": 120}, expected_result=False, test_name="duration_90_negative")

        # Test 3600 seconds = 1 hour
        self._test("duration<3600", {"duration": 3599}, expected_result=True, test_name="duration_3600_positive")
        self._test("duration<3600", {"duration": 3700}, expected_result=False, test_name="duration_3600_negative")

    def test_duration_units_with_suffixes(self):
        """Test duration comparisons with time unit suffixes (m, h). Skip yt-dlp due to known parsing bugs."""
        # Test 2 minutes (120 seconds)
        self._test(
            "duration<2m", {"duration": 90}, expected_result=True, test_name="duration_2m_positive", skip_ytdlp=True
        )
        self._test(
            "duration<2m", {"duration": 150}, expected_result=False, test_name="duration_2m_negative", skip_ytdlp=True
        )

        # Test 5 minutes (300 seconds)
        self._test(
            "duration<5m", {"duration": 240}, expected_result=True, test_name="duration_5m_positive", skip_ytdlp=True
        )
        self._test(
            "duration<5m", {"duration": 360}, expected_result=False, test_name="duration_5m_negative", skip_ytdlp=True
        )

        # Test 10 minutes (600 seconds)
        self._test(
            "duration<10m", {"duration": 480}, expected_result=True, test_name="duration_10m_positive", skip_ytdlp=True
        )
        self._test(
            "duration<10m", {"duration": 720}, expected_result=False, test_name="duration_10m_negative", skip_ytdlp=True
        )

        # Test 1 hour (3600 seconds)
        self._test(
            "duration<1h", {"duration": 3000}, expected_result=True, test_name="duration_1h_positive", skip_ytdlp=True
        )
        self._test(
            "duration<1h", {"duration": 4000}, expected_result=False, test_name="duration_1h_negative", skip_ytdlp=True
        )

        # Test >= operator with minutes
        self._test(
            "duration>=5m", {"duration": 300}, expected_result=True, test_name="duration_gte_5m_equal", skip_ytdlp=True
        )
        self._test(
            "duration>=5m",
            {"duration": 400},
            expected_result=True,
            test_name="duration_gte_5m_greater",
            skip_ytdlp=True,
        )
        self._test(
            "duration>=5m", {"duration": 200}, expected_result=False, test_name="duration_gte_5m_less", skip_ytdlp=True
        )

    def test_filesize_units(self):
        # Test 1MB
        self._test("filesize>1MB", {"filesize": 2000000}, expected_result=True, test_name="filesize_1mb_positive")
        self._test("filesize>1MB", {"filesize": 500000}, expected_result=False, test_name="filesize_1mb_negative")

        # Test 1GiB
        self._test("filesize>=1GiB", {"filesize": 2**30}, expected_result=True, test_name="filesize_1gib_positive")
        self._test("filesize>=1GiB", {"filesize": 1000000}, expected_result=False, test_name="filesize_1gib_negative")

    def test_complex_duration_units_with_or_and_grouping(self):
        """Test complex expressions with duration units, OR operations, and grouping. Skip yt-dlp due to known parsing bugs."""
        # Test grouping with duration units
        expr = "(filesize>1MB & duration<10m) || uploader='BBC'"
        self._test(
            expr,
            {"filesize": 2000000, "duration": 300},
            expected_result=True,
            test_name="complex_duration_filesize_match",
            skip_ytdlp=True,
        )
        self._test(
            expr,
            {"uploader": "BBC"},
            expected_result=True,
            test_name="complex_duration_uploader_match",
            skip_ytdlp=True,
        )
        self._test(
            expr,
            {"filesize": 500000, "duration": 300, "uploader": "CNN"},
            expected_result=False,
            test_name="complex_duration_no_match",
            skip_ytdlp=True,
        )

        # Test OR with different duration units
        expr = "duration<2m || duration>1h"
        self._test(expr, {"duration": 60}, expected_result=True, test_name="complex_or_duration_short", skip_ytdlp=True)
        self._test(
            expr, {"duration": 4000}, expected_result=True, test_name="complex_or_duration_long", skip_ytdlp=True
        )
        self._test(
            expr, {"duration": 1800}, expected_result=False, test_name="complex_or_duration_middle", skip_ytdlp=True
        )

        # Test complex expression with multiple duration conditions
        expr = "(duration>30s & duration<5m) || (duration>1h & uploader*='BBC')"
        self._test(
            expr,
            {"duration": 120},
            expected_result=True,
            test_name="complex_multi_duration_short_range",
            skip_ytdlp=True,
        )
        self._test(
            expr,
            {"duration": 4000, "uploader": "BBC News"},
            expected_result=True,
            test_name="complex_multi_duration_long_bbc",
            skip_ytdlp=True,
        )
        self._test(
            expr,
            {"duration": 4000, "uploader": "CNN"},
            expected_result=False,
            test_name="complex_multi_duration_long_cnn",
            skip_ytdlp=True,
        )
        self._test(
            expr,
            {"duration": 1800},
            expected_result=False,
            test_name="complex_multi_duration_middle_range",
            skip_ytdlp=True,
        )

    def test_string_operators(self):
        d: dict[str, str] = {"uploader": "BBC News Channel"}

        # Test all string operators with both implementations
        self._test("uploader*='News'", d, expected_result=True, test_name="string_contains")
        self._test("uploader^='BBC'", d, expected_result=True, test_name="string_startswith")
        self._test("uploader$='Channel'", d, expected_result=True, test_name="string_endswith")
        self._test("uploader~='News\\s+Channel'", d, expected_result=True, test_name="string_regex")

        # Test negative cases
        self._test("uploader*='CNN'", d, expected_result=False, test_name="string_contains_negative")
        self._test("uploader^='CNN'", d, expected_result=False, test_name="string_startswith_negative")
        self._test("uploader$='BBC'", d, expected_result=False, test_name="string_endswith_negative")

    def test_spaces_around_operators(self):
        """Test that spaces around operators are handled correctly."""
        d: dict[str, str] = {"channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w", "uploader": "BBC"}

        # Test with spaces around equals
        self._test("channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'", d, expected_result=True, test_name="spaced_equals_match")
        self._test("channel_id = 'different-id'", d, expected_result=False, test_name="spaced_equals_non_match")

        # Test with spaces in complex expressions
        self._test(
            "channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w' & uploader = 'BBC'",
            d,
            expected_result=True,
            test_name="complex_spaced_expression",
        )
        self._test(
            "channel_id = 'different-id' & uploader = 'BBC'",
            d,
            expected_result=False,
            test_name="complex_spaced_non_match",
        )

        # Test various operators with spaces
        d_numeric: dict[str, int] = {"filesize": 2000000, "duration": 200}
        self._test("filesize > 1000000", d_numeric, expected_result=True, test_name="spaced_greater_than")
        self._test("filesize >= 2000000", d_numeric, expected_result=True, test_name="spaced_greater_equal")
        self._test("duration < 300", d_numeric, expected_result=True, test_name="spaced_less_than")
        self._test("duration <= 200", d_numeric, expected_result=True, test_name="spaced_less_equal")

    def test_original_bug_reproduction(self):
        """Test the exact case from the original bug report."""
        # Exact data from the original bug report
        test_data: dict[str, Any] = {
            "age_limit": 0,
            "comment_count": 6,
            "channel_id": "UC-7oMv6E4Uz2tF51w5Sj49w",
            "uploader_url": "https://www.youtube.com/@PlayFramePlus",
        }

        # This filter should return FALSE because:
        # 1. channel_id doesn't match (UC-7oMv6E4Uz2tF51w5Sj49w vs UCfmrcEdes7yDtEISGPM1T-A)
        # 2. availability key doesn't exist in the data
        filter_expr = "channel_id = 'UCfmrcEdes7yDtEISGPM1T-A' & availability = subscriber_only"
        self._test(filter_expr, test_data, expected_result=False, test_name="original_bug_full")

        # Individual parts should also be false
        self._test(
            "channel_id = 'UCfmrcEdes7yDtEISGPM1T-A'",
            test_data,
            expected_result=False,
            test_name="original_bug_wrong_channel",
        )
        self._test(
            "availability = subscriber_only", test_data, expected_result=False, test_name="original_bug_missing_key"
        )

        # But the correct channel_id should match
        self._test(
            "channel_id = 'UC-7oMv6E4Uz2tF51w5Sj49w'",
            test_data,
            expected_result=True,
            test_name="original_bug_correct_channel",
        )

    def test_or_operator_precedence(self):
        """Test operator precedence and grouping with OR statements."""
        # Test data for the examples
        test_data: dict[str, int] = {
            "age_limit": 0,
            "fps": 120,
            "like_count": 81,
        }

        # Case 1: (age_limit=0 & fps=120) || like_count=81
        # This should evaluate as: (True & True) || True = True || True = True
        expr1 = "(age_limit=0 & fps=120) || like_count=81"
        self._test(expr1, test_data, expected_result=True, test_name="or_precedence_case1")

        # Case 2: age_limit=0 & fps=120 || like_count=81
        # This evaluates left-to-right as: (age_limit=0 & fps=120) || like_count=81
        # = (True & True) || True = True || True = True
        expr2 = "age_limit=0 & fps=120 || like_count=81"
        self._test(expr2, test_data, expected_result=True, test_name="or_precedence_case2")

        # Test with data that shows left-to-right evaluation
        test_data_partial: dict[str, int] = {
            "age_limit": 0,
            "fps": 60,  # Changed from 120 to make first AND false
            "like_count": 81,
        }

        # Case 1 with partial data: (age_limit=0 & fps=120) || like_count=81
        # This should be: (True & False) || True = False || True = True
        self._test(expr1, test_data_partial, expected_result=True, test_name="or_precedence_case1_partial")

        # Case 2 with partial data: age_limit=0 & fps=120 || like_count=81
        # This evaluates as: (age_limit=0 & fps=120) || like_count=81 = (True & False) || True = False || True = True
        self._test(expr2, test_data_partial, expected_result=True, test_name="or_precedence_case2_partial")

        # Test case where the difference becomes clear
        test_data_edge: dict[str, int] = {
            "age_limit": 1,  # Changed from 0 to make age_limit=0 false
            "fps": 60,  # Changed from 120 to make fps=120 false
            "like_count": 81,
        }

        # Case 1 with edge data: (age_limit=0 & fps=120) || like_count=81
        # This should be: (False & False) || True = False || True = True
        self._test(expr1, test_data_edge, expected_result=True, test_name="or_precedence_case1_edge")

        # Case 2 with edge data: age_limit=0 & fps=120 || like_count=81
        # This evaluates as: (age_limit=0 & fps=120) || like_count=81 = (False & False) || True = False || True = True
        self._test(expr2, test_data_edge, expected_result=True, test_name="or_precedence_case2_edge")

    def test_complex_or_precedence_scenarios(self):
        """Test more complex OR precedence scenarios."""
        # Test case where only the OR part is true
        test_data_or_only: dict[str, int] = {
            "age_limit": 1,  # False
            "fps": 60,  # False (not 120)
            "like_count": 81,  # True
        }

        # Expression: a & b || c
        # Evaluates left-to-right as: (a & b) || c = (False & False) || True = False || True = True
        expr = "age_limit=0 & fps=120 || like_count=81"
        self._test(expr, test_data_or_only, expected_result=True, test_name="complex_or_only_or_true")

        # Test case where only the AND part is true
        test_data_and_only: dict[str, int] = {
            "age_limit": 0,  # True
            "fps": 120,  # True
            "like_count": 50,  # False (not 81)
        }

        # Expression: a & b || c
        # Evaluates as: (a & b) || c = (True & True) || False = True || False = True
        self._test(expr, test_data_and_only, expected_result=True, test_name="complex_or_only_and_true")

        # Test case where everything is false except the OR part
        test_data_only_or: dict[str, int] = {
            "age_limit": 1,  # False
            "fps": 60,  # False
            "like_count": 50,  # False
            "view_count": 1000,  # True
        }

        # Test chained OR with AND: a & b || c || d
        # Evaluates left-to-right as: ((a & b) || c) || d
        expr_chain = "age_limit=0 & fps=120 || like_count=81 || view_count=1000"
        self._test(expr_chain, test_data_only_or, expected_result=True, test_name="complex_or_chained")

    def test_comprehensive_comparison(self):
        """
        Comprehensive test to ensure our implementation and yt-dlp's always agree
        on a variety of test cases.
        """
        test_cases = [
            # Simple cases - use numeric values to avoid yt-dlp unit parsing inconsistencies
            ("filesize>1000000", {"filesize": 2000000}, True),  # 1MB = 1000000 bytes
            ("filesize>1000000", {"filesize": 500000}, False),
            ("duration<600", {"duration": 200}, True),  # 10min = 600 seconds
            ("duration<600", {"duration": 800}, False),
            # String operations
            ("uploader*='BBC'", {"uploader": "BBC News"}, True),
            ("uploader*='BBC'", {"uploader": "CNN News"}, False),
            ("title^='How'", {"title": "How to code"}, True),
            ("title^='How'", {"title": "Learn how"}, False),
            # AND operations - use numeric values
            ("filesize>1000000 & duration<600", {"filesize": 2000000, "duration": 200}, True),
            ("filesize>1000000 & duration<600", {"filesize": 500000, "duration": 200}, False),
            ("filesize>1000000 & duration<600", {"filesize": 2000000, "duration": 800}, False),
            # Unary operations
            ("duration", {"duration": 100}, True),
            ("duration", {}, False),
            ("!duration", {}, True),
            ("!duration", {"duration": 100}, False),
            # Complex expressions with parentheses and OR - use numeric values
            ("(filesize>1000000 & duration<600) || uploader*='BBC'", {"filesize": 2000000, "duration": 200}, True),
            ("(filesize>1000000 & duration<600) || uploader*='BBC'", {"uploader": "BBC News"}, True),
            ("(filesize>1000000 & duration<600) || uploader*='BBC'", {"filesize": 500000, "uploader": "CNN"}, False),
            # Edge cases with missing fields
            ("missing_field=test", {"other_field": "value"}, False),
            ("!missing_field", {"other_field": "value"}, True),
        ]

        for expr, test_data, expected in test_cases:
            test_name = f"comprehensive_{expr.replace(' ', '_').replace('>', 'gt').replace('<', 'lt').replace('=', 'eq').replace('&', 'and').replace('||', 'or').replace('(', '').replace(')', '').replace('*', 'contains').replace('^', 'starts').replace('!', 'not')}"
            self._test(expr, test_data, expected_result=expected, test_name=test_name)

    def test_export_and_yt_dlp_compat(self):
        from yt_dlp.utils import match_str

        d: dict[str, str] = {"filesize": 2000000, "duration": 200, "uploader": "BBC"}
        # Use numeric values to avoid yt-dlp unit parsing inconsistencies
        expr = "(filesize>1000000 & duration<600) || uploader='BBC'"

        parser = MiniFilter(expr)

        for part in parser.export():
            assert match_str(part, d), f"Failed to match {part} with {d}"


if __name__ == "__main__":
    unittest.main()
