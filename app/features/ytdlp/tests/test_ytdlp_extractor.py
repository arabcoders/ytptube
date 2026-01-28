from unittest.mock import MagicMock, patch

from app.features.ytdlp.extractor import extract_info_sync


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
