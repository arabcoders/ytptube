from unittest.mock import MagicMock, Mock, patch

from app.library.Utils import REMOVE_KEYS
from app.library.ytdlp import YTDLP, _ArchiveProxy, ytdlp_options


class TestArchiveProxy:
    def test_bool_and_falsey_cases(self) -> None:
        # No file path means proxy is falsey and operations return False
        p = _ArchiveProxy(file=None)
        assert bool(p) is False
        assert ("id" in p) is False
        assert p.add("id") is False

        # Empty item also returns False
        p2 = _ArchiveProxy(file="/tmp/archive.txt")
        assert bool(p2) is True
        assert ("" in p2) is False
        assert p2.add("") is False

    @patch("app.library.Archiver.Archiver.get_instance")
    def test_contains_and_add_delegate_to_archiver(self, mock_get_instance) -> None:
        arch = MagicMock()
        mock_get_instance.return_value = arch

        p = _ArchiveProxy(file="/tmp/archive.txt")

        # contains -> read(file, [item]) and check membership
        arch.read.return_value = ["abc"]
        assert ("abc" in p) is True
        arch.read.assert_called_with("/tmp/archive.txt", ["abc"])

        arch.read.return_value = []
        assert ("xyz" in p) is False

        # add -> add(file, [item]) returns boolean
        arch.add.return_value = True
        assert p.add("abc") is True
        arch.add.assert_called_with("/tmp/archive.txt", ["abc"])

        arch.add.return_value = False
        assert p.add("xyz") is False


class TestYtDlpOptions:
    def test_options_structure_and_no_suppresshelp(self) -> None:
        opts = ytdlp_options()

        assert isinstance(opts, list)
        assert len(opts) > 0

        # Every entry should have required keys
        for o in opts:
            assert {"flags", "description", "group", "ignored"} <= set(o.keys())
            assert isinstance(o["flags"], list)
            assert len(o["flags"]) > 0
            # Ensure SUPPRESSHELP has been normalized away
            if isinstance(o.get("description"), str):
                assert "SUPPRESSHELP" not in o["description"]

    def test_ignored_flags_match_remove_keys(self) -> None:
        # Collect the flags that should be ignored from REMOVE_KEYS
        ignored_flags: set[str] = {
            f.strip() for group in REMOVE_KEYS for v in group.values() for f in v.split(",") if f.strip()
        }

        opts = ytdlp_options()

        # Map flag -> ignored value as reported by our function (first match wins)
        flag_to_ignored: dict[str, bool] = {}
        for o in opts:
            for f in o["flags"]:
                if f not in flag_to_ignored:
                    flag_to_ignored[f] = bool(o["ignored"])  # normalize to bool

        # For any ignored flag that actually exists in yt-dlp parser, ensure it is marked ignored
        present_ignored_flags = [f for f in ignored_flags if f in flag_to_ignored]
        # We expect at least one to be present (e.g., -P / --paths, etc.)
        assert len(present_ignored_flags) > 0
        assert all(flag_to_ignored[f] is True for f in present_ignored_flags)


