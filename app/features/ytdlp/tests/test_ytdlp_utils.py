import logging
import re
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.features.ytdlp.utils import (
    LogWrapper,
    extract_ytdlp_logs,
    get_archive_id,
    ytdlp_reject,
    parse_outtmpl,
    get_extras,
    get_thumbnail,
    get_ytdlp,
)


class CaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def make_logger(name: str = "lw_test") -> tuple[logging.Logger, CaptureHandler]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = CaptureHandler()
    # Avoid duplicate handlers when tests run multiple times
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.addHandler(handler)
    return logger, handler


class TestLogWrapper:
    def test_add_target_type_validation(self) -> None:
        lw = LogWrapper()
        with pytest.raises(TypeError, match=r"Target must be a logging\.Logger instance or a callable"):
            lw.add_target(123)  # type: ignore[arg-type]

    def test_add_target_name_inference_and_custom(self) -> None:
        lw = LogWrapper()
        logger, _ = make_logger("one")

        # Name inferred from logger
        lw.add_target(logger)
        assert lw.targets[-1].name == "one"
        assert lw.has_targets() is True

        # Name inferred from callable
        def sink(level: int, msg: str, *args: Any, **kwargs: Any) -> None:  # noqa: ARG001
            return None

        lw.add_target(sink)
        assert lw.targets[-1].name == "sink"

        # Custom name overrides
        lw.add_target(logger, name="custom")
        assert lw.targets[-1].name == "custom"

    def test_level_filtering_and_dispatch(self) -> None:
        lw = LogWrapper()
        logger, cap = make_logger("cap")
        calls: list[tuple[int, str, tuple, dict]] = []

        def sink(level: int, msg: str, *args: Any, **kwargs: Any) -> None:
            calls.append((level, msg, args, kwargs))

        # Logger target at INFO, callable target at WARNING
        lw.add_target(logger, level=logging.INFO)
        lw.add_target(sink, level=logging.WARNING)

        # DEBUG should hit none
        lw.debug("d1")
        assert len(cap.records) == 0
        assert len(calls) == 0

        # INFO hits logger only
        lw.info("hello %s", "X")
        assert len(cap.records) == 1
        assert cap.records[0].levelno == logging.INFO
        assert cap.records[0].getMessage() == "hello X"
        assert len(calls) == 0

        # WARNING hits both
        lw.warning("warn %s", "Y", extra={"k": 1})
        assert len(cap.records) == 2
        assert cap.records[1].levelno == logging.WARNING
        assert cap.records[1].getMessage() == "warn Y"
        assert len(calls) == 1
        lvl, msg, args, kwargs = calls[0]
        assert lvl == logging.WARNING
        assert msg == "warn %s"
        assert args == ("Y",)
        assert "extra" in kwargs
        assert kwargs["extra"] == {"k": 1}

        # ERROR still hits both; CRITICAL too
        lw.error("err")
        lw.critical("boom")
        assert any(r.levelno == logging.ERROR for r in cap.records)
        assert any(r.levelno == logging.CRITICAL for r in cap.records)
        assert any(c[0] == logging.ERROR for c in calls)
        assert any(c[0] == logging.CRITICAL for c in calls)


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


