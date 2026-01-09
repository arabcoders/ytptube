"""Tests for YTDLPOpts class."""

from unittest.mock import Mock, patch

import pytest

from app.library.Presets import Preset
from app.library.YTDLPOpts import YTDLPOpts


class TestYTDLPOpts:
    """Test the YTDLPOpts class."""

    def test_constructor_initializes_correctly(self):
        """Test that YTDLPOpts constructor initializes all attributes."""
        with patch("app.library.YTDLPOpts.Config") as mock_config:
            mock_config_instance = Mock()
            mock_config.get_instance.return_value = mock_config_instance

            opts = YTDLPOpts()

            assert opts._config is mock_config_instance
            assert opts._item_opts == {}
            assert opts._preset_opts == {}
            assert opts._item_cli == []
            assert opts._preset_cli == ""

    def test_get_instance_returns_reset_instance(self):
        """Test that get_instance returns a reset YTDLPOpts instance."""
        with patch("app.library.YTDLPOpts.Config"):
            opts = YTDLPOpts.get_instance()

            assert isinstance(opts, YTDLPOpts)
            assert opts._item_opts == {}
            assert opts._preset_opts == {}
            assert opts._item_cli == []
            assert opts._preset_cli == ""

    def test_add_cli_with_valid_args(self):
        """Test adding valid CLI arguments."""
        with patch("app.library.YTDLPOpts.Config"), patch("app.library.YTDLPOpts.arg_converter") as mock_converter:
            mock_converter.return_value = {"format": "best"}
            opts = YTDLPOpts()

            result = opts.add_cli("--format best", from_user=False)

            assert result is opts  # Returns self for chaining
            assert "--format best" in opts._item_cli
            mock_converter.assert_called_once_with(args="--format best", level=False)

    def test_add_cli_with_invalid_args_raises_error(self):
        """Test that invalid CLI arguments raise ValueError."""
        with patch("app.library.YTDLPOpts.Config"), patch("app.library.YTDLPOpts.arg_converter") as mock_converter:
            mock_converter.side_effect = Exception("Invalid argument")
            opts = YTDLPOpts()

            with pytest.raises(ValueError, match="Invalid command options for yt-dlp were given"):
                opts.add_cli("--invalid-arg", from_user=True)

    def test_add_cli_with_empty_args_returns_self(self):
        """Test that empty or invalid args return self without processing."""
        with patch("app.library.YTDLPOpts.Config"):
            opts = YTDLPOpts()

            # Test empty string
            result1 = opts.add_cli("", from_user=False)
            assert result1 is opts
            assert len(opts._item_cli) == 0

            # Test short string
            result2 = opts.add_cli("a", from_user=False)
            assert result2 is opts
            assert len(opts._item_cli) == 0

            # Test non-string (this should be handled gracefully)
            result3 = opts.add_cli(123, from_user=False)  # type: ignore
            assert result3 is opts
            assert len(opts._item_cli) == 0

    def test_add_with_valid_config(self):
        """Test adding configuration options."""
        with patch("app.library.YTDLPOpts.Config"):
            opts = YTDLPOpts()

            config = {"format": "best", "quality": "720p"}
            result = opts.add(config, from_user=False)

            assert result is opts
            assert opts._item_opts["format"] == "best"
            assert opts._item_opts["quality"] == "720p"

    def test_add_with_user_config_filters_bad_options(self):
        """Test that user config filters out dangerous options."""
        with (
            patch("app.library.YTDLPOpts.Config"),
            patch("app.library.YTDLPOpts.REMOVE_KEYS", [{"paths": "-P, --paths", "outtmpl": "-o, --output"}]),
        ):
            opts = YTDLPOpts()

            config = {
                "format": "best",
                "paths": "/dangerous/path",  # Should be filtered
                "outtmpl": "dangerous_template",  # Should be filtered
                "quality": "720p",
            }

            result = opts.add(config, from_user=True)

            assert result is opts
            assert opts._item_opts["format"] == "best"
            assert opts._item_opts["quality"] == "720p"
            assert "paths" not in opts._item_opts
            assert "outtmpl" not in opts._item_opts

    def test_preset_with_valid_preset(self):
        """Test applying a valid preset."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.Presets") as mock_presets,
            patch("app.library.YTDLPOpts.arg_converter") as mock_converter,
        ):
            # Mock config
            mock_config_instance = Mock()
            mock_config_instance.config_path = "/test/config"
            mock_config_instance.download_path = "/test/downloads"
            mock_config_instance.temp_path = "/test/temp"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config.get_instance.return_value = mock_config_instance

            # Mock preset
            mock_preset = Mock(spec=Preset)
            mock_preset.id = "test_preset"
            mock_preset.name = "Test Preset"
            mock_preset.cli = "--format best"
            mock_preset.cookies = None
            mock_preset.template = "custom_template"
            mock_preset.folder = "custom_folder"

            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = mock_preset
            mock_presets.get_instance.return_value = mock_presets_instance

            mock_converter.return_value = {"format": "best"}

            with patch("app.library.YTDLPOpts.calc_download_path") as mock_calc_path:
                mock_calc_path.return_value = "/test/downloads/custom_folder"

                opts = YTDLPOpts()
                result = opts.preset("test_preset")

                assert result is opts
                assert opts._preset_cli == "--format best"
                assert opts._preset_opts["outtmpl"]["default"] == "custom_template"
                assert opts._preset_opts["paths"]["home"] == "/test/downloads/custom_folder"

    def test_preset_with_nonexistent_preset(self):
        """Test applying a nonexistent preset returns self."""
        with patch("app.library.YTDLPOpts.Config"), patch("app.library.YTDLPOpts.Presets") as mock_presets:
            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = None
            mock_presets.get_instance.return_value = mock_presets_instance

            opts = YTDLPOpts()
            result = opts.preset("nonexistent")

            assert result is opts
            assert opts._preset_cli == ""
            assert opts._preset_opts == {}

    def test_preset_with_cookies_creates_file(self):
        """Test that preset with cookies creates cookie file."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.Presets") as mock_presets,
        ):
            # Mock config
            mock_config_instance = Mock()
            mock_config_instance.config_path = "/test/config"
            mock_config.get_instance.return_value = mock_config_instance

            # Mock preset with cookies
            mock_preset = Mock(spec=Preset)
            mock_preset.id = "cookie_preset"
            mock_preset.name = "Cookie Preset"
            mock_preset.cli = None
            mock_preset.cookies = "cookie_data"
            mock_preset.template = None
            mock_preset.folder = None

            # Mock cookie_file path
            mock_cookie_path = Mock()
            mock_cookie_path.exists.return_value = True
            mock_cookie_path.__str__ = Mock(return_value="/test/config/cookies/cookie_preset.txt")
            mock_preset.get_cookies_file.return_value = mock_cookie_path

            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = mock_preset
            mock_presets.get_instance.return_value = mock_presets_instance

            opts = YTDLPOpts()
            opts.preset("cookie_preset")

            # Check that the cookie file would be created at the right path
            expected_path = "/test/config/cookies/cookie_preset.txt"
            assert opts._preset_opts["cookiefile"] == expected_path
            mock_preset.get_cookies_file.assert_called_once_with(config=mock_config_instance)

    def test_preset_with_invalid_cli_raises_error(self):
        """Test that preset with invalid CLI raises ValueError."""
        with (
            patch("app.library.YTDLPOpts.Config"),
            patch("app.library.YTDLPOpts.Presets") as mock_presets,
            patch("app.library.YTDLPOpts.arg_converter") as mock_converter,
        ):
            mock_preset = Mock(spec=Preset)
            mock_preset.id = "bad_preset"
            mock_preset.name = "Bad Preset"
            mock_preset.cli = "--invalid-option"
            mock_preset.cookies = None
            mock_preset.template = None
            mock_preset.folder = None

            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = mock_preset
            mock_presets.get_instance.return_value = mock_presets_instance

            mock_converter.side_effect = Exception("Invalid CLI")

            opts = YTDLPOpts()

            with pytest.raises(ValueError, match="Invalid preset 'Bad Preset' command options for yt-dlp"):
                opts.preset("bad_preset")

    def test_get_all_with_default_options(self):
        """Test get_all returns correct default options."""
        with patch("app.library.YTDLPOpts.Config") as mock_config:
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = False
            mock_config.get_instance.return_value = mock_config_instance

            with patch("app.library.YTDLPOpts.merge_dict") as mock_merge:
                mock_merge.return_value = {
                    "paths": {"home": "/downloads", "temp": "/temp"},
                    "outtmpl": {"default": "default_template", "chapter": "chapter_template"},
                }

                opts = YTDLPOpts()
                result = opts.get_all(keep=True)

                assert result["paths"]["home"] == "/downloads"
                assert result["outtmpl"]["default"] == "default_template"

    def test_get_all_processes_cli_arguments(self):
        """Test get_all processes CLI arguments correctly."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.arg_converter") as mock_converter,
            patch("app.library.YTDLPOpts.merge_dict") as mock_merge,
        ):
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = False
            mock_config_instance.get_replacers.return_value = {"home": "/test"}
            mock_config.get_instance.return_value = mock_config_instance

            mock_converter.return_value = {"format": "best"}
            mock_merge.return_value = {"format": "best"}

            opts = YTDLPOpts()
            opts._item_cli = ["--format best"]
            opts._preset_cli = "--quality 720p"

            opts.get_all(keep=True)

            # Should join CLI args and process replacers
            expected_cli = "--quality 720p\n--format best"
            mock_converter.assert_called_once_with(args=expected_cli, level=True)

    def test_get_all_handles_format_special_cases(self):
        """Test get_all handles special format values correctly."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.merge_dict") as mock_merge,
        ):
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = False
            mock_config.get_instance.return_value = mock_config_instance

            opts = YTDLPOpts()

            # Test "not_set" format
            mock_merge.return_value = {"format": "not_set"}
            result = opts.get_all(keep=True)
            assert result["format"] is None

            # Test "default" format
            mock_merge.return_value = {"format": "default"}
            result = opts.get_all(keep=True)
            assert result["format"] is None

            # Test "best" format
            mock_merge.return_value = {"format": "best"}
            result = opts.get_all(keep=True)
            assert result["format"] is None

            # Test "-best" format (should remove leading dash)
            mock_merge.return_value = {"format": "-best"}
            result = opts.get_all(keep=True)
            assert result["format"] == "best"

    def test_get_all_with_invalid_cli_raises_error(self):
        """Test get_all raises error for invalid CLI arguments."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.arg_converter") as mock_converter,
        ):
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = False
            mock_config_instance.get_replacers.return_value = {}
            mock_config.get_instance.return_value = mock_config_instance

            mock_converter.side_effect = Exception("Invalid CLI")

            opts = YTDLPOpts()
            opts._item_cli = ["--invalid-arg"]

            with pytest.raises(ValueError, match="Invalid command options for yt-dlp were given"):
                opts.get_all()

    def test_get_all_resets_unless_keep_true(self):
        """Test get_all resets instance unless keep=True."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.merge_dict") as mock_merge,
        ):
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = False
            mock_config_instance.get_replacers.return_value = {}  # Return empty dict
            mock_config.get_instance.return_value = mock_config_instance

            mock_merge.return_value = {}

            opts = YTDLPOpts()
            opts._item_opts = {"test": "value"}
            opts._item_cli = ["--test"]

            # Test with keep=False (default)
            opts.get_all(keep=False)
            assert opts._item_opts == {}
            assert opts._item_cli == []

            # Reset test data
            opts._item_opts = {"test": "value"}
            opts._item_cli = ["--test"]

            # Test with keep=True
            opts.get_all(keep=True)
            assert opts._item_opts == {"test": "value"}
            assert opts._item_cli == ["--test"]

    def test_reset_clears_all_options(self):
        """Test reset clears all internal state."""
        with patch("app.library.YTDLPOpts.Config"):
            opts = YTDLPOpts()

            # Set some state
            opts._item_opts = {"format": "best"}
            opts._preset_opts = {"quality": "720p"}
            opts._item_cli = ["--format best"]
            opts._preset_cli = "--quality 720p"

            result = opts.reset()

            assert result is opts
            assert opts._item_opts == {}
            assert opts._preset_opts == {}
            assert opts._item_cli == []
            assert opts._preset_cli == ""

    def test_method_chaining(self):
        """Test that methods support chaining."""
        with (
            patch("app.library.YTDLPOpts.Config"),
            patch("app.library.YTDLPOpts.arg_converter"),
            patch("app.library.YTDLPOpts.Presets") as mock_presets,
        ):
            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = None
            mock_presets.get_instance.return_value = mock_presets_instance

            opts = YTDLPOpts()

            # Test chaining
            result = opts.add_cli("--format best").add({"quality": "720p"}).preset("nonexistent").reset()

            assert result is opts

    def test_debug_logging(self):
        """Test debug logging when enabled."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.merge_dict") as mock_merge,
            patch("app.library.YTDLPOpts.LOG") as mock_log,
        ):
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = True  # Enable debug
            mock_config.get_instance.return_value = mock_config_instance

            test_data = {"format": "best"}
            mock_merge.return_value = test_data

            opts = YTDLPOpts()
            opts.get_all(keep=True)

            mock_log.debug.assert_called_once_with(f"Final yt-dlp options: '{test_data!s}'.")

    def test_cookie_loading_error_handling(self):
        """Test error handling when cookie loading fails."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.Presets") as mock_presets,
            patch("app.library.YTDLPOpts.LOG") as mock_log,
        ):
            # Mock config
            mock_config_instance = Mock()
            mock_config_instance.config_path = "/test/config"
            mock_config.get_instance.return_value = mock_config_instance

            # Mock preset with cookies
            mock_preset = Mock(spec=Preset)
            mock_preset.id = "cookie_preset"
            mock_preset.name = "Cookie Preset"
            mock_preset.cli = None
            mock_preset.cookies = "invalid_cookie_data"
            mock_preset.template = None
            mock_preset.folder = None

            # Mock cookie loading failure
            mock_preset.get_cookies_file.side_effect = ValueError("Invalid cookies")

            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = mock_preset
            mock_presets.get_instance.return_value = mock_presets_instance

            opts = YTDLPOpts()
            opts.preset("cookie_preset")

            # Should log error but not raise
            mock_log.error.assert_called_once()
            error_args = mock_log.error.call_args[0][0]
            assert "Failed to load" in error_args
            assert "Cookie Preset" in error_args

            assert "cookiefile" not in opts._preset_opts, "cookiefile should not be set"

    def test_replacer_substitution_in_cli(self):
        """Test that CLI arguments get replacer substitution."""
        with (
            patch("app.library.YTDLPOpts.Config") as mock_config,
            patch("app.library.YTDLPOpts.arg_converter") as mock_converter,
            patch("app.library.YTDLPOpts.merge_dict") as mock_merge,
        ):
            mock_config_instance = Mock()
            mock_config_instance.download_path = "/downloads"
            mock_config_instance.temp_path = "/temp"
            mock_config_instance.output_template = "default_template"
            mock_config_instance.output_template_chapter = "chapter_template"
            mock_config_instance.debug = False
            mock_config_instance.get_replacers.return_value = {"home": "/actual/home", "user": "testuser"}
            mock_config.get_instance.return_value = mock_config_instance

            mock_converter.return_value = {"output": "/actual/home/testuser"}
            mock_merge.return_value = {}

            opts = YTDLPOpts()
            opts._item_cli = ["--output %(home)s/%(user)s"]

            opts.get_all(keep=True)

            # Should replace %(home)s and %(user)s
            expected_cli = "--output /actual/home/testuser"
            mock_converter.assert_called_once_with(args=expected_cli, level=True)


