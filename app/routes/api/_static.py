import logging
from pathlib import Path, PurePosixPath

import magic
from aiohttp import web
from aiohttp.web import Request, StreamResponse

from app.library.config import Config
from app.library.router import add_route
from app.library.Utils import get_file

MIME = magic.Magic(mime=True)
LOG: logging.Logger = logging.getLogger(__name__)

EXT_TO_MIME: dict[str, str] = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
    ".m4a": "audio/mp4",
}


class StaticState:
    def __init__(self) -> None:
        self.root: Path | None = None
        self.index_file: Path | None = None


STATIC_STATE = StaticState()


def get_root(root_path: Path, config: Config) -> Path | None:
    """
    Get the static root directory.

    Args:
        root_path (Path): The application root path.
        config (Config): The configuration instance.

    Returns:
        Path | None: The static directory, or None when UI is ignored.

    """
    search_paths: list[Path] = []
    if config.static_ui_path:
        search_paths.append(Path(config.static_ui_path).absolute())

    search_paths.extend(
        [
            (root_path / "ui" / "exported").absolute(),
            (root_path.parent / "ui" / "exported").absolute(),
        ]
    )

    for path in search_paths:
        if path.is_dir():
            return path

    message: str = f"Could not find the frontend assets in '{[str(path) for path in search_paths]=}'."
    if config.ignore_ui:
        LOG.warning(message)
        return None

    raise ValueError(message)


def normalize_path(path: str, base_path: str) -> str:
    """
    Normalize the request path by stripping the base path.

    Args:
        path (str): The raw request path.
        base_path (str): The configured base path.

    Returns:
        str: The path relative to the static root.

    """
    if "/" == base_path:
        return path or "/"

    base_prefix: str = base_path.rstrip("/")
    if path == base_prefix:
        return "/"

    if path.startswith(f"{base_prefix}/"):
        stripped: str = path[len(base_prefix) :]
        return stripped or "/"

    return path or "/"


def get_static_file(path: str) -> Path | None:
    """
    Get the static file corresponding to a request path.

    Args:
        path (str): The normalized request path.

    Returns:
        Path | None: The resolved file path.

    """
    if STATIC_STATE.root is None:
        return None

    relative_path: str = path.lstrip("/")
    if not relative_path:
        return STATIC_STATE.index_file if STATIC_STATE.index_file and STATIC_STATE.index_file.is_file() else None

    file, status = get_file(STATIC_STATE.root, relative_path)
    if web.HTTPOk.status_code == status and file.is_file():
        return file

    return None


async def serve_static_file(request: Request, config: Config) -> StreamResponse:
    """
    Serve frontend static files with SPA fallback handling.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.

    Returns:
        StreamResponse: The response object.

    """
    path: str = normalize_path(request.path, config.base_path)
    file_path: Path | None = get_static_file(path)

    if file_path is None:
        if (
            STATIC_STATE.index_file is not None
            and not path.startswith("/api/")
            and not PurePosixPath(path.lstrip("/")).suffix
        ):
            file_path = STATIC_STATE.index_file
        else:
            return web.json_response({"error": "File not found.", "file": path}, status=web.HTTPNotFound.status_code)

    return web.FileResponse(
        path=file_path,
        headers={
            "Pragma": "public",
            "Cache-Control": "public, max-age=31536000",
            "Content-Type": EXT_TO_MIME.get(file_path.suffix, MIME.from_file(str(file_path))),
        },
        status=web.HTTPOk.status_code,
    )


def setup_static_routes(root_path: Path, config: Config) -> None:
    """
    Set up routes for serving frontend static files.

    Args:
        root_path (Path): The application root path.
        config (Config): The configuration instance.

    """
    STATIC_STATE.root = get_root(root_path, config)
    STATIC_STATE.index_file = None

    if STATIC_STATE.root is None:
        return

    index_file: Path = (STATIC_STATE.root / "index.html").resolve()
    if not index_file.is_file():
        message: str = f"Failed to find frontend entry file at '{index_file}'."
        if config.ignore_ui:
            LOG.warning(message)
            STATIC_STATE.root = None
            return

        raise ValueError(message)

    STATIC_STATE.index_file = index_file

    add_route(method="GET", path=config.base_path, handler=serve_static_file, name="index")
    add_route(method="GET", path="/{path:.*}", handler=serve_static_file, name="static_fallback")

    if "/" != config.base_path:

        async def redirect_index(config: Config) -> web.Response:
            return web.Response(status=web.HTTPFound.status_code, headers={"Location": config.base_path})

        add_route(method="GET", path="/", handler=redirect_index, name="index_redirect")

    LOG.info(f"Serving frontend static assets from '{STATIC_STATE.root}'.")
