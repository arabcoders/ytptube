#!/usr/bin/env python3
import io
import os
import sys

os.environ["PYTHONUTF8"] = "1"

if "utf-8" != sys.stdout.encoding.lower():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from pathlib import Path

APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)


import json
import queue
import socket
import threading

ready = threading.Event()
exception_holder = queue.Queue()

APP_NAME = "YTPTube"

try:
    import webview  # type: ignore
except ImportError as e:
    msg = "Please run 'pipenv install pywebview[qt]' package to run YTPTube in native mode."
    raise ImportError(msg) from e


def set_env():
    import platformdirs

    dct = {}

    if not os.getenv("YTP_CONFIG_PATH"):
        dct["YTP_CONFIG_PATH"] = platformdirs.user_config_dir(APP_NAME.lower(), "arabcoders", ensure_exists=True)

    if not os.getenv("YTP_TEMP_PATH"):
        dct["YTP_TEMP_PATH"] = platformdirs.user_cache_dir(APP_NAME.lower(), "arabcoders", ensure_exists=True)

    if not os.getenv("YTP_DOWNLOAD_PATH"):
        dct["YTP_DOWNLOAD_PATH"] = platformdirs.user_downloads_dir()

    if os.getenv("YTP_ACCESS_LOG", None) is None:
        dct["YTP_ACCESS_LOG"] = "false"

    if dct:
        os.environ.update(dct)


def app_start(host: str, port: int) -> None:
    import asyncio

    from main import Main

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        Main(is_native=True).start(host, port, cb=lambda: ready.set())
    except Exception as e:
        exception_holder.put(e)
        ready.set()


if __name__ == "__main__":
    host = "127.0.0.1"
    set_env()

    cfg_path: Path = Path(os.getenv("YTP_CONFIG_PATH")) / "webview.json"

    port = None
    win_conf: dict[str, int] = {}
    if cfg_path.exists():
        data = json.loads(cfg_path.read_text())
        port = data.get("port")
        for key in ("width", "height", "x", "y"):
            if key in data:
                win_conf[key] = data[key]

    if not port:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
        cfg_path.write_text(json.dumps({"port": port}))

    threading.Thread(target=app_start, args=(host, port), daemon=True).start()

    ready.wait()

    if not exception_holder.empty():
        raise exception_holder.get()

    create_kwargs = {**win_conf, "resizable": True}

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    window = webview.create_window(APP_NAME, f"http://{host}:{port}", **create_kwargs)

    def save_geometry():
        cfg = {
            "port": port,
            "width": window.width,
            "height": window.height,
            "x": window.x,
            "y": window.y,
        }
        cfg_path.write_text(json.dumps(cfg))

    window.events.resized += lambda *_: save_geometry()
    window.events.moved += lambda *_: save_geometry()

    gui = os.getenv("YTP_WV_GUI", None)
    gui = "edgechromium" if os.name == "nt" else "qt"

    webview.start(
        gui=gui,
        debug=True,
        storage_path=str(Path(os.getenv("YTP_TEMP_PATH", os.getcwd())) / "webview"),
        private_mode=False,
    )
