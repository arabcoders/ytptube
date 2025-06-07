import json
import logging
import os
import socket
import threading
from pathlib import Path

# 1) create a global event
ready = threading.Event()

APP_NAME = "YTPTube"

try:
    import webview  # type: ignore
except ImportError as e:
    msg = "Please install the 'pywebview' to run YTPTube in native mode."
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

    if len(dct) > 0:
        os.environ.update(dct)


def app_start(host: str, port: int) -> None:
    import asyncio

    from main import Main

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    Main().start(host, port, cb=lambda: ready.set())


if __name__ == "__main__":
    host = "127.0.0.1"

    set_env()

    cfg = Path(os.getenv("YTP_CONFIG_PATH")) / "webview.json"
    if cfg.exists():
        port = json.loads(cfg.read_text())["port"]
    else:
        logging.info(f"Creating configuration file at '{cfg}'.")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            port = s.getsockname()[1]
        cfg.write_text(json.dumps({"port": port}))

    threading.Thread(target=app_start, args=(host, port), daemon=True).start()

    ready.wait()

    webview.create_window(APP_NAME, f"http://{host}:{port}")
    webview.start(
        debug=os.getenv("YTP_WV_DEBUG", "false").lower() in ("true", "1", "yes"),
        storage_path=os.path.join(os.getenv("YTP_CONFIG_PATH", os.getcwd()), "webview"),
        private_mode=False,
    )
