from unittest.mock import MagicMock, patch

from app.features.ytdlp.extractor import ExtractorConfig, ExtractorPool, _get_process_pool_kwargs, extract_info_sync


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

    def test_uses_default_context_when_not_frozen_linux(self, monkeypatch):
        monkeypatch.setattr("app.features.ytdlp.extractor.sys.platform", "linux")
        monkeypatch.delattr("app.features.ytdlp.extractor.sys.frozen", raising=False)

        get_context = MagicMock()
        monkeypatch.setattr("app.features.ytdlp.extractor.multiprocessing.get_context", get_context)

        assert _get_process_pool_kwargs() == {}
        get_context.assert_not_called()

    def test_initializes_process_pool_with_context_kwargs(self, monkeypatch):
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
