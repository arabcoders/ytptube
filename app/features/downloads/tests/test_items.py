import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.features.downloads.items import Item, ItemDTO


def _archive_path(tmp_path: Path) -> str:
    return str(tmp_path / "archive.txt")


class TestItemFormatAndBasics:
    def test_format_force_start(self) -> None:
        item = Item.format({"url": "https://example.com/video", "force_start": True})

        assert item.force_start is True

    @patch("app.features.presets.service.Presets.get_instance")
    def test_format_normalizes(self, mock_presets_get):
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
        with patch("app.features.downloads.items.Item._default_preset", return_value="default"):
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
    def test_format_rejects_input(self, mock_presets_get):
        with pytest.raises(ValueError, match="url param is required"):
            Item.format({})

        mock_presets_get.return_value.has.return_value = False
        with (
            patch("app.features.downloads.items.Item._default_preset", return_value="default"),
            pytest.raises(ValueError, match="Preset 'bad' does not exist"),
        ):
            Item.format({"url": "https://example.com", "preset": "bad"})

    def test_item_helpers(self):
        item = Item(url="https://example.com", extras={"a": 1}, cli="--x")
        assert item.has_extras() is True
        assert item.has_cli() is True
        assert item.get("url") == "https://example.com"
        assert "url" in item.serialize()
        assert json.loads(item.json())["url"] == "https://example.com"

    @patch("app.features.downloads.items.get_archive_id")
    def test_archive_status(self, mock_get_id, tmp_path: Path):
        mock_get_id.return_value = {"archive_id": "x", "id": "x", "ie_key": "k"}
        file = _archive_path(tmp_path)

        item = Item(url="https://example.com")
        assert item.get_archive_id() == "x"

        with (
            patch("app.features.downloads.items.YTDLPOpts") as mock_opts,
            patch("app.features.downloads.items.archive_read") as mock_read,
        ):
            mock_opts.get_instance.return_value.preset.return_value = mock_opts.get_instance.return_value
            mock_opts.get_instance.return_value.add_cli.return_value = mock_opts.get_instance.return_value
            mock_opts.get_instance.return_value.get_all.return_value = {"download_archive": file}
            mock_read.return_value = ["x"]

            assert item.is_archived() is True


