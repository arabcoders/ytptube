from __future__ import annotations

import asyncio
import importlib.metadata
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.library.config import Config
from app.library.httpx_client import resolve_curl_transport

CheckStatus = Literal["pass", "fail", "warn", "skip"]
ReportStatus = Literal["ok", "degraded", "error"]

MIN_PYTHON: tuple[int, int] = (3, 13)


@dataclass(kw_only=True)
class DiagnosticCheck:
    id: str
    label: str
    group: str
    required: bool
    status: CheckStatus
    description: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "group": self.group,
            "required": self.required,
            "status": self.status,
            "description": self.description,
            "message": self.message,
            "details": self.details,
        }


@dataclass(frozen=True, kw_only=True)
class CheckMeta:
    group: str
    description: str


BINARY_META: dict[str, CheckMeta] = {
    "ffmpeg": CheckMeta(
        group="core", description="Used for thumbnails and streaming and various media processing tasks."
    ),
    "ffprobe": CheckMeta(group="core", description="Used for media inspection and metadata extraction."),
    "deno": CheckMeta(group="youtube", description="Used for yt-dlp YouTube support."),
    "yt_dlp_cli": CheckMeta(group="core", description="Used by the built-in terminal."),
    "aria2c": CheckMeta(group="advanced", description="External downloader for yt-dlp."),
    "mkvpropedit": CheckMeta(group="advanced", description="Edit Matroska container properties without remux."),
    "mkvextract": CheckMeta(group="advanced", description="Extract tracks from Matroska containers."),
    "mp4box": CheckMeta(group="advanced", description="MP4 container manipulation tool."),
}

DIRECTORY_DESCRIPTIONS: dict[str, str] = {
    "config_path": "Directory for config files and app data.",
    "download_path": "Directory where downloads are saved.",
    "temp_path": "Directory used for temporary files.",
}


def _first_line(*parts: str) -> str:
    for part in parts:
        for line in part.splitlines():
            if line := line.strip():
                return line

    return ""


def _bin_version(value: str) -> str:
    if not (line := value.strip()):
        return ""

    if match := re.match(r"^deno\s+([0-9][^\s]*)", line, flags=re.IGNORECASE):
        return match.group(1).strip()

    if match := re.match(r"^mkv\w+\s+v([0-9][^\s]*)", line, flags=re.IGNORECASE):
        return match.group(1).strip()

    if match := re.search(r"\bversion\s+(.+?)(?:\s+Copyright\b|$)", line, flags=re.IGNORECASE):
        return match.group(1).strip()

    return line


def _parse_browser_url(value: str) -> tuple[str, str]:
    if value.startswith(("selenium+http://", "selenium+https://")):
        return "selenium", value.removeprefix("selenium+")

    if value.startswith(("playwright+ws://", "playwright+wss://")):
        return "playwright", value.removeprefix("playwright+")

    if value.startswith("playwright+cdp://"):
        return "playwright", f"http://{value.removeprefix('playwright+cdp://')}"

    if value.startswith("playwright+cdp+"):
        return "playwright", value.removeprefix("playwright+cdp+")

    return "unknown", value


