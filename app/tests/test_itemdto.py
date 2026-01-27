import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.library.ItemDTO import Item, ItemDTO


class TestItemFormatAndBasics:
    @patch("app.features.presets.service.Presets.get_instance")
    def test_format_validates_and_normalizes(self, mock_presets_get):
        # Preset exists and is not default => allowed
        mock_presets_get.return_value.has.return_value = True

        data = {
            "url": "dQw4w9WgXcQ",  # 11-char YouTube ID
            "preset": "custom",
            "folder": "media",
            "cookies": "abc",
            "template": "%(title)s.%(ext)s",
            "auto_start": False,
            "extras": {"k": 1},
            "requeued": True,
            "cli": "--embed-metadata",
        }
        with (
            patch("app.library.ItemDTO.Item._default_preset", return_value="default"),
            patch("app.features.ytdlp.utils.arg_converter") as mock_arg_conv,
        ):
            mock_arg_conv.return_value = None
            item = Item.format(data)

        assert isinstance(item, Item)
        assert item.url.startswith("https://www.youtube.com/watch?v="), "URL normalized to full YouTube URL"
        assert item.preset == "custom"
        assert item.folder == "media"
        assert item.cookies == "abc"
        assert item.template == "%(title)s.%(ext)s"
        assert item.auto_start is False
        assert item.extras == {"k": 1}
        assert item.requeued is True
        assert item.cli == "--embed-metadata"

    @patch("app.features.presets.service.Presets.get_instance")
    def test_format_raises_for_missing_url_and_invalid_preset(self, mock_presets_get):
        # Missing url
        with pytest.raises(ValueError, match="url param is required"):
            Item.format({})

        # Invalid preset name (not found)
        mock_presets_get.return_value.has.return_value = False
        with (
            patch("app.library.ItemDTO.Item._default_preset", return_value="default"),
            pytest.raises(ValueError, match="Preset 'bad' does not exist"),
        ):
            Item.format({"url": "https://example.com", "preset": "bad"})

    @patch("app.features.ytdlp.utils.arg_converter")
    def test_format_cli_parse_error(self, mock_arg_conv):
        mock_arg_conv.side_effect = RuntimeError("bad cli")
        with pytest.raises(ValueError, match="Failed to parse command options"):
            Item.format({"url": "https://example.com", "cli": "--bad"})

    def test_item_helpers(self):
        item = Item(url="https://example.com", extras={"a": 1}, cli="--x")
        assert item.has_extras() is True
        assert item.has_cli() is True
        assert item.get("url") == "https://example.com"
        assert "url" in item.serialize()
        assert json.loads(item.json())["url"] == "https://example.com"

    @patch("app.library.ItemDTO.get_archive_id")
    def test_item_archive_id_and_is_archived(self, mock_get_id):
        mock_get_id.return_value = {"archive_id": "x", "id": "x", "ie_key": "k"}

        # get_archive_id
        item = Item(url="https://example.com")
        assert item.get_archive_id() == "x"

        # is_archived uses archive_read through get_archive_file + ytdlp opts
        with (
            patch("app.library.ItemDTO.YTDLPOpts") as mock_opts,
            patch("app.library.ItemDTO.archive_read") as mock_read,
        ):
            mock_opts.get_instance.return_value.preset.return_value = mock_opts.get_instance.return_value
            mock_opts.get_instance.return_value.add_cli.return_value = mock_opts.get_instance.return_value
            mock_opts.get_instance.return_value.get_all.return_value = {"download_archive": "/tmp/archive.txt"}
            mock_read.return_value = ["x"]

            assert item.is_archived() is True


