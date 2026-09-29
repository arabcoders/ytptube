import asyncio
import logging
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.features.downloads.runtime.utils import (
    LIMITS,
    create_debug_safe_dict,
    get_extractor_limit,
    handle_task_exception,
    is_download_stale,
    is_safe_to_delete_dir,
    parse_extractor_limit,
    safe_relative_path,
    wait_for_process_with_timeout,
)


class TestPathUtilities:
    def test_safe_relative_path_success(self) -> None:
        base = Path("/downloads")
        file = Path("/downloads/video.mp4")
        result = safe_relative_path(file, base)
        assert "video.mp4" == result

    def test_safe_relative_path_nested(self) -> None:
        base = Path("/downloads")
        file = Path("/downloads/folder/subfolder/video.mp4")
        result = safe_relative_path(file, base)
        assert "folder/subfolder/video.mp4" == result

    def test_safe_relative_path_fallback(self) -> None:
        base = Path("/wrong/path")
        fallback = Path("/temp")
        file = Path("/temp/video.mp4")
        result = safe_relative_path(file, base, fallback)
        assert "video.mp4" == result

    def test_safe_rel_no_fallback(self) -> None:
        base = Path("/wrong/path")
        file = Path("/downloads/video.mp4")
        result = safe_relative_path(file, base)
        assert "/downloads/video.mp4" == result

    def test_relative_path_fallback_fails(self) -> None:
        base = Path("/wrong/path")
        fallback = Path("/also/wrong")
        file = Path("/downloads/video.mp4")
        result = safe_relative_path(file, base, fallback)
        assert "/downloads/video.mp4" == result

    def test_delete_dir_root_protection(self) -> None:
        path = Path("/tmp/downloads")
        root = Path("/tmp/downloads")
        result = is_safe_to_delete_dir(path, root)
        assert result is False

    def test_delete_dir_safe_path(self) -> None:
        path = Path("/tmp/downloads/subfolder")
        root = Path("/tmp/downloads")
        result = is_safe_to_delete_dir(path, root)
        assert result is True

    def test_delete_dir_string_comparison(self) -> None:
        path = Path("/tmp/downloads")
        root = "/tmp/downloads"
        result = is_safe_to_delete_dir(path, root)
        assert result is False


class TestProcessUtilities:
    def test_wait_timeout_done(self) -> None:
        proc = Mock()
        proc.is_alive = Mock(return_value=False)
        result = wait_for_process_with_timeout(proc, timeout=1.0)
        assert result is True

    def test_wait_timeout_delay(self) -> None:
        proc = Mock()
        call_count = [0]

        def is_alive_side_effect():
            call_count[0] += 1
            return call_count[0] < 3

        proc.is_alive = Mock(side_effect=is_alive_side_effect)

        with patch("time.sleep"):
            result = wait_for_process_with_timeout(proc, timeout=1.0, check_interval=0.1)

        assert result is True
        assert proc.is_alive.call_count >= 3

    def test_wait_process_timeout_expires(self) -> None:
        proc = Mock()
        proc.is_alive = Mock(return_value=True)

        with patch("time.time") as mock_time, patch("time.sleep"):
            mock_time.side_effect = [0, 0.5, 1.0, 1.5]
            result = wait_for_process_with_timeout(proc, timeout=1.0, check_interval=0.1)

        assert result is False

    def test_wait_process_custom_interval(self) -> None:
        proc = Mock()
        proc.is_alive = Mock(return_value=False)
        result = wait_for_process_with_timeout(proc, timeout=5.0, check_interval=0.5)
        assert result is True


class TestConfigUtilities:
    def test_extractor_limit_valid_env(self) -> None:
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "3"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
            assert 3 == result

    def test_limit_env_exceeds_max(self) -> None:
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "15"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
            assert 10 == result

    def test_parse_limit_nondigit(self) -> None:
        logger = logging.getLogger("test")
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "abc"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10, logger=logger)
            assert 5 == result

    def test_limit_invalid_env_zero(self) -> None:
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "0"}):
            result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
            assert 5 == result

    def test_extractor_limit_no_env(self) -> None:
        result = parse_extractor_limit("youtube", default_limit=5, max_workers=10)
        assert 5 == result

    def test_parse_limit_default_max(self) -> None:
        result = parse_extractor_limit("youtube", default_limit=15, max_workers=10)
        assert 10 == result

    def test_parse_limit_warns(self) -> None:
        logger = Mock()
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_YOUTUBE": "invalid"}):
            parse_extractor_limit("youtube", default_limit=5, max_workers=10, logger=logger)
            logger.warning.assert_called_once()
            assert "Invalid extractor limit" in logger.warning.call_args[0][0]

    def test_extractor_limit_creates_new(self) -> None:
        LIMITS.clear()
        logger = logging.getLogger("test")
        semaphore = get_extractor_limit("youtube", max_workers=10, max_workers_per_extractor=5, logger=logger)
        assert isinstance(semaphore, asyncio.Semaphore)
        assert "youtube" in LIMITS

    def test_extractor_limit_reuses_existing(self) -> None:
        LIMITS.clear()
        logger = logging.getLogger("test")
        sem1 = get_extractor_limit("youtube", max_workers=10, max_workers_per_extractor=5, logger=logger)
        sem2 = get_extractor_limit("youtube", max_workers=10, max_workers_per_extractor=5, logger=logger)
        assert sem1 is sem2

    def test_limit_respects_env_var(self) -> None:
        LIMITS.clear()
        logger = logging.getLogger("test")
        with patch.dict(os.environ, {"YTP_MAX_WORKERS_FOR_TWITCH": "2"}):
            semaphore = get_extractor_limit("twitch", max_workers=10, max_workers_per_extractor=5, logger=logger)
            assert semaphore._value == 2