def _safe_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return "***"

    if not parsed.scheme or not parsed.netloc:
        return "***"

    netloc = parsed.netloc
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        netloc = f"***:***@{host}" if host else "***:***"

    path = "/***" if parsed.path and parsed.path != "/" else parsed.path
    query = "***" if parsed.query else ""
    fragment = "***" if parsed.fragment else ""
    return urllib.parse.urlunsplit((parsed.scheme, netloc, path, query, fragment))


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _package_check(
    name: str,
    *,
    label: str,
    group: str,
    required: bool,
    description: str,
    present_message: str = "Installed.",
    missing_message: str = "Missing.",
    missing_status: CheckStatus = "skip",
    check_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> DiagnosticCheck:
    version = _package_version(name)
    installed = version is not None
    base_details: dict[str, Any] = {"package": name, "version": version}
    if details:
        base_details.update(details)

    return DiagnosticCheck(
        id=check_id or name.replace("-", "_"),
        label=label,
        group=group,
        required=required,
        status="pass" if installed else ("fail" if required else missing_status),
        description=description,
        message=present_message if installed else missing_message,
        details=base_details,
    )


def _check_ytdlp_package() -> DiagnosticCheck:
    version = Config._ytdlp_version()
    installed = version != "0.0.0"

    return DiagnosticCheck(
        id="yt_dlp_package",
        label="yt-dlp package",
        group="core",
        required=True,
        status="pass" if installed else "fail",
        description="Main downloader library used by the app.",
        message="Installed." if installed else "Missing.",
        details={"version": version},
    )


def _check_apprise_package(config: Config) -> DiagnosticCheck:
    configured = Path(config.apprise_config).exists()
    return _package_check(
        "apprise",
        label="Apprise",
        group="notifications",
        required=False,
        description="Sends notification targets.",
        present_message="Installed.",
        missing_message="Missing." if configured else "Not installed.",
        missing_status="warn" if configured else "skip",
        check_id="apprise",
        details={"config": str(config.apprise_config) if configured else None},
    )


def _check_curl_transport() -> DiagnosticCheck:
    available = resolve_curl_transport(use_curl=True)
    version = _package_version("httpx-curl-cffi")

    return DiagnosticCheck(
        id="curl_transport",
        label="curl-cffi transport",
        group="advanced",
        required=False,
        status="pass" if available else "skip",
        description="Transport for impersonation support.",
        message="Installed." if available else "Not installed.",
        details={"package": "httpx-curl-cffi", "version": version},
    )


def _check_pot_provider_package() -> DiagnosticCheck:
    return _package_check(
        "bgutil-ytdlp-pot-provider",
        check_id="pot_provider_plugin",
        label="POT provider plugin",
        group="youtube",
        required=False,
        description="Optional plugin for external POT token providers for youtube.",
        present_message="Installed.",
        missing_message="Not installed.",
    )


def _check_configured_pip_packages(config: Config) -> list[DiagnosticCheck]:
    checks: list[DiagnosticCheck] = []

    for raw_pkg in config.pip_packages.split(" "):
        pkg = raw_pkg.strip()
        if not pkg:
            continue

        name = pkg.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].strip()
        installed = False
        version = None

        try:
            version = importlib.metadata.version(name)
            installed = True
        except importlib.metadata.PackageNotFoundError:
            installed = False

        checks.append(
            DiagnosticCheck(
                id=f"pip_{name.replace('-', '_')}",
                label=name,
                group="custom",
                required=False,
                status="pass" if installed else "warn",
                description="Configured extra pip package.",
                message="Installed." if installed else "Missing.",
                details={"package": name, "requested": pkg, "version": version},
            )
        )

    return checks


def _check_browser_endpoint() -> DiagnosticCheck:
    raw_url = (os.environ.get("YTP_BROWSER_URL") or "").strip()
    if not raw_url:
        return DiagnosticCheck(
            id="browser_endpoint",
            label="Remote browser",
            group="advanced",
            required=False,
            status="skip",
            description="Endpoint used by the browser extractor.",
            message="Not configured.",
            details={},
        )

    engine, parsed_url = _parse_browser_url(raw_url)
    if engine == "unknown":
        return DiagnosticCheck(
            id="browser_endpoint",
            label="Remote browser",
            group="advanced",
            required=False,
            status="warn",
            description="Endpoint used by the browser extractor.",
            message="Invalid URL.",
            details={"endpoint": _safe_url(raw_url)},
        )

    return DiagnosticCheck(
        id="browser_endpoint",
        label="Remote browser",
        group="advanced",
        required=False,
        status="pass",
        description="Endpoint used by the browser extractor.",
        message="Configured.",
        details={
            "engine": engine,
            "endpoint": _safe_url(parsed_url),
        },
    )


def _check_browser_client() -> DiagnosticCheck:
    raw_url = (os.environ.get("YTP_BROWSER_URL") or "").strip()
    if not raw_url:
        return DiagnosticCheck(
            id="browser_client",
            label="Browser client",
            group="advanced",
            required=False,
            status="skip",
            description="Client package required for the configured browser backend.",
            message="Not configured.",
            details={},
        )

    engine, _ = _parse_browser_url(raw_url)
    if engine == "unknown":
        return DiagnosticCheck(
            id="browser_client",
            label="Browser client",
            group="advanced",
            required=False,
            status="skip",
            description="Client package required for the configured browser backend.",
            message="Invalid URL.",
            details={},
        )

    package_name = "selenium" if engine == "selenium" else "playwright"
    version = _package_version(package_name)

    return DiagnosticCheck(
        id="browser_client",
        label="Browser client",
        group="advanced",
        required=False,
        status="pass" if version else "warn",
        description="Client package required for the configured browser backend.",
        message="Installed." if version else "Missing.",
        details={"package": package_name, "version": version},
    )


def _check_flaresolverr(config: Config) -> DiagnosticCheck:
    endpoint = (config.flaresolverr_url or "").strip()
    if not endpoint:
        return DiagnosticCheck(
            id="flaresolverr",
            label="FlareSolverr",
            group="advanced",
            required=False,
            status="skip",
            description="Optional Cloudflare challenge bypass service.",
            message="Not configured.",
            details={},
        )

    parsed = urllib.parse.urlsplit(endpoint)
    valid = parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    return DiagnosticCheck(
        id="flaresolverr",
        label="FlareSolverr",
        group="advanced",
        required=False,
        status="pass" if valid else "warn",
        description="Optional Cloudflare challenge bypass service.",
        message="Configured." if valid else "Invalid URL.",
        details={"endpoint": _safe_url(endpoint)},
    )