class TestARGSMerger:
    """Test the ARGSMerger class."""

    def test_constructor_initializes_empty_args(self):
        """Test that ARGSMerger constructor initializes with empty args list."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()

        assert merger.args == []

    def test_add_valid_args(self):
        """Test adding valid command-line arguments."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        result = merger.add("--format best")

        assert result is merger  # Returns self for chaining
        assert merger.args == ["--format", "best"]

    def test_add_filters_comment_lines(self):
        """Test that comment lines (starting with #) are filtered out."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        cli_with_comments = """--format best
# This is a comment
--output test.mp4
#Another comment without space
--no-playlist"""

        merger.add(cli_with_comments)

        assert "#" not in merger.as_string(), "Comments should be filtered out"
        assert "This is a comment" not in merger.as_string()
        assert "Another comment" not in merger.as_string()

        assert "--format" in merger.args, "Valid options should remain"
        assert "best" in merger.args
        assert "--output" in merger.args
        assert "test.mp4" in merger.args
        assert "--no-playlist" in merger.args

    def test_add_filters_indented_comment_lines(self):
        """Test that indented comment lines are filtered out."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        cli_with_indented_comments = """--format best
    # Indented comment with spaces
		# Indented comment with tabs
  --output test.mp4
    # Another indented comment
--socket-timeout 30"""

        merger.add(cli_with_indented_comments)

        result = merger.as_string()
        assert "# Indented comment with spaces" not in result, "Comments should be filtered out"
        assert "# Indented comment with tabs" not in result
        assert "# Another indented comment" not in result

        assert "--format" in merger.args, "Valid options should remain"
        assert "--output" in merger.args
        assert "--socket-timeout" in merger.args

    def test_add_filters_complex_commented_extractor_args(self):
        """Test filtering of complex real-world commented extractor-args."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        cli_with_complex_comments = """--extractor-args "youtube:player-client=default,tv,mweb,-web_safari;formats=incomplete"
