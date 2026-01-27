import asyncio
import functools
import logging
import pickle
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from app.library.LogWrapper import LogWrapper
from app.library.mini_filter import match_str
from app.library.Singleton import Singleton
from app.library.ytdlp import YTDLP

LOG: logging.Logger = logging.getLogger("downloads.extractor")


class ExtractorConfig:
    """Configuration for the extractor."""

    def __init__(
        self,
        concurrency: int = 4,
        timeout: float = 60.0,
        wait_threshold: float = 0.2,
    ):
        """
        Initialize extractor configuration.

        Args:
            concurrency: Maximum number of concurrent extract operations
            timeout: Timeout for extract operations in seconds
            wait_threshold: Log warning if waiting exceeds this threshold in seconds

        """
        self.concurrency = concurrency
        self.timeout = timeout
        self.wait_threshold = wait_threshold


class ExtractorPool(metaclass=Singleton):
    """
    Manages process pool and semaphore for video information extraction.

    This class uses the Singleton pattern to ensure only one instance exists.
    """

    def __init__(self):
        """Initialize the extractor pool."""
        self._pool: ProcessPoolExecutor | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._config: ExtractorConfig | None = None

    @classmethod
    def get_instance(cls) -> "ExtractorPool":
        """
        Get the singleton instance.

        Returns:
            ExtractorPool instance

        """
        return cls()

    def _ensure_initialized(self, config: ExtractorConfig) -> None:
        """
        Ensure pool and semaphore are initialized.

        Args:
            config: Extractor configuration

        """
        if self._config is None or self._config.concurrency != config.concurrency:
            self._config = config

        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(config.concurrency)

        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=config.concurrency)
            LOG.info("Initialized extractor process pool with %s workers", config.concurrency)

    def get_pool(self, config: ExtractorConfig) -> ProcessPoolExecutor:
        """
        Get the process pool executor.

        Args:
            config: Extractor configuration

        Returns:
            ProcessPoolExecutor instance

        """
        self._ensure_initialized(config)
        if self._pool is None:
            msg = "Process pool not initialized"
            raise RuntimeError(msg)
        return self._pool

    def get_semaphore(self, config: ExtractorConfig) -> asyncio.Semaphore:
        """
        Get the semaphore for limiting concurrency.

        Args:
            config: Extractor configuration

        Returns:
            asyncio.Semaphore instance

        """
        self._ensure_initialized(config)
        if self._semaphore is None:
            msg = "Semaphore not initialized"
            raise RuntimeError(msg)
        return self._semaphore

    async def shutdown(self) -> None:
        """Shutdown the extractor pool and clean up resources."""
        if self._pool is not None:
            try:
                self._pool.shutdown(wait=False, cancel_futures=False)
                LOG.debug("Extractor process pool shutdown complete")
            except Exception as exc:
                LOG.error("Error shutting down extractor process pool: %s", exc)
            else:
                self._pool = None

        self._semaphore = None
        self._config = None


def _is_picklable(value: Any) -> bool:
    """
    Check if a value can be pickled.

    Args:
        value: Value to check

    Returns:
        bool: True if value can be pickled, False otherwise

    """
    try:
        pickle.dumps(value)
        return True
    except Exception:
        return False


