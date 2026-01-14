import asyncio
import logging
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.library.downloads.utils import (
    BAD_LIVE_STREAM_OPTIONS,
    DEBUG_MESSAGE_PREFIXES,
    GENERIC_EXTRACTORS,
    LIMITS,
    YTDLP_PROGRESS_FIELDS,
    create_debug_safe_dict,
    get_extractor_limit,
    handle_task_exception,
    is_download_stale,
    is_safe_to_delete_dir,
    parse_extractor_limit,
    safe_relative_path,
    wait_for_process_with_timeout,
)


class TestConstants:
    def test_generic_extractors_tuple(self) -> None:
        assert isinstance(GENERIC_EXTRACTORS, tuple), "Should be a tuple"
        assert "HTML5MediaEmbed" in GENERIC_EXTRACTORS, "Should contain HTML5MediaEmbed"
        assert "generic" in GENERIC_EXTRACTORS, "Should contain generic"

    def test_ytdlp_progress_fields_tuple(self) -> None:
        assert isinstance(YTDLP_PROGRESS_FIELDS, tuple), "Should be a tuple"
        assert "status" in YTDLP_PROGRESS_FIELDS, "Should contain status field"
        assert "downloaded_bytes" in YTDLP_PROGRESS_FIELDS, "Should contain downloaded_bytes field"

    def test_bad_live_stream_options_list(self) -> None:
        assert isinstance(BAD_LIVE_STREAM_OPTIONS, list), "Should be a list"
        assert "concurrent_fragment_downloads" in BAD_LIVE_STREAM_OPTIONS, "Should contain concurrent option"

    def test_debug_message_prefixes_list(self) -> None:
        assert isinstance(DEBUG_MESSAGE_PREFIXES, list), "Should be a list"
        assert "[debug] " in DEBUG_MESSAGE_PREFIXES, "Should contain debug prefix"


class TestPathUtilities:
    def test_safe_relative_path_success(self) -> None:
        base = Path("/downloads")
        file = Path("/downloads/video.mp4")
        result = safe_relative_path(file, base)
        assert "video.mp4" == result, "Should return relative path"

    def test_safe_relative_path_nested(self) -> None:
        base = Path("/downloads")
        file = Path("/downloads/folder/subfolder/video.mp4")
        result = safe_relative_path(file, base)
        assert "folder/subfolder/video.mp4" == result, "Should return nested relative path"

    def test_safe_relative_path_with_fallback(self) -> None:
        base = Path("/wrong/path")
        fallback = Path("/temp")
        file = Path("/temp/video.mp4")
        result = safe_relative_path(file, base, fallback)
        assert "video.mp4" == result, "Should use fallback path"

    def test_safe_relative_path_no_fallback_returns_absolute(self) -> None:
        base = Path("/wrong/path")
        file = Path("/downloads/video.mp4")
        result = safe_relative_path(file, base)
        assert "/downloads/video.mp4" == result, "Should return absolute path when both fail"

    def test_safe_relative_path_fallback_also_fails(self) -> None:
        base = Path("/wrong/path")
        fallback = Path("/also/wrong")
        file = Path("/downloads/video.mp4")
        result = safe_relative_path(file, base, fallback)
        assert "/downloads/video.mp4" == result, "Should return absolute when both fail"

    def test_is_safe_to_delete_dir_root_protection(self) -> None:
        path = Path("/tmp/downloads")
        root = Path("/tmp/downloads")
        result = is_safe_to_delete_dir(path, root)
        assert result is False, "Should refuse to delete root directory"

    def test_is_safe_to_delete_dir_safe_path(self) -> None:
        path = Path("/tmp/downloads/subfolder")
        root = Path("/tmp/downloads")
        result = is_safe_to_delete_dir(path, root)
        assert result is True, "Should allow deleting subdirectory"

    def test_is_safe_to_delete_dir_string_comparison(self) -> None:
        path = Path("/tmp/downloads")
        root = "/tmp/downloads"
        result = is_safe_to_delete_dir(path, root)
        assert result is False, "Should handle string root path"


