import json
import os
import socket
import threading
from pathlib import Path

ready = threading.Event()

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

    Main(is_native=True).start(host, port, cb=lambda: ready.set())


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

    create_kwargs = {**win_conf, "resizable": True}

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

    webview.start(
        gui=str(os.getenv("YTP_WV_GUI", "qt")),  # e.g. "qt" or "gtk"
        debug=os.getenv("YTP_WV_DEBUG", "false").lower() in ("true", "1", "yes"),
        storage_path=str(Path(os.getenv("YTP_TEMP_PATH", os.getcwd())) / "webview"),
        private_mode=False,
    )
