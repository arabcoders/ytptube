import asyncio
import base64
import functools
import hmac
import json
import logging
import os
import random
import time
import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path

import anyio
import httpx
import magic
from aiohttp import web
from aiohttp.web import Request, RequestHandler, Response

from .cache import Cache
from .common import Common
from .config import Config
from .DownloadQueue import DownloadQueue
from .Emitter import Emitter
from .encoder import Encoder
from .EventsSubscriber import Events
from .ffprobe import ffprobe
from .M3u8 import M3u8
from .Notifications import Notification, NotificationEvents
from .Playlist import Playlist
from .Segments import Segments
from .Subtitle import Subtitle
from .Tasks import Task, Tasks
from .Utils import (
    IGNORED_KEYS,
    StreamingError,
    arg_converter,
    calc_download_path,
    get_video_info,
    validate_url,
    validate_uuid,
)

LOG = logging.getLogger("http_api")
MIME = magic.Magic(mime=True)


class HttpAPI(Common):
    _static_holder: dict = {}
    """Holds loaded static assets."""

    _ext_to_mime: dict = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".ico": "image/x-icon",
    }
    """Map ext to mimetype"""

    def __init__(
        self,
        queue: DownloadQueue | None = None,
        emitter: Emitter | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
    ):
        self.queue = queue or DownloadQueue.get_instance()
        self.emitter = emitter or Emitter.get_instance()
        self.encoder = encoder or Encoder()
        self.config = config or Config.get_instance()

        self.rootPath = str(Path(__file__).parent.parent.parent)
        self.routes = web.RouteTableDef()
        self.cache = Cache()

        super().__init__(queue=self.queue, encoder=self.encoder, config=self.config)

    @staticmethod
    def route(method: str, path: str) -> Awaitable:
        """
        Decorator to mark a method as an HTTP route handler.

        Args:
            method (str): The HTTP method.
            path (str): The path to the route.

        Returns:
            Awaitable: The decorated function.

        """

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            wrapper._http_method = method.upper()
            wrapper._http_path = path
            return wrapper

        return decorator

    async def on_shutdown(self, _: web.Application):
        LOG.debug("Shutting down http API server.")

    def attach(self, app: web.Application) -> "HttpAPI":
        """
        Attach the routes to the application.

        Args:
            app (web.Application): The application to attach the routes to.

        Returns:
            HttpAPI: The instance of the HttpAPI.

        """
        if self.config.auth_username and self.config.auth_password:
            app.middlewares.append(HttpAPI.basic_auth(self.config.auth_username, self.config.auth_password))

        self.add_routes(app)

        async def on_prepare(request: Request, response: Response):
            if "Server" in response.headers:
                del response.headers["Server"]

            if "Origin" in request.headers:
                response.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response.headers["Access-Control-Allow-Methods"] = "GET, PATCH, PUT, POST, DELETE"

        try:
            app.on_response_prepare.append(on_prepare)
        except Exception as e:
            LOG.exception(e)

        app.on_shutdown.append(self.on_shutdown)
        return self

    async def _static_file(self, req: Request) -> Response:
        """
        Preload static files from the ui/exported folder.

        Args:
            req (Request): The request object.

        Returns:
            Response: The response object.

        """
        path = req.path

        if req.path not in self._static_holder:
            return web.json_response({"error": "File not found.", "file": path}, status=web.HTTPNotFound.status_code)

        item: dict = self._static_holder[req.path]

        return web.Response(
            body=item.get("content"),
            headers={
                "Pragma": "public",
                "Cache-Control": "public, max-age=31536000",
                "Content-Type": item.get("content_type"),
                "X-Via": "memory" if not item.get("file") else "disk",
            },
            status=web.HTTPOk.status_code,
        )

    def _preload_static(self, app: web.Application) -> "HttpAPI":
        """
        Preload static files from the ui/exported folder.

        Args:
            app (web.Application): The application to attach the routes to.

        Returns:
            HttpAPI: The instance of the HttpAPI.

        """
        staticDir = os.path.join(self.rootPath, "ui", "exported")
        if not os.path.exists(staticDir):
            msg = f"Could not find the frontend UI static assets. '{staticDir}'."
            raise ValueError(msg)

        preloaded = 0

        for root, _, files in os.walk(staticDir):
            for file in files:
                if file.endswith(".map"):
                    continue

                file = os.path.join(root, file)
                urlPath = f"/{file.replace(f'{staticDir}/', '')}"

                with open(file, "rb") as f:
                    content = f.read()

                contentType = self._ext_to_mime.get(os.path.splitext(file)[1], MIME.from_file(file))

                self._static_holder[urlPath] = {"content": content, "content_type": contentType}
                LOG.debug(f"Preloading '{urlPath}'.")
                app.router.add_get(urlPath, self._static_file)
                preloaded += 1

                if urlPath.endswith("/index.html") and urlPath != "/index.html":
                    parentSlash = urlPath.replace("/index.html", "/")
                    parentNoSlash = urlPath.replace("/index.html", "")
                    self._static_holder[parentSlash] = {"content": content, "content_type": contentType}
                    self._static_holder[parentNoSlash] = {"content": content, "content_type": contentType}
                    app.router.add_get(parentSlash, self._static_file)
                    app.router.add_get(parentNoSlash, self._static_file)
                    preloaded += 2

        if preloaded < 1:
            message = f"Failed to find any static files in '{staticDir}'."
            if self.config.ignore_ui:
                LOG.warning(message)
                return self

            raise ValueError(message)

        LOG.info(f"Preloaded '{preloaded}' static files.")

        return self

    def add_routes(self, app: web.Application) -> "HttpAPI":
        """
        Add the routes to the application.

        Args:
            app (web.Application): The application to attach the routes to.

        Returns:
            HttpAPI: The instance of the HttpAPI.

        """
        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, "_http_method") and hasattr(method, "_http_path"):
                http_path = method._http_path
                if http_path.startswith("/"):
                    http_path = method._http_path[1:]

                self.routes.route(method._http_method, f"/{http_path}")(method)

        self.routes.static("/api/download/", self.config.download_path)
        self._preload_static(app)

        try:
            app.add_routes(self.routes)
        except ValueError as e:
            if "ui/exported" in str(e):
                msg = f"Could not find the frontend UI static assets. '{e}'."
                raise RuntimeError(msg) from e
            raise

    @staticmethod
    def basic_auth(username: str, password: str) -> Awaitable:
        """
        Middleware to handle basic authentication.

        Args:
            username (str): The username.
            password (str): The password.

        Returns:
            Awaitable: The middleware handler.

        """

        @web.middleware
        async def middleware_handler(request: Request, handler: RequestHandler) -> Response:
            auth_header = request.headers.get("Authorization")
            if auth_header is None and request.query.get("apikey") is not None:
                auth_header = f"Basic {request.query.get('apikey')}"

            if auth_header is None:
                return web.json_response(
                    status=web.HTTPUnauthorized.status_code,
                    headers={
                        "WWW-Authenticate": 'Basic realm="Authorization Required."',
                    },
                    data={"error": "Authorization Required."},
                )

            auth_type, encoded_credentials = auth_header.split(" ", 1)

            if "basic" != auth_type.lower():
                return web.json_response(
                    data={"error": "Unsupported authentication method.", "method": auth_type},
                    status=web.HTTPUnauthorized.status_code,
                )

            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
            user_name, _, user_password = decoded_credentials.partition(":")

            user_match = hmac.compare_digest(user_name, username)
            pass_match = hmac.compare_digest(user_password, password)

            if not (user_match and pass_match):
                return web.json_response(
                    data={"error": "Unauthorized (Invalid credentials)."}, status=web.HTTPUnauthorized.status_code
                )

            return await handler(request)

        return middleware_handler

    @route("OPTIONS", "/{path:.*}")
    async def add_coors(self, _: Request) -> Response:
        """
        Add CORS headers to the response.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        return web.json_response(data={"status": "ok"}, status=web.HTTPOk.status_code)

    @route("GET", "api/ping")
    async def ping(self, _: Request) -> Response:
        """
        Ping the server.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        await self.queue.test()
        return web.json_response(data={"status": "pong"}, status=web.HTTPOk.status_code)

    @route("POST", "api/yt-dlp/convert")
    async def yt_dlp_convert(self, request: Request) -> Response:
        """
        Convert the yt-dlp args to a dict.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        post = await request.json()
        args: str | None = post.get("args")

        if not args:
            return web.json_response(data={"error": "args param is required."}, status=web.HTTPBadRequest.status_code)

        try:
            response = {"opts": {}, "output_template": None, "download_path": None}

            data = arg_converter(args)

            if "outtmpl" in data and "default" in data["outtmpl"]:
                response["output_template"] = data["outtmpl"]["default"]

            if "paths" in data and "home" in data["paths"]:
                response["download_path"] = data["paths"]["home"]

            for key in data:
                if key in IGNORED_KEYS:
                    continue
                if not key.startswith("_"):
                    response["opts"][key] = data[key]

            return web.json_response(data=response, status=web.HTTPOk.status_code)
        except Exception as e:
            err = str(e).strip()
            err = err.split("\n")[-1] if "\n" in err else err
            LOG.error(f"Failed to convert args. '{err}'.")
            LOG.exception(e)
            return web.json_response(
                data={"error": f"Failed to convert args. '{err}'."}, status=web.HTTPBadRequest.status_code
            )

    @route("GET", "api/yt-dlp/url/info")
    async def get_info(self, request: Request) -> Response:
        """
        Get the video info.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object

        """
        url = request.query.get("url")
        if not url:
            return web.json_response(data={"error": "URL is required."}, status=web.HTTPBadRequest.status_code)

        try:
            validate_url(url)
        except ValueError as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)

        try:
            key = self.cache.hash(url)

            if self.cache.has(key):
                data = self.cache.get(key)
                data["_cached"] = {
                    "key": key,
                    "ttl": data.get("_cached", {}).get("ttl", 300),
                    "ttl_left": data.get("_cached", {}).get("expires", time.time() + 300) - time.time(),
                    "expires": data.get("_cached", {}).get("expires", time.time() + 300),
                }
                return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

            opts = {
                "proxy": self.config.ytdl_options.get("proxy", None),
            }

            data = get_video_info(url=url, ytdlp_opts=opts, no_archive=True)
            self.cache.set(key=self.cache.hash(url), value=data, ttl=300)
            data["_cached"] = {
                "key": self.cache.hash(url),
                "ttl": 300,
                "ttl_left": 300,
                "expires": time.time() + 300,
            }

            return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)
        except Exception as e:
            LOG.error(f"Error encountered while grabbing video info '{url}'. '{e}'.")
            LOG.exception(e)
            return web.json_response(
                data={
                    "error": "failed to get video info.",
                    "message": str(e),
                },
                status=web.HTTPInternalServerError.status_code,
            )

    @route("GET", "api/yt-dlp/archive/recheck")
    async def archive_recheck(self, _) -> Response:
        """
        Recheck the manual archive entries.

        Args:
            _ (Request): The request object.

        Returns:
            Response: The response object

        """
        manual_archive = self.config.manual_archive
        if not manual_archive:
            return web.json_response(
                data={"error": "Manual archive is not enabled."}, status=web.HTTPNotFound.status_code
            )

        if not os.path.exists(manual_archive):
            return web.json_response(
                data={"error": "Manual archive file not found.", "file": manual_archive},
                status=web.HTTPNotFound.status_code,
            )

        tasks = []
        response = []

        def get_video_info_wrapper(id: str, url: str) -> tuple[str, dict]:
            try:
                return (
                    id,
                    get_video_info(
                        url=url,
                        ytdlp_opts={
                            "proxy": self.config.ytdl_options.get("proxy", None),
                            "simulate": True,
                            "dump_single_json": True,
                        },
                        no_archive=True,
                    ),
                )
            except Exception as e:
                return (id, {"error": str(e)})

        async with await anyio.open_file(manual_archive) as f:
            # line format is "youtube ID - at: ISO8601"
            async for line in f:
                line = line.strip()

                if not line or not line.startswith("youtube"):
                    continue

                id = line.split(" ")[1].strip()

                if not id:
                    continue

                url = f"https://www.youtube.com/watch?v={id}"
                key = self.cache.hash(id)

                if self.cache.has(key):
                    data = self.cache.get(key)
                    response.append({id: bool(data.get("id", None)) if isinstance(data, dict) else False})
                    continue

                tasks.append(
                    asyncio.get_event_loop().run_in_executor(
                        None, lambda id=id, url=url: get_video_info_wrapper(id=id, url=url)
                    )
                )

        if len(tasks) > 0:
            results = await asyncio.gather(*tasks)
            for data in results:
                if not data:
                    continue

                id, info = data
                self.cache.set(key=self.cache.hash(id), value=info, ttl=3600 * 6)
                response.append({id: bool(data.get("id", None)) if isinstance(data, dict) else False})

        return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/history/add")
    async def quick_add(self, request: Request) -> Response:
        """
        Add a URL to the download queue.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object

        """
        url: str | None = request.query.get("url")
        if not url:
            return web.json_response(data={"error": "url param is required."}, status=web.HTTPBadRequest.status_code)

        try:
            status = await self.add(**self.format_item({"url": url}))
        except ValueError as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPBadRequest.status_code)

        return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("POST", "api/history")
    async def history_item_add(self, request: Request) -> Response:
        """
        Add a URL to the download queue.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        data = await request.json()

        if isinstance(data, dict):
            data = [data]

        for item in data:
            try:
                self.format_item(item)
            except ValueError as e:
                return web.json_response(data={"error": str(e), "data": item}, status=web.HTTPBadRequest.status_code)

        return web.json_response(
            data=await asyncio.wait_for(
                fut=asyncio.gather(*[self.add(**self.format_item(item)) for item in data]),
                timeout=None,
            ),
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

    @route("GET", "api/tasks")
    async def tasks(self, _: Request) -> Response:
        """
        Get the tasks.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        return web.json_response(
            data=Tasks.get_instance().get_tasks(), status=web.HTTPOk.status_code, dumps=self.encoder.encode
        )

    @route("PUT", "api/tasks")
    async def tasks_add(self, request: Request) -> Response:
        """
        Add tasks to the queue.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object

        """
        data = await request.json()

        if not isinstance(data, list):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        tasks: list = []

        ins = Tasks.get_instance()

        for item in data:
            if not isinstance(item, dict):
                return web.json_response(
                    {"error": "Invalid request body expecting list with dicts."},
                    status=web.HTTPBadRequest.status_code,
                )

            if not item.get("url"):
                return web.json_response(
                    {"error": "url is required.", "data": item}, status=web.HTTPBadRequest.status_code
                )

            if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
                item["id"] = str(uuid.uuid4())

            if not item.get("timer", None) or str(item.get("timer")).strip() == "":
                item["timer"] = f"{random.randint(1,59)} */1 * * *"  # noqa: S311

            if not item.get("cookies", None):
                item["cookies"] = ""

            if not item.get("config", None) or str(item.get("config")).strip() == "":
                item["config"] = {}

            if not item.get("template", None):
                item["template"] = ""

            try:
                ins.validate(item)
            except ValueError as e:
                return web.json_response(
                    {"error": f"Failed to validate task '{item.get('name')}'. '{e!s}'"},
                    status=web.HTTPBadRequest.status_code,
                )

            tasks.append(Task(**item))

        try:
            tasks = ins.save(tasks=tasks).load().get_tasks()
        except Exception as e:
            LOG.exception(e)
            return web.json_response(
                {"error": "Failed to save tasks.", "message": str(e)},
                status=web.HTTPInternalServerError.status_code,
            )

        return web.json_response(data=tasks, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("DELETE", "api/history")
    async def history_delete(self, request: Request) -> Response:
        """
        Delete an item from the queue.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        data = await request.json()
        ids = data.get("ids")
        where = data.get("where")
        if not ids or where not in ["queue", "done"]:
            return web.json_response(
                data={"error": "ids and where are required."}, status=web.HTTPBadRequest.status_code
            )

        remove_file: bool = bool(data.get("remove_file", True))

        return web.json_response(
            data=await (self.queue.cancel(ids) if where == "queue" else self.queue.clear(ids, remove_file=remove_file)),
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

    @route("POST", "api/history/{id}")
    async def history_item_update(self, request: Request) -> Response:
        """
        Update an item in the history.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        id: str = request.match_info.get("id")
        if not id:
            return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

        item = self.queue.done.get_by_id(id)
        if not item:
            return web.json_response(data={"error": "item not found."}, status=web.HTTPNotFound.status_code)

        post = await request.json()
        if not post:
            return web.json_response(data={"error": "no data provided."}, status=web.HTTPBadRequest.status_code)

        updated = False

        for k, v in post.items():
            if not hasattr(item.info, k):
                continue

            if getattr(item.info, k) == v:
                continue

            updated = True
            setattr(item.info, k, v)
            LOG.debug(f"Updated '{k}' to '{v}' for '{item.info.id}'")

        if updated:
            self.queue.done.put(item)
            await self.emitter.emit(Events.UPDATE, item.info)

        return web.json_response(
            data=item.info,
            status=web.HTTPOk.status_code if updated else web.HTTPNotModified.status_code,
            dumps=self.encoder.encode,
        )

    @route("GET", "api/history")
    async def history(self, _: Request) -> Response:
        """
        Get the history.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        data: dict = {"queue": [], "history": []}

        for _, v in self.queue.queue.saved_items():
            data["queue"].append(v)
        for _, v in self.queue.done.saved_items():
            data["history"].append(v)

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/workers")
    async def pool_list(self, _) -> Response:
        """
        Get the workers status.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        status = self.queue.pool.get_workers_status()

        data = []

        for worker in status:
            worker_status = status.get(worker)
            data.append(
                {
                    "id": worker,
                    "data": {"status": "Waiting for download."} if worker_status is None else worker_status,
                }
            )

        return web.json_response(
            data={
                "open": self.queue.pool.has_open_workers(),
                "count": self.queue.pool.get_available_workers(),
                "workers": data,
            },
            status=web.HTTPOk.status_code,
            dumps=lambda obj: json.dumps(obj, default=lambda o: f"<<non-serializable: {type(o).__qualname__}>>"),
        )

    @route("POST", "api/workers")
    async def pool_restart(self, _) -> Response:
        """
        Restart the workers pool.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        self.queue.pool.start()

        return web.json_response({"message": "Workers pool being restarted."}, status=web.HTTPOk.status_code)

    @route("PATCH", "api/workers/{id}")
    async def worker_restart(self, request: Request) -> Response:
        """
        Restart a worker.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object

        """
        id: str = request.match_info.get("id")
        if not id:
            return web.json_response({"error": "worker id is required."}, status=web.HTTPBadRequest.status_code)

        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        status = await self.queue.pool.restart(id, "requested by user.")

        return web.json_response({"status": "restarted" if status else "in_error_state"}, status=web.HTTPOk.status_code)

    @route("DELETE", "api/workers/{id}")
    async def worker_stop(self, request: Request) -> Response:
        """
        Stop a worker.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        id: str = request.match_info.get("id")
        if not id:
            raise web.HTTPBadRequest(text="worker id is required.")

        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        status = await self.queue.pool.stop(id, "requested by user.")

        return web.json_response({"status": "stopped" if status else "in_error_state"}, status=web.HTTPOk.status_code)

    @route("GET", "api/player/playlist/{file:.*}.m3u8")
    async def playlist(self, request: Request) -> Response:
        """
        Get the playlist.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        file: str = request.match_info.get("file")

        if not file:
            raise web.HTTPBadRequest(text="file is required.")

        try:
            text = await Playlist(url="/").make(download_path=self.config.download_path, file=file)
            if isinstance(text, Response):
                return text
        except StreamingError as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPNotFound.status_code)

        return web.Response(
            text=text,
            headers={
                "Content-Type": "application/x-mpegURL",
                "Cache-Control": "no-cache",
                "Access-Control-Max-Age": "300",
            },
            status=web.HTTPOk.status_code,
        )

    @route("GET", "api/player/m3u8/{mode}/{file:.*}.m3u8")
    async def m3u8(self, request: Request) -> Response:
        """
        Get the m3u8 file.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        file: str = request.match_info.get("file")
        mode: str = request.match_info.get("mode")

        if mode not in ["video", "subtitle"]:
            return web.json_response(
                data={"error": "Only video and subtitle modes are supported."}, status=web.HTTPBadRequest.status_code
            )

        if not file:
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        duration = request.query.get("duration", None)

        if "subtitle" in mode:
            if not duration:
                return web.json_response(data={"error": "duration is required."}, status=web.HTTPBadRequest.status_code)

            duration = float(duration)

        try:
            cls = M3u8("/")
            if "subtitle" in mode:
                text = await cls.make_subtitle(self.config.download_path, file, duration)
            else:
                text = await cls.make_stream(self.config.download_path, file)
        except StreamingError as e:
            LOG.exception(e)
            return web.json_response(data={"error": str(e)}, status=web.HTTPNotFound.status_code)

        return web.Response(
            text=text,
            headers={
                "Content-Type": "application/x-mpegURL",
                "Cache-Control": "no-cache",
                "Access-Control-Max-Age": "300",
            },
            status=web.HTTPOk.status_code,
        )

    @route("GET", r"api/player/segments/{segment:\d+}/{file:.*}.ts")
    async def segments(self, request: Request) -> Response:
        """
        Get the segments.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        file: str = request.match_info.get("file")
        segment: int = request.match_info.get("segment")
        sd: int = request.query.get("sd")
        vc: int = int(request.query.get("vc", 0))
        ac: int = int(request.query.get("ac", 0))
        file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
        if not file_path.startswith(self.config.download_path):
            return web.json_response(data={"error": "Invalid file path."}, status=web.HTTPBadRequest.status_code)

        if request.if_modified_since:
            lastMod = time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC).timetuple()
            )
            if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

        if not file:
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        if not segment:
            return web.json_response(data={"error": "segment id is required."}, status=web.HTTPBadRequest.status_code)

        segmenter = Segments(
            index=int(segment),
            duration=float(f"{float(sd if sd else M3u8.duration):.6f}"),
            vconvert=vc == 1,
            aconvert=ac == 1,
        )

        return web.Response(
            body=await segmenter.stream(path=self.config.download_path, file=file),
            headers={
                "Content-Type": "video/mpegts",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Pragma": "public",
                "Cache-Control": f"public, max-age={time.time() + 31536000}",
                "Last-Modified": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC).timetuple()
                ),
                "Expires": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000, tz=UTC).timetuple()
                ),
            },
            status=web.HTTPOk.status_code,
        )

    @route("GET", "api/player/subtitle/{file:.*}.vtt")
    async def subtitles(self, request: Request) -> Response:
        """
        Get the subtitles.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        file: str = request.match_info.get("file")
        file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
        if not file_path.startswith(self.config.download_path):
            return web.json_response(data={"error": "Invalid file path."}, status=web.HTTPBadRequest.status_code)

        if request.if_modified_since:
            lastMod = time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC).timetuple()
            )
            if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

        if not file:
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        return web.Response(
            body=await Subtitle().make(path=self.config.download_path, file=file),
            headers={
                "Content-Type": "text/vtt; charset=UTF-8",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Pragma": "public",
                "Cache-Control": f"public, max-age={time.time() + 31536000}",
                "Last-Modified": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path), tz=UTC).timetuple()
                ),
                "Expires": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000, tz=UTC).timetuple()
                ),
            },
            status=web.HTTPOk.status_code,
        )

    @route("GET", "/")
    async def index(self, _: Request) -> Response:
        """
        Get the index file.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        if "/index.html" not in self._static_holder:
            LOG.error("Static frontend files not found.")
            return web.json_response(
                data={"error": "File not found.", "file": "/index.html"}, status=web.HTTPNotFound.status_code
            )

        data = self._static_holder["/index.html"]
        return web.Response(
            body=data.get("content"),
            content_type=data.get("content_type"),
            charset="utf-8",
            status=web.HTTPOk.status_code,
        )

    @route("GET", "api/thumbnail")
    async def get_thumbnail(self, request: Request) -> Response:
        """
        Get the thumbnail.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        url = request.query.get("url")
        if not url:
            return web.json_response(data={"error": "URL is required."}, status=web.HTTPForbidden.status_code)

        try:
            validate_url(url)
        except ValueError as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPForbidden.status_code)

        try:
            opts = {
                "proxy": self.config.ytdl_options.get("proxy", None),
                "headers": {
                    "User-Agent": self.config.ytdl_options.get(
                        "user_agent", request.headers.get("User-Agent", f"YTPTube/{self.config.version}")
                    ),
                },
            }
            async with httpx.AsyncClient(**opts) as client:
                LOG.debug(f"Fetching thumbnail from '{url}'.")
                response = await client.request(method="GET", url=url)
                return web.Response(
                    body=response.content,
                    headers={
                        "Content-Type": response.headers.get("Content-Type"),
                        "Pragma": "public",
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": f"public, max-age={time.time() + 31536000}",
                        "Expires": time.strftime(
                            "%a, %d %b %Y %H:%M:%S GMT",
                            datetime.fromtimestamp(time.time() + 31536000, tz=UTC).timetuple(),
                        ),
                    },
                )
        except Exception as e:
            LOG.error(f"Error fetching thumbnail from '{url}'. '{e}'.")
            return web.json_response(
                data={"error": "failed to retrieve the thumbnail."}, status=web.HTTPInternalServerError.status_code
            )

    @route("GET", "api/file/ffprobe/{file:.*}")
    async def get_ffprobe(self, request: Request) -> Response:
        """
        Get the ffprobe data.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        file: str = request.match_info.get("file")
        if not file:
            return web.json_response(data={"error": "file is required."}, status=web.HTTPBadRequest.status_code)

        try:
            realFile: str = calc_download_path(base_path=self.config.download_path, folder=file, create_path=False)
            if not os.path.exists(realFile) or not os.path.isfile(realFile):
                return web.json_response(
                    data={"error": f"File '{file}' does not exist."}, status=web.HTTPNotFound.status_code
                )

            return web.json_response(
                data=await ffprobe(realFile), status=web.HTTPOk.status_code, dumps=self.encoder.encode
            )
        except Exception as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)

    @route("GET", "api/youtube/auth")
    async def is_authenticated(self, request: Request) -> Response:
        """
        Check if the user yt-dlp cookie is valid & authenticated.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object

        """
        cookie_file = self.config.ytdl_options.get("cookiefile", None)
        if not cookie_file:
            return web.json_response(data={"message": "No cookie file provided."}, status=web.HTTPForbidden.status_code)

        cookie_file = os.path.realpath(cookie_file)
        if not os.path.exists(cookie_file):
            return web.json_response(
                data={"message": f"Cookie file '{cookie_file}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        try:
            import http.cookiejar

            cookies = http.cookiejar.MozillaCookieJar(cookie_file, None, None)
            cookies.load()
        except Exception as e:
            LOG.error(f"failed to load cookies from '{cookie_file}'. '{e}'.")
            LOG.exception(e)
            return web.json_response(
                data={"message": "Failed to load cookies"},
                status=web.HTTPInternalServerError.status_code,
            )

        url = "https://www.youtube.com/account"

        try:
            opts = {
                "proxy": self.config.ytdl_options.get("proxy", None),
                "headers": {
                    "User-Agent": self.config.ytdl_options.get(
                        "user_agent", request.headers.get("User-Agent", f"YTPTube/{self.config.version}")
                    ),
                },
                "cookies": cookies,
            }
            async with httpx.AsyncClient(**opts) as client:
                LOG.debug(f"Checking '{url}' redirection.")
                response = await client.request(method="GET", url=url, follow_redirects=False)
                return web.json_response(
                    data={"message": "Authenticated." if response.status_code == 200 else "Not authenticated."},
                    status=200 if response.status_code == 200 else 401,
                )
        except Exception as e:
            LOG.error(f"Failed to request '{url}'. '{e}'.")
            LOG.exception(e)
            return web.json_response(
                data={"message": f"Failed to request website. {e!s}"},
                status=web.HTTPInternalServerError.status_code,
            )

    @route("GET", "api/notifications")
    async def notifications(self, _: Request) -> Response:
        """
        Get the notification targets.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        return web.json_response(
            data={
                "notifications": Notification.get_instance().get_targets(),
                "allowedTypes": list(NotificationEvents.get_events().values()),
            },
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

    @route("PUT", "api/notifications")
    async def notification_add(self, request: Request) -> Response:
        """
        Add notification targets.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        post = await request.json()
        if not isinstance(post, list):
            return web.json_response(
                {"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        targets: list = []

        ins = Notification.get_instance()
        for item in post:
            if not isinstance(item, dict):
                return web.json_response(
                    {"error": "Invalid request body expecting list with dicts."},
                    status=web.HTTPBadRequest.status_code,
                )

            if not item.get("id", None) or validate_uuid(item.get("id"), version=4):
                item["id"] = str(uuid.uuid4())

            try:
                Notification.validate(item)
            except ValueError as e:
                return web.json_response(
                    {"error": f"Invalid notification target settings. {e!s}", "data": item},
                    status=web.HTTPBadRequest.status_code,
                )

            targets.append(ins.make_target(item))

        try:
            if len(targets) < 1:
                ins.clear()

            ins.save(targets=targets)
            ins.load()
        except Exception as e:
            LOG.exception(e)
            return web.json_response({"error": "Failed to save tasks."}, status=web.HTTPInternalServerError.status_code)

        data = {"notifications": targets, "allowedTypes": list(NotificationEvents.get_events().values())}

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("POST", "api/notifications/test")
    async def notification_test(self, _: Request) -> Response:
        """
        Test the notification.

        Args:
            _: The request object.

        Returns:
            Response: The response object.

        """
        data = {"type": "test", "message": "This is a test notification."}
        await self.emitter.emit(Events.TEST, data)

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)