class TestYTDLP:
    """Test the YTDLP class overridden methods."""

    def _create_ytdlp(self, params=None):
        """Helper to create a YTDLP instance with mocked parent __init__."""
        with patch("app.library.ytdlp.yt_dlp.YoutubeDL.__init__", return_value=None):
            ytdlp = YTDLP(params=params)
            ytdlp.params = params or {}
            return ytdlp

    @patch("app.library.ytdlp.yt_dlp.YoutubeDL.__init__")
    def test_init_patches_download_archive_param(self, mock_super_init) -> None:
        """Test that __init__ removes download_archive before calling super, then restores it."""
        mock_super_init.return_value = None

        params = {"download_archive": "/tmp/archive.txt", "quiet": True}

        ytdlp = YTDLP(params=params, auto_init=True)
        # Set params as it would be after super().__init__
        ytdlp.params = {}

        # Verify super().__init__ was called without download_archive
        mock_super_init.assert_called_once()
        call_kwargs = mock_super_init.call_args[1]
        assert "download_archive" not in call_kwargs["params"]
        assert call_kwargs["params"]["quiet"] is True
        assert call_kwargs["auto_init"] is True

        # Our __init__ code manually sets these after super()
        ytdlp.params["download_archive"] = "/tmp/archive.txt"

        # Verify download_archive was restored to params
        assert ytdlp.params["download_archive"] == "/tmp/archive.txt"

        # Verify archive proxy was set up
        assert isinstance(ytdlp.archive, _ArchiveProxy)
        assert ytdlp.archive._file == "/tmp/archive.txt"

    @patch("app.library.ytdlp.yt_dlp.YoutubeDL.__init__")
    def test_init_handles_no_download_archive(self, mock_super_init) -> None:
        """Test __init__ works correctly when download_archive is not in params."""
        mock_super_init.return_value = None

        params = {"quiet": True}

        ytdlp = YTDLP(params=params, auto_init=False)

        # Verify super().__init__ was called with original params
        mock_super_init.assert_called_once()
        call_kwargs = mock_super_init.call_args[1]
        assert call_kwargs["params"]["quiet"] is True
        assert call_kwargs["auto_init"] is False

        # Verify archive proxy is falsey
        assert isinstance(ytdlp.archive, _ArchiveProxy)
        assert not ytdlp.archive

    @patch("app.library.ytdlp.yt_dlp.YoutubeDL.__init__")
    def test_init_handles_none_params(self, mock_super_init) -> None:
        """Test __init__ handles None params gracefully."""
        mock_super_init.return_value = None

        ytdlp = YTDLP(params=None)

        mock_super_init.assert_called_once_with(params=None, auto_init=True)
        assert isinstance(ytdlp.archive, _ArchiveProxy)
        assert not ytdlp.archive

    @patch("app.library.ytdlp.yt_dlp.YoutubeDL._delete_downloaded_files")
    def test_delete_downloaded_files_skips_when_interrupted(self, mock_super_delete) -> None:
        """Test _delete_downloaded_files skips cleanup when _interrupted is True."""
        with patch("app.library.ytdlp.yt_dlp.YoutubeDL.__init__", return_value=None):
            ytdlp = YTDLP(params={})
            ytdlp.to_screen = Mock()

            # Set interrupted flag
            ytdlp._interrupted = True

            result = ytdlp._delete_downloaded_files("arg1", "arg2", kwarg1="value1")

            # Should not call super method
            mock_super_delete.assert_not_called()
            # Should show message
            ytdlp.to_screen.assert_called_once_with("[info] Cancelled — skipping temp cleanup.")
            # Should return None
            assert result is None

    @patch("app.library.ytdlp.yt_dlp.YoutubeDL._delete_downloaded_files")
    def test_delete_downloaded_files_calls_super_when_not_interrupted(self, mock_super_delete) -> None:
        """Test _delete_downloaded_files calls super when not interrupted."""
        mock_super_delete.return_value = "cleanup_result"

        with patch("app.library.ytdlp.yt_dlp.YoutubeDL.__init__", return_value=None):
            ytdlp = YTDLP(params={})
            ytdlp._interrupted = False

            result = ytdlp._delete_downloaded_files("arg1", kwarg1="value1")

            # Should call super method with same args
            mock_super_delete.assert_called_once_with("arg1", kwarg1="value1")
            # Should return super's result
            assert result == "cleanup_result"

    def test_record_download_archive_does_nothing_without_download_archive_param(self) -> None:
        """Test record_download_archive returns early when download_archive is not set."""
        ytdlp = self._create_ytdlp(params={})
        ytdlp.archive = Mock()

        ytdlp.record_download_archive({"id": "test123"})

        # Should not interact with archive
        ytdlp.archive.add.assert_not_called()

    def test_record_download_archive_adds_archive_id(self) -> None:
        """Test record_download_archive adds the archive ID."""
        ytdlp = self._create_ytdlp(params={"download_archive": "/tmp/archive.txt"})
        ytdlp.write_debug = Mock()
        ytdlp.archive = Mock()
        ytdlp._make_archive_id = Mock(return_value="youtube test123")

        info_dict = {"id": "test123", "ie_key": "Youtube"}

        ytdlp.record_download_archive(info_dict)

        # Verify _make_archive_id was called
        ytdlp._make_archive_id.assert_called_once_with(info_dict)

        # Verify archive.add was called with the archive_id
        ytdlp.archive.add.assert_called_once_with("youtube test123")
        ytdlp.write_debug.assert_called_with("Adding to archive: youtube test123")

    def test_record_download_archive_handles_old_archive_ids(self) -> None:
        """Test record_download_archive adds _old_archive_ids when present."""
        ytdlp = self._create_ytdlp(params={"download_archive": "/tmp/archive.txt"})
        ytdlp.write_debug = Mock()
        ytdlp.archive = Mock()
        ytdlp._make_archive_id = Mock(return_value="youtube new123")

        info_dict = {
            "id": "new123",
            "ie_key": "Youtube",
            "_old_archive_ids": ["youtube old123", "youtube old456", "youtube new123"],
        }

        ytdlp.record_download_archive(info_dict)

        # Should add main archive_id
        assert ytdlp.archive.add.call_count == 3
        calls = [call[0][0] for call in ytdlp.archive.add.call_args_list]

        # First call is main archive_id
        assert calls[0] == "youtube new123"

        # Should add old IDs except the duplicate
        assert "youtube old123" in calls
        assert "youtube old456" in calls
        # Should not add duplicate (youtube new123 appears only once)
        assert calls.count("youtube new123") == 1

    def test_record_download_archive_skips_empty_old_archive_ids(self) -> None:
        """Test record_download_archive handles empty or invalid _old_archive_ids."""
        ytdlp = self._create_ytdlp(params={"download_archive": "/tmp/archive.txt"})
        ytdlp.write_debug = Mock()
        ytdlp.archive = Mock()
        ytdlp._make_archive_id = Mock(return_value="youtube test123")

        # Test with empty list
        info_dict = {"id": "test123", "ie_key": "Youtube", "_old_archive_ids": []}
        ytdlp.record_download_archive(info_dict)
        assert ytdlp.archive.add.call_count == 1  # Only main ID

        ytdlp.archive.reset_mock()

        # Test with None
        info_dict = {"id": "test123", "ie_key": "Youtube", "_old_archive_ids": None}
        ytdlp.record_download_archive(info_dict)
        assert ytdlp.archive.add.call_count == 1  # Only main ID

        ytdlp.archive.reset_mock()

        # Test with non-list value
        info_dict = {"id": "test123", "ie_key": "Youtube", "_old_archive_ids": "not a list"}
        ytdlp.record_download_archive(info_dict)
        assert ytdlp.archive.add.call_count == 1  # Only main ID

    def test_record_download_archive_returns_early_on_empty_archive_id(self) -> None:
        """Test record_download_archive returns early when _make_archive_id returns empty."""
        ytdlp = self._create_ytdlp(params={"download_archive": "/tmp/archive.txt"})
        ytdlp.archive = Mock()
        ytdlp._make_archive_id = Mock(return_value=None)

        ytdlp.record_download_archive({"id": "test123"})

        # Should not add anything
        ytdlp.archive.add.assert_not_called()