class TestProcessUtilities:
    def test_wait_for_process_with_timeout_completes_immediately(self) -> None:
        proc = Mock()
        proc.is_alive = Mock(return_value=False)
        result = wait_for_process_with_timeout(proc, timeout=1.0)
        assert result is True, "Should return True when process terminates immediately"

    def test_wait_for_process_with_timeout_completes_after_delay(self) -> None:
        proc = Mock()
        call_count = [0]

        def is_alive_side_effect():
            call_count[0] += 1
            return call_count[0] < 3

        proc.is_alive = Mock(side_effect=is_alive_side_effect)

        with patch("time.sleep"):
            result = wait_for_process_with_timeout(proc, timeout=1.0, check_interval=0.1)

        assert result is True, "Should return True when process terminates during wait"
        assert proc.is_alive.call_count >= 3, "Should check process multiple times"

    def test_wait_for_process_with_timeout_expires(self) -> None:
        proc = Mock()
        proc.is_alive = Mock(return_value=True)

        with patch("time.time") as mock_time, patch("time.sleep"):
            mock_time.side_effect = [0, 0.5, 1.0, 1.5]
            result = wait_for_process_with_timeout(proc, timeout=1.0, check_interval=0.1)

        assert result is False, "Should return False when timeout reached"

    def test_wait_for_process_with_custom_interval(self) -> None:
        proc = Mock()
        proc.is_alive = Mock(return_value=False)
        result = wait_for_process_with_timeout(proc, timeout=5.0, check_interval=0.5)
        assert result is True, "Should respect custom check interval"


class TestConfigUtilities:
    def test_parse_extractor_limit_valid_env(self) -> None:
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "3"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
            assert 3 == result, "Should use environment variable value"

    def test_parse_extractor_limit_env_exceeds_max(self) -> None:
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "15"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
            assert 10 == result, "Should cap at max_workers"

    def test_parse_extractor_limit_invalid_env_not_digit(self) -> None:
        logger = logging.getLogger("test")
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "abc"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10, logger=logger)
            assert 5 == result, "Should use default when env var is invalid"

    def test_parse_extractor_limit_invalid_env_zero(self) -> None:
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "0"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
            assert 5 == result, "Should use default when env var is zero"

    def test_parse_extractor_limit_no_env(self) -> None:
        result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
        assert 5 == result, "Should use default when no env var set"

    def test_parse_extractor_limit_respects_max_on_default(self) -> None:
        result = parse_extractor_limit("youtube", default_limit=15, max_workers=10)
        assert 10 == result, "Should cap default at max_workers"

    def test_parse_extractor_limit_logs_warning_on_invalid(self) -> None:
        logger = Mock()
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "invalid"}):
            parse_extractor_limit("youtube", default_limit=5, max_workers=10, logger=logger)
            logger.warning.assert_called_once()
            assert "Invalid extractor limit" in logger.warning.call_args[0][0], "Should log warning"

    def test_get_extractor_limit_creates_new(self) -> None:
        LIMITS.clear()
        logger = logging.getLogger("test")
        semaphore = get_extractor_limit("youtube", max_workers=10, max_workers_per_extractor=5, logger=logger)
        assert isinstance(semaphore, asyncio.Semaphore), "Should return semaphore"
        assert "youtube" in LIMITS, "Should store in LIMITS dict"

    def test_get_extractor_limit_reuses_existing(self) -> None:
        LIMITS.clear()
        logger = logging.getLogger("test")
        sem1 = get_extractor_limit("youtube", max_workers=10, max_workers_per_extractor=5, logger=logger)
        sem2 = get_extractor_limit("youtube", max_workers=10, max_workers_per_extractor=5, logger=logger)
        assert sem1 is sem2, "Should reuse existing semaphore"

    def test_get_extractor_limit_respects_env_var(self) -> None:
        LIMITS.clear()
        logger = logging.getLogger("test")
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_TWITCH": "2"}):
            semaphore = get_extractor_limit("twitch", max_workers=10, max_workers_per_extractor=5, logger=logger)
            assert semaphore._value == 2, "Should respect environment variable"


