#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import queue
import socket
import sys
import threading
import traceback
from pathlib import Path

import platformdirs

sys.path.insert(0, os.path.join(getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__))), "app"))

APP_NAME = "YTPTube"
APP_ROOT = str((Path(__file__).parent / "..").resolve())
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

try:
    import webview  # type: ignore
except ImportError as e:
    pkgs = "pywebview[edgechromium]" if os.name == "nt" else "pywebview[qt]"
    msg: str = f"Please run 'uv pip install {pkgs}' to run YTPTube in native mode."
    raise ImportError(msg) from e


def error_window(exc: Exception | str) -> None:
    trace: str = "\n".join(traceback.format_exception(exc)) if isinstance(exc, Exception) else exc
    webview.create_window(
        f"{APP_NAME} - Error",
        html=f"<h1 style='color:red;'>An error occurred</h1><pre>{trace}</pre>",
        width=600,
        height=400,
        resizable=True,
    )
    webview.start(
        gui="edgechromium" if os.name == "nt" else "qt",
        debug=False,
        storage_path=str(Path(os.getenv("YTP_TEMP_PATH", os.getcwd())) / "webview"),
        private_mode=False,
    )
    sys.exit(1)


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

    if dct:
        os.environ.update(dct)


def run_backend(host: str, port: int, ready_event: threading.Event, error_queue: queue.Queue):
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        from app.main import Main

        Main(is_native=True).start(host, port, cb=lambda: ready_event.set())
    except Exception as e:
        logging.exception(e)
        error_queue.put(e)
        ready_event.set()


def main():
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

    ready = threading.Event()
    errors: queue.Queue = queue.Queue()
    threading.Thread(target=run_backend, args=(host, port, ready, errors), daemon=False).start()

    ready.wait(timeout=5)

    if not errors.empty():
        error_window(errors.get())
        return

    from app.library.version import APP_VERSION

    gui = "edgechromium" if os.name == "nt" else "qt"
    create_kwargs = {**win_conf, "resizable": True}
    window = webview.create_window(f"{APP_NAME} - {APP_VERSION}", f"http://{host}:{port}", **create_kwargs)

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
    window.events.closing += lambda *_: os._exit(0)

    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = False
    webview.start(
        gui=gui,
        debug=True,
        storage_path=str(Path(os.getenv("YTP_TEMP_PATH", os.getcwd())) / "webview"),
        private_mode=False,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(e)
        error_window(e)
        os._exit(1)
