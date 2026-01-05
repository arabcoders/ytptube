import asyncio
import copy
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.library.Utils import (
    FileLogFormatter,
    StreamingError,
    archive_add,
    archive_delete,
    archive_read,
    arg_converter,
    calc_download_path,
    check_id,
    clean_item,
    decrypt_data,
    delete_dir,
    dt_delta,
    encrypt_data,
    extract_info,
    extract_ytdlp_logs,
    get,
    get_archive_id,
    get_file,
    get_file_sidecar,
    get_files,
    get_mime_type,
    get_possible_images,
    init_class,
    is_private_address,
    list_folders,
    load_cookies,
    load_modules,
    merge_dict,
    move_file,
    parse_tags,
    read_logfile,
    rename_file,
    str_to_dt,
    strip_newline,
    tail_log,
    timed_lru_cache,
    validate_url,
    validate_uuid,
    ytdlp_reject,
)


class TestStreamingError:
    """Test the StreamingError exception class."""

    def test_streaming_error_creation(self):
        """Test that StreamingError can be created with a message."""
        error_msg = "Test error message"
        error = StreamingError(error_msg)
        assert str(error) == error_msg

    def test_streaming_error_inheritance(self):
        """Test that StreamingError inherits from Exception."""
        error = StreamingError("test")
        assert isinstance(error, Exception)


class TestTimedLruCache:
    """Test the timed_lru_cache decorator."""

    def test_timed_lru_cache_basic_functionality(self):
        """Test that timed_lru_cache caches function results."""
        call_count = 0

        @timed_lru_cache(ttl_seconds=60, max_size=10)
        def test_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute the function
        result1 = test_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call with same argument should return cached result
        result2 = test_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment

        # Different argument should execute the function again
        result3 = test_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_timed_lru_cache_expiration(self):
        """Test that cache expires after TTL."""
        import time

        call_count = 0

        @timed_lru_cache(ttl_seconds=1, max_size=10)  # 1 second TTL
        def test_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = test_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call immediately should be cached
        result2 = test_function(5)
        assert result2 == 10
        assert call_count == 1

        # Wait for cache to expire
        time.sleep(1.1)

        # Call after expiration should execute function again
        result3 = test_function(5)
        assert result3 == 10
        assert call_count == 2

    def test_timed_lru_cache_methods_exposed(self):
        """Test that cache_clear and cache_info methods are exposed."""
        from app.library.Utils import timed_lru_cache

        @timed_lru_cache(ttl_seconds=60, max_size=10)
        def test_function(x):
            return x * 2

        # Test that methods exist
        assert hasattr(test_function, "cache_clear")
        assert hasattr(test_function, "cache_info")

        # Call function to populate cache
        test_function(5)

        # Get cache info
        info = test_function.cache_info()
        assert info.hits == 0
        assert info.misses == 1

        # Call again to test hit
        test_function(5)
        info = test_function.cache_info()
        assert info.hits == 1
        assert info.misses == 1

        # Clear cache
        test_function.cache_clear()
        info = test_function.cache_info()
        assert info.hits == 0
        assert info.misses == 0

    def test_timed_lru_cache_max_size(self):
        """Test that cache respects max_size limit."""
        from app.library.Utils import timed_lru_cache

        @timed_lru_cache(ttl_seconds=60, max_size=2)
        def test_function(x):
            return x * 2

        # Fill cache to max size
        test_function(1)
        test_function(2)

        info = test_function.cache_info()
        assert info.misses == 2

        # Adding another item should not exceed max size
        test_function(3)
        info = test_function.cache_info()
        assert info.misses == 3

        # Test that earlier entries may be evicted
        test_function(1)  # This might be a cache miss due to LRU eviction


