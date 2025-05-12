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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote_plus, urlparse

import anyio
import httpx
import magic
from aiohttp import web
from aiohttp.web import Request, RequestHandler, Response
from yt_dlp.cookies import LenientSimpleCookie

from .cache import Cache
from .common import Common
from .conditions import Condition, Conditions
from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import EventBus, Events, message
from .ffprobe import ffprobe
from .ItemDTO import Item
from .M3u8 import M3u8
from .Notifications import Notification, NotificationEvents
from .Playlist import Playlist
from .Presets import Preset, Presets
from .Segments import Segments
from .Subtitle import Subtitle
from .Tasks import Task, Tasks
from .Utils import (
    REMOVE_KEYS,
    StreamingError,
    arg_converter,
    decrypt_data,
    encrypt_data,
    extract_info,
    get_file,
    get_file_sidecar,
    get_files,
    get_mime_type,
    load_cookies,
    read_logfile,
    validate_url,
    validate_uuid,
)
from .YTDLPOpts import YTDLPOpts

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

    _frontend_routes = [
        "/console",
        "/presets",
        "/tasks",
        "/notifications",
        "/changelog",
        "/logs",
        "/conditions",
        "/browser",
        "/browser/{path:.*}",
    ]
    """Frontend routes to be preloaded"""

    def __init__(
        self,
        queue: DownloadQueue | None = None,
        encoder: Encoder | None = None,
        config: Config | None = None,
    ):
        self.queue = queue or DownloadQueue.get_instance()
        self.encoder = encoder or Encoder()
        self.config = config or Config.get_instance()
        self._notify = EventBus.get_instance()

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
        app.middlewares.append(HttpAPI.middle_wares(download_path=self.config.download_path))
        if self.config.auth_username and self.config.auth_password:
            app.middlewares.append(HttpAPI.basic_auth(self.config.auth_username, self.config.auth_password))

        self.add_routes(app)

        async def on_prepare(request: Request, response: Response):
            if "Server" in response.headers:
                del response.headers["Server"]

            response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, PATCH, PUT, POST, DELETE"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = str(60 * 15)

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

        if path not in self._static_holder:
            for k in self._static_holder:
                if path.startswith(k):
                    path = k
                    break
            else:
                return web.json_response(
                    {"error": "File not found.", "file": path}, status=web.HTTPNotFound.status_code
                )

        item: dict = self._static_holder[path]

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

                if urlPath.endswith("/index.html"):
                    for path in self._frontend_routes:
                        self._static_holder[path] = {"content": content, "content_type": contentType}
                        app.router.add_get(path, self._static_file)
                        if "{" not in path:
                            self._static_holder[path + "/"] = {"content": content, "content_type": contentType}
                            app.router.add_get(path + "/", self._static_file)
                        LOG.debug(f"Preloading '{path}'.")
                        preloaded += 1

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
            # if OPTIONS request, skip auth
            if request.method == "OPTIONS":
                return await handler(request)

            auth_header = request.headers.get("Authorization")
            if auth_header is None and request.query.get("apikey") is not None:
                auth_header = f"Basic {request.query.get('apikey')}"

            if auth_header is None:
                auth_cookie = request.cookies.get("auth")
                if auth_cookie is not None:
                    try:
                        data = decrypt_data(auth_cookie, key=Config.get_instance().secret_key)
                        if data is not None:
                            data = base64.b64encode(data.encode()).decode()
                            auth_header = f"Basic {data}"
                    except Exception as e:
                        LOG.exception(e)

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

            response = await handler(request)
            if request.path != "/":
                return response

            try:
                response.set_cookie(
                    "auth",
                    encrypt_data(
                        f"{user_name}:{user_password}",
                        key=Config.get_instance().secret_key,
                    ),
                    max_age=60 * 60 * 24 * 7,
                    expires=datetime.now(UTC) + timedelta(days=7),
                    httponly=True,
                    samesite="Strict",
                )
            except Exception as e:
                LOG.exception(e)

            return response

        return middleware_handler

    @staticmethod
    def middle_wares(download_path: str) -> Awaitable:
        @web.middleware
        async def middleware_handler(request: Request, handler: RequestHandler) -> Response:
            if request.path.startswith("/api/download"):
                realFile, status = get_file(
                    download_path=download_path,
                    file=request.path.replace("/api/download/", ""),
                )
                if web.HTTPFound.status_code == status:
                    return Response(
                        status=status,
                        headers={
                            "Location": f"/api/download/{quote(str(realFile).replace(download_path, '').strip('/'))}"
                        },
                    )

            response = await handler(request)

            if isinstance(response, web.FileResponse):
                try:
                    ff_info = await ffprobe(response._path)
                    mime_type = get_mime_type(ff_info.get("metadata", {}), response._path)
                    response.content_type = mime_type
                except Exception:
                    pass

            return response

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

            data = arg_converter(args, dumps=True)

            if "outtmpl" in data and "default" in data["outtmpl"]:
                response["output_template"] = data["outtmpl"]["default"]

            if "paths" in data and "home" in data["paths"]:
                response["download_path"] = data["paths"]["home"]

            if "format" in data:
                response["format"] = data["format"]

            bad_options = {k: v for d in REMOVE_KEYS for k, v in d.items()}
            removed_options = []

            for key in data:
                if key in bad_options.items():
                    removed_options.append(bad_options[key])
                    continue
                if not key.startswith("_"):
                    response["opts"][key] = data[key]

            if len(removed_options) > 0:
                response["opts"]["removed"] = ", ".join(removed_options)

            return web.json_response(data=response, status=web.HTTPOk.status_code)
        except Exception as e:
            err = str(e).strip()
            err = err.split("\n")[-1] if "\n" in err else err
            err = err.replace("main.py: error: ", "").strip().capitalize()
            return web.json_response(
                data={"error": f"Failed to parse command arguments for yt-dlp. '{err}'."},
                status=web.HTTPBadRequest.status_code,
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

        preset = request.query.get("preset")
        if preset:
            exists = Presets.get_instance().get(preset)
            if not exists:
                return web.json_response(
                    data={"status": False, "message": f"Preset '{preset}' does not exist."},
                    status=web.HTTPBadRequest.status_code,
                )
        else:
            preset = self.config.default_preset

        try:
            key = self.cache.hash(url + str(preset))

            if self.cache.has(key) and not request.query.get("force", False):
                data = self.cache.get(key)
                data["_cached"] = {
                    "status": "hit",
                    "key": key,
                    "ttl": data.get("_cached", {}).get("ttl", 300),
                    "ttl_left": data.get("_cached", {}).get("expires", time.time() + 300) - time.time(),
                    "expires": data.get("_cached", {}).get("expires", time.time() + 300),
                }
                return web.Response(body=json.dumps(data, indent=4), status=web.HTTPOk.status_code)

            opts = {}

            if ytdlp_proxy := self.config.get_ytdlp_args().get("proxy", None):
                opts["proxy"] = ytdlp_proxy

            ytdlp_opts = YTDLPOpts.get_instance().preset(name=preset, with_cookies=True).add(opts).get_all()

            data = extract_info(
                config=ytdlp_opts,
                url=url,
                debug=False,
                no_archive=True,
                follow_redirect=True,
                sanitize_info=True,
            )

            if "formats" in data:
                for index, item in enumerate(data["formats"]):
                    if "cookies" in item and len(item["cookies"]) > 0:
                        cookies = [f"{c.key}={c.value}" for c in LenientSimpleCookie(item["cookies"]).values()]
                        if len(cookies) > 0:
                            data["formats"][index]["h_cookies"] = "; ".join(cookies)
                            data["formats"][index]["h_cookies"] = data["formats"][index]["h_cookies"].strip()

            data["_cached"] = {
                "status": "miss",
                "key": key,
                "ttl": 300,
                "ttl_left": 300,
                "expires": time.time() + 300,
            }

            self.cache.set(key=key, value=data, ttl=300)

            return web.Response(body=json.dumps(data, indent=4), status=web.HTTPOk.status_code)
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Error encountered while getting video info for '{url}'. '{e!s}'.")
            return web.json_response(
                data={
                    "error": "failed to get video info.",
                    "message": str(e),
                    "formats": [],
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

        def info_wrapper(id: str, url: str) -> tuple[str, dict]:
            try:
                return (
                    id,
                    extract_info(
                        config={
                            "proxy": self.config.get_ytdlp_args().get("proxy", None),
                            "simulate": True,
                            "dump_single_json": True,
                        },
                        url=url,
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
                    asyncio.get_event_loop().run_in_executor(None, lambda id=id, url=url: info_wrapper(id=id, url=url))
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

        data = {
            "url": url,
        }

        preset = request.query.get("preset")
        if preset:
            exists = Presets.get_instance().get(preset)
            if not exists:
                return web.json_response(
                    data={"status": False, "message": f"Preset '{preset}' does not exist."},
                    status=web.HTTPBadRequest.status_code,
                )
            data["preset"] = preset

        try:
            status = await self.add(item=Item.format(data))
        except ValueError as e:
            return web.json_response(data={"status": False, "message": str(e)}, status=web.HTTPBadRequest.status_code)

        return web.json_response(
            data={"status": status.get("status") == "ok", "message": status.get("msg", "URL added")},
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

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

        items = []
        for item in data:
            try:
                items.append(Item.format(item))
            except ValueError as e:
                return web.json_response(data={"error": str(e), "data": item}, status=web.HTTPBadRequest.status_code)

        status = await asyncio.wait_for(
            fut=asyncio.gather(*[self.add(item=item) for item in items]),
            timeout=None,
        )
        response = []
        for i, item in enumerate(items):
            response.append({"item": item, "status": status[i].get("status") == "ok", "msg": status[i].get("msg")})

        return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/logs")
    async def logs(self, request: Request) -> Response:
        """
        Get recent logs

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        if not self.config.file_logging:
            return web.json_response(
                data={"error": "File logging is not enabled."}, status=web.HTTPNotFound.status_code
            )

        offset = int(request.query.get("offset", 0))
        limit = int(request.query.get("limit", 100))
        if limit < 1 or limit > 150:
            limit = 50

        logs_data = await read_logfile(
            file=os.path.join(self.config.config_path, "logs", "app.log"),
            offset=offset,
            limit=limit,
        )
        return web.json_response(
            data={
                "logs": logs_data["logs"],
                "offset": offset,
                "limit": limit,
                "next_offset": logs_data["next_offset"],
                "end_is_reached": logs_data["end_is_reached"],
            },
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

    @route("GET", "api/conditions")
    async def conditions(self, _: Request) -> Response:
        """
        Get the conditions

        Args:
            _ (Request): The request object.

        Returns:
            Response: The response object.

        """
        return web.json_response(
            data=Conditions.get_instance().get_all(),
            status=web.HTTPOk.status_code,
            dumps=self.encoder.encode,
        )

    @route("PUT", "api/conditions")
    async def conditions_add(self, request: Request) -> Response:
        """
        Save Conditions.

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

        items: list = []

        cls = Conditions.get_instance()

        for item in data:
            if not isinstance(item, dict):
                return web.json_response(
                    {"error": "Invalid request body expecting list with dicts."},
                    status=web.HTTPBadRequest.status_code,
                )

            if not item.get("name"):
                return web.json_response(
                    {"error": "name is required.", "data": item}, status=web.HTTPBadRequest.status_code
                )

            if not item.get("filter"):
                return web.json_response(
                    {"error": "filter is required.", "data": item}, status=web.HTTPBadRequest.status_code
                )

            if not item.get("cli"):
                return web.json_response(
                    {"error": "CLI arguments is required.", "data": item}, status=web.HTTPBadRequest.status_code
                )

            if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
                item["id"] = str(uuid.uuid4())

            try:
                cls.validate(item)
            except ValueError as e:
                return web.json_response(
                    {"error": f"Failed to validate condition '{item.get('name')}'. '{e!s}'"},
                    status=web.HTTPBadRequest.status_code,
                )

            items.append(Condition(**item))
        try:
            items = cls.save(items=items).load().get_all()
        except Exception as e:
            LOG.exception(e)
            return web.json_response(
                {"error": "Failed to save conditions.", "message": str(e)},
                status=web.HTTPInternalServerError.status_code,
            )

        await self._notify.emit(Events.CONDITIONS_UPDATE, data=items)
        return web.json_response(data=items, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/presets")
    async def presets(self, request: Request) -> Response:
        """
        Get the presets.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        data = Presets.get_instance().get_all()
        filter_fields = request.query.get("filter", None)

        if filter_fields:
            fields = [field.strip() for field in filter_fields.split(",")]
            data = [{key: value for key, value in preset.__dict__.items() if key in fields} for preset in data]

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("PUT", "api/presets")
    async def presets_add(self, request: Request) -> Response:
        """
        Add presets.

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

        presets: list = []

        cls = Presets.get_instance()

        for item in data:
            if not isinstance(item, dict):
                return web.json_response(
                    {"error": "Invalid request body expecting list with dicts."},
                    status=web.HTTPBadRequest.status_code,
                )

            if not item.get("name"):
                return web.json_response(
                    {"error": "name is required.", "data": item}, status=web.HTTPBadRequest.status_code
                )

            if not item.get("id", None) or not validate_uuid(item.get("id"), version=4):
                item["id"] = str(uuid.uuid4())

            try:
                cls.validate(item)
            except ValueError as e:
                return web.json_response(
                    {"error": f"Failed to validate preset '{item.get('name')}'. '{e!s}'"},
                    status=web.HTTPBadRequest.status_code,
                )

            presets.append(Preset(**item))
        try:
            presets = cls.save(items=presets).load().get_all()
        except Exception as e:
            LOG.exception(e)
            return web.json_response(
                {"error": "Failed to save presets.", "message": str(e)},
                status=web.HTTPInternalServerError.status_code,
            )

        await self._notify.emit(Events.PRESETS_UPDATE, data=presets)
        return web.json_response(data=presets, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

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
            data=Tasks.get_instance().get_all(), status=web.HTTPOk.status_code, dumps=self.encoder.encode
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

            if not item.get("template", None):
                item["template"] = ""

            if not item.get("cli", None):
                item["cli"] = ""

            try:
                ins.validate(item)
            except ValueError as e:
                return web.json_response(
                    {"error": f"Failed to validate task '{item.get('name')}'. '{e!s}'"},
                    status=web.HTTPBadRequest.status_code,
                )

            tasks.append(Task(**item))

        try:
            tasks = ins.save(tasks=tasks).load().get_all()
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
            await self._notify.emit(Events.UPDATE, data=item.info)

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
        q = self.queue.get()

        data["queue"].extend([q.get("queue", {}).get(k) for k in q.get("queue", {})])
        data["history"].extend([q.get("done", {}).get(k) for k in q.get("done", {})])

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
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        try:
            realFile, status = get_file(download_path=self.config.download_path, file=file)
            if web.HTTPFound.status_code == status:
                return Response(
                    status=web.HTTPFound.status_code,
                    headers={
                        "Location": f"/api/player/playlist/{quote(str(realFile).replace(self.config.download_path, '').strip('/'))}.m3u8"
                    },
                )

            if web.HTTPNotFound.status_code == status:
                return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

            return web.Response(
                text=await Playlist(download_path=self.config.download_path, url="/").make(file=realFile),
                headers={
                    "Content-Type": "application/x-mpegURL",
                    "Cache-Control": "no-cache",
                    "Access-Control-Max-Age": "300",
                },
                status=web.HTTPOk.status_code,
            )
        except StreamingError as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPNotFound.status_code)

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
            cls = M3u8(download_path=self.config.download_path, url="/")

            realFile, status = get_file(download_path=self.config.download_path, file=file)
            if web.HTTPFound.status_code == status:
                return Response(
                    status=status,
                    headers={
                        "Location": f"/api/player/m3u8/{mode}/{quote(str(realFile).replace(self.config.download_path, '').strip('/'))}.m3u8"
                    },
                )

            if web.HTTPNotFound.status_code == status:
                return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

            if "subtitle" in mode:
                text = await cls.make_subtitle(file=realFile, duration=duration)
            else:
                text = await cls.make_stream(file=realFile)
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

        if not file:
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        if not segment:
            return web.json_response(data={"error": "segment id is required."}, status=web.HTTPBadRequest.status_code)

        realFile, status = get_file(download_path=self.config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=status,
                headers={
                    "Location": f"/api/player/segments/{segment}/{quote(str(realFile).replace(self.config.download_path, '').strip('/'))}.ts"
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        mtime = realFile.stat().st_mtime

        if request.if_modified_since and request.if_modified_since.timestamp() == mtime:
            lastMod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple())
            return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

        segmenter = Segments(
            download_path=self.config.download_path,
            index=int(segment),
            duration=float(f"{float(sd if sd else M3u8.duration):.6f}"),
            vconvert=vc == 1,
            aconvert=ac == 1,
        )

        return web.Response(
            body=await segmenter.stream(file=realFile),
            headers={
                "Content-Type": "video/mpegts",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Pragma": "public",
                "Cache-Control": f"public, max-age={time.time() + 31536000}",
                "Last-Modified": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple()
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

        if not file:
            return web.json_response(data={"error": "file is required"}, status=web.HTTPBadRequest.status_code)

        realFile, status = get_file(download_path=self.config.download_path, file=file)
        if web.HTTPFound.status_code == status:
            return Response(
                status=status,
                headers={
                    "Location": f"/api/player/subtitle/{quote(str(realFile).replace(self.config.download_path, '').strip('/'))}.vtt"
                },
            )

        if web.HTTPNotFound.status_code == status:
            return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

        mtime = realFile.stat().st_mtime

        if request.if_modified_since and request.if_modified_since.timestamp() == mtime:
            lastMod = time.strftime("%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple())
            return web.Response(status=web.HTTPNotModified.status_code, headers={"Last-Modified": lastMod})

        return web.Response(
            body=await Subtitle(download_path=self.config.download_path).make(file=realFile),
            headers={
                "Content-Type": "text/vtt; charset=UTF-8",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Pragma": "public",
                "Cache-Control": f"public, max-age={time.time() + 31536000}",
                "Last-Modified": time.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT", datetime.fromtimestamp(mtime, tz=UTC).timetuple()
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
            ytdlp_args = self.config.get_ytdlp_args()
            opts = {
                "proxy": ytdlp_args.get("proxy", None),
                "headers": {
                    "User-Agent": ytdlp_args.get(
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

    @route("GET", "api/random/background")
    async def get_background(self, request: Request) -> Response:
        """
        Get random background.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        backend = None

        try:
            backend = random.choice(self.config.pictures_backends)  # noqa: S311
            CACHE_KEY = "random_background"

            if self.cache.has(CACHE_KEY) and not request.query.get("force", False):
                data = await self.cache.aget(CACHE_KEY)
                return web.Response(
                    body=data.get("content"),
                    headers={
                        "X-Cache": "HIT",
                        "X-Cache-TTL": str(await self.cache.attl(CACHE_KEY)),
                        "X-Image-Via": data.get("backend"),
                        **data.get("headers"),
                    },
                )

            ytdlp_args = self.config.get_ytdlp_args()
            opts = {
                "proxy": ytdlp_args.get("proxy", None),
                "headers": {
                    "User-Agent": ytdlp_args.get("user_agent", f"YTPTube/{self.config.version}"),
                },
            }

            async with httpx.AsyncClient(**opts) as client:
                response = await client.request(method="GET", url=backend, follow_redirects=True)

                if response.status_code != web.HTTPOk.status_code:
                    return web.json_response(
                        data={"error": "failed to retrieve the random background image."},
                        status=web.HTTPInternalServerError.status_code,
                    )

                data = {
                    "content": response.content,
                    "backend": urlparse(backend).netloc,
                    "headers": {
                        "Content-Type": response.headers.get("Content-Type", "image/jpeg"),
                        "Content-Length": str(len(response.content)),
                    },
                }

                await self.cache.aset(key=CACHE_KEY, value=data, ttl=3600)

                return web.Response(
                    body=data.get("content"),
                    headers={
                        "X-Cache": "MISS",
                        "X-Cache-TTL": "3600",
                        "X-Image-Via": data.get("backend"),
                        **data.get("headers"),
                    },
                )
        except Exception as e:
            LOG.exception(e)
            LOG.error(f"Failed to request random background image from '{backend!s}'.'. '{e!s}'.")
            return web.json_response(
                data={"error": "failed to retrieve the random background image."},
                status=web.HTTPInternalServerError.status_code,
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
            realFile, status = get_file(download_path=self.config.download_path, file=file)
            if web.HTTPFound.status_code == status:
                return Response(
                    status=web.HTTPFound.status_code,
                    headers={
                        "Location": f"/api/file/ffprobe/{quote(str(realFile).replace(self.config.download_path, '').strip('/'))}"
                    },
                )

            if web.HTTPNotFound.status_code == status:
                return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

            return web.json_response(
                data=await ffprobe(realFile), status=web.HTTPOk.status_code, dumps=self.encoder.encode
            )
        except Exception as e:
            return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)

    @route("GET", "api/file/info/{file:.*}")
    async def get_file_info(self, request: Request) -> Response:
        """
        Get file info

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        file: str = request.match_info.get("file")
        if not file:
            return web.json_response(data={"error": "file is required."}, status=web.HTTPBadRequest.status_code)

        try:
            realFile, status = get_file(download_path=self.config.download_path, file=file)
            if web.HTTPFound.status_code == status:
                return Response(
                    status=web.HTTPFound.status_code,
                    headers={
                        "Location": f"/api/file/info/{quote(str(realFile).replace(self.config.download_path, '').strip('/'))}"
                    },
                )

            if web.HTTPNotFound.status_code == status:
                return web.json_response(data={"error": f"File '{file}' does not exist."}, status=status)

            ff_info = await ffprobe(realFile)

            response = {
                "title": str(Path(realFile).stem),
                "ffprobe": ff_info,
                "mimetype": get_mime_type(ff_info.get("metadata", {}), realFile),
                "sidecar": get_file_sidecar(realFile),
            }

            for key in response["sidecar"]:
                for i, f in enumerate(response["sidecar"][key]):
                    response["sidecar"][key][i]["file"] = (
                        str(Path(realFile).with_name(Path(f["file"]).name))
                        .replace(self.config.download_path, "")
                        .strip("/")
                    )

            return web.json_response(data=response, status=web.HTTPOk.status_code, dumps=self.encoder.encode)
        except Exception as e:
            LOG.exception(e)
            return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)

    @route("GET", "api/youtube/auth")
    async def is_authenticated(self, _: Request) -> Response:
        """
        Check if the user cookies are valid.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object

        """
        ytdlp_args = self.config.get_ytdlp_args()

        c_request = {}
        c_request_file = os.path.join(self.config.config_path, "check_cookie_request.json")
        if os.path.exists(c_request_file):
            async with await anyio.open_file(c_request_file, "r", encoding="utf-8") as f:
                try:
                    c_request = json.loads(await f.read())
                except json.JSONDecodeError as e:
                    LOG.error(f"Failed to load '{c_request_file}'. '{e!s}'.")
                    LOG.exception(e)
                    return web.json_response(
                        data={"message": "Failed to load cookie request file. Check logs for more details."},
                        status=web.HTTPInternalServerError.status_code,
                    )

        cookie_file = c_request.get("cookie_file", None)
        if not cookie_file:
            cookie_file = ytdlp_args.get("cookiefile", None)
            if not cookie_file:
                return web.json_response(
                    data={"message": "No cookie file provided."}, status=web.HTTPNotFound.status_code
                )

        if not os.path.exists(cookie_file):
            return web.json_response(
                data={"message": f"Cookie file '{cookie_file}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        try:
            _, cookies = load_cookies(cookie_file)
        except ValueError as e:
            LOG.error(f"Failed to load cookies from '{cookie_file}'. '{e!s}'.")
            LOG.exception(e)
            return web.json_response(
                data={"message": "Failed to load cookies. Check logs for more details."},
                status=web.HTTPInternalServerError.status_code,
            )

        url = c_request.get("url", "https://www.youtube.com/paid_memberships")

        try:
            opts = {}
            if c_request.get("proxy"):
                opts["proxy"] = c_request.get("proxy")

            try:
                c_status = c_request.get("status", [200])
                if isinstance(c_status, int):
                    c_status = [c_status]
                if not isinstance(c_status, list):
                    c_status = [200]
            except Exception:
                c_status = [200]

            async with httpx.AsyncClient(**opts) as client:
                if "user-agent" in client.headers:
                    client.headers.pop("user-agent")

                LOG.info(f"Checking '{url}' to validate if cookies are valid.")
                response = await client.request(
                    method=c_request.get("method", "GET"),
                    url=url,
                    data=c_request.get("data", None),
                    json=c_request.get("json", None),
                    params=c_request.get("params", None),
                    headers=c_request.get("headers", None),
                    cookies=cookies,
                    follow_redirects=bool(c_request.get("follow_redirects", False)),
                )

                valid = response.status_code in c_status

                return web.json_response(
                    data={"message": "Authenticated." if valid else "Not authenticated."},
                    status=web.HTTPOk.status_code if valid else web.HTTPUnauthorized.status_code,
                )
        except Exception as e:
            LOG.error(f"Failed to request '{url}'. '{e!s}'.")
            LOG.exception(e)
            return web.json_response(
                data={"message": "Failed to check cookies status. Check logs for more details."},
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
        data = message("test", "This is a test notification.")

        await self._notify.emit(Events.TEST, data=data)

        return web.json_response(data=data, status=web.HTTPOk.status_code, dumps=self.encoder.encode)

    @route("GET", "api/file/browser/{path:.*}")
    async def file_browser(self, request: Request) -> Response:
        """
        Get the file browser.

        Args:
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        if not self.config.browser_enabled:
            return web.json_response(data={"error": "File browser is disabled."}, status=web.HTTPForbidden.status_code)

        path = request.match_info.get("path")
        path = "/" if not path else unquote_plus(path)

        test = os.path.realpath(os.path.join(self.config.download_path, path))
        if not os.path.exists(test):
            return web.json_response(
                data={"error": f"path '{path}' does not exist."}, status=web.HTTPNotFound.status_code
            )

        try:
            return web.json_response(
                data={
                    "path": path,
                    "contents": get_files(base_path=self.config.download_path, dir=path),
                },
                status=web.HTTPOk.status_code,
                dumps=self.encoder.encode,
            )
        except OSError as e:
            LOG.exception(e)
            return web.json_response(data={"error": str(e)}, status=web.HTTPInternalServerError.status_code)
