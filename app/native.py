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

    if "linux" in sys.platform:
        os.environ.setdefault("LC_ALL", "C.UTF-8")
        os.environ.setdefault("LANG", "C.UTF-8")
        import webview.platforms.qt  # type: ignore

        # monkey patch the download handler for pywebview to support qt6.
        def on_download_requested(self, download):
            from qtpy import QtCore  # type: ignore
            from qtpy.QtWidgets import QFileDialog  # type: ignore

            old_path = download.url().path()
            suffix = QtCore.QFileInfo(old_path).suffix()
            filename, _ = QFileDialog.getSaveFileName(
                self, self.localization["global.saveFile"], old_path, "*." + suffix
            )
            if filename:
                if hasattr(download, "setPath"):
                    download.setPath(filename)
                else:
                    download.setDownloadDirectory(os.path.dirname(filename))
                    download.setDownloadFileName(os.path.basename(filename))
                    download.accept()
            else:
                download.cancel()

        webview.platforms.qt.BrowserView.on_download_requested = on_download_requested

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
    defaults = {
        "YTP_CONFIG_PATH": lambda: platformdirs.user_config_dir(APP_NAME.lower(), "arabcoders", ensure_exists=True),
        "YTP_TEMP_PATH": lambda: platformdirs.user_cache_dir(APP_NAME.lower(), "arabcoders", ensure_exists=True),
        "YTP_DOWNLOAD_PATH": lambda: platformdirs.user_downloads_dir(),
        "YTP_ACCESS_LOG": "false",
        "YTP_BROWSER_ENABLED": "true",
        "YTP_BROWSER_CONTROL_ENABLED": "true",
    }

    for key, value in defaults.items():
        if os.getenv(key) is not None:
            continue

        os.environ[key] = value() if callable(value) else value


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


def get_usable_port(host: str = "127.0.0.1") -> int:
    """
    Get a usable port on the specified host.
    If no port is available, it will raise an OSError.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        port = s.getsockname()[1]
        s.close()

    return port


def main():
    host = "127.0.0.1"
    set_env()

    cfg_path: Path = Path(os.getenv("YTP_CONFIG_PATH")) / "webview.json"
    win_conf: dict[str, int] = {}

    if cfg_path.exists():
        data = json.loads(cfg_path.read_text())
        for key in ("width", "height", "x", "y"):
            if key in data:
                win_conf[key] = data[key]

    port = get_usable_port(host)

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
        from multiprocessing import freeze_support

        freeze_support()
        main()
    except Exception as e:
        logging.exception(e)
        error_window(e)
        os._exit(1)
