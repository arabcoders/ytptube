
from unittest.mock import MagicMock, patch

from app.library.Utils import REMOVE_KEYS
from app.library.ytdlp import _ArchiveProxy, ytdlp_options


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