class TestItemDTO:
    @patch("app.library.ItemDTO.get_archive_id")
    @patch("app.library.ItemDTO.YTDLPOpts")
    @patch("app.library.ItemDTO.archive_read")
    def test_post_init_sets_archive_flags(self, mock_read, mock_opts, mock_get_id):
        # Setup archive id and archive file
        mock_get_id.return_value = {"archive_id": "arch", "id": "arch", "ie_key": "YT"}
        mock_opts.get_instance.return_value.preset.return_value = mock_opts.get_instance.return_value
        mock_opts.get_instance.return_value.add_cli.return_value = mock_opts.get_instance.return_value
        mock_opts.get_instance.return_value.get_all.return_value = {"download_archive": "/tmp/a.txt"}
        mock_read.return_value = ["arch"]

        dto = ItemDTO(id="vid", title="t", url="u", folder="f")

        assert dto.archive_id == "arch"
        assert dto._archive_file == "/tmp/a.txt"
        assert dto.is_archivable is True
        assert dto.is_archived is True

    @patch("app.library.ItemDTO.archive_read")
    def test_serialize_triggers_archive_status_when_finished(self, mock_read):
        # Given a finished item with archive info
        dto = ItemDTO(id="vid", title="t", url="u", folder="f")
        dto.archive_id = "arch"
        dto._archive_file = "/tmp/a.txt"
        dto.status = "finished"
        mock_read.return_value = ["arch"]

        data = dto.serialize()
        assert data["is_archived"] is True
        # Removed fields must not be present
        for key in ItemDTO.removed_fields():
            assert key not in data

    @patch("app.library.ItemDTO.YTDLPOpts")
    def test_get_ytdlp_opts_uses_preset_and_cli(self, mock_opts):
        mock_opts.get_instance.return_value.preset.return_value = mock_opts.get_instance.return_value
        mock_opts.get_instance.return_value.add_cli.return_value = mock_opts.get_instance.return_value

        dto = ItemDTO(id="id", title="t", url="u", folder="f", preset="p", cli="--x")
        opts = dto.get_ytdlp_opts()

        mock_opts.get_instance.assert_called_once()
        mock_opts.get_instance.return_value.preset.assert_called_once_with(name="p")
        mock_opts.get_instance.return_value.add_cli.assert_called_once()
        assert opts is mock_opts.get_instance.return_value

    def test_name_and_ids(self):
        dto = ItemDTO(id="abc", title="Title", url="u", folder="f")
        assert dto.name() == 'id="abc", title="Title"'
        assert isinstance(dto.get_id(), str)

    def test_archive_add_and_delete_paths(self):
        dto = ItemDTO(id="id", title="t", url="u", folder="f")
        assert dto.archive_add() is False, "Precondition not met yet"

        # Set up to allow add
        dto.archive_id = "arch"
        dto._archive_file = "/tmp/a.txt"
        dto.is_archivable = True
        dto.is_archived = False

        with patch("app.library.ItemDTO.archive_add", return_value=True) as m_add:
            ok = dto.archive_add()
            assert ok is True
            m_add.assert_called_once()

        # Delete requires is_archived True
        dto.is_archived = True
        with patch("app.library.ItemDTO.archive_delete") as m_del:
            ok2 = dto.archive_delete()
            assert ok2 is True
            m_del.assert_called_once()

    def test_get_file_method(self):
        """Test ItemDTO get_file method returns correct path."""
        # Create ItemDTO with filename but no folder
        dto = ItemDTO(
            id="test-id",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            folder="",
            status="finished",
            filename="test_video.mp4",
        )

        # Test with no filename returns None
        dto_no_file = ItemDTO(
            id="test-id-2",
            title="Test Video 2",
            url="https://youtube.com/watch?v=test456",
            folder="",
            status="finished",
        )
        assert dto_no_file.get_file() is None

        # Mock get_file function to return success (without custom download_path)
        with patch("app.library.ItemDTO.get_file") as mock_get_file, patch("app.library.config.Config") as mock_config:
            mock_get_file.return_value = ("/downloads/test_video.mp4", 200)
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto.get_file()
            assert result == Path("/downloads/test_video.mp4")

        # Test with folder
        dto_with_folder = ItemDTO(
            id="test-id-3",
            title="Test Video 3",
            url="https://youtube.com/watch?v=test789",
            folder="media",
            status="finished",
            filename="test_video.mp4",
        )

        with patch("app.library.ItemDTO.get_file") as mock_get_file, patch("app.library.config.Config") as mock_config:
            mock_get_file.return_value = ("/downloads/media/test_video.mp4", 200)
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto_with_folder.get_file()
            assert result == Path("/downloads/media/test_video.mp4")

        # Test with file not found
        with patch("app.library.ItemDTO.get_file") as mock_get_file, patch("app.library.config.Config") as mock_config:
            mock_get_file.return_value = ("/downloads/test_video.mp4", 404)
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto.get_file()
            assert result is None

        # Test with exception during file access
        with patch("app.library.ItemDTO.get_file") as mock_get_file, patch("app.library.config.Config") as mock_config:
            mock_get_file.side_effect = ValueError("File path error")
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto.get_file()
            assert result is None

        # Test with custom download_path parameter (Config not imported in this case)
        with patch("app.library.ItemDTO.get_file") as mock_get_file:
            mock_get_file.return_value = ("/custom/test_video.mp4", 200)

            result = dto.get_file(download_path=Path("/custom"))
            assert result == Path("/custom/test_video.mp4")

    def test_get_file_sidecar_populates_from_utils(self):
        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="sidecar", title="Title", url="u", folder="f")

        expected_sidecar = {
            "subtitle": [
                {
                    "file": Path("/downloads/video.en.srt"),
                    "lang": "en",
                    "name": "SRT (0) - en",
                }
            ]
        }

        with (
            patch(
                "app.library.ItemDTO.ItemDTO.get_file", autospec=True, return_value=Path("/downloads/video.mp4")
            ) as mock_get_file,
            patch("app.library.ItemDTO.get_file_sidecar", return_value=expected_sidecar) as mock_utils_sidecar,
        ):
            result = dto.get_file_sidecar()

        mock_get_file.assert_called_once_with(dto)
        mock_utils_sidecar.assert_called_once_with(Path("/downloads/video.mp4"))
        assert result is expected_sidecar
        assert dto.sidecar is expected_sidecar

    def test_get_file_sidecar_returns_existing_when_no_file(self):
        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="sidecar-none", title="Title", url="u", folder="f")

        existing = {"existing": []}
        dto.sidecar = existing

        with (
            patch("app.library.ItemDTO.ItemDTO.get_file", autospec=True, return_value=None) as mock_get_file,
            patch("app.library.ItemDTO.get_file_sidecar") as mock_utils_sidecar,
        ):
            result = dto.get_file_sidecar()

        mock_get_file.assert_called_once_with(dto)
        mock_utils_sidecar.assert_not_called()
        assert result is existing
        assert dto.sidecar is existing

    def test_get_preset_returns_preset_instance(self):
        """Test ItemDTO.get_preset returns the Preset instance."""
        from app.features.presets.schemas import Preset

        mock_preset = Preset(id=1, name="test-preset", cli="--format best")

        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="vid", title="t", url="u", folder="f", preset="test-preset")

        with patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_presets.return_value.get.return_value = mock_preset

            result = dto.get_preset()

            mock_presets.return_value.get.assert_called_once_with("test-preset")
            assert result is mock_preset
            assert result.name == "test-preset"

    def test_get_preset_uses_default_when_no_preset_set(self):
        """Test ItemDTO.get_preset uses 'default' when preset is empty."""
        from app.features.presets.schemas import Preset

        mock_preset = Preset(id=2, name="default", cli="--format best")

        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="vid", title="t", url="u", folder="f", preset="")

        with patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_presets.return_value.get.return_value = mock_preset

            result = dto.get_preset()

            mock_presets.return_value.get.assert_called_once_with("default")
            assert result is mock_preset

    def test_get_preset_returns_none_when_not_found(self):
        """Test ItemDTO.get_preset returns None when preset not found."""
        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="vid", title="t", url="u", folder="f", preset="nonexistent")

        with patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_presets.return_value.get.return_value = None

            result = dto.get_preset()

            mock_presets.return_value.get.assert_called_once_with("nonexistent")
            assert result is None


