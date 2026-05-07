import logging
from unittest.mock import MagicMock, patch

from app.features.ytdlp.extractor import (
    ExtractorConfig,
    ExtractorPool,
    _get_process_pool_kwargs,
    _ytdlp_logger,
    extract_info_sync,
)


class TestProcessPoolConfiguration:
    def setup_method(self):
        ExtractorPool._reset_singleton()

    def test_uses_fork_context_for_frozen_linux(self, monkeypatch):
        monkeypatch.setattr("app.features.ytdlp.extractor.sys.platform", "linux")
        monkeypatch.setattr("app.features.ytdlp.extractor.sys.frozen", True, raising=False)

        context = object()
        get_context = MagicMock(return_value=context)
        monkeypatch.setattr("app.features.ytdlp.extractor.multiprocessing.get_context", get_context)

        kwargs = _get_process_pool_kwargs()

        assert kwargs == {"mp_context": context}
        get_context.assert_called_once_with("fork")

    def test_default_context_linux(self, monkeypatch):
        monkeypatch.setattr("app.features.ytdlp.extractor.sys.platform", "linux")
        monkeypatch.delattr("app.features.ytdlp.extractor.sys.frozen", raising=False)

        get_context = MagicMock()
        monkeypatch.setattr("app.features.ytdlp.extractor.multiprocessing.get_context", get_context)

        assert _get_process_pool_kwargs() == {}
        get_context.assert_not_called()

    def test_init_pool_kwargs(self, monkeypatch):
        context = object()
        monkeypatch.setattr("app.features.ytdlp.extractor._get_process_pool_kwargs", lambda: {"mp_context": context})

        executor = MagicMock()
        executor_cls = MagicMock(return_value=executor)
        monkeypatch.setattr("app.features.ytdlp.extractor.ProcessPoolExecutor", executor_cls)

        pool = ExtractorPool.get_instance()
        pool._ensure_initialized(ExtractorConfig(concurrency=3))

        executor_cls.assert_called_once_with(max_workers=3, mp_context=context)
        assert pool.get_pool(ExtractorConfig(concurrency=3)) is executor


class TestExtractInfo:
    """Test the extract_info function."""

    @patch("app.features.ytdlp.extractor.YTDLP")
    def test_extract_info_basic(self, mock_ytdlp_class):
        """Test basic extract_info functionality."""
        mock_ytdlp = MagicMock()
        mock_ytdlp.extract_info.return_value = {"title": "Test Video", "id": "test123"}
        mock_ytdlp_class.return_value = mock_ytdlp

        config = {"quiet": True}
        url = "https://example.com/video"

        (result, logs) = extract_info_sync(config, url)
        assert isinstance(result, dict), "Result should be a dictionary"
        assert isinstance(logs, list), "Logs should be a list"
        mock_ytdlp.extract_info.assert_called_once()

    @patch("app.features.ytdlp.extractor.YTDLP")
    def test_extract_info_with_debug(self, mock_ytdlp_class):
        """Test extract_info with debug enabled."""
        mock_ytdlp = MagicMock()
        mock_ytdlp.extract_info.return_value = {"title": "Test Video"}
        mock_ytdlp_class.return_value = mock_ytdlp

        config = {}
        url = "https://example.com/video"

        (result, logs) = extract_info_sync(config, url, debug=True)
        assert isinstance(result, dict), "Result should be a dictionary"
        assert isinstance(logs, list), "Logs should be a list"

    @patch("app.features.ytdlp.extractor.YTDLP")
    def test_extract_info_mirrors_debug_to_console(self, mock_ytdlp_class):
        seen: list[tuple[int, str]] = []

        def fake_extract_info(url, download=False):  # noqa: ARG001
            logger = mock_ytdlp_class.call_args.kwargs["params"]["logger"]
            logger.debug("[generic_browser] Using remote browser for https://example.com/video")
            logger.debug("[debug] [generic_browser] Loading page https://example.com/video")
            logger.warning("[generic_browser] Browser fallback warning")
            return {"title": "Test Video", "id": "test123"}

        mock_ytdlp = MagicMock()
        mock_ytdlp.extract_info.side_effect = fake_extract_info
        mock_ytdlp_class.return_value = mock_ytdlp

        logger = logging.getLogger("yt-dlp.extract_info")
        with patch.object(
            logger, "info", side_effect=lambda msg, *a, **k: seen.append((logging.INFO, msg % a if a else msg))
        ):
            with patch.object(
                logger,
                "debug",
                side_effect=lambda msg, *a, **k: seen.append((logging.DEBUG, msg % a if a else msg)),
            ):
                with patch.object(
                    logger,
                    "log",
                    side_effect=lambda level, msg, *a, **k: seen.append((level, msg % a if a else msg)),
                ):
                    (result, logs) = extract_info_sync(
                        {}, "https://example.com/video", debug=True, capture_logs=logging.WARNING
                    )

        assert result["id"] == "test123"
        assert logs == ["[generic_browser] Browser fallback warning"]
        assert (logging.INFO, "[generic_browser] Using remote browser for https://example.com/video") in seen
        assert (logging.DEBUG, "[generic_browser] Loading page https://example.com/video") in seen
        assert (logging.WARNING, "[generic_browser] Browser fallback warning") in seen

    @patch("app.features.ytdlp.extractor.YTDLP")
    def test_extract_info_mirrors_screen_logs_without_debug(self, mock_ytdlp_class):
        seen: list[tuple[int, str]] = []

        def fake_extract_info(url, download=False):  # noqa: ARG001
            logger = mock_ytdlp_class.call_args.kwargs["params"]["logger"]
            logger.debug("[generic_browser] Using remote browser for https://example.com/video")
            logger.warning("[generic_browser] Browser fallback warning")
            return {"title": "Test Video", "id": "test123"}

        mock_ytdlp = MagicMock()
        mock_ytdlp.extract_info.side_effect = fake_extract_info
        mock_ytdlp_class.return_value = mock_ytdlp

        logger = logging.getLogger("yt-dlp.extract_info")
        with patch.object(
            logger, "info", side_effect=lambda msg, *a, **k: seen.append((logging.INFO, msg % a if a else msg))
        ):
            with patch.object(
                logger,
                "log",
                side_effect=lambda level, msg, *a, **k: seen.append((level, msg % a if a else msg)),
            ):
                (result, logs) = extract_info_sync(
                    {}, "https://example.com/video", debug=False, capture_logs=logging.WARNING
                )

        assert result["id"] == "test123"
        assert logs == ["[generic_browser] Browser fallback warning"]
        assert (logging.INFO, "[generic_browser] Using remote browser for https://example.com/video") in seen
        assert (logging.WARNING, "[generic_browser] Browser fallback warning") in seen


class TestYtdlpLogger:
    def test_debug_prefix_uses_debug(self) -> None:
        logger = MagicMock()

        _ytdlp_logger(logger)(logging.DEBUG, "[debug] hello")

        logger.debug.assert_called_once_with("hello")

    def test_screen_style_debug_uses_info(self) -> None:
        logger = MagicMock()

        _ytdlp_logger(logger)(logging.DEBUG, "screen line")

        logger.info.assert_called_once_with("screen line")
