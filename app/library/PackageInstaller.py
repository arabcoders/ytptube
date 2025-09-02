import importlib
import importlib.metadata
import logging
import os
import subprocess
import sys
from pathlib import Path

import httpx

LOG: logging.Logger = logging.getLogger("package_installer")

if base_dir := os.environ.get("YTP_CONFIG_PATH"):
    base_dir = Path(base_dir)
    user_site: Path = base_dir / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"

    if not user_site.exists():
        user_site.mkdir(parents=True, exist_ok=True)

    if user_site.is_dir() and str(user_site) not in sys.path:
        sys.path.insert(0, str(user_site))


def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int("".join(filter(str.isdigit, part)) or "0") for part in v.strip().split("."))


class Packages:
    def __init__(self, env: str | None, file: str | None, upgrade: bool = False):
        from_env = env.split() if env else []
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
    user_site: Path | None = None

    def __init__(self):
        if base_dir := os.environ.get("YTP_CONFIG_PATH"):
            base_dir = Path(base_dir)
            self.user_site = base_dir / f"python{sys.version_info.major}.{sys.version_info.minor}-packages"
            self.user_site.mkdir(parents=True, exist_ok=True)

            if str(self.user_site) not in sys.path:
                sys.path.insert(0, str(self.user_site))

    def action(self, pkg: str, upgrade: bool = False):
        version: str | None = None
        if "==" in pkg:
            pkg, version = pkg.split("==", 1)

        current_version: str | None = self._get_installed_version(pkg)

        if current_version and version and self.compare_versions(current_version, version):
            LOG.info(f"'{pkg}' is already installed with the specified version ({version}). Skipping installation.")
            return

        if upgrade and current_version and not version:
            latest_version: str | None = self._get_latest_version(pkg)
            if latest_version and parse_version(current_version) >= parse_version(latest_version):
                LOG.info(f"'{pkg}' is already the latest version ({current_version}). Skipping upgrade.")
                return

        if current_version:
            LOG.info(f"'{pkg}' is already installed (version: {current_version}). Proceeding with upgrade...")
        else:
            LOG.info(f"'{pkg}' is not installed. Installing...")

        self._install_pkg(pkg, version=version)

    def _get_installed_version(self, pkg: str) -> str | None:
        try:
            return importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            return None

    def _get_latest_version(self, pkg: str) -> str | None:
        url = f"https://pypi.org/pypi/{pkg}/json"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                if 200 == resp.status_code:
                    return resp.json()["info"]["version"]
                LOG.warning(f"Failed to fetch '{pkg}' info: HTTP {resp.status_code}")
        except Exception as e:
            LOG.warning(f"Error while querying PyPI for '{pkg}': {e}")
        return None

    def _install_pkg(self, pkg: str, version: str | None = None):
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

        if version:
            if "nightly" == version and pkg == "yt_dlp":
                cmd.extend(["--pre", "yt-dlp[default]"])
            elif "master" == version and pkg == "yt_dlp":
                cmd.append("git+https://github.com/yt-dlp/yt-dlp.git@master")
            else:
                cmd.append(version if str(version).startswith("git+") else f"{pkg}=={version}")
        else:
            cmd.extend(["--disable-pip-version-check", pkg])

        try:
            proc: subprocess.CompletedProcess[bytes] = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.out(out=proc.stdout, err=proc.stderr)
        except subprocess.CalledProcessError as e:
            LOG.error(f"Failed to install '{pkg}' (exit {e.returncode}). {e!s}")
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

        LOG.info(f"Checking for user pip packages: {', '.join(pkgs.packages)}")
        for package in pkgs.packages:
            try:
                self.action(package, upgrade=pkgs.allow_upgrade())
            except Exception as e:
                LOG.error(f"Failed to install or upgrade package '{package}'. Error message: {e!s}")
                LOG.exception(e)

    def compare_versions(self, current: str, target: str) -> bool:
        """
        Compare versions, handling yt-dlp format where pip uses 2025.7.21 but actual is 2025.07.21
        Returns True if versions match, False otherwise
        """
        if current == target:
            return True

        # Handle yt-dlp version format differences
        current_parts = current.split(".")
        target_parts = target.split(".")

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

    def out(self, out: bytes | str | None = None, err=bytes | str | None) -> None:
        if out:
            for line in (line.strip() for line in out.strip().splitlines() if line.strip()):
                LOG.info(line.decode() if isinstance(line, bytes) else line)

        if err:
            for line in (line.strip() for line in err.strip().splitlines() if line.strip()):
                LOG.warning(line.decode() if isinstance(line, bytes) else line)
