import base64
import hmac
import inspect
import logging
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
from aiohttp import web
from aiohttp.web import Request, RequestHandler, Response

from app.library.Services import Services

from .cache import Cache
from .config import Config
from .DownloadQueue import DownloadQueue
from .encoder import Encoder
from .Events import EventBus
from .ffprobe import ffprobe
from .router import RouteType, get_routes
from .Utils import decrypt_data, encrypt_data, get_file, get_mime_type, load_modules

LOG: logging.Logger = logging.getLogger("http_api")


class HttpAPI:
    def __init__(self, root_path: Path, queue: DownloadQueue):
        self.queue: DownloadQueue = queue or DownloadQueue.get_instance()
        self.encoder: Encoder = Encoder()
        self.config: Config = Config.get_instance()
        self._notify: EventBus = EventBus.get_instance()
        self.rootPath: Path = root_path
        self.cache = Cache()
        self.app: web.Application | None = None

        services = Services.get_instance()
        services.add_all(
            {
                k: v
                for k, v in {
                    "queue": self.queue,
                    "encoder": self.encoder,
                    "config": self.config,
                    "notify": self._notify,
                    "cache": self.cache,
                    "http_api": self,
                    "root_path": self.rootPath,
                }.items()
                if not services.has(k)
            }
        )

    async def on_shutdown(self, _: web.Application):
        pass

    def attach(self, app: web.Application):
        """
        Attach the routes to the application.

        Args:
            app (web.Application): The application to attach the routes to.

        Returns:
            HttpAPI: The instance of the HttpAPI.

        """
        self.app = app

        app.middlewares.append(
            HttpAPI.middle_wares(
                app=app,
                base_path=self.config.base_path.rstrip("/"),
                download_path=self.config.download_path,
            )
        )

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

    def add_routes(self, app: web.Application) -> None:
        """
        Add the routes to the application.

        Args:
            app (web.Application): The application to attach the routes to.

        Returns:
            HttpAPI: The instance of the HttpAPI.

        """
        registered_options: list = []

        base_path: str = self.config.base_path.rstrip("/")
        from app.routes.api._static import preload_static

        load_modules(self.rootPath, self.rootPath / "routes" / "api")
        preload_static(self.rootPath, self.config)

        async def options_handler(_: Request) -> Response:
            return web.Response(status=204)

        def _handle(handler):
            async def wrapped(request):
                return await self._handle(handler, request)

            return wrapped

        for route in get_routes(RouteType.HTTP).values():
            routePath: str = f"/{route.path.lstrip('/')}"

            if route.path in (self.config.base_path, "/"):
                pass
            elif "" == base_path or not routePath.rstrip("/").startswith(base_path.rstrip("/")):
                route.path = f"{base_path}/{route.path.lstrip('/')}"

            if self.config.debug:
                LOG.debug(f"Add ({route.name}) {route.method}: {route.path}.")

            app.router.add_route(route.method, route.path, handler=_handle(route.handler), name=route.name)

            if route.path in registered_options:
                continue

            app.router.add_route("OPTIONS", route.path, handler=options_handler, name=f"{route.name}_opts")
            registered_options.append(route.path)

        app.router.add_static(f"{base_path}/api/download/", self.config.download_path, name="download_static")

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
        async def auth_handler(request: Request, handler: RequestHandler) -> Response:
            # if OPTIONS request, skip auth
            if "OPTIONS" == request.method:
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
                    data={"error": "Unauthorized (Invalid credentials)."},
                    status=web.HTTPUnauthorized.status_code,
                    headers={
                        "WWW-Authenticate": 'Basic realm="Authorization Required."',
                    },
                )

            response: Response = await handler(request)

            contentType: str | None = response.headers.get("content-type", None)
            if contentType and not contentType.startswith("text/html"):
                return response

            try:
                response.set_cookie(
                    "auth",
                    encrypt_data(
                        f"{user_name}:{user_password}",
                        key=Config.get_instance().secret_key,
                    ),
                    max_age=60 * 60 * 24 * 7,
                    expires=(datetime.now(UTC) + timedelta(days=7)).strftime("%a, %d %b %Y %H:%M:%S GMT"),
                    httponly=True,
                    samesite="Strict",
                )
            except Exception as e:
                LOG.exception(e)

            return response

        return auth_handler

    @staticmethod
    def middle_wares(app: web.Application, base_path: str, download_path: str) -> Awaitable:
        @web.middleware
        async def middleware_handler(request: Request, handler: RequestHandler) -> Response:
            static_path = str(app.router["download_static"].url_for(filename=""))
            if request.path.startswith(static_path):
                realFile, status = get_file(
                    download_path=download_path,
                    file=request.path.replace(static_path, ""),
                )
                if web.HTTPFound.status_code == status:
                    return Response(
                        status=status,
                        headers={
                            "Location": str(
                                app.router["download_static"].url_for(
                                    filename=str(realFile).replace(download_path, "").strip("/")
                                )
                            )
                        },
                    )

            response: Response = await handler(request)

            contentType: str | None = response.headers.get("content-type", None)
            if contentType and contentType.startswith("text/html"):
                rewrite_path: str = base_path.rstrip("/")
                async with await anyio.open_file(response._path, "rb") as f:
                    content = await f.read()
                    content: str = (
                        content.decode("utf-8")
                        .replace('<base href="/">', f'<base href="{rewrite_path}/">')
                        .replace("/_base_path/", f"{rewrite_path}/")
                    )

                new_response = web.Response(text=content, content_type="text/html")

                for k, v in response.headers.items():
                    if k.lower() != "content-type":
                        new_response.headers[k] = v

                for morsel in response.cookies.values():
                    new_response.set_cookie(
                        morsel.key,
                        morsel.value,
                        expires=morsel["expires"],
                        domain=morsel["domain"],
                        max_age=morsel["max-age"],
                        path=morsel["path"],
                        secure=bool(morsel["secure"]),
                        httponly=bool(morsel["httponly"]),
                        samesite=morsel["samesite"] or None,
                    )

                return new_response

            if request.path.startswith(static_path) and isinstance(response, web.FileResponse):
                try:
                    ff_info = await ffprobe(response._path)
                    mime_type = get_mime_type(ff_info.get("metadata", {}), response._path)
                    response.content_type = mime_type
                except Exception:
                    pass

            return response

        return middleware_handler

    async def _handle(self, handler: RequestHandler, request: Request) -> Response:
        """
        Call the handler with the request and return the response.

        Args:
            handler (RequestHandler): The handler to call.
            request (Request): The request object.

        Returns:
            Response: The response object.

        """
        try:
            sig = inspect.signature(handler)
            expected_args = sig.parameters.keys()

            try:
                if 1 == len(expected_args) and "request" in expected_args:
                    response = await handler(request)
                else:
                    response = await Services.get_instance().handle_async(handler, request=request)
            except TypeError as te:
                LOG.exception(te)
                if "missing 1 required positional argument" in str(te) and "request" in str(te):
                    response = await handler(request)
                else:
                    raise
        except web.HTTPException as e:
            return web.json_response(data={"error": str(e)}, status=e.status_code)
        except Exception as e:
            LOG.exception(e)
            response = web.json_response(
                data={"error": "Internal Server Error"},
                status=web.HTTPInternalServerError.status_code,
            )

        return response
