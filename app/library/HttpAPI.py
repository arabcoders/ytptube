import base64
import functools
import hmac
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import httpx
import magic
from aiohttp import web
from aiohttp.web import Request, RequestHandler, Response

from .cache import Cache
from .common import common
from .config import Config
from .DownloadQueue import DownloadQueue
from .Emitter import Emitter
from .encoder import Encoder
from .ffprobe import ffprobe
from .M3u8 import M3u8
from .Playlist import Playlist
from .Segments import Segments
from .Subtitle import Subtitle
from .Utils import StreamingError, calcDownloadPath, getVideoInfo, validate_url

LOG = logging.getLogger("http_api")
MIME = magic.Magic(mime=True)


class HttpAPI(common):
    staticHolder: dict = {}
    extToMime: dict = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".ico": "image/x-icon",
    }

    def __init__(self, queue: DownloadQueue, emitter: Emitter, encoder: Encoder):
        super().__init__(queue=queue, encoder=encoder)

        self.rootPath = str(Path(__file__).parent.parent.parent)
        self.config = Config.get_instance()

        self.routes = web.RouteTableDef()

        self.encoder = encoder
        self.emitter = emitter
        self.queue = queue
        self.cache = Cache()

    def route(method: str, path: str):
        """
        Decorator to mark a method as an HTTP route handler.
        """

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            wrapper._http_method = method.upper()
            wrapper._http_path = path
            return wrapper

        return decorator

    async def staticFile(self, req: Request) -> Response:
        """
        Preload static files from the ui/exported folder.
        """
        path = req.path
        if req.path not in self.staticHolder:
            return web.json_response({"error": "File not found.", "file": path}, status=web.HTTPNotFound.status_code)

        item: dict = self.staticHolder[req.path]

        return web.Response(
            body=item.get("content"),
            headers={
                "Pragma": "public",
                "Cache-Control": "public, max-age=31536000",
                "Content-Type": item.get("content_type"),
                "X-Via": "memory" if not item.get("file", None) else "disk",
            },
            status=web.HTTPOk.status_code,
        )

    def preloadStatic(self, app: web.Application):
        """
        Preload static files from the ui/exported folder.
        """
        staticDir = os.path.join(self.rootPath, "ui", "exported")
        if not os.path.exists(staticDir):
            raise ValueError(f"Could not find the frontend UI static assets. '{staticDir}'.")

        preloaded = 0

        for root, _, files in os.walk(staticDir):
            for file in files:
                if file.endswith(".map"):
                    continue

                file = os.path.join(root, file)
                urlPath = f"{self.config.url_prefix}{file.replace(f'{staticDir}/', '')}"

                content = open(file, "rb").read()
                contentType = self.extToMime.get(os.path.splitext(file)[1], MIME.from_file(file))

                self.staticHolder[urlPath] = {"content": content, "content_type": contentType}
                LOG.debug(f"Preloading '{urlPath}'.")
                app.router.add_get(urlPath, self.staticFile)
                preloaded += 1

                if urlPath.endswith("/index.html") and urlPath != "/index.html":
                    parentSlash = urlPath.replace("/index.html", "/")
                    parentNoSlash = urlPath.replace("/index.html", "")
                    self.staticHolder[parentSlash] = {"content": content, "content_type": contentType}
                    self.staticHolder[parentNoSlash] = {"content": content, "content_type": contentType}
                    app.router.add_get(parentSlash, self.staticFile)
                    app.router.add_get(parentNoSlash, self.staticFile)
                    preloaded += 2

        if preloaded < 1:
            message = f"Could not find the frontend UI static assets. '{staticDir}'."
            if self.config.ignore_ui:
                LOG.warning(message)
                return

            raise ValueError(message)

        LOG.info(f"Preloaded '{preloaded}' static files.")

    def attach(self, app: web.Application):
        if self.config.auth_username and self.config.auth_password:
            app.middlewares.append(HttpAPI.basic_auth(self.config.auth_username, self.config.auth_password))

        self.add_routes(app)

    def add_routes(self, app: web.Application):
        for attr_name in dir(self):
            method = getattr(self, attr_name)
            if hasattr(method, "_http_method") and hasattr(method, "_http_path"):
                http_path = method._http_path
                if http_path.startswith("/") and self.config.url_prefix.endswith("/"):
                    http_path = method._http_path[1:]

                self.routes.route(method._http_method, self.config.url_prefix + http_path)(method)

        async def on_prepare(request: Request, response: Response):
            if "Server" in response.headers:
                del response.headers["Server"]

            if "Origin" in request.headers:
                response.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]
                response.headers["Access-Control-Allow-Headers"] = "Content-Type"
                response.headers["Access-Control-Allow-Methods"] = "PATCH, PUT, POST, DELETE"

        if self.config.url_prefix != "/":
            self.routes.route("GET", "/")(lambda _: web.HTTPFound(self.config.url_prefix))
            self.routes.get(self.config.url_prefix[:-1])(lambda _: web.HTTPFound(self.config.url_prefix))

        self.routes.static(f"{self.config.url_prefix}api/download/", self.config.download_path)
        self.preloadStatic(app)

        try:
            app.add_routes(self.routes)
            app.on_response_prepare.append(on_prepare)
        except ValueError as e:
            if "ui/exported" in str(e):
                raise RuntimeError(f"Could not find the frontend UI static assets. '{e}'.") from e
            raise e

    def basic_auth(username: str, password: str):
        @web.middleware
        async def middleware_handler(request: Request, handler: RequestHandler) -> Response:
            auth_header = request.headers.get("Authorization")

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

    @route("GET", "api/ping")
    async def ping(self, _) -> Response:
        await self.queue.test()
        return web.json_response(data={"status": "pong"}, status=web.HTTPOk.status_code)

    @route("POST", "api/add")
    async def add_url(self, request: Request) -> Response:
        post = await request.json()

        url: str = post.get("url")

        if not url:
            return web.json_response(data={"error": "url is required."}, status=web.HTTPBadRequest.status_code)

        preset: str = str(post.get("preset", self.config.default_preset))
        folder: str = str(post.get("folder")) if post.get("folder") else ""
        ytdlp_cookies: str = str(post.get("ytdlp_cookies")) if post.get("ytdlp_cookies") else ""
        output_template: str = str(post.get("output_template")) if post.get("output_template") else ""

        ytdlp_config = post.get("ytdlp_config")
        if isinstance(ytdlp_config, str) and ytdlp_config:
            try:
                ytdlp_config = json.loads(ytdlp_config)
            except Exception as e:
                LOG.error(f"Failed to parse json yt-dlp config for '{url}'. {str(e)}")
                return web.json_response(
                    data={"error": f"Failed to parse json yt-dlp config. {str(e)}"},
                    status=web.HTTPBadRequest.status_code,
                )

        status = await self.add(
            url=url,
            preset=preset,
            folder=folder,
            ytdlp_cookies=ytdlp_cookies,
            ytdlp_config=ytdlp_config if isinstance(ytdlp_config, dict) else {},
            output_template=output_template,
        )

        return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/tasks")
    async def tasks(self, _: Request) -> Response:
        tasks_file: str = os.path.join(self.config.config_path, "tasks.json")

        if not os.path.exists(tasks_file):
            return web.json_response({"error": "No tasks defined."}, status=web.HTTPNotFound.status_code)

        try:
            with open(tasks_file, "r") as f:
                tasks = json.load(f)
        except Exception as e:
            LOG.exception(e)
            return web.json_response({"error": "Failed to load tasks."}, status=web.HTTPInternalServerError.status_code)

        return web.json_response(data=tasks, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/url/info")
    async def get_info(self, request: Request) -> Response:
        url = request.query.get("url")
        if not url:
            return web.json_response(data={"error": "URL is required."}, status=web.HTTPForbidden.status_code)

        try:
            validate_url(url)
        except ValueError as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPForbidden.status_code)

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

            data = getVideoInfo(url=url, ytdlp_opts=opts, no_archive=True)
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

    @route("POST", "api/add_batch")
    async def add_batch(self, request: Request) -> Response:
        status = {}

        post = await request.json()
        if not isinstance(post, list):
            return web.json_response(
                data={"error": "Invalid request body expecting list with dicts."},
                status=web.HTTPBadRequest.status_code,
            )

        for item in post:
            if not isinstance(item, dict):
                return web.json_response(
                    data={"error": "Invalid request body expecting list with dicts."},
                    status=web.HTTPBadRequest.status_code,
                )

            if not item.get("url"):
                return web.json_response(
                    data={"error": "url is required.", "data": post}, status=web.HTTPBadRequest.status_code
                )

        for item in post:
            status[item.get("url")] = await self.add(
                url=item.get("url"),
                preset=item.get("preset", "default"),
                folder=item.get("folder"),
                ytdlp_cookies=item.get("ytdlp_cookies"),
                ytdlp_config=item.get("ytdlp_config"),
                output_template=item.get("output_template"),
            )

        return web.json_response(data=status, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("DELETE", "api/delete")
    async def delete(self, request: Request) -> Response:
        post = await request.json()
        ids = post.get("ids")
        where = post.get("where")
        if not ids or where not in ["queue", "done"]:
            return web.json_response(
                data={"error": "ids and where are required."}, status=web.HTTPBadRequest.status_code
            )

        remove_file: bool = bool(post.get("remove_file", True))

        return web.json_response(
            data=await (self.queue.cancel(ids) if where == "queue" else self.queue.clear(ids, remove_file=remove_file)),
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

    @route("POST", "api/history/{id}")
    async def update_item(self, request: Request) -> Response:
        id: str = request.match_info.get("id")
        if not id:
            return web.json_response(data={"error": "id is required."}, status=web.HTTPBadRequest.status_code)

        item = self.queue.done.getById(id)
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
            await self.emitter.emit("update", item.info)

        return web.json_response(
            data=item.info,
            status=web.HTTPOk.status_code if updated else web.HTTPNotModified.status_code,
            dumps=self.encoder.encode,
        )

    @route("GET", "api/history")
    async def history(self, _: Request) -> Response:
        data: dict = {"queue": [], "history": []}

        for _, v in self.queue.queue.saved_items():
            data["queue"].append(v)
        for _, v in self.queue.done.saved_items():
            data["history"].append(v)

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/workers")
    async def workers(self, _) -> Response:
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
    async def restart_pool(self, _) -> Response:
        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        self.queue.pool.start()

        return web.json_response({"message": "Workers pool being restarted."}, status=web.HTTPOk.status_code)

    @route("PATCH", "api/workers/{id}")
    async def restart_worker(self, request: Request) -> Response:
        id: str = request.match_info.get("id")
        if not id:
            return web.json_response({"error": "worker id is required."}, status=web.HTTPBadRequest.status_code)

        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        status = await self.queue.pool.restart(id, "requested by user.")

        return web.json_response({"status": "restarted" if status else "in_error_state"}, status=web.HTTPOk.status_code)

    @route("delete", "api/workers/{id}")
    async def stop_worker(self, request: Request) -> Response:
        id: str = request.match_info.get("id")
        if not id:
            raise web.HTTPBadRequest(text="worker id is required.")

        if self.queue.pool is None:
            return web.json_response({"error": "Worker pool not initialized."}, status=web.HTTPNotFound.status_code)

        status = await self.queue.pool.stop(id, "requested by user.")

        return web.json_response({"status": "stopped" if status else "in_error_state"}, status=web.HTTPOk.status_code)

    @route("GET", "api/player/playlist/{file:.*}.m3u8")
    async def playlist(self, request: Request) -> Response:
        file: str = request.match_info.get("file")

        if not file:
            raise web.HTTPBadRequest(text="file is required.")

        try:
            text = await Playlist(url=f"{self.config.url_host}{self.config.url_prefix}").make(
                download_path=self.config.download_path, file=file
            )
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
            cls = M3u8(f"{self.config.url_host}{self.config.url_prefix}")
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
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()
            )
            if os.path.exists(file_path) and request.if_modified_since.timestamp() == os.path.getmtime(file_path):
                return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

        if not file:
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        if not segment:
            return web.json_response(data={"error": "segment id is required."}, status=web.HTTPBadRequest.status_code)

        segmenter = Segments(
            index=int(segment),
            duration=float("{:.6f}".format(float(sd if sd else M3u8.duration))),
            vconvert=True if vc == 1 else False,
            aconvert=True if ac == 1 else False,
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
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()
                ),
                "Expires": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000).timetuple()
                ),
            },
            status=web.HTTPOk.status_code,
        )

    @route("GET", "api/player/subtitle/{file:.*}.vtt")
    async def subtitles(self, request: Request) -> Response:
        file: str = request.match_info.get("file")
        file_path: str = os.path.normpath(os.path.join(self.config.download_path, file))
        if not file_path.startswith(self.config.download_path):
            return web.json_response(data={"error": "Invalid file path."}, status=web.HTTPBadRequest.status_code)

        if request.if_modified_since:
            lastMod = time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()
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
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(os.path.getmtime(file_path)).timetuple()
                ),
                "Expires": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000).timetuple()
                ),
            },
            status=web.HTTPOk.status_code,
        )

    @route("OPTIONS", "api/add")
    async def add_cors(self, _: Request) -> Response:
        return web.json_response(data={"status": "ok"}, status=web.HTTPOk.status_code)

    @route("OPTIONS", "api/delete")
    async def delete_cors(self, _: Request) -> Response:
        return web.json_response(data={"status": "ok"}, status=web.HTTPOk.status_code)

    @route("GET", "/")
    async def index(self, _) -> Response:
        if "/index.html" not in self.staticHolder:
            LOG.error("Static frontend files not found.")
            return web.json_response(
                data={"error": "File not found.", "file": "/index.html"}, status=web.HTTPNotFound.status_code
            )

        data = self.staticHolder["/index.html"]
        return web.Response(
            body=data.get("content"),
            content_type=data.get("content_type"),
            charset="utf-8",
            status=web.HTTPOk.status_code,
        )

    @route("GET", "api/thumbnail")
    async def get_thumbnail(self, request: Request) -> Response:
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
                            "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(time.time() + 31536000).timetuple()
                        ),
                    },
                )
        except Exception as e:
            LOG.error(f"Error fetching thumbnail from '{url}'. '{e}'.")
            LOG.exception(e)
            return web.json_response(
                data={"error": "failed to retrieve the thumbnail."}, status=web.HTTPInternalServerError.status_code
            )

    @route("GET", "api/ffprobe/{file:.*}")
    async def get_ffprobe(self, request: Request) -> Response:
        file: str = request.match_info.get("file")
        try:
            realFile: str = calcDownloadPath(basePath=self.config.download_path, folder=file, createPath=False)
            if not os.path.exists(realFile):
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
                data={"message": f"Failed to request website. {str(e)}"},
                status=web.HTTPInternalServerError.status_code,
            )