def _probe_directory(path: Path) -> tuple[CheckStatus, str]:
    if not path.exists():
        return "fail", "Directory does not exist."

    if not path.is_dir():
        return "fail", "Path is not a directory."

    if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
        return "fail", "Not readable or writable."

    return "pass", "Writable."


async def _check_directory(path: Path, *, check_id: str, label: str) -> DiagnosticCheck:
    status, message = await asyncio.to_thread(_probe_directory, path)
    return DiagnosticCheck(
        id=check_id,
        label=label,
        group="core",
        required=True,
        status=status,
        description=DIRECTORY_DESCRIPTIONS.get(check_id, "Directory check."),
        message=message,
        details={"path": str(path)},
    )


def _probe_db_file(path: Path) -> tuple[CheckStatus, str]:
    if not path.exists():
        return "fail", "Missing."

    if not path.is_file():
        return "fail", "Invalid path."

    if not os.access(path, os.R_OK):
        return "fail", "Not readable."

    if not os.access(path, os.W_OK):
        return "fail", "Not writable."

    try:
        uri = f"file:{urllib.parse.quote(str(path))}?mode=ro"
        with sqlite3.connect(uri, timeout=3, uri=True) as conn:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1")
    except sqlite3.Error as exc:
        return "fail", f"SQLite error. {exc!s}"

    return "pass", "Ready."


async def _check_db_file(path: Path) -> DiagnosticCheck:
    status, message = await asyncio.to_thread(_probe_db_file, path)
    return DiagnosticCheck(
        id="database",
        label="SQLite database",
        group="core",
        required=True,
        status=status,
        description="Local database used for app state and history.",
        message=message,
        details={"path": str(path)},
    )


async def _run_command(command: str, *args: str, wait_seconds: float = 5.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        command,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=wait_seconds)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise

    return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


def _binary_meta(check_id: str) -> CheckMeta:
    return BINARY_META.get(check_id, CheckMeta(group="core", description="Command line tool."))


def _make_binary_check(
    command: str,
    *,
    check_id: str,
    label: str,
    required: bool,
    status: CheckStatus,
    message: str,
    path: str | None = None,
    version: str | None = None,
) -> DiagnosticCheck:
    meta = _binary_meta(check_id)
    details: dict[str, Any] = {"command": command}

    if path:
        details["path"] = path
    if version:
        details["version"] = version

    return DiagnosticCheck(
        id=check_id,
        label=label,
        group=meta.group,
        required=required,
        status=status,
        description=meta.description,
        message=message,
        details=details,
    )


def _resolve_binary(*names: str) -> tuple[str, str | None]:
    for name in names:
        path = shutil.which(name)
        if path:
            return name, path
    return names[0], None


async def _check_binary(
    command: str,
    *,
    check_id: str,
    label: str,
    required: bool,
    args: tuple[str, ...] = ("--version",),
    enabled: bool = True,
    disabled_message: str = "Check is not applicable.",
    missing_status: CheckStatus | None = None,
    aliases: tuple[str, ...] = (),
) -> DiagnosticCheck:
    if not enabled:
        return _make_binary_check(
            command,
            check_id=check_id,
            label=label,
            required=required,
            status="skip",
            message=disabled_message,
        )

    resolved_name, command_path = _resolve_binary(command, *aliases)
    not_found_status: CheckStatus = missing_status or ("fail" if required else "warn")

    if not command_path:
        return _make_binary_check(
            resolved_name,
            check_id=check_id,
            label=label,
            required=required,
            status=not_found_status,
            message="Missing." if not_found_status == "fail" else "Not installed.",
        )

    try:
        return_code, stdout, stderr = await _run_command(resolved_name, *args)
    except FileNotFoundError:
        return _make_binary_check(
            resolved_name,
            check_id=check_id,
            label=label,
            required=required,
            status=not_found_status,
            message="Missing." if not_found_status == "fail" else "Not installed.",
            path=command_path,
        )
    except TimeoutError:
        return _make_binary_check(
            resolved_name,
            check_id=check_id,
            label=label,
            required=required,
            status="fail" if required else "warn",
            message="Timed out.",
            path=command_path,
        )
    except Exception as exc:
        return _make_binary_check(
            resolved_name,
            check_id=check_id,
            label=label,
            required=required,
            status="fail" if required else "warn",
            message=f"Error. {exc!s}",
            path=command_path,
        )

    version: str = _bin_version(_first_line(stdout, stderr))
    status: CheckStatus = "pass" if return_code == 0 else ("fail" if required else "warn")
    message: str = "Available." if return_code == 0 else f"Exit code {return_code}."

    return _make_binary_check(
        resolved_name,
        check_id=check_id,
        label=label,
        required=required,
        status=status,
        message=message,
        path=command_path,
        version=version,
    )


