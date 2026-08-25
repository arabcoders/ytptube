import mimetypes
import sys
from pathlib import Path

from aiohttp import web
from aiohttp.web import Request, Response

from app.features.core.utils import api_error_response
from app.library.config import Config
from app.library.logging import get_logger
from app.library.router import route

LOG = get_logger()
STATIC_FILES: set[str] = {
    "README.md",
    "FAQ.md",
    "API.md",
    "SECURITY.md",
    "sc_short.jpg",
    "sc_simple.jpg",
    "docs/README.md",
    "docs/features.md",
    "docs/native-builds.md",
    "docs/task-definitions.md",
}


def _bundle_root(config: Config) -> Path:
    candidates: list[Path] = [Path(config.app_path).parent]
    bundle_path = getattr(sys, "_MEIPASS", None)
    if bundle_path:
        candidates.insert(0, Path(bundle_path))
    candidates.extend((Path.cwd(), Path(__file__).resolve().parents[3]))
    for root in candidates:
        if (root / "docs").is_dir() and (root / "README.md").is_file():
            return root
    return candidates[0]


def _doc_path(config: Config, name: str) -> Path | None:
    if name not in STATIC_FILES or name.startswith("/") or "\\" in name:
        return None

    root = _bundle_root(config).resolve()
    path = (root / name).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


@route("GET", "api/docs/{file:.*}", name="get_doc")
async def get_doc(request: Request, config: Config) -> Response:
    name: str = request.match_info.get("file", "")
    if not (path := _doc_path(config, name)):
        return api_error_response(
            "Doc file not found.",
            code="NOT_FOUND",
            status=web.HTTPNotFound.status_code,
            params={"resource": "api.resources.file"},
            extra={"file": name},
        )

    LOG.debug("Serving bundled doc '%s'.", name, extra={"route": "docs.get", "doc_file": name})
    return web.Response(
        body=path.read_bytes(),
        headers={
            "Content-Type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store",
        },
    )