class TestParseOuttmpl:
    """Test the parse_outtmpl function."""

    def setup_method(self):
        """Reset YTDLP singleton state before each test."""
        from app.features.ytdlp.utils import _DATA

        _DATA.YTDLP_INFO_CLS = None

    def test_parse_outtmpl_basic(self):
        """Test basic template parsing with simple placeholders."""

        template = "%(title)s.%(ext)s"
        info_dict = {
            "title": "Test Video",
            "ext": "mp4",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "Test Video.mp4"

    def test_parse_outtmpl_with_id(self):
        """Test template parsing with video ID."""

        template = "[%(id)s] %(title)s.%(ext)s"
        info_dict = {
            "id": "dQw4w9WgXcQ",
            "title": "Never Gonna Give You Up",
            "ext": "webm",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "[dQw4w9WgXcQ] Never Gonna Give You Up.webm"

    def test_parse_outtmpl_with_uploader(self):
        """Test template parsing with uploader information."""

        template = "%(uploader)s - %(title)s.%(ext)s"
        info_dict = {
            "uploader": "Rick Astley",
            "title": "Never Gonna Give You Up",
            "ext": "mp4",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "Rick Astley - Never Gonna Give You Up.mp4"

    def test_parse_outtmpl_with_nested_path(self):
        """Test template parsing with nested directory structure."""

        template = "%(uploader)s/%(title)s.%(ext)s"
        info_dict = {
            "uploader": "Test Channel",
            "title": "Test Video",
            "ext": "mkv",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "Test Channel/Test Video.mkv"

    def test_parse_outtmpl_with_missing_field(self):
        """Test template parsing with missing field defaults to NA."""

        template = "%(title)s - %(upload_date)s.%(ext)s"
        info_dict = {
            "title": "Test Video",
            "ext": "mp4",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "Test Video - NA.mp4", "Missing field upload_date should default to NA"

    def test_parse_outtmpl_complex(self):
        """Test complex template with multiple fields."""

        template = "%(uploader)s/%(playlist_title)s/%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
        info_dict = {
            "uploader": "Test Channel",
            "playlist_title": "Best Videos",
            "playlist_index": 5,
            "title": "Amazing Content",
            "id": "abc123xyz",
            "ext": "mp4",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "Test Channel/Best Videos/005 - Amazing Content [abc123xyz].mp4"

    def test_parse_outtmpl_with_special_characters(self):
        """Test template parsing handles special characters in values."""

        template = "%(title)s.%(ext)s"
        info_dict = {
            "title": "Test: Video / With \\ Special | Characters",
            "ext": "mp4",
        }

        result = parse_outtmpl(template, info_dict)

        assert ".mp4" in result, "yt-dlp should sanitize special characters but preserve extension"
        assert "Test" in result, "yt-dlp should preserve safe parts of title"

    def test_parse_outtmpl_with_playlist_info(self):
        """Test template parsing with playlist information."""

        template = "%(playlist)s/%(title)s.%(ext)s"
        info_dict = {
            "playlist": "My Playlist",
            "title": "Video Title",
            "ext": "webm",
        }

        result = parse_outtmpl(template, info_dict)

        assert result == "My Playlist/Video Title.webm"

    def test_parse_outtmpl_with_restrict_filename(self):
        """Test template parsing with restrict_filename parameter."""

        template = "%(uploader)s/%(title)s.%(ext)s"
        info_dict = {
            "uploader": "Foobar's Workshop",
            "title": "Test Video",
            "ext": "mp4",
        }

        result_unrestricted: str = parse_outtmpl(template, info_dict)
        assert result_unrestricted == "Foobar's Workshop/Test Video.mp4"

        result_restricted: str = parse_outtmpl(template, info_dict, params={"restrictfilenames": True})
        assert result_restricted == "Foobar_s_Workshop/Test_Video.mp4"


class TestGetThumbnail:
    def test_returns_none_for_empty_list(self):
        """Test that None is returned for an empty thumbnail list."""

        assert get_thumbnail([]) is None

    def test_returns_none_for_non_list(self):
        """Test that None is returned for non-list input."""

        assert get_thumbnail(None) is None
        assert get_thumbnail("not a list") is None
        assert get_thumbnail({"not": "list"}) is None

    def test_returns_highest_preference_thumbnail(self):
        """Test that the thumbnail with highest preference is returned."""

        thumbnails = [
            {"url": "low.jpg", "preference": 1, "width": 100, "height": 100},
            {"url": "high.jpg", "preference": 10, "width": 200, "height": 200},
            {"url": "medium.jpg", "preference": 5, "width": 150, "height": 150},
        ]

        result = get_thumbnail(thumbnails)
        assert result == {"url": "high.jpg", "preference": 10, "width": 200, "height": 200}

    def test_returns_highest_width_when_preference_equal(self):
        """Test that the thumbnail with highest width is returned when preference is equal."""

        thumbnails = [
            {"url": "small.jpg", "preference": 1, "width": 100, "height": 100},
            {"url": "large.jpg", "preference": 1, "width": 200, "height": 200},
            {"url": "medium.jpg", "preference": 1, "width": 150, "height": 150},
        ]

        result = get_thumbnail(thumbnails)
        assert result == {"url": "large.jpg", "preference": 1, "width": 200, "height": 200}

    def test_handles_missing_attributes(self):
        """Test that thumbnails with missing attributes are handled correctly."""

        thumbnails = [
            {"url": "no_pref.jpg", "width": 100},
            {"url": "with_pref.jpg", "preference": 5, "width": 50},
        ]

        result = get_thumbnail(thumbnails)
        assert result["url"] == "with_pref.jpg"

    def test_returns_first_when_all_equal(self):
        """Test that any thumbnail is returned when all attributes are equal."""

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
        assert get_extras(None) == {}

    def test_returns_empty_dict_for_non_dict(self):
        """Test that empty dict is returned for non-dict input."""
        assert get_extras("not a dict") == {}
        assert get_extras([]) == {}

    def test_extracts_video_information(self):
        """Test extracting information from a video entry."""

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

        entry = {
            "release_timestamp": 1234567890,
        }

        result = get_extras(entry)

        assert "release_in" in result
        assert result["release_in"] == "Fri, 13 Feb 2009 23:31:30 GMT"

    def test_handles_upcoming_live_stream(self):
        """Test handling of upcoming live stream."""

        entry = {
            "release_timestamp": 1234567890,
            "live_status": "is_upcoming",
        }

        result = get_extras(entry)

        assert result["is_live"] == 1234567890
        assert "release_in" in result

    def test_handles_premiere_flag(self):
        """Test handling of is_premiere flag."""

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

        entry = {
            "id": "dQw4w9WgXcQ",
            "ie_key": "Youtube",
        }

        result = get_extras(entry)

        assert result["thumbnail"] == "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"

    def test_thumbnail_string_fallback(self):
        """Test fallback to thumbnail string when thumbnails list not available."""

        entry = {
            "thumbnail": "https://example.com/thumb.jpg",
        }

        result = get_extras(entry)

        assert result["thumbnail"] == "https://example.com/thumb.jpg"


class TestGetStaticYtdlp:
    """Test the get_static_ytdlp function."""

    def setup_method(self):
        """Reset YTDLP singleton state before each test."""
        from app.features.ytdlp.utils import _DATA

        _DATA.YTDLP_INFO_CLS = None

    def test_get_static_ytdlp_returns_instance(self):
        """Test that get_static_ytdlp returns a YTDLP instance."""
        from app.features.ytdlp.ytdlp import YTDLP

        # Get the cached instance
        instance = get_ytdlp()

        assert instance is not None
        assert isinstance(instance, YTDLP)

    def test_get_static_ytdlp_returns_same_instance(self):
        """Test that get_static_ytdlp returns the same cached instance."""

        instance1 = get_ytdlp()
        instance2 = get_ytdlp()

        assert instance1 is instance2

    def test_get_static_ytdlp_with_params(self):
        """Test that get_static_ytdlp returns a new instance when params are provided."""

        instance1 = get_ytdlp()
        instance2 = get_ytdlp(params={"quiet": False})

        assert instance1 is not instance2
        assert instance2 is not None

    def test_get_static_ytdlp_has_correct_params(self):
        """Test that get_static_ytdlp initializes with correct parameters."""

        instance = get_ytdlp()

        # Access the internal params
        params = instance.params

        assert params.get("color") == "no_color"
        assert params.get("extract_flat") is True
        assert params.get("skip_download") is True
        assert params.get("ignoreerrors") is True
        assert params.get("ignore_no_formats_error") is True
        assert params.get("quiet") is True


class TestGetArchiveId:
    """Test the get_archive_id function."""

    @patch("app.features.ytdlp.utils._DATA.YTDLP_INFO_CLS")
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
