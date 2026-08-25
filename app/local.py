#!/usr/bin/env python3

import argparse
import http.client
import os
import pathlib
import socket
import sys
import time
import webbrowser
from urllib.parse import urlsplit

if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()

os.environ["PYTHONUTF8"] = "1"

sys.path.insert(0, os.path.join(getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__))), "app"))

APP_ROOT = str((pathlib.Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


def open_browser_when_ready(url: str, timeout: float = 5.0) -> None:
    import threading

    def wait_then_open():
        parsed = urlsplit(url)
        path = parsed.path or "/"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                conn = http.client.HTTPConnection(parsed.hostname or "127.0.0.1", parsed.port or 80, timeout=1)
                try:
                    conn.request("GET", path)
                    response = conn.getresponse()
                    if response.status == 200:
                        os.environ.pop("LD_LIBRARY_PATH", None)
                        webbrowser.open_new(url)
                        return
                finally:
                    conn.close()
            except Exception:
                time.sleep(0.5)

        sys.stderr.write(
            f"Failed to open browser automatically within {timeout} seconds. Please open {url} manually.\n"
        )

    threading.Thread(target=wait_then_open, daemon=True).start()


def app_start(host: str, port: int) -> None:
    import asyncio

    from aiohttp.web_runner import GracefulExit

    from app.main import Main

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        Main(is_native=True).start(host, port)
    except GracefulExit:
        sys.exit(0)


def update_env_file(env_file: pathlib.Path, port: int) -> None:
    lines = []
    if env_file.exists():
        with env_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()

    port_line = f"YTP_PORT={port}\n"
    for i, line in enumerate(lines):
        if line.startswith("YTP_PORT="):
            lines[i] = port_line
            break
    else:
        lines.append(port_line)

    env_file.parent.mkdir(parents=True, exist_ok=True)
    with env_file.open("w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    parser = argparse.ArgumentParser(description="Start YTPTube server", allow_abbrev=False)
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser on start")
    parser.add_argument("--reset-password", action="store_true", help="Reset the administrator password")
    parser.add_argument("--username", help="Account username for password reset")
    args, _ = parser.parse_known_args()

    if args.reset_password and not args.username:
        parser.error("--username is required with --reset-password")

    from app import _add_package_paths
    from app.library.config import Config

    config = Config.get_instance(is_native=True)
    _add_package_paths(config.config_path)
    env_file = pathlib.Path(config.config_path) / ".env"
    port = config.port

    if args.reset_password:
        from app.scripts.reset_password import main as reset_password

        raise SystemExit(reset_password(["--username", args.username]))

    host = config.host

    if 8081 == port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
        update_env_file(env_file, port)

    url = f"http://{host}:{port}"

    if not args.no_browser and not config.no_browser:
        open_browser_when_ready(url)

    app_start(host, int(port))


if __name__ == "__main__":
    main()
