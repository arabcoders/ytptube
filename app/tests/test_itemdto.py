import json
from unittest.mock import patch

import pytest

from app.library.ItemDTO import Item, ItemDTO


class TestItemFormatAndBasics:
    @patch("app.library.Presets.Presets.get_instance")
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
            patch("app.library.Utils.arg_converter") as mock_arg_conv,
        ):
            mock_arg_conv.return_value = None
            item = Item.format(data)

        assert isinstance(item, Item)
        # URL normalized to full YouTube URL
        assert item.url.startswith("https://www.youtube.com/watch?v=")
        assert item.preset == "custom"
        assert item.folder == "media"
        assert item.cookies == "abc"
        assert item.template == "%(title)s.%(ext)s"
        assert item.auto_start is False
        assert item.extras == {"k": 1}
        assert item.requeued is True
        assert item.cli == "--embed-metadata"

    @patch("app.library.Presets.Presets.get_instance")
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

    @patch("app.library.Utils.arg_converter")
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
        # Precondition not met yet
        assert dto.archive_add() is False

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
        from pathlib import Path
        from unittest.mock import patch

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