def _make_runtime(config: Config) -> dict[str, Any]:
    started = int(config.started) if config.started else 0
    uptime_seconds = max(int(time.time()) - started, 0) if started else 0

    return {
        "app_version": config.app_version,
        "app_branch": config.app_branch,
        "app_commit_sha": config.app_commit_sha,
        "app_build_date": config.app_build_date,
        "started": started,
        "uptime_seconds": uptime_seconds,
        "platform": platform.system().lower(),
        "platform_release": platform.release(),
        "platform_machine": platform.machine(),
        "python_version": platform.python_version(),
        "python_minimum": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
        "is_native": config.is_native,
        "console_enabled": config.console_enabled,
    }


def _requirements() -> dict[str, Any]:
    return {
        "python": {
            "current": platform.python_version(),
            "required": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            "supported": sys.version_info[:2] >= MIN_PYTHON,
            "note": "",
        }
    }


def _summarize(checks: list[DiagnosticCheck]) -> tuple[ReportStatus, dict[str, int]]:
    summary = {"total": len(checks), "pass": 0, "fail": 0, "warn": 0, "skip": 0, "required_failed": 0}

    for check in checks:
        summary[check.status] += 1
        if check.required and check.status == "fail":
            summary["required_failed"] += 1

    if summary["required_failed"] > 0:
        status: ReportStatus = "error"
    elif summary["warn"] > 0 or any(check.status == "fail" for check in checks):
        status = "degraded"
    else:
        status = "ok"

    return status, summary


def _make_report(config: Config, checks: list[DiagnosticCheck]) -> dict[str, Any]:
    status, summary = _summarize(checks)
    return {
        "status": status,
        "generated_at": int(time.time()),
        "summary": summary,
        "runtime": _make_runtime(config),
        "requirements": _requirements(),
        "checks": [check.to_dict() for check in checks],
    }


def diagnostics_error_report(config: Config) -> dict[str, Any]:
    return _make_report(
        config,
        [
            DiagnosticCheck(
                id="diagnostics",
                label="Diagnostics",
                group="core",
                required=True,
                status="fail",
                description="Diagnostics collector.",
                message="Diagnostics collection failed.",
                details={},
            )
        ],
    )


async def collect_diagnostics(config: Config) -> dict[str, Any]:
    checks: list[DiagnosticCheck] = [
        _check_ytdlp_package(),
        _check_apprise_package(config),
        _check_curl_transport(),
        _check_pot_provider_package(),
        _check_browser_endpoint(),
        _check_browser_client(),
        _check_flaresolverr(config),
    ]
    checks.extend(_check_configured_pip_packages(config))

    storage_checks, binary_checks = await asyncio.gather(
        asyncio.gather(
            _check_directory(Path(config.config_path), check_id="config_path", label="Config directory"),
            _check_directory(Path(config.download_path), check_id="download_path", label="Download directory"),
            _check_directory(Path(config.temp_path), check_id="temp_path", label="Temp directory"),
            _check_db_file(Path(config.db_file)),
        ),
        asyncio.gather(
            _check_binary(
                "ffmpeg",
                check_id="ffmpeg",
                label="ffmpeg",
                required=True,
                args=("-version",),
            ),
            _check_binary(
                "ffprobe",
                check_id="ffprobe",
                label="ffprobe",
                required=True,
                args=("-version",),
            ),
            _check_binary(
                "deno",
                check_id="deno",
                label="deno",
                required=True,
            ),
            _check_binary(
                "yt-dlp",
                check_id="yt_dlp_cli",
                label="yt-dlp CLI",
                required=True,
                enabled=config.console_enabled,
                disabled_message="Disabled.",
            ),
            _check_binary(
                "aria2c",
                check_id="aria2c",
                label="aria2c",
                required=False,
                missing_status="skip",
            ),
            _check_binary(
                "mkvpropedit",
                check_id="mkvpropedit",
                label="mkvpropedit",
                required=False,
                missing_status="skip",
            ),
            _check_binary(
                "mkvextract",
                check_id="mkvextract",
                label="mkvextract",
                required=False,
                missing_status="skip",
            ),
            _check_binary(
                "MP4Box",
                check_id="mp4box",
                label="MP4Box",
                required=False,
                missing_status="skip",
                args=("-version",),
                aliases=("mp4box",),
            ),
        ),
    )

    checks.extend(storage_checks)
    checks.extend(binary_checks)

    return _make_report(config, checks)