def _sanitize_picklable(value: Any) -> Any:
    """
    Convert a value to a picklable format.

    Args:
        value: Value to sanitize

    Returns:
        Sanitized value that can be pickled

    """
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _sanitize_picklable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_picklable(v) for v in value]
    if _is_picklable(value):
        return value
    return str(value)


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize configuration for use in process pool.

    Removes unpicklable keys and converts values to picklable formats.

    Args:
        config: Configuration dictionary

    Returns:
        Sanitized configuration dictionary

    """
    sanitized: dict[str, Any] = {}
    for key, value in config.items():
        if key in {"logger", "progress_hooks", "postprocessor_hooks", "postprocessors", "post_hooks"}:
            continue
        sanitized[key] = _sanitize_picklable(value)

    return sanitized


def _get_archive_id_dict(url: str) -> dict[str, str | None]:
    """
    Get archive ID for logging purposes.

    Args:
        url: URL to get archive ID for

    Returns:
        Dictionary with id, ie_key, and archive_id

    """
    from app.library.Utils import get_archive_id

    return get_archive_id(url=url)


def extract_info_sync(
    config: dict[str, Any],
    url: str,
    debug: bool = False,
    no_archive: bool = False,
    follow_redirect: bool = False,
    sanitize_info: bool = False,
    capture_logs: int | None = None,
    **kwargs,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """
    Extract video information from a URL.

    Args:
        config: yt-dlp configuration options
        url: URL to extract information from
        debug: Enable debug logging
        no_archive: Disable download archive
        follow_redirect: Follow URL redirects
        sanitize_info: Sanitize the extracted information
        capture_logs: If provided (e.g., logging.WARNING), capture logs at this level.
        **kwargs: Additional arguments

    Returns:
        tuple[dict | None, list[dict]]: Extracted information and captured logs.

    """
    params: dict[str, Any] = {
        **config,
        "simulate": True,
        "color": "no_color",
        "extract_flat": True,
        "skip_download": True,
        "ignoreerrors": True,
        "ignore_no_formats_error": True,
    }

    if debug:
        params["verbose"] = True
    else:
        params["quiet"] = True

    log_wrapper = LogWrapper()
    id_dict: dict[str, str | None] = _get_archive_id_dict(url=url)
    archive_id: str | None = f".{id_dict['id']}" if id_dict.get("id") else None

    log_wrapper.add_target(
        target=logging.getLogger(f"yt-dlp{archive_id if archive_id else '.extract_info'}"),
        level=logging.DEBUG if debug else logging.WARNING,
    )

    captured_logs: list[str] = kwargs.get("captured_logs", [])
    if capture_logs is not None:
        log_wrapper.add_target(
            target=lambda _, msg: captured_logs.append(msg),
            level=capture_logs,
            name="log-capture",
        )

    if log_wrapper.has_targets():
        if "logger" in params:
            log_wrapper.add_target(target=params["logger"], level=logging.DEBUG)

        params["logger"] = log_wrapper

    if kwargs.get("no_log", False):
        params["logger"] = LogWrapper()
        params["quiet"] = True
        params["no_warnings"] = True

    if no_archive and "download_archive" in params:
        del params["download_archive"]

    data: dict[str, Any] | None = YTDLP(params=params).extract_info(url, download=False)

    if data and follow_redirect and "_type" in data and "url" == data["_type"]:
        return extract_info_sync(
            config,
            data["url"],
            debug=debug,
            no_archive=no_archive,
            follow_redirect=follow_redirect,
            sanitize_info=sanitize_info,
            capture_logs=capture_logs,
            captured_logs=captured_logs,
            **kwargs,
        )

    if not data:
        return (data, captured_logs)

    data["is_premiere"] = match_str("media_type=video & duration & is_live", data)
    if not data["is_premiere"]:
        data["is_premiere"] = "video" == data.get("media_type") and "is_upcoming" == data.get("live_status")

    result = YTDLP.sanitize_info(data, remove_private_keys=True) if sanitize_info else data

    return (result, captured_logs)


async def fetch_info(
    config: dict[str, Any],
    url: str,
    debug: bool = False,
    no_archive: bool = False,
    follow_redirect: bool = False,
    sanitize_info: bool = False,
    capture_logs: int | None = None,
    extractor_config: ExtractorConfig | None = None,
    **kwargs,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """
    Extract video information from a URL.

    This function uses a process pool to avoid blocking the event loop.
    If the process pool fails, it falls back to using a thread pool.

    Args:
        config: yt-dlp configuration options
        url: URL to extract information from
        debug: Enable debug logging
        no_archive: Disable download archive
        follow_redirect: Follow URL redirects
        sanitize_info: Sanitize the extracted information
        capture_logs: If provided (e.g., logging.WARNING), capture logs
        extractor_config: Configuration for the extractor
        **kwargs: Additional arguments

    Returns:
        tuple[dict | None, list[dict]]: Extracted information and captured logs.

    """
    if extractor_config is None:
        from app.library.config import Config

        conf = Config.get_instance()
        extractor_config = ExtractorConfig(
            concurrency=conf.extract_info_concurrency,
            timeout=conf.extract_info_timeout,
            wait_threshold=0.2,
        )

    pool_manager: ExtractorPool = ExtractorPool.get_instance()
    semaphore: asyncio.Semaphore = pool_manager.get_semaphore(extractor_config)

    await semaphore.acquire()
    loop = asyncio.get_running_loop()

    safe_config = _sanitize_config(config)

    try:
        try:
            executor: ProcessPoolExecutor = pool_manager.get_pool(extractor_config)

            return await asyncio.wait_for(
                fut=loop.run_in_executor(
                    executor,
                    functools.partial(
                        extract_info_sync,
                        config=safe_config,
                        url=url,
                        debug=debug,
                        no_archive=no_archive,
                        follow_redirect=follow_redirect,
                        sanitize_info=sanitize_info,
                        capture_logs=capture_logs,
                        **kwargs,
                    ),
                ),
                timeout=extractor_config.timeout,
            )

        except Exception as exc:
            LOG.warning("extract_info process pool failed, falling back to thread pool url=%s error=%s", url, exc)
            return await asyncio.wait_for(
                fut=loop.run_in_executor(
                    None,
                    functools.partial(
                        extract_info_sync,
                        config=config,
                        url=url,
                        debug=debug,
                        no_archive=no_archive,
                        follow_redirect=follow_redirect,
                        sanitize_info=sanitize_info,
                        capture_logs=capture_logs,
                        **kwargs,
                    ),
                ),
                timeout=extractor_config.timeout,
            )
    finally:
        semaphore.release()


async def shutdown_extractor() -> None:
    await ExtractorPool.get_instance().shutdown()
