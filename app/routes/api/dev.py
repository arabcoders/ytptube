import asyncio
import logging

from aiohttp import web
from aiohttp.web import Response

from app.library.config import Config
from app.library.encoder import Encoder
from app.library.router import route

LOG: logging.Logger = logging.getLogger(__name__)


@route("GET", "api/dev/loop/", "debug_loop")
async def debug_asyncio(config: Config, encoder: Encoder) -> Response:
    if not config.is_dev():
        return web.json_response(
            data={"error": "This endpoint is only available in development mode."},
            status=web.HTTPForbidden.status_code,
        )

    import traceback

    tasks = []
    for task in asyncio.all_tasks():
        task_info = {"task": str(task), "stack": []}
        for frame in task.get_stack():
            formatted = traceback.format_stack(f=frame)
            task_info["stack"].extend(formatted)

        tasks.append(task_info)

    return web.json_response(
        data={
            "total_tasks": len(tasks),
            "loop": str(asyncio.get_event_loop()),
            "tasks": tasks,
        },
        status=web.HTTPOk.status_code,
        dumps=encoder.encode,
    )


@route("GET", "api/dev/pip", "check_pip_packages")
async def check_pip_packages(config: Config, encoder: Encoder) -> Response:
    pkgs = config.pip_packages.split(" ") if config.pip_packages else []
    if not pkgs:
        return web.json_response(
            data={"message": "No pip packages configured."},
            status=web.HTTPOk.status_code,
        )

    def _get_installed_version(pkg: str) -> str | None:
        try:
            import importlib.metadata

            return importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            return None

    response = {}
    for pkg in pkgs:
        if not (pkg := pkg.strip()):
            continue

        response.update({pkg: _get_installed_version(pkg)})

    return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=encoder.encode)