class TestItemAddExtras:
    def test_add_extras_to_empty_dict(self):
        """Test adding extras when extras dict is empty."""
        item = Item(url="https://example.com")
        item.extras = {}

        item.add_extras("key1", "value1")

        assert item.extras["key1"] == "value1"

    def test_add_extras_when_extras_is_none(self):
        """Test adding extras when extras is None."""
        item = Item(url="https://example.com")
        item.extras = None

        item.add_extras("key1", "value1")

        assert item.extras == {"key1": "value1"}

    def test_add_extras_to_existing_dict(self):
        """Test adding extras to an existing extras dict."""
        item = Item(url="https://example.com", extras={"existing": "data"})

        item.add_extras("new_key", "new_value")

        assert item.extras["existing"] == "data"
        assert item.extras["new_key"] == "new_value"

    def test_add_extras_overwrites_existing_key(self):
        """Test that adding extras overwrites existing keys."""
        item = Item(url="https://example.com", extras={"key1": "old_value"})

        item.add_extras("key1", "new_value")

        assert item.extras["key1"] == "new_value"

    def test_add_extras_with_various_types(self):
        """Test adding extras with various data types."""
        item = Item(url="https://example.com")
        item.extras = {}

        item.add_extras("string", "value")
        item.add_extras("number", 42)
        item.add_extras("boolean", True)
        item.add_extras("list", [1, 2, 3])
        item.add_extras("dict", {"nested": "data"})

        assert item.extras["string"] == "value"
        assert item.extras["number"] == 42
        assert item.extras["boolean"] is True
        assert item.extras["list"] == [1, 2, 3]
        assert item.extras["dict"] == {"nested": "data"}