#--extractor-args "youtube:player-client=default,tv,mweb;-formats=incomplete;player_js_version=actual"
#--extractor-args "youtube:player-client=default,tv,mweb,web_safari;formats=incomplete"
--socket-timeout 60"""

        merger.add(cli_with_complex_comments)

        result = merger.as_string()

        assert "player_js_version=actual" not in result, "Commented lines should be filtered out completely"
        assert "mweb,web_safari;formats=incomplete" not in result, (
            "Check the specific commented variant (with comma before web_safari, not dash)"
        )

        assert "youtube:player-client=default,tv,mweb,-web_safari;formats=incomplete" in result, (
            "Valid extractor-args should remain (with -web_safari, note the dash)"
        )
        assert "--socket-timeout" in merger.args
        assert "60" in merger.args

    def test_add_multiple_args_with_chaining(self):
        """Test adding multiple arguments using method chaining."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format best").add("--output test.mp4").add("--no-playlist")

        assert merger.args == ["--format", "best", "--output", "test.mp4", "--no-playlist"]

    def test_add_args_with_quotes(self):
        """Test adding arguments containing quoted strings."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add('--output "%(title)s.%(ext)s"')

        assert merger.args == ["--output", "%(title)s.%(ext)s"]

    def test_add_complex_args(self):
        """Test adding complex arguments with multiple values."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format 'bestvideo[height<=1080]+bestaudio/best'")

        assert "--format" in merger.args
        assert "bestvideo[height<=1080]+bestaudio/best" in merger.args

    def test_add_empty_string_returns_self(self):
        """Test that adding empty string returns self without modifying args."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        result = merger.add("")

        assert result is merger
        assert merger.args == []

    def test_add_short_string_returns_self(self):
        """Test that adding short string (len < 2) returns self without modifying args."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        result = merger.add("a")

        assert result is merger
        assert merger.args == []

    def test_add_non_string_returns_self(self):
        """Test that adding non-string returns self without modifying args."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        result = merger.add(123)  # type: ignore

        assert result is merger
        assert merger.args == []

    def test_as_string(self):
        """Test converting args to string."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format best").add("--output test.mp4")

        result = merger.as_string()

        assert result == "--format best --output test.mp4"

    def test_str_method(self):
        """Test __str__ method."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format best").add("--output test.mp4")

        result = str(merger)

        assert result == "--format best --output test.mp4"

    def test_as_dict(self):
        """Test converting args to dict."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format best").add("--output test.mp4")

        result = merger.as_dict()

        assert isinstance(result, list)
        assert result == ["--format", "best", "--output", "test.mp4"]

    def test_as_ytdlp(self):
        """Test converting args to yt-dlp JSON options."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format best")

        with patch("app.library.YTDLPOpts.arg_converter") as mock_converter:
            mock_converter.return_value = {"format": "best"}

            result = merger.as_ytdlp()

            assert result == {"format": "best"}
            mock_converter.assert_called_once_with(args="--format best", level=False)

    def test_get_instance(self):
        """Test get_instance static method."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger.get_instance()

        assert isinstance(merger, ARGSMerger)
        assert merger.args == []

    def test_reset(self):
        """Test reset method clears args."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add("--format best").add("--output test.mp4")

        assert len(merger.args) > 0

        result = merger.reset()

        assert result is merger
        assert merger.args == []

    def test_args_with_special_characters(self):
        """Test handling arguments with special characters."""
        from app.library.YTDLPOpts import ARGSMerger

        merger = ARGSMerger()
        merger.add('--postprocessor-args "-movflags +faststart"')

        assert "--postprocessor-args" in merger.args
        assert "-movflags +faststart" in merger.args


class TestYTDLPCli:
    """Test the YTDLPCli class."""

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_constructor_with_valid_item(self, mock_config, mock_presets):
        """Test YTDLPCli constructor with valid Item."""
        from app.library.ItemDTO import Item
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_presets.get_instance.return_value.get.return_value = None

        item = Item(url="https://example.com/video")
        cli = YTDLPCli(item=item)

        assert cli.item is item
        assert cli._config is mock_config_instance

    def test_constructor_with_invalid_type_raises_error(self):
        """Test YTDLPCli constructor raises error with non-Item type."""
        from app.library.YTDLPOpts import YTDLPCli

        with pytest.raises(ValueError, match="Expected Item instance"):
            YTDLPCli(item="not an item")  # type: ignore

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_with_user_fields_only(self, mock_config, mock_presets):
        """Test build with only user-provided fields."""
        from app.library.ItemDTO import Item
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_presets.get_instance.return_value.get.return_value = None

        item = Item(
            url="https://example.com/video",
            folder="myfolder",
            template="%(id)s.%(ext)s",
            cli="--format best",
        )

        cli = YTDLPCli(item=item)
        command, info = cli.build()

        assert isinstance(command, str)
        assert isinstance(info, dict)
        assert "command" in info
        assert "dict" in info
        assert "ytdlp" in info
        assert "merged" in info
        assert info["merged"]["template"] == "%(id)s.%(ext)s"
        assert info["merged"]["save_path"] == "/downloads/myfolder"
        assert "--format best" in command

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_with_preset_fields_fallback(self, mock_config, mock_presets):
        """Test build falls back to preset fields when user doesn't provide them."""
        from app.library.ItemDTO import Item
        from app.library.Presets import Preset
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        # Create a preset with fields
        preset = Preset(
            name="test_preset",
            folder="preset_folder",
            template="%(channel)s/%(title)s.%(ext)s",
            cli="--format 720p",
        )

        mock_presets.get_instance.return_value.get.return_value = preset

        # Item without folder/template - should use preset's
        item = Item(url="https://example.com/video", preset="test_preset")

        cli = YTDLPCli(item=item)
        command, info = cli.build()

        assert info["merged"]["template"] == "%(channel)s/%(title)s.%(ext)s", "Should use preset values"
        assert info["merged"]["save_path"] == "/downloads/preset_folder"
        assert "--format 720p" in command

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_user_fields_override_preset(self, mock_config, mock_presets):
        """Test that user fields override preset fields."""
        from app.library.ItemDTO import Item
        from app.library.Presets import Preset
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        preset = Preset(
            name="test_preset",
            folder="preset_folder",
            template="%(channel)s/%(title)s.%(ext)s",
            cli="--format 720p",
        )

        mock_presets.get_instance.return_value.get.return_value = preset

        # Item with user fields - should override preset
        item = Item(
            url="https://example.com/video",
            preset="test_preset",
            folder="user_folder",
            template="%(id)s.%(ext)s",
            cli="--format best",
        )

        cli = YTDLPCli(item=item)
        command, info = cli.build()

        assert info["merged"]["template"] == "%(id)s.%(ext)s", "Should use user values, not preset"
        assert info["merged"]["save_path"] == "/downloads/user_folder"
        assert "--format best" in command, "User CLI should appear after preset CLI in command"

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_with_default_fallback(self, mock_config, mock_presets):
        """Test build falls back to defaults when neither user nor preset provide fields."""
        from app.library.ItemDTO import Item
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/default/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_presets.get_instance.return_value.get.return_value = None

        # Item with minimal fields
        item = Item(url="https://example.com/video")

        cli = YTDLPCli(item=item)
        _, info = cli.build()

        # Should use default values
        assert info["merged"]["template"] == "%(title)s.%(ext)s"
        assert info["merged"]["save_path"] == "/default/downloads"

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.create_cookies_file")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_with_cookies_from_user(self, mock_config, mock_create_cookies, mock_presets):
        """Test build with cookies from user."""
        from app.library.ItemDTO import Item
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_cookie_path = Mock()
        mock_cookie_path.__str__ = Mock(return_value="/tmp/cookies.txt")
        mock_create_cookies.return_value = mock_cookie_path

        mock_presets.get_instance.return_value.get.return_value = None

        item = Item(url="https://example.com/video", cookies="session_id=abc123")

        cli = YTDLPCli(item=item)
        command, info = cli.build()

        mock_create_cookies.assert_called_once_with("session_id=abc123")
        assert "--cookies" in command
        assert "/tmp/cookies.txt" in command
        assert info["merged"]["cookie_file"] == "/tmp/cookies.txt"

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_with_cookies_from_preset(self, mock_config, mock_presets):
        """Test build with cookies from preset when user doesn't provide."""
        from app.library.ItemDTO import Item
        from app.library.Presets import Preset
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_cookie_path = Mock()
        mock_cookie_path.__str__ = Mock(return_value="/preset/cookies.txt")

        preset = Mock(spec=Preset)
        preset.name = "test_preset"
        preset.cookies = "preset_cookies"
        preset.get_cookies_file = Mock(return_value=mock_cookie_path)
        preset.folder = None
        preset.template = None
        preset.cli = None

        mock_presets.get_instance.return_value.get.return_value = preset

        item = Item(url="https://example.com/video", preset="test_preset")

        cli = YTDLPCli(item=item)
        command, _ = cli.build()

        preset.get_cookies_file.assert_called_once_with(config=mock_config_instance)
        assert "--cookies" in command
        assert "/preset/cookies.txt" in command

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_with_absolute_folder_path(self, mock_config, mock_presets):
        """Test build with absolute folder path from user."""
        from app.library.ItemDTO import Item
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_presets.get_instance.return_value.get.return_value = None

        # Absolute path gets leading slash stripped and joined with download_path
        # This is the actual behavior: /absolute/path -> absolute/path -> /downloads/absolute/path
        item = Item(url="https://example.com/video", folder="/absolute/path")

        cli = YTDLPCli(item=item)
        command, info = cli.build()

        assert info["merged"]["save_path"] == "/downloads/absolute/path", (
            "The implementation strips leading slash and joins with download_path"
        )
        assert "--paths" in command

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_includes_url_in_command(self, mock_config, mock_presets):
        """Test that build includes the URL in the final command."""
        from app.library.ItemDTO import Item
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        mock_presets.get_instance.return_value.get.return_value = None

        item = Item(url="https://youtube.com/watch?v=test123")

        cli = YTDLPCli(item=item)
        command, _ = cli.build()

        assert "https://youtube.com/watch?v=test123" in command

    @patch("app.library.Presets.Presets")
    @patch("app.library.YTDLPOpts.Config")
    def test_build_cli_args_priority_order(self, mock_config, mock_presets):
        """Test that CLI args are added in correct priority order (preset first, user last)."""
        from app.library.ItemDTO import Item
        from app.library.Presets import Preset
        from app.library.YTDLPOpts import YTDLPCli

        mock_config_instance = Mock()
        mock_config_instance.download_path = "/downloads"
        mock_config_instance.output_template = "%(title)s.%(ext)s"
        mock_config_instance.get_replacers.return_value = {}
        mock_config.get_instance.return_value = mock_config_instance

        preset = Preset(name="test_preset", cli="--format 720p --extract-audio")

        mock_presets.get_instance.return_value.get.return_value = preset

        item = Item(url="https://example.com/video", preset="test_preset", cli="--format best --no-playlist")

        cli = YTDLPCli(item=item)
        _, info = cli.build()

        # User args should come after preset args in the command
        # This ensures user args can override preset args
        args_list = info["dict"]
        preset_format_idx = args_list.index("720p") if "720p" in args_list else -1
        user_format_idx = args_list.index("best") if "best" in args_list else -1

        assert user_format_idx > preset_format_idx, "User's 'best' should appear after preset's '720p'"
