import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from app.library.logging import get_logger

from .httpx_client import sync_client

LOG = get_logger()

YTDLP_MASTER_API_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/commits/master"
YTDLP_MASTER_URL = "https://github.com/yt-dlp/yt-dlp.git"


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int("".join(filter(str.isdigit, part)) or "0") for part in v.strip().split("."))


class Packages:
    def __init__(self, env: str | None, file: str | Path | None, upgrade: bool = False):
        from_env: list[str] = env.split() if env else []
        from_file = []

        if file:
            file = Path(file)
            if file.exists() and os.access(str(file), os.R_OK):
                with open(file) as f:
                    from_file: list[str] = [pkg.strip() for pkg in f if pkg.strip()]

        self.packages: list[str] = list(set(from_env + from_file))
        self.upgrade = bool(upgrade)

    def has_packages(self) -> bool:
        return len(self.packages) > 0

    def allow_upgrade(self) -> bool:
        return self.upgrade


class PackageInstaller:
    def __init__(self, pkg_path: Path | None = None):
        self.user_site: Path | None = None
        "Where to install user packages."

        if pkg_path:
            self.user_site = pkg_path

        if not self.user_site and (base_dir := os.environ.get("YTP_CONFIG_PATH")):
            base_dir = Path(base_dir)
            self.user_site = base_dir / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
            self.user_site.mkdir(parents=True, exist_ok=True)

        if not self.user_site:
            LOG.error("No valid package path provided or found in environment. Aborting.")
            return

        if str(self.user_site) not in sys.path:
            sys.path.insert(0, str(self.user_site))

    def action(self, pkg: str, upgrade: bool = False) -> None:
        version: str | None = None
        if "==" in pkg:
            pkg, version = pkg.split("==", 1)

        if "yt_dlp" == pkg and version and version not in {"master", "nightly"}:
            try:
                Version(version)
            except InvalidVersion as e:
                msg = f"Invalid yt-dlp version '{version}'; expected 'nightly', 'master', or a valid version."
                raise ValueError(msg) from e

        current_version: str | None = self._get_installed_version(pkg)
        target_version: str | None = version
        latest_revision: str | None = None
        channel_state = self._get_channel_state() if "yt_dlp" == pkg else None
        channel_changed = bool(channel_state and version != channel_state.get("channel"))

        if "yt_dlp" == pkg and "nightly" == version:
            target_version = self._get_latest_version(pkg, prerelease=True)
            installed_version = channel_state.get("version") if channel_state and not channel_changed else None
            if installed_version and (not current_version or Version(current_version) != Version(installed_version)):
                installed_version = None
            if installed_version and not target_version:
                LOG.info("Keeping the installed yt-dlp nightly because the latest version could not be determined.")
                return
            if installed_version and target_version and Version(installed_version) >= Version(target_version):
                LOG.info(
                    "Package '%s' is already installed from the latest nightly channel; skipping installation.",
                    pkg,
                    extra={"package": pkg, "installed_version": installed_version, "latest_version": target_version},
                )
                return
        elif "yt_dlp" == pkg and "master" == version:
            latest_revision = self._get_master_revision()
            installed_revision = (
                channel_state.get("revision") if current_version and channel_state and not channel_changed else None
            )
            if installed_revision and not latest_revision:
                LOG.info("Keeping the installed yt-dlp master because the latest revision could not be determined.")
                return
            if installed_revision and latest_revision and installed_revision == latest_revision:
                LOG.info(
                    "Package '%s' is already installed from the latest master revision; skipping installation.",
                    pkg,
                    extra={"package": pkg, "installed_revision": installed_revision},
                )
                return

        is_current = bool(
            current_version
            and target_version
            and not channel_changed
            and version not in {"master", "nightly"}
            and (self.compare_versions(current_version, target_version))
        )
        if is_current:
            LOG.info(
                "Package '%s' is already installed at version '%s'; skipping installation.",
                pkg,
                current_version,
                extra={"package": pkg, "installed_version": current_version, "requested_version": target_version},
            )
            return

        if upgrade and current_version and not version and not channel_changed:
            latest_version: str | None = self._get_latest_version(pkg)
            if latest_version and parse_version(current_version) >= parse_version(latest_version):
                LOG.info(
                    "Package '%s' is already at the latest version '%s'; skipping upgrade.",
                    pkg,
                    current_version,
                    extra={"package": pkg, "installed_version": current_version, "latest_version": latest_version},
                )
                return

        if current_version:
            LOG.info(
                "Package '%s' is installed at '%s'; proceeding with upgrade.",
                pkg,
                current_version,
                extra={"package": pkg, "installed_version": current_version},
            )
        else:
            LOG.info("Package '%s' is not installed; installing it.", pkg, extra={"package": pkg})

        installed = self._install_pkg(pkg, version=version)
        if installed and "yt_dlp" == pkg:
            if "nightly" == version and target_version:
                self._set_channel_state({"channel": "nightly", "version": target_version})
            elif "master" == version and latest_revision:
                self._set_channel_state({"channel": "master", "revision": latest_revision})
            else:
                self._set_channel_state(None)

    def _get_installed_version(self, pkg: str) -> str | None:
        try:
            return self._get_distribution(pkg).version
        except importlib.metadata.PackageNotFoundError:
            return None

    def _get_distribution(self, pkg: str) -> importlib.metadata.Distribution:
        normalized = pkg.lower().replace("_", "-").replace(".", "-")
        if self.user_site:
            for distribution in importlib.metadata.distributions(path=[str(self.user_site)]):
                name = distribution.metadata["Name"].lower().replace("_", "-").replace(".", "-")
                if normalized == name:
                    return distribution
        return importlib.metadata.distribution(pkg)

    def _get_latest_version(self, pkg: str, prerelease: bool = False) -> str | None:
        url: str = f"https://pypi.org/pypi/{pkg}/json"
        try:
            with sync_client(timeout=5.0) as client:
                resp = client.get(url)
                if 200 == resp.status_code:
                    data = resp.json()
                    if prerelease:
                        versions: list[tuple[Version, str]] = []
                        for version, files in data.get("releases", {}).items():
                            try:
                                parsed = Version(version)
                            except InvalidVersion:
                                continue
                            if any(self._is_compatible(file) for file in files):
                                versions.append((parsed, version))
                        return max(versions)[1] if versions else None
                    return data["info"]["version"]
                LOG.warning(
                    "Failed to fetch PyPI metadata for '%s': HTTP %s.",
                    pkg,
                    resp.status_code,
                    extra={"package": pkg, "status_code": resp.status_code, "url": url},
                )
        except Exception as e:
            LOG.warning(
                "Failed to query PyPI for '%s': %s",
                pkg,
                e,
                extra={"package": pkg, "url": url, "exception_type": type(e).__name__},
                exc_info=True,
            )
        return None

    def _is_compatible(self, file: dict) -> bool:
        if file.get("yanked", False):
            return False
        requires_python = file.get("requires_python")
        if not requires_python:
            return True
        try:
            return Version(platform.python_version()) in SpecifierSet(requires_python)
        except InvalidSpecifier:
            return False

    def _get_channel_state(self) -> dict[str, str] | None:
        if not self.user_site:
            return None
        try:
            state = json.loads((self.user_site / ".yt-dlp-channel.json").read_text())
            if not isinstance(state, dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in state.items()
            ):
                return None
            return state
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _set_channel_state(self, state: dict[str, str] | None) -> None:
        if not self.user_site:
            return
        state_file = self.user_site / ".yt-dlp-channel.json"
        try:
            if state:
                temp_file = state_file.with_suffix(".tmp")
                temp_file.write_text(json.dumps(state))
                temp_file.replace(state_file)
            else:
                state_file.unlink(missing_ok=True)
        except OSError as e:
            LOG.warning(
                "Failed to persist yt-dlp channel state: %s",
                e,
                extra={"state_file": str(state_file), "exception_type": type(e).__name__},
                exc_info=True,
            )

    def _get_master_revision(self) -> str | None:
        try:
            with sync_client(timeout=5.0) as client:
                resp = client.get(YTDLP_MASTER_API_URL, headers={"Accept": "application/vnd.github+json"})
                if 200 == resp.status_code:
                    return resp.json().get("sha")
                LOG.warning(
                    "Failed to fetch yt-dlp master metadata: HTTP %s.",
                    resp.status_code,
                    extra={"status_code": resp.status_code, "url": YTDLP_MASTER_API_URL},
                )
        except Exception as e:
            LOG.warning(
                "Failed to query yt-dlp master metadata: %s",
                e,
                extra={"url": YTDLP_MASTER_API_URL, "exception_type": type(e).__name__},
                exc_info=True,
            )
        return None

    def _install_pkg(self, pkg: str, version: str | None = None) -> bool:
        cmd: list[str] = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-warn-script-location",
            "--upgrade",
            "--target",
            str(self.user_site),
        ]

        if "yt_dlp" == pkg:
            pkg = "yt-dlp"

        pkg_name: str = "yt-dlp[default]" if pkg == "yt-dlp" else pkg
        if version:
            if "nightly" == version and "yt-dlp" == pkg:
                cmd.extend(["--pre", pkg_name])
            elif "master" == version and "yt-dlp" == pkg:
                cmd.append(f"{pkg_name} @ git+{YTDLP_MASTER_URL}@master")
            else:
                cmd.append(version if str(version).startswith("git+") else f"{pkg_name}=={version}")
        else:
            cmd.extend(["--disable-pip-version-check", pkg_name])

        try:
            proc: subprocess.CompletedProcess[bytes] = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.out(out=proc.stdout, err=proc.stderr)

            return 0 == proc.returncode
        except subprocess.CalledProcessError as e:
            LOG.exception(
                "Failed to install package '%s' (exit %s).",
                pkg,
                e.returncode,
                extra={"package": pkg, "returncode": e.returncode, "exception_type": type(e).__name__},
            )
            self.out(out=e.stdout, err=e.stderr)
            raise

    def check(self, pkgs: Packages):
        """
        Checks for user supplied pip packages and installs them if they are not already installed.

        Args:
            pkgs (GetPackages): the class with packages and their settings.

        """
        if not pkgs.has_packages() or not self.user_site:
            return

        LOG.info("Checking configured user pip packages.", extra={"packages": pkgs.packages})
        for package in pkgs.packages:
            try:
                self.action(package, upgrade=pkgs.allow_upgrade())
            except Exception as e:
                LOG.exception(
                    "Failed to install or upgrade package '%s'.",
                    package,
                    extra={
                        "package": package,
                        "allow_upgrade": pkgs.allow_upgrade(),
                        "exception_type": type(e).__name__,
                    },
                )

    def compare_versions(self, current: str, target: str) -> bool:
        """
        Compare versions, handling yt-dlp format where pip uses 2025.7.21 but actual is 2025.07.21
        Returns True if versions match, False otherwise
        """
        if current == target:
            return True

        # Handle yt-dlp version format differences
        current_parts: list[str] = current.split(".")
        target_parts: list[str] = target.split(".")

        if len(current_parts) == len(target_parts):
            # Normalize parts by zero-padding single digits
            current_normalized: list[str] = [
                part.zfill(2) if part.isdigit() and len(part) == 1 else part for part in current_parts
            ]
            target_normalized: list[str] = [
                part.zfill(2) if part.isdigit() and len(part) == 1 else part for part in target_parts
            ]
            if current_normalized == target_normalized:
                return True

        return False

    def out(self, out: bytes | str | None = None, err: bytes | str | None = None) -> None:
        if out:
            for line in (line.strip() for line in out.strip().splitlines() if line.strip()):
                LOG.info(line.decode() if isinstance(line, bytes) else line)

        if err:
            for line in (line.strip() for line in err.strip().splitlines() if line.strip()):
                LOG.warning(line.decode() if isinstance(line, bytes) else line)
