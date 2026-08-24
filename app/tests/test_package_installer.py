import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.library.PackageInstaller import PackageInstaller, Packages, parse_version


@pytest.fixture(autouse=True)
def restore_sys_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", sys.path.copy())


class TestParseVersion:
    def test_parse_version_basic(self) -> None:
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("01.002.0003") == (1, 2, 3)

    def test_parse_version_with_chars(self) -> None:
        # Non-digits are stripped per part
        assert parse_version("1a.2b.3c") == (1, 2, 3)
        assert parse_version("2025.07.21") == (2025, 7, 21)


class TestPackages:
    def test_packages_env_file(self, tmp_path: Path) -> None:
        req = tmp_path / "req.txt"
        req.write_text("\nfoo\nbar==1.0.0\nfoo\n\n")

        pkgs = Packages(env="baz qux", file=str(req), upgrade=True)

        # Order not guaranteed (set), but content should be unique
        assert set(pkgs.packages) == {"foo", "bar==1.0.0", "baz", "qux"}
        assert pkgs.has_packages() is True
        assert pkgs.allow_upgrade() is True

    def test_packages_empty(self) -> None:
        pkgs = Packages(env=None, file=None, upgrade=False)
        assert pkgs.has_packages() is False
        assert pkgs.allow_upgrade() is False


class TestPackageInstallerInit:
    def test_init_adds_sys_path(self, tmp_path: Path) -> None:
        p = tmp_path / "site"
        p.mkdir()

        # Snapshot sys.path length to verify insertion
        original_len = len(sys.path)
        installer = PackageInstaller(pkg_path=p)

        assert installer.user_site == p
        assert sys.path[0] == str(p)
        assert len(sys.path) == original_len + 1

    def test_init_with_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("YTP_CONFIG_PATH", str(tmp_path))
        installer = PackageInstaller(pkg_path=None)

        assert installer.user_site is not None
        assert installer.user_site.exists() is True
        assert str(installer.user_site) in sys.path

    def test_init_no_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("YTP_CONFIG_PATH", raising=False)
        installer = PackageInstaller(pkg_path=None)
        # No user_site is set when no path or env provided
        assert installer.user_site is None


