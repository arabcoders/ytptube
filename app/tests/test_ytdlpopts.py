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
            patch("app.library.YTDLPOpts.load_cookies") as mock_load_cookies,
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

            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = mock_preset
            mock_presets.get_instance.return_value = mock_presets_instance

            # Use real Path but mock file operations
            with (
                patch("pathlib.Path.exists", return_value=False),
                patch("pathlib.Path.mkdir"),
                patch("pathlib.Path.write_text"),
            ):
                opts = YTDLPOpts()
                opts.preset("cookie_preset")

                # Check that the cookie file would be created at the right path
                expected_path = "/test/config/cookies/cookie_preset.txt"
                assert opts._preset_opts["cookiefile"] == expected_path
                mock_load_cookies.assert_called_once()

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
            patch("app.library.YTDLPOpts.load_cookies") as mock_load_cookies,
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

            mock_presets_instance = Mock()
            mock_presets_instance.get.return_value = mock_preset
            mock_presets.get_instance.return_value = mock_presets_instance

            # Mock cookie loading failure
            mock_load_cookies.side_effect = ValueError("Invalid cookies")

            with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.write_text"):
                opts = YTDLPOpts()
                opts.preset("cookie_preset")

                # Should log error but not raise
                mock_log.error.assert_called_once()
                error_args = mock_log.error.call_args[0][0]
                assert "Failed to load 'Cookie Preset' cookies" in error_args

                # cookiefile should not be set
                assert "cookiefile" not in opts._preset_opts

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
