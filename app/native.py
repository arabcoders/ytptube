import socket
import threading

try:
    import webview  # type: ignore
except ImportError as e:
    msg = "Please install the 'webview' package to run this application."
    raise ImportError(msg) from e

if __name__ == "__main__":
    host = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        port = s.getsockname()[1]

    from main import Main

    threading.Thread(target=Main().start, args=(host, port), daemon=True).start()
    webview.create_window("YTPTube", f"http://{host}:{port}")
    webview.start()