class TestVersionCompare:
    def test_compare_versions_equal(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        assert inst.compare_versions("1.2.3", "1.2.3") is True

    def test_yt_dlp_like_padding(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        assert inst.compare_versions("2025.7.21", "2025.07.21") is True
        assert inst.compare_versions("2025.07.1", "2025.7.01") is True

    def test_compare_versions_not_equal(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        assert inst.compare_versions("1.2.3", "1.2.4") is False


class TestInstalledAndLatest:
    @patch.object(PackageInstaller, "_get_distribution")
    def test_get_installed_version(self, mock_distribution, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_distribution.return_value.version = "1.0.0"
        assert inst._get_installed_version("foo") == "1.0.0"

    @patch.object(PackageInstaller, "_get_distribution")
    def test_installed_version_not_found(self, mock_distribution, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        from importlib.metadata import PackageNotFoundError

        mock_distribution.side_effect = PackageNotFoundError
        assert inst._get_installed_version("bar") is None

    @patch("app.library.PackageInstaller.importlib.metadata.distributions")
    def test_distribution_target(self, mock_distributions, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        distribution = MagicMock()
        distribution.metadata = {"Name": "yt-dlp"}
        mock_distributions.return_value = [distribution]

        assert inst._get_distribution("yt_dlp") is distribution
        mock_distributions.assert_called_once_with(path=[str(tmp_path)])

    @patch("app.library.PackageInstaller.sync_client")
    def test_get_latest_version_success(self, mock_client, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"info": {"version": "9.9.9"}}
        client.get.return_value = resp
        mock_client.return_value.__enter__.return_value = client

        assert inst._get_latest_version("foo") == "9.9.9"

    @patch("app.library.PackageInstaller.sync_client")
    def test_latest_prerelease(self, mock_client, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "info": {"version": "2025.6.1"},
            "releases": {
                "2025.5.1.1.dev0": [{"yanked": False}],
                "2025.6.2.2.dev0": [{"yanked": False}],
                "2025.6.3.3.dev0": [{"yanked": True}],
                "2025.6.4": [{"yanked": False}],
                "2025.6.5": [{"yanked": False, "requires_python": ">=99"}],
            },
        }
        client.get.return_value = resp
        mock_client.return_value.__enter__.return_value = client

        assert inst._get_latest_version("yt_dlp", prerelease=True) == "2025.6.4"

    @patch("app.library.PackageInstaller.sync_client")
    def test_prerelease_missing(self, mock_client, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"info": {"version": "2025.6.1"}, "releases": {}}
        client.get.return_value = resp
        mock_client.return_value.__enter__.return_value = client

        assert inst._get_latest_version("yt_dlp", prerelease=True) is None

    def test_channel_state(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        state = {"channel": "master", "revision": "abc123"}

        inst._set_channel_state(state)

        assert inst._get_channel_state() == state

    def test_state_malformed(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        (tmp_path / ".yt-dlp-channel.json").write_text("not-json")

        assert inst._get_channel_state() is None

    def test_state_removed(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "nightly", "version": "2025.6.4"})

        inst._set_channel_state(None)

        assert inst._get_channel_state() is None

    @patch("app.library.PackageInstaller.sync_client")
    def test_master_revision(self, mock_client, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"sha": "abc123"}
        client.get.return_value = resp
        mock_client.return_value.__enter__.return_value = client

        assert inst._get_master_revision() == "abc123"

    @patch("app.library.PackageInstaller.sync_client")
    def test_latest_version_non_200(self, mock_client, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        client = MagicMock()
        resp = MagicMock()
        resp.status_code = 404
        client.get.return_value = resp
        mock_client.return_value.__enter__.return_value = client
        assert inst._get_latest_version("foo") is None

    @patch("app.library.PackageInstaller.sync_client")
    def test_get_latest_version_exception(self, mock_client, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_client.side_effect = RuntimeError("boom")
        assert inst._get_latest_version("foo") is None


class TestInstallCmd:
    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_default_latest(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        # Simulate successful run
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"out", stderr=b"err")

        ok = inst._install_pkg("pkg")

        assert ok is True
        cmd = mock_run.call_args.kwargs["args"] if "args" in mock_run.call_args.kwargs else mock_run.call_args.args[0]
        assert cmd[:5] == [sys.executable, "-m", "pip", "install", "--no-warn-script-location"]
        assert "--disable-pip-version-check" in cmd
        assert "pkg" in cmd
        assert "--target" in cmd
        assert str(inst.user_site) in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_pinned_version(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("pkg", version="1.2.3")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "pkg==1.2.3" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_git_url_version(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("pkg", version="git+https://example/repo.git@abc")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "git+https://example/repo.git@abc" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_yt_dlp_nightly(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("yt_dlp", version="nightly")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        # should include pre-release flag and yt-dlp extra
        assert "--pre" in cmd
        assert "yt-dlp[default]" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_yt_dlp_master(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("yt_dlp", version="master")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git@master" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_called_process_error(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        err = SimpleNamespace(returncode=1, stdout=b"o", stderr=b"e")

        class _CPEError(Exception):
            def __init__(self) -> None:
                self.returncode = err.returncode
                self.stdout = err.stdout
                self.stderr = err.stderr
                super().__init__("fail")

        mock_run.side_effect = _CPEError()

        with pytest.raises(_CPEError, match="fail"):
            inst._install_pkg("pkg")


class TestActionAndCheck:
    @patch.object(PackageInstaller, "_install_pkg")
    def test_ytdlp_invalid(self, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        with pytest.raises(ValueError, match="Invalid yt-dlp version 'nighly'"):
            inst.action("yt_dlp==nighly", upgrade=True)

        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_action_skip_pinned(self, mock_get_installed, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_get_installed.return_value = "1.2.3"
        # compare_versions normal equality should hold
        inst.action("pkg==1.2.3")
        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_installed_version")
    @patch.object(PackageInstaller, "_get_latest_version")
    def test_action_skip_latest(self, mock_get_latest, mock_get_installed, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_get_installed.return_value = "2.0.0"
        mock_get_latest.return_value = "2.0.0"
        inst.action("pkg", upgrade=True)
        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_installed_version")
    @patch.object(PackageInstaller, "_get_latest_version")
    def test_action_upgrade_newer(self, mock_get_latest, mock_get_installed, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_get_installed.return_value = "1.0.0"
        mock_get_latest.return_value = "1.1.0"
        inst.action("pkg", upgrade=True)
        mock_install.assert_called_once_with("pkg", version=None)

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_action_install_missing(self, mock_get_installed, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_get_installed.return_value = None
        inst.action("pkg")
        mock_install.assert_called_once_with("pkg", version=None)

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_channel_state")
    @patch.object(PackageInstaller, "_get_latest_version")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_nightly_current(self, mock_installed, mock_latest, mock_state, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_installed.return_value = "2025.6.2.2.dev0"
        mock_latest.return_value = "2025.6.2.2.dev0"
        mock_state.return_value = {"channel": "nightly", "version": "2025.6.2.2.dev0"}

        inst.action("yt_dlp==nightly", upgrade=True)

        mock_latest.assert_called_once_with("yt_dlp", prerelease=True)
        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_channel_state")
    @patch.object(PackageInstaller, "_get_latest_version")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_nightly_newer(self, mock_installed, mock_latest, mock_state, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_installed.return_value = "2025.6.3.3.dev0"
        mock_latest.return_value = "2025.6.2.2.dev0"
        mock_state.return_value = {"channel": "nightly", "version": "2025.6.3.3.dev0"}

        inst.action("yt_dlp==nightly", upgrade=True)

        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_latest_version")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_nightly_outdated(self, mock_installed, mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_installed.return_value = "2025.6.1.1.dev0"
        mock_latest.return_value = "2025.6.2.2.dev0"

        inst.action("yt_dlp==nightly", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="nightly")

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_latest_version")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_nightly_lookup_fails(self, mock_installed, mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_installed.return_value = "2025.6.1.1.dev0"
        mock_latest.return_value = None

        inst.action("yt_dlp==nightly", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="nightly")

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_channel_state")
    @patch.object(PackageInstaller, "_get_latest_version")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_nightly_lookup_keeps(self, mock_installed, mock_latest, mock_state, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_installed.return_value = "2025.6.1.1.dev0"
        mock_latest.return_value = None
        mock_state.return_value = {"channel": "nightly", "version": "2025.6.1.1.dev0"}

        inst.action("yt_dlp==nightly", upgrade=True)

        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg", return_value=True)
    @patch.object(
        PackageInstaller, "_get_channel_state", return_value={"channel": "nightly", "version": "2025.6.2.2.dev0"}
    )
    @patch.object(PackageInstaller, "_get_latest_version", return_value="2025.6.2.2.dev0")
    @patch.object(PackageInstaller, "_get_installed_version", return_value=None)
    def test_nightly_missing(self, _mock_version, _mock_latest, _mock_state, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        inst.action("yt_dlp==nightly", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="nightly")

    @patch.object(PackageInstaller, "_install_pkg", return_value=True)
    @patch.object(PackageInstaller, "_get_latest_version", return_value="2025.6.2.2.dev0")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_nightly_restart(self, _mock_version, _mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        _mock_version.side_effect = ["2025.6.1", "2025.6.2.2.dev0"]

        inst.action("yt_dlp==nightly", upgrade=True)
        inst.action("yt_dlp==nightly", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="nightly")

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_master_revision")
    @patch.object(PackageInstaller, "_get_channel_state")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_master_current(self, mock_version, mock_installed, mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_version.return_value = "2025.6.1"
        mock_installed.return_value = {"channel": "master", "revision": "abc123"}
        mock_latest.return_value = "abc123"

        inst.action("yt_dlp==master", upgrade=True)

        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_master_revision")
    @patch.object(PackageInstaller, "_get_channel_state")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_master_outdated(self, mock_version, mock_installed, mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_version.return_value = "2025.6.1"
        mock_installed.return_value = {"channel": "master", "revision": "abc123"}
        mock_latest.return_value = "def456"

        inst.action("yt_dlp==master", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="master")

    @patch.object(PackageInstaller, "_install_pkg")
    @patch.object(PackageInstaller, "_get_master_revision")
    @patch.object(PackageInstaller, "_get_channel_state")
    @patch.object(PackageInstaller, "_get_installed_version")
    def test_master_lookup_fails(self, mock_version, mock_installed, mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_version.return_value = "2025.6.1"
        mock_installed.return_value = {"channel": "master", "revision": "abc123"}
        mock_latest.return_value = None

        inst.action("yt_dlp==master", upgrade=True)

        mock_install.assert_not_called()

    @patch.object(PackageInstaller, "_install_pkg", return_value=True)
    @patch.object(PackageInstaller, "_get_master_revision", return_value="abc123")
    @patch.object(PackageInstaller, "_get_channel_state", return_value={"channel": "master", "revision": "abc123"})
    @patch.object(PackageInstaller, "_get_installed_version", return_value=None)
    def test_master_missing(self, _mock_version, _mock_state, _mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        inst.action("yt_dlp==master", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="master")

    @patch.object(PackageInstaller, "_install_pkg", return_value=True)
    @patch.object(PackageInstaller, "_get_master_revision", return_value="abc123")
    @patch.object(PackageInstaller, "_get_installed_version", return_value="2025.6.1")
    def test_master_restart(self, _mock_version, _mock_latest, mock_install, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        inst.action("yt_dlp==master", upgrade=True)
        inst.action("yt_dlp==master", upgrade=True)

        mock_install.assert_called_once_with("yt_dlp", version="master")

    @patch.object(PackageInstaller, "action")
    def test_check_runs_all(self, mock_action, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        pkgs = Packages(env="foo bar", file=None, upgrade=True)

        # First call raises, second succeeds
        def side_effect(pkg, upgrade=False):  # noqa: ARG001
            if pkg == "foo":
                msg = "boom"
                raise RuntimeError(msg)

        mock_action.side_effect = side_effect

        inst.check(pkgs)
        assert mock_action.call_count == 2
        mock_action.assert_any_call("foo", upgrade=True)
        mock_action.assert_any_call("bar", upgrade=True)