class TestDataUtilities:
    def test_safe_dict_filters_formats(self) -> None:
        data = {
            "status": "downloading",
            "filename": "video.mp4",
            "info_dict": {"id": "123", "title": "Video", "formats": [{"format_id": "1"}], "description": "Long text"},
        }
        result = create_debug_safe_dict(data)
        assert "downloading" == result["status"]
        assert "video.mp4" == result["filename"]
        assert "formats" not in result["info_dict"]
        assert "description" not in result["info_dict"]
        assert "123" == result["info_dict"]["id"]

    def test_safe_dict_custom_exclude(self) -> None:
        data = {
            "status": "downloading",
            "filename": "video.mp4",
            "info_dict": {"id": "123", "title": "Video", "custom_field": "value"},
        }
        result = create_debug_safe_dict(data, exclude_keys=["custom_field"])
        assert "custom_field" not in result["info_dict"]
        assert "123" == result["info_dict"]["id"]

    def test_debug_safe_filters_none(self) -> None:
        data = {
            "status": "downloading",
            "info_dict": {"id": "123", "none_value": None, "lambda_value": lambda: None, "title": "Video"},
        }
        result = create_debug_safe_dict(data)
        assert "none_value" not in result["info_dict"]
        assert "lambda_value" not in result["info_dict"]
        assert "Video" == result["info_dict"]["title"]

    def test_dict_empty_info_dict(self) -> None:
        data = {"status": "downloading", "filename": "video.mp4"}
        result = create_debug_safe_dict(data)
        assert {} == result["info_dict"]


class TestStateUtilities:
    @pytest.mark.parametrize("status", ["finished", "error", "cancelled", "downloading", "postprocessing"])
    def test_stale_status(self, status: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.features.downloads.runtime.utils.time.time", lambda: 1_000)
        result = is_download_stale(started_time=500, current_status=status, is_running=False, auto_start=True)
        assert result is False, f"{status} downloads are never stale"

    def test_stale_not_auto_start(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.features.downloads.runtime.utils.time.time", lambda: 1_000)
        result = is_download_stale(started_time=500, current_status="pending", is_running=False, auto_start=False)
        assert result is False, "Non-auto-start downloads are never stale"

    def test_download_stale_still_running(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.features.downloads.runtime.utils.time.time", lambda: 1_000)
        result = is_download_stale(started_time=500, current_status="pending", is_running=True, auto_start=True)
        assert result is False, "Running downloads are never stale"

    def test_stale_not_enough_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.features.downloads.runtime.utils.time.time", lambda: 1_000)
        result = is_download_stale(
            started_time=900,
            current_status="pending",
            is_running=False,
            auto_start=True,
            min_elapsed=300,
        )
        assert result is False

    def test_download_stale_timeout_reached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.features.downloads.runtime.utils.time.time", lambda: 1_000)
        result = is_download_stale(
            started_time=600,
            current_status="pending",
            is_running=False,
            auto_start=True,
            min_elapsed=300,
        )
        assert result is True

    def test_download_stale_custom_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("app.features.downloads.runtime.utils.time.time", lambda: 1_000)
        result = is_download_stale(
            started_time=850,
            current_status="pending",
            is_running=False,
            auto_start=True,
            min_elapsed=100,
        )
        assert result is True


class TestTaskExceptionHandling:
    @pytest.mark.asyncio
    async def test_task_exception_ignores_cancelled(self) -> None:
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
    async def test_task_exception_success(self) -> None:
        logger = Mock()

        async def successful_task():
            return "success"

        task = asyncio.create_task(successful_task())
        await task

        handle_task_exception(task, logger)
        logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_task_exception_logs_exception(self) -> None:
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
        error_msg = logger.error.call_args[0][0] % logger.error.call_args[0][1:]
        assert "test_task" in error_msg
        assert "Test error" in error_msg

    @pytest.mark.asyncio
    async def test_exception_unknown_task_name(self) -> None:
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
        error_msg = logger.error.call_args[0][0] % logger.error.call_args[0][1:]
        assert "unknown_task" in error_msg or "Task" in error_msg
