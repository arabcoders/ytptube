from unittest.mock import Mock, patch

import pytest

from app.features.downloads.items import Item
from app.features.presets.schemas import Preset
from app.features.ytdlp.ytdlp_opts import ARGSMerger, YTDLPCli, YTDLPOpts


COOKIE_DATA = "# Netscape HTTP Cookie File\n.example.com\tTRUE\t/\tFALSE\t0\tsession\tvalue\n"


def config_mock() -> Mock:
    config = Mock()
    config.download_path = "/downloads"
    config.temp_path = "/temp"
    config.config_path = "/config"
    config.output_template = "%(title)s.%(ext)s"
    config.output_template_chapter = "%(chapter)s"
    config.default_preset = ""
    config.debug = False
    config.get_replacers.return_value = {}
    return config


class TestYTDLPOpts:
    def test_malformed_cli(self):
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config_mock()):
            with pytest.raises(ValueError, match="Invalid command options"):
                YTDLPOpts().add_cli('--output "unterminated')

    def test_accumulated_cli(self):
        config = config_mock()
        config.get_replacers.return_value = {"value": "enabled"}
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            opts = YTDLPOpts().add_cli("--format best").add_cli('--add-header "X-Test:%(value)s"')
            result = opts.get_all(keep=True)

        assert result["format"] is None
        assert result["http_headers"] == {"x-test": "enabled"}

    def test_invalid_accumulated(self):
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config_mock()):
            opts = YTDLPOpts()
            opts._item_cli = ['--output "unterminated']
            with pytest.raises(ValueError, match="Invalid command options"):
                opts.get_all(keep=True)

    def test_preset_cookies(self, tmp_path):
        config = config_mock()
        config.download_path = str(tmp_path / "downloads")
        config.config_path = str(tmp_path)
        preset = Preset(name="custom", id=12, cookies=COOKIE_DATA, folder="media", template="%(id)s.%(ext)s")
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = preset
                result = YTDLPOpts().preset("custom").get_all(keep=True)

        cookie_file = tmp_path / "cookies" / "12.txt"
        assert cookie_file.read_text() == COOKIE_DATA.rstrip()
        assert result["cookiefile"] == str(cookie_file)

    def test_invalid_preset_cli(self):
        config = config_mock()
        preset = Preset.model_construct(name="broken", cli='--output "unterminated')
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = preset
                with pytest.raises(ValueError, match="Invalid preset 'broken'"):
                    YTDLPOpts().preset("broken")

    def test_default_options(self):
        config = config_mock()
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            result = YTDLPOpts().get_all(keep=True)

        assert result["paths"] == {"home": "/downloads", "temp": "/temp"}
        assert result["outtmpl"] == {"default": "%(title)s.%(ext)s", "chapter": "%(chapter)s"}

    def test_keep_state(self):
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config_mock()):
            opts = YTDLPOpts().add({"format": "-best"}).add_cli("--no-playlist")
            opts.get_all(keep=False)
            assert opts._item_opts == {}
            assert opts._item_cli == []
            opts.add({"format": "-best"}).add_cli("--no-playlist").get_all(keep=True)

        assert opts._item_opts == {"format": "-best"}
        assert opts._item_cli == ["--no-playlist"]

    def test_absolute_folder(self, tmp_path):
        config = config_mock()
        config.download_path = str(tmp_path / "downloads")
        preset = Preset(name="custom", folder="/nested/media")
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = preset
                result = YTDLPOpts().preset("custom").get_all(keep=True)

        assert result["paths"]["home"] == str(tmp_path / "downloads" / "nested/media")


class TestARGSMerger:
    def test_converts_arguments(self):
        merger = ARGSMerger().add("--format best").add('--output "%(title)s.%(ext)s"')

        assert merger.as_dict() == ["--format", "best", "--output", "%(title)s.%(ext)s"]
        assert str(merger) == "--format best --output '%(title)s.%(ext)s'"

    def test_filters_comments(self):
        merger = ARGSMerger().add(
            '  # ignored\n--format "bv*[height<=1080]+ba/b"\n    # also ignored\n--output "name#part.%(ext)s"'
        )

        assert merger.args == ["--format", "bv*[height<=1080]+ba/b", "--output", "name#part.%(ext)s"]

    def test_non_string_input(self):
        assert ARGSMerger().add(42).args == []  # ty: ignore[invalid-argument-type]

    def test_special_options(self):
        merger = ARGSMerger().add('--format "bv*[height<=1080]+ba/b" --postprocessor-args "ffmpeg:-vf scale=1280:720"')

        assert merger.as_ytdlp() == {
            "format": "bv*[height<=1080]+ba/b",
            "postprocessor_args": {"ffmpeg": ["-vf", "scale=1280:720"]},
        }

    def test_reset_arguments(self):
        assert ARGSMerger().add("--format best").reset().args == []


class TestYTDLPCli:
    def test_rejects_wrong_item(self):
        with pytest.raises(ValueError, match="Expected Item instance"):
            YTDLPCli(item="not an item")

    def test_default_fallback(self):
        config = config_mock()
        item = Item(url="https://example.com/video", preset="")
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = None
                command, info = YTDLPCli(item=item).build()

        assert info["merged"] == {"template": config.output_template, "save_path": "/downloads", "cookie_file": None}
        assert "--output" in command
        assert item.url in command

    def test_user_cookie_file(self, tmp_path):
        config = config_mock()
        config.temp_path = str(tmp_path)
        item = Item(url="https://example.com/video", preset="", cookies=COOKIE_DATA)
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = None
                command, info = YTDLPCli(item=item).build()

        cookie_file = info["merged"]["cookie_file"]
        assert cookie_file is not None
        assert (tmp_path / cookie_file.split("/")[-1]).read_text() == COOKIE_DATA
        assert "--cookies" in command

    def test_preset_cookie_file(self, tmp_path):
        config = config_mock()
        config.config_path = str(tmp_path)
        preset = Preset(name="custom", id=4, cookies=COOKIE_DATA)
        item = Item(url="https://example.com/video", preset="custom")
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = preset
                command, info = YTDLPCli(item=item).build()

        assert (tmp_path / "cookies" / "4.txt").read_text() == COOKIE_DATA.rstrip()
        assert info["merged"]["cookie_file"] == str(tmp_path / "cookies" / "4.txt")
        assert "--cookies" in command

    def test_absolute_item_folder(self):
        config = config_mock()
        item = Item(url="https://example.com/video", preset="", folder="/media/clips")
        with patch("app.features.ytdlp.ytdlp_opts.Config.get_instance", return_value=config):
            with patch("app.features.presets.service.Presets.get_instance") as get_presets:
                get_presets.return_value.get.return_value = None
                _, info = YTDLPCli(item=item).build()

        assert info["merged"]["save_path"] == "/downloads/media/clips"
