import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.library.PackageInstaller import PackageInstaller, Packages, parse_version
from app.tests.helpers import set_test_env


@pytest.fixture(autouse=True)
def restore_sys_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "path", sys.path.copy())


class TestParseVersion:
    def test_parse_version_basic(self) -> None:
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("01.002.0003") == (1, 2, 3)

    def test_parse_chars(self) -> None:
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

    def test_init_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        set_test_env(monkeypatch, {"config_path": tmp_path})
        installer = PackageInstaller(pkg_path=None)

        assert installer.user_site is not None
        assert installer.user_site.exists() is True
        assert str(installer.user_site) in sys.path

    def test_init_no_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        set_test_env(monkeypatch)
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
    def test_get_installed_version(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        write_metadata(tmp_path, "foo", "1.0.0")
        assert inst._get_installed_version("foo") == "1.0.0"

    def test_installed_version_not_found(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        assert inst._get_installed_version("bar") is None

    def test_distribution_target(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        write_metadata(tmp_path, "yt-dlp", "1.0.0")

        assert inst._get_distribution("yt_dlp").version == "1.0.0"

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
    def test_install_git(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("pkg", version="git+https://example/repo.git@abc")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "git+https://example/repo.git@abc" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_nightly(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("yt_dlp", version="nightly")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        # should include pre-release flag and yt-dlp extra
        assert "--pre" in cmd
        assert "yt-dlp[default]" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_master(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        mock_run.return_value = SimpleNamespace(returncode=0, stdout=b"o", stderr=b"e")

        ok = inst._install_pkg("yt_dlp", version="master")
        assert ok is True
        cmd = mock_run.call_args.args[0]
        assert "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git@master" in cmd

    @patch("app.library.PackageInstaller.subprocess.run")
    def test_install_process_error(self, mock_run, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)

        error = subprocess.CalledProcessError(1, ["pip"], output=b"o", stderr=b"e")
        mock_run.side_effect = error

        with pytest.raises(subprocess.CalledProcessError):
            inst._install_pkg("pkg")


def write_metadata(path: Path, name: str, version: str) -> None:
    dist_info = path / f"{name.replace('-', '_')}-{version}.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")


def package_response(version: str) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=200,
        json=lambda: {"releases": {version: [{"yanked": False}]}},
    )


def master_response(revision: str) -> SimpleNamespace:
    return SimpleNamespace(status_code=200, json=lambda: {"sha": revision})


class TestActionAndCheck:
    def test_ytdlp_invalid(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid yt-dlp version 'nighly'"):
            PackageInstaller(pkg_path=tmp_path).action("yt_dlp==nighly")

    def test_pinned_current(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "pkg", "1.2.3")
        with patch("app.library.PackageInstaller.subprocess.run") as run:
            PackageInstaller(pkg_path=tmp_path).action("pkg==1.2.3")
        run.assert_not_called()

    def test_upgrade_latest(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "pkg", "2.0.0")
        response = SimpleNamespace(status_code=200, json=lambda: {"info": {"version": "2.0.0"}})
        client = MagicMock()
        client.get.return_value = response
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch("app.library.PackageInstaller.subprocess.run") as run,
        ):
            http.return_value.__enter__.return_value = client
            PackageInstaller(pkg_path=tmp_path).action("pkg", upgrade=True)
        run.assert_not_called()

    def test_upgrade_newer(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "pkg", "1.0.0")
        response = SimpleNamespace(status_code=200, json=lambda: {"info": {"version": "1.1.0"}})
        client = MagicMock()
        client.get.return_value = response
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            PackageInstaller(pkg_path=tmp_path).action("pkg", upgrade=True)
        assert run.call_args.args[0][-1] == "pkg"

    def test_missing_package(self, tmp_path: Path) -> None:
        with patch(
            "app.library.PackageInstaller.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
        ) as run:
            PackageInstaller(pkg_path=tmp_path).action("pkg")
        assert run.call_args.args[0][-1] == "pkg"

    def test_nightly_current(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.2.2.dev0")
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "nightly", "version": "2025.6.2.2.dev0"})
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {"releases": {"2025.6.2.2.dev0": [{"yanked": False}]}},
        )
        client = MagicMock()
        client.get.return_value = response
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch("app.library.PackageInstaller.subprocess.run") as run,
        ):
            http.return_value.__enter__.return_value = client
            inst.action("yt_dlp==nightly", upgrade=True)
        run.assert_not_called()

    def test_nightly_installs(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.1.1.dev0")
        response = package_response("2025.6.2.2.dev0")
        client = MagicMock()
        client.get.return_value = response
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            inst = PackageInstaller(pkg_path=tmp_path)
            inst.action("yt_dlp==nightly", upgrade=True)
        assert "--pre" in run.call_args.args[0]
        assert inst._get_channel_state() == {"channel": "nightly", "version": "2025.6.2.2.dev0"}

    def test_nightly_newer(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.3.3.dev0")
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "nightly", "version": "2025.6.3.3.dev0"})
        client = MagicMock()
        client.get.return_value = package_response("2025.6.2.2.dev0")
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch("app.library.PackageInstaller.subprocess.run") as run,
        ):
            http.return_value.__enter__.return_value = client
            inst.action("yt_dlp==nightly", upgrade=True)
        run.assert_not_called()

    def test_nightly_lookup_failure(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.2.2.dev0")
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "nightly", "version": "2025.6.2.2.dev0"})
        with (
            patch("app.library.PackageInstaller.sync_client", side_effect=RuntimeError("offline")),
            patch("app.library.PackageInstaller.subprocess.run") as run,
        ):
            inst.action("yt_dlp==nightly", upgrade=True)
        run.assert_not_called()

    def test_nightly_without_state(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.2.2.dev0")
        with (
            patch("app.library.PackageInstaller.sync_client", side_effect=RuntimeError("offline")),
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            PackageInstaller(pkg_path=tmp_path).action("yt_dlp==nightly", upgrade=True)
        assert "--pre" in run.call_args.args[0]

    def test_nightly_missing(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.get.return_value = package_response("2025.6.2.2.dev0")
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            inst = PackageInstaller(pkg_path=tmp_path)
            inst.action("yt_dlp==nightly")
        assert "--pre" in run.call_args.args[0]
        assert inst._get_channel_state() == {"channel": "nightly", "version": "2025.6.2.2.dev0"}

    def test_nightly_restart(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.2.2.dev0")
        client = MagicMock()
        client.get.return_value = package_response("2025.6.2.2.dev0")

        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            PackageInstaller(pkg_path=tmp_path).action("yt_dlp==nightly")
            PackageInstaller(pkg_path=tmp_path).action("yt_dlp==nightly", upgrade=True)
        run.assert_called_once()

    def test_master_current(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.1")
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "master", "revision": "abc123"})
        response = SimpleNamespace(status_code=200, json=lambda: {"sha": "abc123"})
        client = MagicMock()
        client.get.return_value = response
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch("app.library.PackageInstaller.subprocess.run") as run,
        ):
            http.return_value.__enter__.return_value = client
            inst.action("yt_dlp==master", upgrade=True)
        run.assert_not_called()

    def test_master_installs(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.1")
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "master", "revision": "abc123"})
        response = master_response("def456")
        client = MagicMock()
        client.get.return_value = response
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            inst.action("yt_dlp==master", upgrade=True)
        assert "@master" in run.call_args.args[0][-1]
        assert inst._get_channel_state() == {"channel": "master", "revision": "def456"}

    def test_master_lookup_failure(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.1")
        inst = PackageInstaller(pkg_path=tmp_path)
        inst._set_channel_state({"channel": "master", "revision": "abc123"})
        with (
            patch("app.library.PackageInstaller.sync_client", side_effect=RuntimeError("offline")),
            patch("app.library.PackageInstaller.subprocess.run") as run,
        ):
            inst.action("yt_dlp==master", upgrade=True)
        run.assert_not_called()

    def test_master_missing(self, tmp_path: Path) -> None:
        client = MagicMock()
        client.get.return_value = master_response("def456")
        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            inst = PackageInstaller(pkg_path=tmp_path)
            inst.action("yt_dlp==master")
        assert "@master" in run.call_args.args[0][-1]
        assert inst._get_channel_state() == {"channel": "master", "revision": "def456"}

    def test_master_restart(self, tmp_path: Path) -> None:
        write_metadata(tmp_path, "yt-dlp", "2025.6.1")
        client = MagicMock()
        client.get.return_value = master_response("def456")

        with (
            patch("app.library.PackageInstaller.sync_client") as http,
            patch(
                "app.library.PackageInstaller.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ) as run,
        ):
            http.return_value.__enter__.return_value = client
            installer = PackageInstaller(pkg_path=tmp_path)
            installer.action("yt_dlp==master")
            PackageInstaller(pkg_path=tmp_path).action("yt_dlp==master", upgrade=True)
        run.assert_called_once()

    def test_check_runs_all(self, tmp_path: Path) -> None:
        inst = PackageInstaller(pkg_path=tmp_path)
        pkgs = Packages(env="foo bar", file=None, upgrade=True)
        pkgs.packages = ["foo", "bar"]

        with patch(
            "app.library.PackageInstaller.subprocess.run",
            side_effect=[
                subprocess.CalledProcessError(1, ["pip"], output=b"", stderr=b""),
                SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
            ],
        ) as run:
            inst.check(pkgs)

        assert run.call_count == 2
        assert {call.args[0][-1] for call in run.call_args_list} == {"foo", "bar"}
