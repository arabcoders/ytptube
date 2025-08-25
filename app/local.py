#!/usr/bin/env python3
# flake8: noqa: SIM115 S310 T201

import argparse
import os
import pathlib
import socket
import sys
import time
import urllib.request
import webbrowser

import dotenv

os.environ["PYTHONUTF8"] = "1"

sys.path.insert(0, os.path.join(getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__))), "app"))

APP_NAME = "YTPTube"
APP_ROOT = str((pathlib.Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

import platformdirs  # type: ignore


def set_env():
    dct = {}

    if not os.getenv("YTP_CONFIG_PATH"):
        dct["YTP_CONFIG_PATH"] = platformdirs.user_config_dir(APP_NAME.lower(), "arabcoders", ensure_exists=True)

    if not os.getenv("YTP_TEMP_PATH"):
        dct["YTP_TEMP_PATH"] = platformdirs.user_cache_dir(APP_NAME.lower(), "arabcoders", ensure_exists=True)

    if not os.getenv("YTP_DOWNLOAD_PATH"):
        dct["YTP_DOWNLOAD_PATH"] = platformdirs.user_downloads_dir()

    if os.getenv("YTP_ACCESS_LOG", None) is None:
        dct["YTP_ACCESS_LOG"] = "false"

    if not os.getenv("YTP_HOST"):
        dct["YTP_HOST"] = "127.0.0.1"

    if dct:
        os.environ.update(dct)


def open_browser_when_ready(url: str, timeout: float = 5.0) -> None:
    import threading

    def wait_then_open():
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    if 200 == response.status:
                        os.environ.pop("LD_LIBRARY_PATH", None)
                        webbrowser.open_new(url)
                        return
            except Exception:
                time.sleep(0.5)

        print(f"Failed to open browser automatically within {timeout} seconds. Please open {url} manually.")

    threading.Thread(target=wait_then_open, daemon=True).start()


def app_start(host: str, port: int) -> None:
    import asyncio

    from app.main import Main

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    Main(is_native=True).start(host, port)


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

    with env_file.open("w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    parser = argparse.ArgumentParser(description="Start YTPTube server", allow_abbrev=False)
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser on start")
    args, _ = parser.parse_known_args()

    set_env()

    env_file: pathlib.Path = pathlib.Path(os.getenv("YTP_CONFIG_PATH")) / ".env"

    port = None
    if env_file.exists():
        dotenv.load_dotenv(env_file)
        port = os.getenv("YTP_PORT")

    host = os.getenv("YTP_HOST", "127.0.0.1")

    if not port or 8081 == int(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
        update_env_file(env_file, port)

    url = f"http://{host}:{port}"

    env_no_browser: bool = os.getenv("YTP_NO_BROWSER", "false").lower() in ("1", "true", "yes")
    if not args.no_browser and not env_no_browser:
        open_browser_when_ready(url)

    app_start(host, int(port))


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    main()