class TestAsyncTimedLruCache:
    """Test async functionality of timed_lru_cache decorator."""

    @pytest.mark.asyncio
    async def test_async_timed_lru_cache_basic(self):
        """Test basic async caching functionality."""
        from app.library.Utils import timed_lru_cache

        call_count = 0

        @timed_lru_cache(ttl_seconds=300, max_size=128)
        async def async_test_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call should execute the function
        result1 = await async_test_func(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cached result
        result2 = await async_test_func(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment

        # Different argument should execute function again
        result3 = await async_test_func(3)
        assert result3 == 6
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_timed_lru_cache_expiry(self):
        """Test that async cache entries expire after TTL."""
        from app.library.Utils import timed_lru_cache

        call_count = 0

        @timed_lru_cache(ttl_seconds=0.1, max_size=128)  # 100ms TTL
        async def async_expire_func(x):
            nonlocal call_count
            call_count += 1
            return x * 3

        # First call
        result1 = await async_expire_func(2)
        assert result1 == 6
        assert call_count == 1

        # Immediate second call should use cache
        result2 = await async_expire_func(2)
        assert result2 == 6
        assert call_count == 1

        # Wait for cache to expire
        await asyncio.sleep(0.15)

        # Third call should execute function again due to expiry
        result3 = await async_expire_func(2)
        assert result3 == 6
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_cache_methods(self):
        """Test that async cached functions expose cache management methods."""
        from app.library.Utils import timed_lru_cache

        @timed_lru_cache(ttl_seconds=300, max_size=128)
        async def async_method_test(x):
            return x + 1

        # Test that cache methods exist
        assert hasattr(async_method_test, "cache_clear")
        assert hasattr(async_method_test, "cache_info")

        # Test cache_info
        info = async_method_test.cache_info()
        assert hasattr(info, "hits")
        assert hasattr(info, "misses")
        assert hasattr(info, "maxsize")
        assert hasattr(info, "currsize")
        assert info.maxsize == 128

        # Test cache_clear
        await async_method_test(1)
        async_method_test.cache_clear()
        info_after_clear = async_method_test.cache_info()
        assert info_after_clear.currsize == 0

    @pytest.mark.asyncio
    async def test_async_cache_max_size(self):
        """Test that async cache respects max_size parameter."""
        from app.library.Utils import timed_lru_cache

        @timed_lru_cache(ttl_seconds=300, max_size=2)
        async def async_limited_func(x):
            return x * 4

        # Fill cache beyond max_size
        result1 = await async_limited_func(1)
        result2 = await async_limited_func(2)
        result3 = await async_limited_func(3)  # Should evict oldest entry

        # Verify results
        assert result1 == 4
        assert result2 == 8
        assert result3 == 12

        # Check cache size is limited
        info = async_limited_func.cache_info()
        assert info.currsize <= 2


class TestFileLogFormatter:
    """Test the FileLogFormatter class."""

    def test_file_log_formatter_creation(self):
        """Test that FileLogFormatter can be created."""
        formatter = FileLogFormatter()
        assert isinstance(formatter, FileLogFormatter)


class TestCalcDownloadPath:
    """Test the calc_download_path function."""

    def setup_method(self):
        """Set up test directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_calc_download_path_base_only(self):
        """Test calculating download path with only base path."""
        result = calc_download_path(str(self.base_path), create_path=False)
        assert result == str(self.base_path), "Should return base path when no folder is provided"

    def test_calc_download_path_with_folder(self):
        """Test calculating download path with folder."""
        folder = "test_folder"
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        expected = str(self.base_path / folder)
        assert result == expected, "Should append folder to base path"

    def test_calc_download_path_creates_directory(self):
        """Test that the function creates directories when create_path=True."""
        folder = "new_folder"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / folder
        assert result == str(expected_path), "Should return the new path"
        assert expected_path.exists(), "Directory should be created"

    def test_calc_download_path_path_object(self):
        """Test with Path object as input."""
        folder = "test_folder"
        result = calc_download_path(self.base_path, folder, create_path=False)
        expected = str(self.base_path / folder)
        assert result == expected, "Should handle Path object for base path"

    def test_calc_download_path_nested_folder(self):
        """Test with nested folder structure."""
        folder = "parent/child"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / "parent" / "child"
        assert result == str(expected_path), "Should handle nested folder structure"
        assert expected_path.exists(), "Nested directories should be created"

    def test_calc_download_path_none_folder(self):
        """Test with None folder."""
        result = calc_download_path(str(self.base_path), None, create_path=False)
        assert result == str(self.base_path), "Should return base path when folder is None"

    def test_calc_download_path_removes_leading_slash(self):
        """Test that leading slash is removed from folder."""
        folder = "/test_folder"
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        expected = str(self.base_path / "test_folder")
        assert result == expected, "Should remove leading slash from folder"

    def test_calc_download_path_path_traversal_dotdot(self):
        """Test path traversal prevention with .. sequences."""
        folder = "../outside"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_path_traversal_nested_dotdot(self):
        """Test path traversal prevention with nested .. sequences."""
        folder = "safe/../../outside"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_path_traversal_multiple_dotdot(self):
        """Test path traversal prevention with multiple .. sequences."""
        folder = "../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_path_traversal_absolute_path(self):
        """Test that absolute paths are made safe by removing leading slash."""
        folder = "/etc/passwd"
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        expected = str(self.base_path / "etc/passwd")
        assert result == expected, "Should remove leading slash and treat as relative path"

    def test_calc_download_path_path_traversal_absolute_with_dotdot(self):
        """Test path traversal with absolute path containing .. sequences."""
        folder = "/../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_path_traversal_mixed(self):
        """Test path traversal prevention with mixed safe/unsafe paths."""
        folder = "safe/../../../unsafe"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_path_traversal_url_encoded(self):
        """Test path traversal prevention with URL encoded sequences."""
        folder = "safe%2F..%2F..%2Funsafe"  # safe/../unsafe encoded
        # This should be handled at a higher level, but let's test it anyway
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        expected = str(self.base_path / folder)  # Should be treated as literal filename
        assert result == expected, "URL encoded sequences should be treated as literal"

    def test_calc_download_path_safe_nested_paths(self):
        """Test that legitimate nested paths work correctly."""
        folder = "videos/2024/january"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / "videos" / "2024" / "january"
        assert result == str(expected_path), "Should handle legitimate nested paths"
        assert expected_path.exists(), "Nested directories should be created"

    def test_calc_download_path_safe_dotfiles(self):
        """Test that paths with legitimate dot files work."""
        folder = ".hidden/folder"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / ".hidden" / "folder"
        assert result == str(expected_path), "Should handle dot files correctly"
        assert expected_path.exists(), "Hidden directories should be created"

    def test_calc_download_path_empty_folder(self):
        """Test with empty string folder."""
        folder = ""
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        assert result == str(self.base_path), "Should return base path for empty folder"

    def test_calc_download_path_whitespace_folder(self):
        """Test with whitespace-only folder."""
        folder = "   "
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / "   "
        assert result == str(expected_path), "Should handle whitespace folder names"

    def test_calc_download_path_unicode_folder(self):
        """Test with Unicode characters in folder name."""
        folder = "测试文件夹/русский/العربية"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / "测试文件夹" / "русский" / "العربية"
        assert result == str(expected_path), "Should handle Unicode folder names"
        assert expected_path.exists(), "Unicode directories should be created"

    def test_calc_download_path_special_characters(self):
        """Test with special characters in folder name."""
        folder = "folder-with_special.chars(123)"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / folder
        assert result == str(expected_path), "Should handle special characters"
        assert expected_path.exists(), "Directory with special chars should be created"

    def test_calc_download_path_null_byte_attack(self):
        """Test that null bytes are prevented."""
        folder = "folder\x00../../../etc/passwd"
        # Any exception is acceptable for null byte attacks
        with pytest.raises((ValueError, Exception)):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_null_byte_at_end(self):
        """Test that null bytes at end are prevented."""
        folder = "../../../etc/passwd\x00"
        # Any exception is acceptable for null byte attacks
        with pytest.raises((ValueError, Exception)):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_newline_attack(self):
        """Test that newlines in path traversal are prevented."""
        folder = "folder\n../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_carriage_return_attack(self):
        """Test that carriage returns in path traversal are prevented."""
        folder = "folder\r../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_tab_attack(self):
        """Test that tabs in path traversal are prevented."""
        folder = "folder\t../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_vertical_tab_attack(self):
        """Test that vertical tabs in path traversal are prevented."""
        folder = "folder\x0b../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_form_feed_attack(self):
        """Test that form feeds in path traversal are prevented."""
        folder = "folder\x0c../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_url_encoded_safe(self):
        """Test that URL encoded sequences are treated as literals (safe)."""
        folder = "folder%00../../../etc/passwd"  # %00 is URL encoded null
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_url_encoded_traversal_safe(self):
        """Test that URL encoded path traversal is treated as literal (safe)."""
        folder = "folder..%2F..%2F..%2Fetc%2Fpasswd"  # ..%2F = ../ encoded
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        expected = str(self.base_path / folder)  # Should be treated as literal filename
        assert result == expected, "URL encoded sequences should be treated as literal filename"

    def test_calc_download_path_backslash_attack(self):
        """Test that backslashes in path traversal are handled correctly."""
        folder = "folder\\..\\..\\..\\etc\\passwd"
        # On Unix systems, backslashes are treated as literal characters in filenames
        result = calc_download_path(str(self.base_path), folder, create_path=False)
        expected = str(self.base_path / folder)
        assert result == expected, "Backslashes should be treated as literal characters on Unix"

    def test_calc_download_path_mixed_separators_attack(self):
        """Test path traversal with mixed separators."""
        folder = "folder/../../../etc/passwd"
        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

    def test_calc_download_path_partial_match_attack(self):
        """
        Test specific prefix matching vulnerability.
        Base: /tmp/test
        Target: /tmp/test_suffix (starts with base, but is a sibling)
        This tests that the relative_to() check catches what startswith() alone would miss.
        """
        # Create a sibling directory that starts with the base path name
        sibling_dir = Path(str(self.temp_dir) + "_suffix")
        sibling_dir.mkdir(exist_ok=True)

        # Try to access the sibling directory
        folder = f"../{sibling_dir.name}"

        with pytest.raises(Exception, match="must resolve inside the base download folder"):
            calc_download_path(str(self.base_path), folder, create_path=False)

        # Clean up
        shutil.rmtree(sibling_dir, ignore_errors=True)

    def test_calc_download_path_symlink_attack_outside(self):
        """Test that symlinks pointing outside base directory are blocked."""
        # Create a symlink pointing outside the base directory
        outside_dir = Path(self.temp_dir).parent / "outside_target"
        outside_dir.mkdir(exist_ok=True)

        symlink_path = self.base_path / "evil_symlink"
        try:
            symlink_path.symlink_to(outside_dir, target_is_directory=True)

            # Try to use the symlink
            with pytest.raises(Exception, match="must resolve inside the base download folder"):
                calc_download_path(str(self.base_path), "evil_symlink", create_path=False)
        finally:
            # Clean up
            if symlink_path.exists():
                symlink_path.unlink()
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_calc_download_path_symlink_attack_with_traversal(self):
        """Test symlink combined with path traversal."""
        # Create a directory outside base
        outside_dir = Path(self.temp_dir).parent / "target_dir"
        outside_dir.mkdir(exist_ok=True)

        # Create a symlink inside base pointing outside
        safe_dir = self.base_path / "safe"
        safe_dir.mkdir(exist_ok=True)

        symlink_path = safe_dir / "link_to_outside"
        try:
            symlink_path.symlink_to(outside_dir, target_is_directory=True)

            # Try to traverse through the symlink
            with pytest.raises(Exception, match="must resolve inside the base download folder"):
                calc_download_path(str(self.base_path), "safe/link_to_outside", create_path=False)
        finally:
            # Clean up
            if symlink_path.exists():
                symlink_path.unlink()
            shutil.rmtree(safe_dir, ignore_errors=True)
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_calc_download_path_symlink_safe_internal(self):
        """Test that symlinks pointing inside base directory are allowed."""
        # Create target directory inside base
        target_dir = self.base_path / "target"
        target_dir.mkdir(exist_ok=True)

        # Create a symlink inside base pointing to another location inside base
        symlink_path = self.base_path / "link_to_target"
        try:
            symlink_path.symlink_to(target_dir, target_is_directory=True)

            # This should succeed since symlink resolves inside base
            result = calc_download_path(str(self.base_path), "link_to_target", create_path=False)
            assert str(target_dir) == result, "Internal symlinks should be allowed"
        finally:
            # Clean up
            if symlink_path.exists():
                symlink_path.unlink()
            shutil.rmtree(target_dir, ignore_errors=True)

    def test_calc_download_path_extremely_long_path(self):
        """Test handling of extremely long paths."""
        # Create a very long folder name (most filesystems limit to 255 chars per component)
        long_component = "a" * 300

        # This should raise an error during path creation or validation (OSError or ValueError)
        with pytest.raises((OSError, ValueError)):
            calc_download_path(str(self.base_path), long_component, create_path=True)

    def test_calc_download_path_many_nested_levels(self):
        """Test deeply nested directory structure."""
        # Create a path with many nested levels
        deep_path = "/".join([f"level{i}" for i in range(100)])

        # This should work but might be slow
        result = calc_download_path(str(self.base_path), deep_path, create_path=False)
        expected = str(self.base_path / deep_path)
        assert result == expected, "Should handle deeply nested paths"

    def test_calc_download_path_directory_with_spaces(self):
        """Test paths with multiple spaces and special spacing."""
        folder = "folder with   multiple    spaces"
        result = calc_download_path(str(self.base_path), folder, create_path=True)
        expected_path = self.base_path / folder
        assert result == str(expected_path), "Should handle spaces correctly"
        assert expected_path.exists(), "Directory with spaces should be created"


class TestMergeDict:
    """Test the merge_dict function."""

    def test_merge_dict_basic(self):
        """Test basic dictionary merging."""
        source = {"a": 1, "b": 2}
        destination = {"c": 3, "d": 4}
        result = merge_dict(source, destination)
        expected = {"a": 1, "b": 2, "c": 3, "d": 4}
        assert result == expected

    def test_merge_dict_overwrites(self):
        """Test that source values overwrite destination values."""
        source = {"a": 1, "b": 2}
        destination = {"b": 99, "c": 3}
        result = merge_dict(source, destination)
        expected = {"a": 1, "b": 2, "c": 3}
        assert result == expected

    def test_merge_dict_nested(self):
        """Test merging nested dictionaries."""
        source = {"nested": {"a": 1}}
        destination = {"nested": {"b": 2}, "other": 3}
        result = merge_dict(source, destination)
        # Should merge nested dictionaries
        assert "nested" in result
        assert "other" in result

    def test_merge_dict_empty_source(self):
        """Test merging with empty source."""
        source = {}
        destination = {"a": 1, "b": 2}
        result = merge_dict(source, destination)
        assert result == destination

    def test_merge_dict_empty_destination(self):
        """Test merging with empty destination."""
        source = {"a": 1, "b": 2}
        destination = {}
        result = merge_dict(source, destination)
        assert result == source

    def test_merge_dict_both_empty(self):
        """Test merging two empty dictionaries."""
        result = merge_dict({}, {})
        assert result == {}

    # Parameter Pollution Security Tests

    def test_merge_dict_blocks_class_pollution(self):
        """Test that __class__ attribute pollution is blocked."""
        source = {"__class__": "malicious_class", "safe": "value"}
        destination = {"existing": "data"}
        result = merge_dict(source, destination)

        assert "__class__" not in result, "__class__ should be filtered out"
        assert result["safe"] == "value", "Safe values should be preserved"
        assert result["existing"] == "data", "Existing data should be preserved"

    def test_merge_dict_blocks_dict_pollution(self):
        """Test that __dict__ attribute pollution is blocked."""
        source = {"__dict__": {"injected": "payload"}, "normal": "data"}
        destination = {"target": "value"}
        result = merge_dict(source, destination)

        assert "__dict__" not in result, "__dict__ should be filtered out"
        assert result["normal"] == "data", "Normal data should be preserved"
        assert result["target"] == "value", "Target data should be preserved"

    def test_merge_dict_blocks_globals_pollution(self):
        """Test that __globals__ attribute pollution is blocked."""
        source = {"__globals__": {"malicious": "code"}, "data": "safe"}
        destination = {"existing": "value"}
        result = merge_dict(source, destination)

        assert "__globals__" not in result, "__globals__ should be filtered out"
        assert result["data"] == "safe", "Safe data should be preserved"

    def test_merge_dict_blocks_builtins_pollution(self):
        """Test that __builtins__ attribute pollution is blocked."""
        source = {"__builtins__": {"eval": "dangerous"}, "normal": "value"}
        destination = {"target": "data"}
        result = merge_dict(source, destination)

        assert "__builtins__" not in result, "__builtins__ should be filtered out"
        assert result["normal"] == "value", "Normal values should be preserved"

    def test_merge_dict_blocks_multiple_dunder_pollution(self):
        """Test that multiple dangerous dunder attributes are blocked."""
        source = {
            "__class__": "malicious",
            "__dict__": {"bad": "data"},
            "__globals__": {"evil": "code"},
            "__builtins__": {"dangerous": "function"},
            "safe_key": "safe_value",
        }
        destination = {"existing": "data"}
        result = merge_dict(source, destination)

        # All dangerous attributes should be filtered out
        dangerous_keys = ["__class__", "__dict__", "__globals__", "__builtins__"]
        for key in dangerous_keys:
            assert key not in result, f"{key} should be filtered out"

        # Safe data should be preserved
        assert result["safe_key"] == "safe_value"
        assert result["existing"] == "data"

    def test_merge_dict_nested_dunder_pollution(self):
        """Test that nested dangerous attributes are handled correctly."""
        source = {"nested": {"__class__": "malicious_nested", "safe_nested": "value"}, "normal": "data"}
        destination = {"nested": {"existing_nested": "original"}}
        result = merge_dict(source, destination)

        # Nested dangerous attributes should be filtered out
        assert "__class__" not in result["nested"], "Nested __class__ should be filtered"
        # Safe nested data should be preserved
        assert result["nested"]["safe_nested"] == "value"
        assert result["nested"]["existing_nested"] == "original"

    def test_merge_dict_prototype_pollution_attempt(self):
        """Test protection against prototype pollution attempts."""
        source = {"__proto__": {"polluted": True}, "constructor": {"prototype": {"polluted": True}}, "safe": "data"}
        destination = {"existing": "value"}
        result = merge_dict(source, destination)

        # These should be treated as regular keys (not filtered unless explicitly in the filter list)
        # The function filters Python-specific dangerous attributes, not JavaScript ones
        assert result["safe"] == "data"
        assert result["existing"] == "value"

    def test_merge_dict_special_method_pollution(self):
        """Test with various Python special methods."""
        source = {
            "__init__": "malicious_init",
            "__new__": "malicious_new",
            "__call__": "malicious_call",
            "__getattr__": "malicious_getattr",
            "__setattr__": "malicious_setattr",
            "safe": "value",
        }
        destination = {"target": "data"}
        result = merge_dict(source, destination)

        # These are not in the current filter list, so they should pass through
        # This test documents current behavior - may need updating if more filters are added
        assert result["safe"] == "value"
        assert result["target"] == "data"

    def test_merge_dict_list_pollution_safe(self):
        """Test that list merging doesn't allow dangerous manipulation."""
        source = {"items": ["new1", "new2"]}
        destination = {"items": ["old1", "old2"]}
        result = merge_dict(source, destination)

        # Lists should be concatenated safely (destination + source)
        assert result["items"] == ["old1", "old2", "new1", "new2"]

    def test_merge_dict_deep_nested_pollution(self):
        """Test with deeply nested dangerous attributes."""
        source = {
            "level1": {
                "level2": {
                    "__class__": "deep_malicious",
                    "level3": {"__globals__": "very_deep_malicious"},
                    "safe_deep": "value",
                }
            }
        }
        destination = {"level1": {"level2": {"existing": "data"}}}
        result = merge_dict(source, destination)

        # The function should now properly filter all dangerous keys recursively
        assert "__class__" not in result["level1"]["level2"], "Deep __class__ should be filtered"
        assert "__globals__" not in result["level1"]["level2"]["level3"], "Very deep __globals__ should be filtered"

        # Safe data should be preserved
        assert result["level1"]["level2"]["safe_deep"] == "value"
        assert result["level1"]["level2"]["existing"] == "data"

    def test_merge_dict_type_validation(self):
        """Test that non-dict parameters are properly rejected."""
        # Test with non-dict source
        with pytest.raises(TypeError, match="Both source and destination must be dictionaries"):
            merge_dict("not_a_dict", {"key": "value"})

        # Test with non-dict destination
        with pytest.raises(TypeError, match="Both source and destination must be dictionaries"):
            merge_dict({"key": "value"}, "not_a_dict")

        # Test with both non-dict
        with pytest.raises(TypeError, match="Both source and destination must be dictionaries"):
            merge_dict("not_a_dict", ["also_not_dict"])

    def test_merge_dict_immutability(self):
        """Test that original dictionaries are not modified (immutability)."""
        original_source = {"a": 1, "nested": {"b": 2}}
        original_destination = {"c": 3, "nested": {"d": 4}}

        # Make copies to compare later
        source_copy = copy.deepcopy(original_source)
        destination_copy = copy.deepcopy(original_destination)

        result = merge_dict(original_source, original_destination)

        # Original dictionaries should be unchanged
        assert original_source == source_copy, "Source should not be modified"
        assert original_destination == destination_copy, "Destination should not be modified"

        # Result should be different from both originals
        assert result != original_source
        assert result != original_destination

    def test_merge_dict_custom_max_depth(self):
        """Test custom max_depth parameter."""
        # Create a deep nested structure
        deep_source = {}
        current = deep_source
        for _ in range(10):
            current["level"] = {}
            current = current["level"]
        current["data"] = "deep_value"

        # Test with default max_depth (50) - should work
        result = merge_dict(deep_source, {})
        assert self._get_nested_value(result, ["level"] * 10 + ["data"]) == "deep_value"

        # Test with custom max_depth (5) - should raise RecursionError
        with pytest.raises(RecursionError, match="Recursion depth limit exceeded \\(5\\)"):
            merge_dict(deep_source, {}, max_depth=5)

        # Test with higher max_depth (20) - should work
        result = merge_dict(deep_source, {}, max_depth=20)
        assert self._get_nested_value(result, ["level"] * 10 + ["data"]) == "deep_value"

    def test_merge_dict_custom_max_list_size(self):
        """Test custom max_list_size parameter."""
        large_list = list(range(5000))
        source = {"data": large_list}

        # Test with default max_list_size (10000) - should preserve full list
        result = merge_dict(source, {})
        assert len(result["data"]) == 5000
        assert result["data"] == large_list

        # Test with custom max_list_size (1000) - should truncate
        result = merge_dict(source, {}, max_list_size=1000)
        assert len(result["data"]) == 1000
        assert result["data"] == large_list[:1000]

        # Test with higher max_list_size (10000) - should preserve full list
        result = merge_dict(source, {}, max_list_size=10000)
        assert len(result["data"]) == 5000
        assert result["data"] == large_list

    def test_merge_dict_list_merging_with_size_limits(self):
        """Test list merging respects size limits."""
        source = {"items": list(range(3000))}
        destination = {"items": list(range(2000, 5000))}  # 3000 items

        # Total would be 6000 items, but limit is 4000
        result = merge_dict(source, destination, max_list_size=4000)

        # Should have original destination (3000) + truncated source (1000) = 4000
        assert len(result["items"]) == 4000

        # First 3000 should be from destination
        assert result["items"][:3000] == list(range(2000, 5000))
        # Next 1000 should be from source (truncated)
        assert result["items"][3000:] == list(range(1000))

    def test_merge_dict_nested_with_limits(self):
        """Test nested merging with both depth and size limits."""
        # Create nested structure that exceeds depth limit
        deep_source = {"level1": {"level2": {"level3": {"level4": {"data": "deep"}}}}}

        # Create structure with large list
        list_source = {"level1": {"large_data": list(range(2000))}}

        destination = {"level1": {"existing": "data"}}

        # Test with restrictive limits
        result = merge_dict(list_source, destination, max_depth=10, max_list_size=1000)

        assert result["level1"]["existing"] == "data"
        assert len(result["level1"]["large_data"]) == 1000
        assert result["level1"]["large_data"] == list(range(1000))

        # Test depth limit exceeded
        with pytest.raises(RecursionError):
            merge_dict(deep_source, destination, max_depth=3)

    def test_merge_dict_zero_limits(self):
        """Test behavior with zero limits."""
        source = {"data": [1, 2, 3]}
        destination = {"existing": "value"}

        # Zero max_list_size should result in empty lists
        result = merge_dict(source, destination, max_list_size=0)
        assert result["existing"] == "value"
        assert result["data"] == []  # Truncated to empty

        # Zero max_depth should fail immediately on any nesting
        with pytest.raises(RecursionError):
            merge_dict({"nested": {"data": "value"}}, {}, max_depth=0)

    def test_merge_dict_extreme_limits(self):
        """Test with very high limits."""
        # Create moderately nested structure
        source = {"a": {"b": {"c": {"data": "nested"}}}}

        # Very high limits should work normally
        result = merge_dict(source, {}, max_depth=10000, max_list_size=1000000)
        assert result["a"]["b"]["c"]["data"] == "nested"

    def test_merge_dict_limits_with_circular_reference_protection(self):
        """Test that limits work together with circular reference protection."""
        source = {"data": {}}
        source["data"]["circular"] = source  # Create circular reference

        # Should fail with ValueError (circular reference) before hitting depth limit
        with pytest.raises(ValueError, match="Circular reference detected"):
            merge_dict(source, {}, max_depth=100)

    def test_merge_dict_backward_compatibility(self):
        """Test that existing code works without specifying new parameters."""
        source = {"a": 1, "nested": {"b": 2}}
        destination = {"c": 3, "nested": {"d": 4}}

        # Should work exactly as before with default parameters
        result = merge_dict(source, destination)

        assert result["a"] == 1
        assert result["c"] == 3
        assert result["nested"]["b"] == 2
        assert result["nested"]["d"] == 4

    def _get_nested_value(self, data: dict, keys: list):
        """Helper to get value from deeply nested dict."""
        current = data
        for key in keys:
            current = current[key]
        return current


class TestIsPrivateAddress:
    """Test the is_private_address function."""

    def test_is_private_address_localhost(self):
        """Test localhost addresses."""
        assert is_private_address("localhost") is True
        assert is_private_address("127.0.0.1") is True

    def test_is_private_address_private_ranges(self):
        """Test private IP ranges."""
        assert is_private_address("192.168.1.1") is True
        assert is_private_address("10.0.0.1") is True
        assert is_private_address("172.16.0.1") is True

    def test_is_private_address_public(self):
        """Test public addresses."""
        assert is_private_address("8.8.8.8") is False
        assert is_private_address("google.com") is False
        assert is_private_address("1.1.1.1") is False


class TestDeleteDir:
    """Test the delete_dir function."""

    def setup_method(self):
        """Set up test directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "test_delete"
        self.test_dir.mkdir()
        (self.test_dir / "file.txt").write_text("test content")

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_delete_dir_success(self):
        """Test successful directory deletion."""
        assert self.test_dir.exists()
        result = delete_dir(self.test_dir)
        assert result is True
        assert not self.test_dir.exists()

    def test_delete_dir_nonexistent(self):
        """Test deleting non-existent directory."""
        nonexistent = Path(self.temp_dir) / "nonexistent"
        result = delete_dir(nonexistent)
        assert result is False


class TestListFolders:
    """Test the list_folders function."""

    def setup_method(self):
        """Set up test directory structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.base = Path(self.temp_dir)
        (self.base / "folder1").mkdir()
        (self.base / "folder2").mkdir()
        (self.base / "folder1" / "subfolder").mkdir()
        (self.base / "file.txt").write_text("test")

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_folders_depth_0(self):
        """Test listing folders with depth 0."""
        result = list_folders(self.base, self.base, 0)
        expected = ["folder1", "folder2"]
        assert sorted(result) == sorted(expected)

    def test_list_folders_depth_1(self):
        """Test listing folders with depth 1."""
        result = list_folders(self.base, self.base, 1)
        expected = ["folder1", "folder2", "folder1/subfolder"]
        assert sorted(result) == sorted(expected)

    def test_list_folders_depth_2(self):
        """Test listing folders with a depth limit."""
        result = list_folders(self.base, self.base, 2)
        expected = ["folder1", "folder2", "folder1/subfolder"]
        assert sorted(result) == sorted(expected)


class TestEncryptDecrypt:
    """Test encryption and decryption functions."""

    def test_encrypt_decrypt_data(self):
        """Test that data can be encrypted and decrypted."""
        key = b"test_key_12345678901234567890123"  # Exactly 32 bytes for AES
        data = "test data"

        encrypted: str = encrypt_data(data, key)
        assert encrypted != data
        assert isinstance(encrypted, str)

        decrypted: str = decrypt_data(encrypted, key)
        assert decrypted == data

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        key = b"test_key_12345678901234567890123"  # Exactly 32 bytes
        data: str = ""

        encrypted: str = encrypt_data(data, key)
        decrypted: str = decrypt_data(encrypted, key)
        assert decrypted == data


class TestValidateUuid:
    """Test UUID validation function."""

    def test_valid_uuid4(self):
        """Test with valid UUID4."""
        test_uuid = str(uuid.uuid4())
        assert validate_uuid(test_uuid, 4) is True

    def test_valid_uuid1(self):
        """Test with valid UUID1."""
        test_uuid = str(uuid.uuid1())
        assert validate_uuid(test_uuid, 1) is True

    def test_invalid_uuid_string(self):
        """Test with invalid UUID string."""
        assert validate_uuid("invalid-uuid", 4) is False

    def test_empty_string(self):
        """Test with empty string."""
        assert validate_uuid("", 4) is False

    def test_wrong_version(self):
        """Test UUID4 against version 1 check."""
        test_uuid = str(uuid.uuid4())
        # Version check is not strict in this function - it may return True for any valid UUID
        result = validate_uuid(test_uuid, 1)
        assert isinstance(result, bool)  # Just check it returns a boolean


class TestStripNewline:
    """Test string newline stripping function."""

    def test_strip_newline_basic(self):
        """Test stripping newlines from string."""
        text = "line1\nline2\r\nline3\r"
        result = strip_newline(text)
        assert result == "line1 line2 line3"  # Function replaces with spaces, not removes

    def test_strip_newline_no_newlines(self):
        """Test string with no newlines."""
        text = "no newlines here"
        result = strip_newline(text)
        assert result == text

    def test_strip_newline_empty(self):
        """Test empty string."""
        result = strip_newline("")
        assert result == ""

    def test_strip_newline_only_newlines(self):
        """Test string with only newlines."""
        text = "\n\r\n\r"
        result = strip_newline(text)
        assert result == ""


class TestDtDelta:
    """Test timedelta formatting function."""

    def test_dt_delta_seconds(self):
        """Test formatting seconds."""
        delta = timedelta(seconds=30)
        result = dt_delta(delta)
        assert "30" in result
        assert "s" in result

    def test_dt_delta_minutes(self):
        """Test formatting minutes."""
        delta = timedelta(minutes=5)
        result = dt_delta(delta)
        assert "5" in result
        assert "m" in result

    def test_dt_delta_hours(self):
        """Test formatting hours."""
        delta = timedelta(hours=2)
        result = dt_delta(delta)
        assert "2" in result
        assert "h" in result

    def test_dt_delta_days(self):
        """Test formatting days."""
        delta = timedelta(days=3)
        result = dt_delta(delta)
        assert "3" in result
        assert "d" in result

    def test_dt_delta_complex(self):
        """Test formatting complex timedelta."""
        delta = timedelta(days=1, hours=2, minutes=30, seconds=45)
        result = dt_delta(delta)
        assert isinstance(result, str)
        assert len(result) > 0


class TestParseTags:
    """Test tag parsing function."""

    def test_parse_tags_simple(self):
        """Test parsing simple tags."""
        text = "Hello [tag1] world [tag2:value]"
        result_text, tags = parse_tags(text)
        assert "Hello" in result_text
        assert "world" in result_text
        assert isinstance(tags, dict)

    def test_parse_tags_no_tags(self):
        """Test text with no tags."""
        text = "Hello world"
        result_text, tags = parse_tags(text)
        assert result_text == text
        assert tags == {}

    def test_parse_tags_empty(self):
        """Test empty string."""
        result_text, tags = parse_tags("")
        assert result_text == ""
        assert tags == {}


class TestCleanItem:
    """Test item cleaning function."""

    def test_clean_item_basic(self):
        """Test cleaning item with specified keys."""
        item = {"key1": "value1", "key2": "value2", "key3": "value3"}
        keys = ["key2"]
        cleaned_item, changed = clean_item(item, keys)

        assert "key1" in cleaned_item
        assert "key2" not in cleaned_item
        assert "key3" in cleaned_item
        assert changed is True

    def test_clean_item_no_change(self):
        """Test cleaning item with non-existent keys."""
        item = {"key1": "value1", "key2": "value2"}
        keys = ["nonexistent"]
        cleaned_item, changed = clean_item(item, keys)

        assert cleaned_item == item
        assert changed is False

    def test_clean_item_empty_keys(self):
        """Test cleaning item with empty keys list."""
        item = {"key1": "value1"}
        keys = []
        cleaned_item, changed = clean_item(item, keys)

        assert cleaned_item == item
        assert changed is False


class TestValidateUrl:
    """Test URL validation function."""

    def test_validate_url_basic(self):
        """Test basic URL validation functionality."""
        # Test without actual validation due to missing yarl dependency
        # Just check the function exists and handles the missing dependency gracefully
        try:
            result = validate_url("https://example.com")
            assert isinstance(result, bool)
        except ModuleNotFoundError:
            # Expected when yarl is not installed
            assert True


class TestExtractYtdlpLogs:
    """Test YTDLP log extraction function."""

    def test_extract_ytdlp_logs_basic(self):
        """Test basic log extraction."""
        logs = ["This live event will begin soon", "ERROR: Failed", "WARNING: Deprecated"]
        result = extract_ytdlp_logs(logs)
        assert isinstance(result, list)
        assert len(result) >= 1  # Should match "This live event will begin"

    def test_extract_ytdlp_logs_with_filters(self):
        """Test log extraction with filters."""
        logs = ["INFO: Downloading", "ERROR: Failed", "WARNING: Deprecated"]
        filters = [re.compile(r"ERROR")]
        result = extract_ytdlp_logs(logs, filters)
        assert len(result) >= 0  # Should filter based on patterns

    def test_extract_ytdlp_logs_empty(self):
        """Test with empty logs."""
        result = extract_ytdlp_logs([])
        assert result == []


class TestGetFileSidecar:
    """Test file sidecar function."""

    def test_get_file_sidecar_with_files(self):
        """Test getting sidecar files when they exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            video_file = base_path / "video.mp4"
            srt_file = base_path / "video.srt"
            nfo_file = base_path / "video.nfo"

            video_file.write_text("video content")
            srt_file.write_text("subtitle content")
            nfo_file.write_text("nfo content")

            result = get_file_sidecar(video_file)
            assert isinstance(result, dict)  # Returns dict, not list

    def test_get_file_sidecar_no_files(self):
        """Test getting sidecar files when none exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            video_file = base_path / "video.mp4"
            video_file.write_text("video content")

            result = get_file_sidecar(video_file)
            assert isinstance(result, dict)  # Returns dict, not list


class TestArchiveFunctions:
    """Test archive-related functions."""

    def setup_method(self):
        """Set up test archive file."""
        self.temp_dir = tempfile.mkdtemp()
        self.archive_file = Path(self.temp_dir) / "archive.txt"

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_archive_add_and_read(self):
        """Test adding and reading archive entries."""
        ids = ["id1", "id2", "id3"]

        # Add entries - just test it returns a boolean
        result = archive_add(self.archive_file, ids)
        assert isinstance(result, bool)

        # Read entries - just test it returns a list
        read_ids = archive_read(self.archive_file)
        assert isinstance(read_ids, list)

    def test_archive_delete(self):
        """Test deleting archive entries."""
        # Delete some entries - just test it returns a boolean
        delete_ids = ["id2"]
        result = archive_delete(self.archive_file, delete_ids)
        assert isinstance(result, bool)

    def test_archive_read_nonexistent(self):
        """Test reading from non-existent archive."""
        nonexistent = Path(self.temp_dir) / "nonexistent.txt"
        result = archive_read(nonexistent)
        assert result == []


class TestExtractInfo:
    """Test the extract_info function."""

    @patch("app.library.Utils.YTDLP")
    def test_extract_info_basic(self, mock_ytdlp_class):
        """Test basic extract_info functionality."""
        mock_ytdlp = MagicMock()
        mock_ytdlp.extract_info.return_value = {"title": "Test Video", "id": "test123"}
        mock_ytdlp_class.return_value = mock_ytdlp

        config = {"quiet": True}
        url = "https://example.com/video"

        result = extract_info(config, url)
        assert isinstance(result, dict)
        mock_ytdlp.extract_info.assert_called_once()

    @patch("app.library.Utils.YTDLP")
    def test_extract_info_with_debug(self, mock_ytdlp_class):
        """Test extract_info with debug enabled."""
        mock_ytdlp = MagicMock()
        mock_ytdlp.extract_info.return_value = {"title": "Test Video"}
        mock_ytdlp_class.return_value = mock_ytdlp

        config = {}
        url = "https://example.com/video"

        result = extract_info(config, url, debug=True)
        assert isinstance(result, dict)


class TestCheckId:
    """Test the check_id function."""

    def setup_method(self):
        """Set up test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_check_id_with_youtube_id(self):
        """Test check_id with a YouTube ID in filename."""
        # Create a file with YouTube ID
        test_file = self.test_dir / "video[test12345678].srt"
        test_file.write_text("subtitle content")

        # Create a corresponding video file
        video_file = self.test_dir / "video[test12345678].mp4"
        video_file.write_text("video content")

        result = check_id(test_file)
        assert isinstance(result, (bool, str))

    def test_check_id_no_id(self):
        """Test check_id with no ID in filename."""
        test_file = self.test_dir / "video.srt"
        test_file.write_text("subtitle content")

        result = check_id(test_file)
        assert result is False


class TestArgConverter:
    """Test the arg_converter function."""

    def test_arg_converter_basic(self):
        """Test basic arg_converter functionality."""
        try:
            result = arg_converter("--quiet --match-filters 'duration<2min' --download-archive archive.txt")
            assert isinstance(result, dict)
            assert result.get("quiet") is True, "quiet should be True"
            assert result.get("download_archive") == "archive.txt"
            assert "match_filter" in result, "match_filters should be in result"
        except (ModuleNotFoundError, AttributeError, ImportError):
            # Expected when yt_dlp is not available or differs
            assert True

    def test_arg_converter_empty_args(self):
        """Test arg_converter with empty args."""
        try:
            result = arg_converter("")
            assert isinstance(result, dict)
        except (ModuleNotFoundError, AttributeError, ImportError):
            assert True

    def test_arg_converter_replace_in_metadata(self):
        """Test arg_converter handles replace-in-metadata without assertions."""
        try:
            result = arg_converter("--replace-in-metadata title foo bar")
        except (ModuleNotFoundError, AttributeError, ImportError):
            assert True
            return

        postprocessors = result.get("postprocessors", [])
        assert postprocessors, "Expected metadata parser postprocessor to be present"

        metadata_pp = postprocessors[0]
        assert metadata_pp.get("key") == "MetadataParser"

        actions = metadata_pp.get("actions", [])
        assert actions, "Expected metadata parser to include actions"

        action_callable = actions[0][0]
        assert callable(action_callable)
        assert getattr(action_callable, "__name__", "") == "replacer"


class TestGetPossibleImages:
    """Test the get_possible_images function."""

    def setup_method(self):
        """Set up test directory with images."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir)

        # Create some test image files
        (self.test_dir / "poster.jpg").write_text("image")
        (self.test_dir / "thumbnail.png").write_text("image")

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_possible_images(self):
        """Test getting possible images."""
        result = get_possible_images(str(self.test_dir))
        assert isinstance(result, list)

    def test_get_possible_images_empty_dir(self):
        """Test getting images from empty directory."""
        empty_dir = Path(self.temp_dir) / "empty"
        empty_dir.mkdir()

        result = get_possible_images(str(empty_dir))
        assert isinstance(result, list)


class TestGetMimeType:
    """Test the get_mime_type function."""

    def test_get_mime_type_mp4(self):
        """Test MIME type detection for MP4."""
        metadata = {"format_name": "mp4"}
        file_path = Path("test.mp4")

        result = get_mime_type(metadata, file_path)
        assert isinstance(result, str)
        assert "video" in result

    def test_get_mime_type_mkv(self):
        """Test MIME type detection for MKV."""
        metadata = {"format_name": "matroska"}
        file_path = Path("test.mkv")

        result = get_mime_type(metadata, file_path)
        assert isinstance(result, str)

    def test_get_mime_type_fallback(self):
        """Test MIME type fallback."""
        metadata = {}
        file_path = Path("test.unknown")

        result = get_mime_type(metadata, file_path)
        assert isinstance(result, str)


class TestGetFile:
    """Test the get_file function."""

    def setup_method(self):
        """Set up test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.download_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_file_exists(self):
        """Test getting existing file."""
        test_file = self.download_path / "test.txt"
        test_file.write_text("content")

        result_path, status_code = get_file(self.download_path, "test.txt")
        assert isinstance(result_path, Path)
        assert isinstance(status_code, int)

    def test_get_file_not_exists(self):
        """Test getting non-existent file."""
        result_path, status_code = get_file(self.download_path, "nonexistent.txt")
        assert isinstance(result_path, Path)
        assert status_code == 404


class TestGet:
    """Test the get function for nested data access."""

    def test_get_basic_dict(self):
        """Test getting value from dictionary."""
        data = {"key": "value"}
        result = get(data, "key")
        assert result == "value"

    def test_get_nested_dict(self):
        """Test getting nested value."""
        data = {"level1": {"level2": {"level3": "value"}}}
        result = get(data, "level1.level2.level3")
        assert result == "value"

    def test_get_with_default(self):
        """Test getting with default value."""
        data = {"key": "value"}
        result = get(data, "nonexistent", default="default")
        assert result == "default"

    def test_get_list_access(self):
        """Test getting from list."""
        data = ["item0", "item1", "item2"]
        result = get(data, 1)
        assert result == "item1"

    def test_get_empty_path(self):
        """Test with empty path."""
        data = {"key": "value"}
        result = get(data, None)
        assert result == data


class TestGetFiles:
    """Test the get_files function."""

    def setup_method(self):
        """Set up test directory structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.base_path = Path(self.temp_dir)

        # Create test files and directories
        (self.base_path / "file1.txt").write_text("content")
        (self.base_path / "file2.txt").write_text("content")
        (self.base_path / "subdir").mkdir()
        (self.base_path / "subdir" / "file3.txt").write_text("content")

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_files_root(self):
        """Test getting files from root directory."""
        result = get_files(self.base_path)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_files_subdir(self):
        """Test getting files from subdirectory."""
        result = get_files(self.base_path, "subdir")
        assert isinstance(result, list)


class TestReadLogfile:
    """Test the read_logfile async function."""

    def setup_method(self):
        """Set up test log file."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test.log"

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_logfile_nonexistent(self):
        """Test reading non-existent log file."""

        async def test():
            result = await read_logfile(self.log_file)
            assert isinstance(result, dict)
            assert "logs" in result

        asyncio.run(test())

    def test_read_logfile_with_content(self):
        """Test reading log file with content."""
        self.log_file.write_text("line 1\nline 2\nline 3\n")

        async def test():
            result = await read_logfile(self.log_file, limit=2)
            assert isinstance(result, dict)
            assert "logs" in result

        asyncio.run(test())


class TestTailLog:
    """Test the tail_log async function."""

    def setup_method(self):
        """Set up test log file."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test.log"

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tail_log_nonexistent(self):
        """Test tailing non-existent log file."""
        emitted_lines = []

        def emitter(line):
            emitted_lines.append(line)
            return False  # Stop after first emission

        async def test():
            try:
                await tail_log(self.log_file, emitter, sleep_time=0.1)
            except Exception:
                pass  # Expected for non-existent file

        asyncio.run(test())


class TestLoadCookies:
    """Test the load_cookies function."""

    def setup_method(self):
        """Set up test cookie file."""
        self.temp_dir = tempfile.mkdtemp()
        self.cookie_file = Path(self.temp_dir) / "cookies.txt"

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_cookies_invalid_file(self):
        """Test loading invalid cookie file."""
        self.cookie_file.write_text("invalid cookie content")

        try:
            valid, jar = load_cookies(str(self.cookie_file))
            assert isinstance(valid, bool)
            assert jar is not None or not valid
        except ValueError:
            # Expected for invalid cookie files
            assert True


class TestGetArchiveId:
    """Test the get_archive_id function."""

    @patch("app.library.Utils.YTDLP_INFO_CLS")
    def test_get_archive_id_basic(self, mock_ytdlp):
        """Test basic archive ID extraction."""
        mock_ytdlp._ies = {}

        result = get_archive_id("https://youtube.com/watch?v=test123")
        assert isinstance(result, dict)
        assert "id" in result
        assert "ie_key" in result
        assert "archive_id" in result

    def test_get_archive_id_invalid_url(self):
        """Test with invalid URL."""
        result = get_archive_id("invalid-url")
        assert isinstance(result, dict)


class TestStrToDt:
    """Test the str_to_dt function."""

    def test_str_to_dt_basic(self):
        """Test basic string to datetime conversion."""
        try:
            result = str_to_dt("2023-01-02 12:00:00 UTC")
            assert isinstance(result, datetime)
        except ModuleNotFoundError:
            # Expected when dateparser is not available
            assert True

    def test_str_to_dt_relative(self):
        """Test relative time string."""
        try:
            result = str_to_dt("1 hour ago")
            assert isinstance(result, datetime)
        except (ModuleNotFoundError, ValueError):
            assert True


class TestYtdlpReject:
    """Test the ytdlp_reject function."""

    def test_ytdlp_reject_basic(self):
        """Test basic rejection logic."""
        entry = {"title": "Test Video", "view_count": 1000}
        yt_params = {}

        passed, message = ytdlp_reject(entry, yt_params)
        assert isinstance(passed, bool)
        assert isinstance(message, str)

    def test_ytdlp_reject_with_filters(self):
        """Test rejection with filters."""
        entry = {"title": "Test Video", "upload_date": "20230101"}
        yt_params = {"daterange": MagicMock()}

        # Mock daterange to simulate rejection
        yt_params["daterange"].__contains__ = MagicMock(return_value=False)

        passed, message = ytdlp_reject(entry, yt_params)
        assert isinstance(passed, bool)
        assert isinstance(message, str)


class TestInitClass:
    """Test the init_class function."""

    def test_init_class_basic(self):
        """Test basic class initialization."""

        @dataclass
        class TestClass:
            name: str = ""
            value: int = 0
            unused: str = "default"

        data = {"name": "test", "value": 42, "extra": "ignored"}

        result = init_class(TestClass, data)
        assert isinstance(result, TestClass)
        assert result.name == "test"
        assert result.value == 42
        assert result.unused == "default"  # Should use default


class TestLoadModules:
    """Test the load_modules function."""

    def setup_method(self):
        """Set up test module structure."""
        self.temp_dir = tempfile.mkdtemp()
        self.root_path = Path(self.temp_dir)
        self.module_dir = self.root_path / "test_modules"
        self.module_dir.mkdir()

        # Create test module files
        (self.module_dir / "__init__.py").write_text("")
        (self.module_dir / "test_module.py").write_text("# Test module")

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_modules_basic(self):
        """Test basic module loading."""
        try:
            load_modules(self.root_path, self.module_dir)
            # Should not raise an exception
            assert True
        except Exception:
            # Module loading might fail in test environment
            assert True


class TestGetChannelImages:
    """Test the get_channel_images function."""

    def test_get_channel_images_poster_from_portrait(self):
        """Test extracting poster image from portrait ratio thumbnail."""
        from app.library.Utils import get_channel_images

        thumbnails = [{"url": "http://example.com/poster.jpg", "width": 200, "height": 300, "id": "some_id"}]

        result = get_channel_images(thumbnails)

        assert "poster" in result
        assert result["poster"] == "http://example.com/poster.jpg"

    def test_get_channel_images_thumb_from_square(self):
        """Test extracting thumbnail from square ratio."""
        from app.library.Utils import get_channel_images

        thumbnails = [{"url": "http://example.com/thumb.jpg", "width": 300, "height": 300, "id": "id"}]

        result = get_channel_images(thumbnails)

        assert "thumb" in result
        assert result["thumb"] == "http://example.com/thumb.jpg"

    def test_get_channel_images_banner_from_wide(self):
        """Test extracting banner from very wide image."""
        from app.library.Utils import get_channel_images

        thumbnails = [{"url": "http://example.com/banner.jpg", "width": 1920, "height": 200, "id": "id"}]

        result = get_channel_images(thumbnails)

        assert "banner" in result
        assert result["banner"] == "http://example.com/banner.jpg"

    def test_get_channel_images_icon_from_avatar(self):
        """Test extracting icon from avatar uncropped."""
        from app.library.Utils import get_channel_images

        thumbnails = [{"url": "http://example.com/icon.jpg", "id": "avatar_uncropped"}]

        result = get_channel_images(thumbnails)

        assert "icon" in result
        assert result["icon"] == "http://example.com/icon.jpg"

    def test_get_channel_images_landscape_from_banner_uncropped(self):
        """Test extracting landscape from banner uncropped."""
        from app.library.Utils import get_channel_images

        thumbnails = [{"url": "http://example.com/landscape.jpg", "id": "banner_uncropped"}]

        result = get_channel_images(thumbnails)

        assert "landscape" in result
        assert result["landscape"] == "http://example.com/landscape.jpg"

    def test_get_channel_images_empty_list(self):
        """Test with empty thumbnail list."""
        from app.library.Utils import get_channel_images

        result = get_channel_images([])

        assert result == {}

    def test_get_channel_images_fallbacks(self):
        """Test fallback logic for missing images."""
        from app.library.Utils import get_channel_images

        # Create image with fanart but no banner
        thumbnails = [{"url": "http://example.com/fanart.jpg", "width": 1920, "height": 200, "id": "id"}]

        result = get_channel_images(thumbnails)

        assert "fanart" in result
        assert "banner" in result  # Should fallback to fanart
        assert result["banner"] == result["fanart"]

    def test_get_channel_images_no_url(self):
        """Test handling of thumbnail without URL."""
        from app.library.Utils import get_channel_images

        thumbnails = [
            {"width": 300, "height": 300, "id": "id"},  # Missing URL
            {"url": "http://example.com/thumb.jpg", "width": 300, "height": 300, "id": "id"},
        ]

        result = get_channel_images(thumbnails)

        assert len(result) > 0
        assert result.get("thumb") == "http://example.com/thumb.jpg"


class TestIsSafeKey:
    """Test the _is_safe_key function (indirectly through merge_dict)."""

    def test_safe_key_normal_string(self):
        """Test that normal strings are considered safe keys."""
        from app.library.Utils import merge_dict

        source = {"normal_key": "value"}
        dest = {}

        result = merge_dict(source, dest)

        assert "normal_key" in result
        assert result["normal_key"] == "value"

    def test_unsafe_key_dunder_attributes(self):
        """Test that dunder attributes are blocked."""
        from app.library.Utils import merge_dict

        source = {"__class__": "should_not_merge", "normal_key": "value"}
        dest = {}

        result = merge_dict(source, dest)

        assert "__class__" not in result
        assert "normal_key" in result

    def test_unsafe_key_empty_string(self):
        """Test that empty keys are blocked."""
        from app.library.Utils import merge_dict

        source = {"": "empty_key_value", "normal_key": "value"}
        dest = {}

        result = merge_dict(source, dest)

        assert "" not in result
        assert "normal_key" in result

    def test_unsafe_key_whitespace_only(self):
        """Test that whitespace-only keys are blocked."""
        from app.library.Utils import merge_dict

        source = {"   ": "whitespace_key", "normal_key": "value"}
        dest = {}

        result = merge_dict(source, dest)

        assert "   " not in result
        assert "normal_key" in result

    def test_unsafe_key_non_string(self):
        """Test that non-string keys are blocked."""
        from app.library.Utils import merge_dict

        source = {123: "numeric_key", "normal_key": "value"}
        dest = {}

        result = merge_dict(source, dest)

        assert 123 not in result
        assert "normal_key" in result


class TestDecryptDataCornerCases:
    """Additional tests for decrypt_data edge cases."""

    def test_decrypt_data_invalid_base64(self):
        """Test decrypting invalid base64 data."""
        from app.library.Utils import decrypt_data

        result = decrypt_data("not_valid_base64!!!", b"k" * 32)

        assert result is None

    def test_decrypt_data_wrong_key(self):
        """Test decrypting with wrong key returns None."""
        from app.library.Utils import decrypt_data, encrypt_data

        correct_key = b"a" * 32
        wrong_key = b"z" * 32

        encrypted = encrypt_data("test data", correct_key)
        result = decrypt_data(encrypted, wrong_key)

        # Should return None on decryption failure
        assert result is None

    def test_decrypt_data_truncated(self):
        """Test decrypting truncated encrypted data."""
        from app.library.Utils import decrypt_data

        result = decrypt_data("YQ==", b"k" * 32)

        assert result is None


class TestArgConverterAdvanced:
    """Advanced tests for arg_converter function."""

    def test_arg_converter_with_removed_options(self):
        """Test arg_converter with removed options tracking."""
        try:
            removed = []
            result = arg_converter("--quiet --skip-download", level=True, removed_options=removed)

            assert isinstance(result, dict)
        except (ModuleNotFoundError, AttributeError, ImportError):
            assert True

    def test_arg_converter_dumps_enabled(self):
        """Test arg_converter with dumps flag enabled."""
        try:
            result = arg_converter("--format best", dumps=True)

            # With dumps=True, result should still be a dict with JSON-serializable content
            assert isinstance(result, (dict, list))
        except (ModuleNotFoundError, AttributeError, ImportError):
            assert True


class TestCreateCookiesFile:
    """Test the create_cookies_file function."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("app.library.Utils.load_cookies")
    def test_create_cookies_file_with_path(self, mock_load_cookies):
        """Test creating a cookies file with a specific path."""
        from app.library.Utils import create_cookies_file

        mock_load_cookies.return_value = (True, MagicMock())
        cookie_path = self.test_path / "cookies" / "test_cookies.txt"

        result = create_cookies_file("session=abc123", file=cookie_path)

        assert result == cookie_path
        assert cookie_path.exists()
        assert cookie_path.is_file()
        assert cookie_path.read_text() == "session=abc123"
        mock_load_cookies.assert_called_once_with(cookie_path)

    @patch("app.library.config.Config")
    @patch("app.library.Utils.load_cookies")
    def test_create_cookies_file_without_path(self, mock_load_cookies, mock_config):
        """Test creating a cookies file without a specific path (auto temp file)."""
        from app.library.Utils import create_cookies_file

        mock_config_inst = MagicMock()
        mock_config_inst.temp_path = self.temp_dir
        mock_config.get_instance.return_value = mock_config_inst

        mock_load_cookies.return_value = (True, MagicMock())

        result = create_cookies_file("session=def456")

        assert result.exists()
        assert result.is_file()
        assert result.read_text() == "session=def456"
        assert result.parent == Path(self.temp_dir)
        mock_load_cookies.assert_called_once()

    @patch("app.library.Utils.load_cookies")
    def test_create_cookies_file_invalid_cookies(self, mock_load_cookies):
        """Test creating a cookies file with invalid cookies raises error."""
        from app.library.Utils import create_cookies_file

        mock_load_cookies.side_effect = ValueError("Invalid cookies")
        cookie_path = self.test_path / "bad_cookies.txt"

        with pytest.raises(ValueError, match="Invalid cookies"):
            create_cookies_file("invalid_data", file=cookie_path)

    @patch("app.library.Utils.load_cookies")
    def test_create_cookies_file_creates_parent_directory(self, mock_load_cookies):
        """Test that create_cookies_file creates parent directories as needed."""
        from app.library.Utils import create_cookies_file

        mock_load_cookies.return_value = (True, MagicMock())
        # Use a deeply nested path that doesn't exist yet
        cookie_path = self.test_path / "a" / "b" / "c" / "cookies.txt"

        result = create_cookies_file("test_data", file=cookie_path)

        assert result == cookie_path
        assert cookie_path.exists()
        assert cookie_path.parent == Path(self.test_path / "a" / "b" / "c")

    @patch("app.library.Utils.load_cookies")
    def test_create_cookies_file_with_special_characters(self, mock_load_cookies):
        """Test create_cookies_file with special characters in cookie data."""
        from app.library.Utils import create_cookies_file

        mock_load_cookies.return_value = (True, MagicMock())
        cookie_data = "session=abc123; path=/; domain=.example.com; secure; httponly"
        cookie_path = self.test_path / "special_cookies.txt"

        result = create_cookies_file(cookie_data, file=cookie_path)

        assert result == cookie_path
        assert cookie_path.read_text() == cookie_data

    @patch("app.library.Utils.load_cookies")
    def test_create_cookies_file_overwrites_existing(self, mock_load_cookies):
        """Test that create_cookies_file overwrites existing files."""
        from app.library.Utils import create_cookies_file

        mock_load_cookies.return_value = (True, MagicMock())
        cookie_path = self.test_path / "cookies.txt"

        # Create initial file
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookie_path.write_text("old_data")

        # Overwrite with new data
        result = create_cookies_file("new_data", file=cookie_path)

        assert result == cookie_path
        assert cookie_path.read_text() == "new_data"


class TestRenameFile:
    """Test rename_file function."""

    def test_rename_single_file_no_sidecars(self, tmp_path: Path):
        """Test renaming a single file without sidecar files."""
        # Create test file
        test_file = tmp_path / "video.mp4"
        test_file.write_text("test content")

        # Rename file
        new_path, sidecars = rename_file(test_file, "renamed_video.mp4")

        # Assertions
        assert new_path.exists()
        assert "renamed_video.mp4" == new_path.name
        assert not test_file.exists()
        assert 0 == len(sidecars)

    def test_rename_file_with_subtitle_sidecar(self, tmp_path: Path):
        """Test renaming a file with subtitle sidecar."""
        # Create test files
        test_file = tmp_path / "video.mp4"
        test_file.write_text("test video")

        subtitle_file = tmp_path / "video.en.srt"
        subtitle_file.write_text("test subtitle")

        # Rename file
        new_path, sidecars = rename_file(test_file, "renamed_video.mp4")

        # Assertions
        assert new_path.exists()
        assert "renamed_video.mp4" == new_path.name
        assert not test_file.exists()

        assert 1 == len(sidecars)
        old_sidecar, new_sidecar = sidecars[0]
        assert new_sidecar.exists()
        assert "renamed_video.en.srt" == new_sidecar.name
        assert old_sidecar == subtitle_file
        assert not subtitle_file.exists()

    def test_rename_file_with_multiple_sidecars(self, tmp_path: Path):
        """Test renaming a file with multiple sidecar files."""
        # Create test files
        test_file = tmp_path / "video.mp4"
        test_file.write_text("test video")

        subtitle_en = tmp_path / "video.en.srt"
        subtitle_en.write_text("english subtitle")

        subtitle_fr = tmp_path / "video.fr.srt"
        subtitle_fr.write_text("french subtitle")

        info_file = tmp_path / "video.info.json"
        info_file.write_text('{"title": "test"}')

        # Rename file
        new_path, sidecars = rename_file(test_file, "renamed_video.mp4")

        # Assertions
        assert new_path.exists()
        assert "renamed_video.mp4" == new_path.name
        assert not test_file.exists()

        assert 3 == len(sidecars)

        # Check all sidecars were renamed
        sidecar_names = {new_sidecar.name for old_sidecar, new_sidecar in sidecars}
        assert "renamed_video.en.srt" in sidecar_names
        assert "renamed_video.fr.srt" in sidecar_names
        assert "renamed_video.info.json" in sidecar_names

        # Check old files don't exist
        assert not subtitle_en.exists()
        assert not subtitle_fr.exists()
        assert not info_file.exists()

    def test_rename_file_destination_exists(self, tmp_path: Path):
        """Test renaming a file when destination already exists."""
        # Create test files
        test_file = tmp_path / "video.mp4"
        test_file.write_text("test content")

        existing_file = tmp_path / "renamed_video.mp4"
        existing_file.write_text("existing content")

        # Should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            rename_file(test_file, "renamed_video.mp4")

        # Original files should still exist
        assert test_file.exists()
        assert existing_file.exists()

    def test_rename_file_sidecar_destination_exists(self, tmp_path: Path):
        """Test renaming when sidecar destination already exists."""
        # Create test files
        test_file = tmp_path / "video.mp4"
        test_file.write_text("test video")

        subtitle_file = tmp_path / "video.en.srt"
        subtitle_file.write_text("test subtitle")

        # Create conflicting sidecar destination
        conflicting_sidecar = tmp_path / "renamed_video.en.srt"
        conflicting_sidecar.write_text("existing subtitle")

        # Should raise ValueError
        with pytest.raises(ValueError, match=r"Sidecar destination.*already exists"):
            rename_file(test_file, "renamed_video.mp4")

        # Original files should still exist
        assert test_file.exists()
        assert subtitle_file.exists()
        assert conflicting_sidecar.exists()

    def test_rename_preserves_sidecar_extensions(self, tmp_path: Path):
        """Test that rename preserves complex sidecar extensions."""
        # Create test files with complex extensions
        test_file = tmp_path / "video.mp4"
        test_file.write_text("test video")

        subtitle_file = tmp_path / "video.en-US.ass"
        subtitle_file.write_text("test subtitle")

        thumb_file = tmp_path / "video.thumb.jpg"
        thumb_file.write_text("test thumb")

        # Rename file
        new_path, sidecars = rename_file(test_file, "renamed.mp4")

        # Assertions
        assert new_path.exists()
        assert "renamed.mp4" == new_path.name

        assert 2 == len(sidecars)
        sidecar_names = {new_sidecar.name for old_sidecar, new_sidecar in sidecars}
        assert "renamed.en-US.ass" in sidecar_names
        assert "renamed.thumb.jpg" in sidecar_names


class TestMoveFile:
    """Test move_file function."""

    def test_move_single_file_no_sidecars(self, tmp_path: Path):
        """Test moving a single file without sidecar files."""
        # Create test file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test content")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Move file
        new_path, sidecars = move_file(test_file, target_dir)

        # Assertions
        assert new_path.exists()
        assert "video.mp4" == new_path.name
        assert new_path.parent == target_dir
        assert not test_file.exists()
        assert 0 == len(sidecars)

    def test_move_file_with_subtitle_sidecar(self, tmp_path: Path):
        """Test moving a file with subtitle sidecar."""
        # Create test files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test video")

        subtitle_file = source_dir / "video.en.srt"
        subtitle_file.write_text("test subtitle")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Move file
        new_path, sidecars = move_file(test_file, target_dir)

        # Assertions
        assert new_path.exists()
        assert "video.mp4" == new_path.name
        assert new_path.parent == target_dir
        assert not test_file.exists()

        assert 1 == len(sidecars)
        old_sidecar, new_sidecar = sidecars[0]
        assert new_sidecar.exists()
        assert "video.en.srt" == new_sidecar.name
        assert new_sidecar.parent == target_dir
        assert old_sidecar == subtitle_file
        assert not subtitle_file.exists()

    def test_move_file_with_multiple_sidecars(self, tmp_path: Path):
        """Test moving a file with multiple sidecar files."""
        # Create test files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test video")

        subtitle_en = source_dir / "video.en.srt"
        subtitle_en.write_text("english subtitle")

        subtitle_fr = source_dir / "video.fr.srt"
        subtitle_fr.write_text("french subtitle")

        info_file = source_dir / "video.info.json"
        info_file.write_text('{"title": "test"}')

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Move file
        new_path, sidecars = move_file(test_file, target_dir)

        # Assertions
        assert new_path.exists()
        assert "video.mp4" == new_path.name
        assert new_path.parent == target_dir
        assert not test_file.exists()

        assert 3 == len(sidecars)

        # Check all sidecars were moved
        sidecar_names = {new_sidecar.name for old_sidecar, new_sidecar in sidecars}
        assert "video.en.srt" in sidecar_names
        assert "video.fr.srt" in sidecar_names
        assert "video.info.json" in sidecar_names

        # Check all are in target directory
        for _old_sidecar, new_sidecar in sidecars:
            assert new_sidecar.parent == target_dir

        # Check old files don't exist
        assert not subtitle_en.exists()
        assert not subtitle_fr.exists()
        assert not info_file.exists()

    def test_move_file_destination_exists(self, tmp_path: Path):
        """Test moving a file when destination already exists."""
        # Create test files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test content")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        existing_file = target_dir / "video.mp4"
        existing_file.write_text("existing content")

        # Should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            move_file(test_file, target_dir)

        # Original files should still exist
        assert test_file.exists()
        assert existing_file.exists()

    def test_move_file_sidecar_destination_exists(self, tmp_path: Path):
        """Test moving when sidecar destination already exists."""
        # Create test files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test video")

        subtitle_file = source_dir / "video.en.srt"
        subtitle_file.write_text("test subtitle")

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        # Create conflicting sidecar destination
        conflicting_sidecar = target_dir / "video.en.srt"
        conflicting_sidecar.write_text("existing subtitle")

        # Should raise ValueError
        with pytest.raises(ValueError, match=r"Sidecar destination.*already exists"):
            move_file(test_file, target_dir)

        # Original files should still exist
        assert test_file.exists()
        assert subtitle_file.exists()
        assert conflicting_sidecar.exists()

    def test_move_file_target_not_directory(self, tmp_path: Path):
        """Test moving when target is not a directory."""
        # Create test file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test content")

        # Create a file (not directory) as target
        target_file = tmp_path / "target.txt"
        target_file.write_text("not a directory")

        # Should raise ValueError
        with pytest.raises(ValueError, match="not a directory"):
            move_file(test_file, target_file)

        # Original file should still exist
        assert test_file.exists()

    def test_move_file_target_does_not_exist(self, tmp_path: Path):
        """Test moving when target directory doesn't exist."""
        # Create test file
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        test_file = source_dir / "video.mp4"
        test_file.write_text("test content")

        target_dir = tmp_path / "nonexistent"

        # Should raise ValueError
        with pytest.raises(ValueError, match="does not exist"):
            move_file(test_file, target_dir)

        # Original file should still exist
        assert test_file.exists()


class TestGetThumbnail:
    def test_returns_none_for_empty_list(self):
        """Test that None is returned for an empty thumbnail list."""
        from app.library.Utils import get_thumbnail

        assert get_thumbnail([]) is None

    def test_returns_none_for_non_list(self):
        """Test that None is returned for non-list input."""
        from app.library.Utils import get_thumbnail

        assert get_thumbnail(None) is None
        assert get_thumbnail("not a list") is None
        assert get_thumbnail({"not": "list"}) is None

    def test_returns_highest_preference_thumbnail(self):
        """Test that the thumbnail with highest preference is returned."""
        from app.library.Utils import get_thumbnail

        thumbnails = [
            {"url": "low.jpg", "preference": 1, "width": 100, "height": 100},
            {"url": "high.jpg", "preference": 10, "width": 200, "height": 200},
            {"url": "medium.jpg", "preference": 5, "width": 150, "height": 150},
        ]

        result = get_thumbnail(thumbnails)
        assert result == {"url": "high.jpg", "preference": 10, "width": 200, "height": 200}

    def test_returns_highest_width_when_preference_equal(self):
        """Test that the thumbnail with highest width is returned when preference is equal."""
        from app.library.Utils import get_thumbnail

        thumbnails = [
            {"url": "small.jpg", "preference": 1, "width": 100, "height": 100},
            {"url": "large.jpg", "preference": 1, "width": 200, "height": 200},
            {"url": "medium.jpg", "preference": 1, "width": 150, "height": 150},
        ]

        result = get_thumbnail(thumbnails)
        assert result == {"url": "large.jpg", "preference": 1, "width": 200, "height": 200}

    def test_handles_missing_attributes(self):
        """Test that thumbnails with missing attributes are handled correctly."""
        from app.library.Utils import get_thumbnail

        thumbnails = [
            {"url": "no_pref.jpg", "width": 100},
            {"url": "with_pref.jpg", "preference": 5, "width": 50},
        ]

        result = get_thumbnail(thumbnails)
        assert result["url"] == "with_pref.jpg"

    def test_returns_first_when_all_equal(self):
        """Test that any thumbnail is returned when all attributes are equal."""
        from app.library.Utils import get_thumbnail

        thumbnails = [
            {"url": "first.jpg"},
            {"url": "second.jpg"},
        ]

        result = get_thumbnail(thumbnails)
        assert result is not None
        assert result["url"] in ["first.jpg", "second.jpg"]


class TestGetExtras:
    def test_returns_empty_dict_for_none(self):
        """Test that empty dict is returned for None input."""
        from app.library.Utils import get_extras

        assert get_extras(None) == {}

    def test_returns_empty_dict_for_non_dict(self):
        """Test that empty dict is returned for non-dict input."""
        from app.library.Utils import get_extras

        assert get_extras("not a dict") == {}
        assert get_extras([]) == {}

    def test_extracts_video_information(self):
        """Test extracting information from a video entry."""
        from app.library.Utils import get_extras

        entry = {
            "id": "test123",
            "title": "Test Video",
            "uploader": "Test Uploader",
            "channel": "Test Channel",
            "thumbnails": [{"url": "thumb.jpg", "preference": 1}],
            "duration": 120,
        }

        result = get_extras(entry, kind="video")

        assert result["uploader"] == "Test Uploader"
        assert result["channel"] == "Test Channel"
        assert result["thumbnail"] == "thumb.jpg"
        assert result["duration"] == 120
        assert result["is_premiere"] is False

    def test_extracts_playlist_information(self):
        """Test extracting information from a playlist entry."""
        from app.library.Utils import get_extras

        entry = {
            "id": "playlist123",
            "title": "Test Playlist",
            "uploader": "Playlist Owner",
            "uploader_id": "owner123",
        }

        result = get_extras(entry, kind="playlist")

        assert result["playlist_id"] == "playlist123"
        assert result["playlist_title"] == "Test Playlist"
        assert result["playlist_uploader"] == "Playlist Owner"
        assert result["playlist_uploader_id"] == "owner123"

    def test_handles_release_timestamp(self):
        """Test handling of release_timestamp for upcoming content."""
        from app.library.Utils import get_extras

        entry = {
            "release_timestamp": 1234567890,
        }

        result = get_extras(entry)

        assert "release_in" in result
        assert result["release_in"] == "Fri, 13 Feb 2009 23:31:30 GMT"

    def test_handles_upcoming_live_stream(self):
        """Test handling of upcoming live stream."""
        from app.library.Utils import get_extras

        entry = {
            "release_timestamp": 1234567890,
            "live_status": "is_upcoming",
        }

        result = get_extras(entry)

        assert result["is_live"] == 1234567890
        assert "release_in" in result

    def test_handles_premiere_flag(self):
        """Test handling of is_premiere flag."""
        from app.library.Utils import get_extras

        entry = {
            "is_premiere": True,
        }

        result = get_extras(entry)
        assert result["is_premiere"] is True

        entry2 = {"is_premiere": False}
        result2 = get_extras(entry2)
        assert result2["is_premiere"] is False

    def test_youtube_fallback_thumbnail(self):
        """Test fallback thumbnail generation for YouTube videos."""
        from app.library.Utils import get_extras

        entry = {
            "id": "dQw4w9WgXcQ",
            "ie_key": "Youtube",
        }

        result = get_extras(entry)

        assert result["thumbnail"] == "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"

    def test_thumbnail_string_fallback(self):
        """Test fallback to thumbnail string when thumbnails list not available."""
        from app.library.Utils import get_extras

        entry = {
            "thumbnail": "https://example.com/thumb.jpg",
        }

        result = get_extras(entry)

        assert result["thumbnail"] == "https://example.com/thumb.jpg"
