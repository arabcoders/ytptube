"""Utility functions and constants for the downloads module."""

import asyncio
import logging
import os
import time
from pathlib import Path

# Global limits container for per-extractor semaphores
LIMITS: dict[str, asyncio.Semaphore] = {}

# Extractor Constants
GENERIC_EXTRACTORS = ("HTML5MediaEmbed", "generic")

# yt-dlp Field Filtering
YTDLP_PROGRESS_FIELDS = (
    "tmpfilename",
    "filename",
    "status",
    "msg",
    "total_bytes",
    "total_bytes_estimate",
    "downloaded_bytes",
    "speed",
    "eta",
    "postprocessor",
)

# Live Stream Options (known to cause issues)
BAD_LIVE_STREAM_OPTIONS = [
    "concurrent_fragment_downloads",
    "fragment_retries",
    "skip_unavailable_fragments",
]

# Debug Logging
DEBUG_MESSAGE_PREFIXES = ["[debug] ", "[download] "]


def safe_relative_path(file_path: Path, base_path: Path, fallback_path: Path | None = None) -> str:
    """
    Get relative path with fallback handling.

    Attempts to compute the relative path from base_path. If that fails,
    tries fallback_path. If both fail, returns absolute path as string.

    Args:
        file_path: The file path to make relative
        base_path: The base path to compute relative to
        fallback_path: Optional fallback base path

    Returns:
        str: Relative path string, or absolute path if relative computation fails

    """
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        if fallback_path:
            try:
                return str(file_path.relative_to(fallback_path))
            except ValueError:
                pass
        return str(file_path)


def is_safe_to_delete_dir(path: Path, root_path: str | Path) -> bool:
    """
    Safety check before deleting directories.

    Prevents accidental deletion of the root temporary directory.

    Args:
        path: The path to check
        root_path: The root path that should not be deleted

    Returns:
        bool: True if safe to delete, False if it's the root

    """
    return str(path) != str(root_path)


def wait_for_process_with_timeout(proc, timeout: float, check_interval: float = 0.1) -> bool:
    """
    Wait for process to terminate with timeout.

    Args:
        proc: The multiprocessing.Process to wait for
        timeout: Maximum time to wait in seconds
        check_interval: How often to check process state

    Returns:
        bool: True if process terminated, False if timeout reached

    """
    start_time = time.time()
    while proc.is_alive() and (time.time() - start_time) < timeout:
        time.sleep(check_interval)
    return not proc.is_alive()


def parse_extractor_limit(
    extractor: str,
    default_limit: int,
    max_workers: int,
    logger: logging.Logger | None = None,
) -> int:
    """
    Parse and validate environment variable limits for extractors.

    Checks for YTP_MAX_WORKERS_FOR_{EXTRACTOR} environment variable,
    validates the value, and ensures it doesn't exceed max_workers.

    Args:
        extractor: The extractor name
        default_limit: Default limit if no valid env var found
        max_workers: Maximum workers to never exceed
        logger: Optional logger for warnings

    Returns:
        int: The validated limit for this extractor

    """
    env_limit: str | None = os.environ.get(f"YTP_MAX_WORKERS_FOR_{extractor.upper()}")

    if env_limit and env_limit.isdigit() and 1 <= int(env_limit):
        limit: int = min(int(env_limit), max_workers)
    else:
        if env_limit and logger:
            logger.warning(f"Invalid extractor limit '{env_limit}' for '{extractor}', using default limit.")
        limit = default_limit

    return min(limit, max_workers)


def get_extractor_limit(
    extractor: str,
    max_workers: int,
    max_workers_per_extractor: int,
    logger: logging.Logger,
) -> asyncio.Semaphore:
    """
    Get or create a semaphore for the given extractor.

    Args:
        extractor: The extractor name
        max_workers: Maximum workers allowed
        max_workers_per_extractor: Default per-extractor limit
        logger: Logger for info messages

    Returns:
        asyncio.Semaphore: The semaphore for this extractor

    """
    if extractor not in LIMITS:
        limit = parse_extractor_limit(extractor, max_workers_per_extractor, max_workers, logger)
        LIMITS[extractor] = asyncio.Semaphore(limit)
        logger.info(f"Created limits container for extractor '{extractor}': {limit}")

    return LIMITS[extractor]


def create_debug_safe_dict(data: dict, exclude_keys: list[str] | None = None) -> dict:
    """
    Create sanitized dict for debug logging.

    Args:
        data: The data dict to sanitize
        exclude_keys: Additional keys to exclude from info_dict

    Returns:
        dict: Sanitized dict safe for logging

    """
    if exclude_keys is None:
        exclude_keys = ["formats", "thumbnails", "description", "tags", "_format_sort_fields"]

    import types

    d_safe: dict = {
        "status": data.get("status"),
        "filename": data.get("filename"),
        "info_dict": {
            k: v
            for k, v in data.get("info_dict", {}).items()
            if k not in exclude_keys and v is not None and not isinstance(v, (types.FunctionType, types.LambdaType))
        },
    }

    return d_safe


def is_download_stale(
    started_time: int, current_status: str, is_running: bool, auto_start: bool, min_elapsed: int = 300
) -> bool:
    """
    Determine if download task has become stale.

    A download is stale if it's been running too long without progress,
    or if the process died unexpectedly.

    Terminal statuses (finished, error, cancelled, downloading, postprocessing)
    are never stale - status is source of truth.

    Args:
        started_time: Unix timestamp when download started
        current_status: Current download status
        is_running: Whether the process is currently running
        auto_start: Whether download was set to auto-start
        min_elapsed: Minimum seconds before considering stale

    Returns:
        bool: True if download is stale and should be cancelled

    """
    terminal_statuses = ["finished", "error", "cancelled", "downloading", "postprocessing"]

    if current_status in terminal_statuses:
        return False

    if not auto_start:
        return False

    if is_running:
        return False

    elapsed = int(time.time()) - started_time
    return elapsed >= min_elapsed


def handle_task_exception(task: asyncio.Task, logger: logging.Logger) -> None:
    """
    Handle exceptions from background tasks.

    Logs unhandled exceptions from asyncio tasks. Ignores cancelled tasks.

    Args:
        task: The completed task to check
        logger: Logger to use for error output

    """
    if task.cancelled():
        return

    if not (exc := task.exception()):
        return

    task_name: str = task.get_name() if task.get_name() else "unknown_task"
    import traceback

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"Unhandled exception in background task '{task_name}': {exc!s}. {tb}")
