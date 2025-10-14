import logging
from pathlib import Path

import magic
from aiohttp import web
from aiohttp.web import Request, Response

from app.library.config import Config
from app.library.router import add_route

MIME = magic.Magic(mime=True)
LOG: logging.Logger = logging.getLogger(__name__)

STATIC_FILES: dict[str, dict] = {}

EXT_TO_MIME: dict = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".ico": "image/x-icon",
}

FRONTEND_ROUTES: list[str] = [
    "/console/",
    "/presets/",
    "/tasks/",
    "/notifications/",
    "/changelog/",
    "/logs/",
    "/conditions/",
    "/browser/",
    "/browser/{path:.*}",
]


async def serve_static_file(request: Request, config: Config) -> Response:
    """
    Preload static files from the ui/exported folder.

    Args:
        request (Request): The request object.
        config (Config): The configuration instance.

    Returns:
        Response: The response object.

    """
    path: str = request.path

    if "/" != config.base_path and path.startswith(config.base_path):
        path = path.replace(config.base_path[:-1], "", 1)

    if path not in STATIC_FILES:
        for k in STATIC_FILES:
            if path.startswith(k):
                path = k
                break
        else:
            return web.json_response({"error": "File not found.", "file": path}, status=web.HTTPNotFound.status_code)

    item: dict = STATIC_FILES[path]

    return web.FileResponse(
        path=item["file"],
        headers={
            "Pragma": "public",
            "Cache-Control": "public, max-age=31536000",
            "Content-Type": item.get("content_type"),
        },
        status=web.HTTPOk.status_code,
    )


def preload_static(root_path: Path, config: Config) -> None:
    """
    Preload static files from the ui/exported folder.

    Args:
        root_path (Path): The root path of the application.
        config (Config): The configuration instance.

    """
    global STATIC_FILES  # noqa: PLW0602
    static_dir: Path | None = None
    webui_files: list[Path] = [
        (root_path / "ui" / "exported").absolute(),
        (root_path.parent / "ui" / "exported").absolute(),
    ]

    if config.static_ui_path:
        webui_files = [Path(config.static_ui_path).absolute()]

    for p in webui_files:
        if p.exists():
            static_dir = p
            break

    if static_dir is None:
        webui_files = [str(p) for p in webui_files]
        msg: str = f"Could not find the frontend UI static assets in '{webui_files=}'."
        raise ValueError(msg)

    preloaded = 0

    for file in static_dir.rglob("*.*"):
        if ".map" == file.suffix:
            continue

        uri_path: str = f"/{file.relative_to(static_dir).as_posix()!s}"
        # uri_path: str = f"/{str(file.as_posix()).replace(f'{static_dir.as_posix()!s}/', '')}"
        contentType = EXT_TO_MIME.get(file.suffix)
        if not contentType:
            contentType = MIME.from_file(str(file))

        STATIC_FILES[uri_path] = {
            "uri": uri_path,
            "content_type": contentType,
            "file": file,
        }

        add_route(method="GET", path=uri_path, handler=serve_static_file)
        preloaded += 1

    if "/index.html" in STATIC_FILES:
        for path in FRONTEND_ROUTES:
            STATIC_FILES[path] = STATIC_FILES["/index.html"]
            STATIC_FILES[path.lstrip("/")] = STATIC_FILES["/index.html"]
            add_route(method="GET", path=path, handler=serve_static_file)
            LOG.debug(f"Preloading frontend static route '{path}'.")
            preloaded += 1

        # Add main app route
        STATIC_FILES["/"] = STATIC_FILES["/index.html"]
        STATIC_FILES[config.base_path] = STATIC_FILES["/index.html"]
        add_route(method="GET", path=config.base_path, handler=serve_static_file, name="index")

    if "/" != config.base_path:

        async def redirect_index(config: Config) -> web.Response:
            return web.Response(status=web.HTTPFound.status_code, headers={"Location": config.base_path})

        add_route(method="GET", path="/", handler=redirect_index, name="index_redirect")

    if preloaded < 1:
        message: str = f"Failed to find any static files in '{static_dir}'."
        if config.ignore_ui:
            LOG.warning(message)
            return

        raise ValueError(message)

    LOG.info(f"Loaded '{preloaded}' static files.")