class TestDataUtilities:
    def test_create_debug_safe_dict_filters_formats(self) -> None:
        data = {
            "status": "downloading",
            "filename": "video.mp4",
            "info_dict": {"id": "123", "title": "Video", "formats": [{"format_id": "1"}], "description": "Long text"},
        }
        result = create_debug_safe_dict(data)
        assert "downloading" == result["status"], "Should include status"
        assert "video.mp4" == result["filename"], "Should include filename"
        assert "formats" not in result["info_dict"], "Should exclude formats"
        assert "description" not in result["info_dict"], "Should exclude description"
        assert "123" == result["info_dict"]["id"], "Should include id"

    def test_create_debug_safe_dict_custom_exclude(self) -> None:
        data = {
            "status": "downloading",
            "filename": "video.mp4",
            "info_dict": {"id": "123", "title": "Video", "custom_field": "value"},
        }
        result = create_debug_safe_dict(data, exclude_keys=["custom_field"])
        assert "custom_field" not in result["info_dict"], "Should exclude custom field"
        assert "123" == result["info_dict"]["id"], "Should include id"

    def test_create_debug_safe_dict_filters_none_and_functions(self) -> None:
        data = {
            "status": "downloading",
            "info_dict": {"id": "123", "none_value": None, "lambda_value": lambda: None, "title": "Video"},
        }
        result = create_debug_safe_dict(data)
        assert "none_value" not in result["info_dict"], "Should filter None values"
        assert "lambda_value" not in result["info_dict"], "Should filter lambda functions"
        assert "Video" == result["info_dict"]["title"], "Should include regular values"

    def test_create_debug_safe_dict_empty_info_dict(self) -> None:
        data = {"status": "downloading", "filename": "video.mp4"}
        result = create_debug_safe_dict(data)
        assert {} == result["info_dict"], "Should handle missing info_dict"


class TestStateUtilities:
    def test_is_download_stale_terminal_status_finished(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="finished", is_running=False, auto_start=True
        )
        assert result is False, "Finished downloads are never stale"

    def test_is_download_stale_terminal_status_error(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="error", is_running=False, auto_start=True
        )
        assert result is False, "Error downloads are never stale"

    def test_is_download_stale_terminal_status_cancelled(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="cancelled", is_running=False, auto_start=True
        )
        assert result is False, "Cancelled downloads are never stale"

    def test_is_download_stale_terminal_status_downloading(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="downloading", is_running=False, auto_start=True
        )
        assert result is False, "Downloading status is never stale"

    def test_is_download_stale_terminal_status_postprocessing(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="postprocessing", is_running=False, auto_start=True
        )
        assert result is False, "Postprocessing status is never stale"

    def test_is_download_stale_not_auto_start(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="pending", is_running=False, auto_start=False
        )
        assert result is False, "Non-auto-start downloads are never stale"

    def test_is_download_stale_still_running(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 500, current_status="pending", is_running=True, auto_start=True
        )
        assert result is False, "Running downloads are never stale"

    def test_is_download_stale_not_enough_time(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 100,
            current_status="pending",
            is_running=False,
            auto_start=True,
            min_elapsed=300,
        )
        assert result is False, "Should not be stale before timeout"

    def test_is_download_stale_timeout_reached(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 400,
            current_status="pending",
            is_running=False,
            auto_start=True,
            min_elapsed=300,
        )
        assert result is True, "Should be stale after timeout"

    def test_is_download_stale_custom_timeout(self) -> None:
        result = is_download_stale(
            started_time=int(time.time()) - 150,
            current_status="pending",
            is_running=False,
            auto_start=True,
            min_elapsed=100,
        )
        assert result is True, "Should respect custom timeout"


class TestTaskExceptionHandling:
    @pytest.mark.asyncio
    async def test_handle_task_exception_ignores_cancelled(self) -> None:
        logger = Mock()

        async def cancelled_task():
            raise asyncio.CancelledError()

        task = asyncio.create_task(cancelled_task())
        try:
            await task
        except asyncio.CancelledError:
            pass

        handle_task_exception(task, logger)
        logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_task_exception_ignores_successful(self) -> None:
        logger = Mock()

        async def successful_task():
            return "success"

        task = asyncio.create_task(successful_task())
        await task

        handle_task_exception(task, logger)
        logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_task_exception_logs_exception(self) -> None:
        logger = Mock()

        async def failing_task():
            raise ValueError("Test error")

        task = asyncio.create_task(failing_task(), name="test_task")
        try:
            await task
        except ValueError:
            pass

        handle_task_exception(task, logger)
        logger.error.assert_called_once()
        error_msg = logger.error.call_args[0][0]
        assert "test_task" in error_msg, "Should include task name"
        assert "Test error" in error_msg, "Should include exception message"

    @pytest.mark.asyncio
    async def test_handle_task_exception_unknown_task_name(self) -> None:
        logger = Mock()

        async def failing_task():
            raise RuntimeError("Unknown task error")

        task = asyncio.create_task(failing_task())
        try:
            await task
        except RuntimeError:
            pass

        handle_task_exception(task, logger)
        logger.error.assert_called_once()
        error_msg = logger.error.call_args[0][0]
        assert "unknown_task" in error_msg or "Task" in error_msg, "Should handle unknown task name"