class TestItemDTO:
    @patch("app.features.downloads.items.get_archive_id")
    @patch("app.features.downloads.items.YTDLPOpts")
    @patch("app.features.downloads.items.archive_read")
    def test_init_archive_flags(self, mock_read, mock_opts, mock_get_id, tmp_path: Path):
        mock_get_id.return_value = {"archive_id": "arch", "id": "arch", "ie_key": "YT"}
        mock_opts.get_instance.return_value.preset.return_value = mock_opts.get_instance.return_value
        mock_opts.get_instance.return_value.add_cli.return_value = mock_opts.get_instance.return_value
        file = _archive_path(tmp_path)
        mock_opts.get_instance.return_value.get_all.return_value = {"download_archive": file}
        mock_read.return_value = ["arch"]

        dto = ItemDTO(id="vid", title="t", url="u", folder="f")

        assert dto.archive_id == "arch"
        assert dto._archive_file == file
        assert dto.is_archivable is True
        assert dto.is_archived is True

    @patch("app.features.downloads.items.archive_read")
    def test_serialize_archive_status(self, mock_read, tmp_path: Path):
        dto = ItemDTO(id="vid", title="t", url="u", folder="f")
        dto.archive_id = "arch"
        dto._archive_file = _archive_path(tmp_path)
        dto.status = "finished"
        mock_read.return_value = ["arch"]

        data = dto.serialize()
        assert data["is_archived"] is True

    def test_name_and_ids(self):
        dto = ItemDTO(id="abc", title="Title", url="u", folder="f")
        assert dto.name() == 'id="abc", title="Title"'
        assert isinstance(dto.get_id(), str)

    def test_file_lookup(self):
        dto = ItemDTO(
            id="test-id",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            folder="",
            status="finished",
            filename="test_video.mp4",
        )

        dto_no_file = ItemDTO(
            id="test-id-2",
            title="Test Video 2",
            url="https://youtube.com/watch?v=test456",
            folder="",
            status="finished",
        )
        assert dto_no_file.get_file() is None

        # Mock get_file function to return success (without custom download_path)
        with (
            patch("app.features.downloads.items.get_file") as mock_get_file,
            patch("app.library.config.Config") as mock_config,
        ):
            mock_get_file.return_value = ("/downloads/test_video.mp4", 200)
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto.get_file()
            assert result == Path("/downloads/test_video.mp4")

        dto_with_folder = ItemDTO(
            id="test-id-3",
            title="Test Video 3",
            url="https://youtube.com/watch?v=test789",
            folder="media",
            status="finished",
            filename="test_video.mp4",
        )

        with (
            patch("app.features.downloads.items.get_file") as mock_get_file,
            patch("app.library.config.Config") as mock_config,
        ):
            mock_get_file.return_value = ("/downloads/media/test_video.mp4", 200)
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto_with_folder.get_file()
            assert result == Path("/downloads/media/test_video.mp4")

        with (
            patch("app.features.downloads.items.get_file") as mock_get_file,
            patch("app.library.config.Config") as mock_config,
        ):
            mock_get_file.return_value = ("/downloads/test_video.mp4", 404)
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto.get_file()
            assert result is None

        with (
            patch("app.features.downloads.items.get_file") as mock_get_file,
            patch("app.library.config.Config") as mock_config,
        ):
            mock_get_file.side_effect = ValueError("File path error")
            mock_config.get_instance.return_value.download_path = "/downloads"

            result = dto.get_file()
            assert result is None

        with patch("app.features.downloads.items.get_file") as mock_get_file:
            mock_get_file.return_value = ("/custom/test_video.mp4", 200)

            result = dto.get_file(download_path=Path("/custom"))
            assert result == Path("/custom/test_video.mp4")

    def test_file_sidecar(self):
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
            patch("app.features.downloads.items.ItemDTO.get_file", return_value=Path("/downloads/video.mp4")),
            patch("app.features.downloads.items.get_file_sidecar", return_value=expected_sidecar),
        ):
            result = dto.get_file_sidecar()

        assert result is expected_sidecar
        assert dto.sidecar is expected_sidecar

    def test_sidecar_no_file(self):
        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="sidecar-none", title="Title", url="u", folder="f")

        existing = {"existing": []}
        dto.sidecar = existing

        with (
            patch("app.features.downloads.items.ItemDTO.get_file", return_value=None),
            patch("app.features.downloads.items.get_file_sidecar"),
        ):
            result = dto.get_file_sidecar()

        assert result is existing
        assert dto.sidecar is existing

    def test_get_preset_hit(self):
        from app.features.presets.schemas import Preset

        mock_preset = Preset(id=1, name="test-preset", cli="--format best")

        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="vid", title="t", url="u", folder="f", preset="test-preset")

        with patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_presets.return_value.get.return_value = mock_preset

            result = dto.get_preset()

            assert result is mock_preset
            assert result.name == "test-preset"

    def test_get_preset_default(self):
        from app.features.presets.schemas import Preset

        mock_preset = Preset(id=2, name="default", cli="--format best")

        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="vid", title="t", url="u", folder="f", preset="")

        with patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_presets.return_value.get.return_value = mock_preset

            result = dto.get_preset()

            assert result is mock_preset

    def test_get_preset_miss(self):
        with patch.object(ItemDTO, "__post_init__", lambda _: None):
            dto = ItemDTO(id="vid", title="t", url="u", folder="f", preset="nonexistent")

        with patch("app.features.presets.service.Presets.get_instance") as mock_presets:
            mock_presets.return_value.get.return_value = None

            result = dto.get_preset()

            assert result is None


class TestItemAddExtras:
    def test_add_extras_empty(self):
        item = Item(url="https://example.com")
        item.extras = {}

        item.add_extras("key1", "value1")

        assert item.extras["key1"] == "value1"

    def test_add_extras_none(self):
        item = Item(url="https://example.com")
        setattr(item, "extras", None)

        item.add_extras("key1", "value1")

        assert item.extras == {"key1": "value1"}

    def test_add_extras_existing(self):
        item = Item(url="https://example.com", extras={"existing": "data"})

        item.add_extras("new_key", "new_value")

        assert item.extras["existing"] == "data"
        assert item.extras["new_key"] == "new_value"

    def test_extras_overwrite(self):
        item = Item(url="https://example.com", extras={"key1": "old_value"})

        item.add_extras("key1", "new_value")

        assert item.extras["key1"] == "new_value"

    def test_extras_accept_types(self):
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
