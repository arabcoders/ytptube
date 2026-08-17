import inspect
import re
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import anyio
from aiohttp import web
from aiohttp.typedefs import Handler, Middleware
from aiohttp.web import Request, Response
from aiohttp.web_log import AccessLogger
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import StreamResponse

from app.features.auth.middleware import auth_middleware, cors_headers
from app.features.auth.service import AuthService
from app.features.core.utils import api_error_response
from app.library.log import get_logger
from app.library.Services import Services

from .cache import Cache
from .config import Config
from .encoder import Encoder
from .Events import EventBus
from .router import RouteType, get_routes
from .Utils import get_file, load_modules

LOG = get_logger("http")

_REQUEST_LINE: re.Pattern[str] = re.compile(r"^(?P<prefix>\S+\s+)(?P<target>\S+)(?P<suffix>\s+HTTP/\d+(?:\.\d+)?)$")
_SENSITIVE_QUERY: set[str] = {"apikey", "ticket"}


_HTTP_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "BAD_REQUEST",
    405: "BAD_REQUEST",
    409: "ALREADY_EXISTS",
    500: "INTERNAL_ERROR",
    501: "INTERNAL_ERROR",
    502: "INTERNAL_ERROR",
    503: "INTERNAL_ERROR",
    504: "TIMEOUT",
}


def _http_status_to_code(status: int) -> str:
    return _HTTP_STATUS_CODES.get(status, "INTERNAL_ERROR")


def redact_url(value: str) -> str:
    match: re.Match[str] | None = _REQUEST_LINE.match(value)
    target: str | Any = match.group("target") if match else value
    try:
        parsed = urlsplit(target)
    except ValueError:
        return "[INVALID URL]"
    query: list[tuple[str, str]] = parse_qsl(parsed.query, keep_blank_values=True)
    if not any(name.lower() in _SENSITIVE_QUERY for name, _ in query):
        return value
    redacted: str = urlencode(
        [(name, "[REDACTED]" if name.lower() in _SENSITIVE_QUERY else item) for name, item in query], safe="[]"
    )
    target = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, redacted, parsed.fragment))
    return f"{match.group('prefix')}{target}{match.group('suffix')}" if match else target


class HttpAccessLogger(AccessLogger):
    def log(self, request: BaseRequest, response: StreamResponse, time: float) -> None:
        try:
            fmt_info = self._format_line(request, response, time)

            values: list[object] = []
            extra: dict[str, Any] = {"elapsed_ms": round(time * 1000.0, 2)}
            for key, value in fmt_info:
                if isinstance(value, str) and key in {"first_request_line", ("request_header", "Referer")}:
                    value: str = redact_url(value)
                values.append(value)

                if isinstance(key, str):
                    extra[key] = value
                else:
                    parent, child = key
                    group: dict[str, Any] = extra.get(parent, {})  # type: ignore[assignment]
                    if not isinstance(group, dict):
                        group = {}
                    group[child] = value
                    extra[parent] = group

            message = self._log_format % tuple(values)
            self.logger.info(message, extra=extra)
        except Exception:
            self.logger.exception("Error in logging")


class HttpAPI:
    def __init__(self, root_path: Path):
        self.encoder: Encoder = Encoder()
        self.config: Config = Config.get_instance()
        self._notify: EventBus = EventBus.get_instance()
        self.rootPath: Path = root_path
        self.cache: Cache = Cache.get_instance()
        self.app: web.Application | None = None

        services: Services = Services.get_instance()
        services.add_all(
            {
                k: v
                for k, v in {
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

        app.middlewares.append(auth_middleware(AuthService.get_instance(), self.config))

        app.middlewares.append(
            HttpAPI.middle_wares(
                app=app,
                base_path=self.config.base_path.rstrip("/"),
                download_path=self.config.download_path,
            )
        )

        self.add_routes(app)

        async def on_prepare(request: Request, response: StreamResponse):
            if "Server" in response.headers:
                del response.headers["Server"]

            response.headers.update(cors_headers(request, self.config))

        try:
            app.on_response_prepare.append(on_prepare)
        except Exception as e:
            LOG.exception(
                "Failed to register response preparation middleware.",
                extra={"operation": "register_on_response_prepare", "exception_type": type(e).__name__},
            )

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
        from app.routes.api._static import setup_static_routes

        load_modules(self.rootPath, self.rootPath / "routes" / "api")
        setup_static_routes(self.rootPath, self.config)

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
                LOG.debug(
                    "Adding route '%s' %s: %s.",
                    route.name,
                    route.method,
                    route.path,
                    extra={"route_name": route.name, "method": route.method, "path": route.path},
                )

            app.router.add_route(route.method, route.path, handler=_handle(route.handler), name=route.name)

            if route.path in registered_options:
                continue

            app.router.add_route("OPTIONS", route.path, handler=options_handler, name=f"{route.name}_opts")
            registered_options.append(route.path)

    @staticmethod
    def middle_wares(app: web.Application, base_path: str, download_path: str) -> Middleware:
        @web.middleware
        async def middleware_handler(request: Request, handler: Handler) -> StreamResponse:
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

            response: StreamResponse = await handler(request)

            contentType: str = str(response.headers.get("content-type", ""))
            if contentType.startswith("text/html") and getattr(response, "_path", None):
                rewrite_path: str = base_path.rstrip("/")
                response_path = cast("Any", response)._path
                async with await anyio.open_file(response_path, "rb") as f:
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
                        expires=morsel.get("expires"),
                        domain=morsel.get("domain"),
                        max_age=morsel.get("max-age"),
                        path=morsel.get("path") or "/",
                        secure=bool(morsel.get("secure")),
                        httponly=bool(morsel.get("httponly")),
                        samesite=morsel.get("samesite") or None,
                    )

                return new_response

            return response

        return middleware_handler

    async def _handle(self, handler: Handler, request: Request) -> StreamResponse:
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
                LOG.exception(
                    "Failed to inject route handler dependencies for '%s'.",
                    getattr(handler, "__name__", handler.__class__.__name__),
                    extra={
                        "handler": getattr(handler, "__name__", handler.__class__.__name__),
                        "route": redact_url(str(request.rel_url)),
                        "method": request.method,
                        "exception_type": type(te).__name__,
                    },
                )
                if "missing 1 required positional argument" in str(te) and "request" in str(te):
                    response = await handler(request)
                else:
                    raise
        except web.HTTPException as e:
            return api_error_response(
                str(e),
                code=_http_status_to_code(e.status_code),
                status=e.status_code,
                detail=str(e),
            )
        except Exception as e:
            LOG.exception(
                "Failed to handle request '%s %s'.",
                request.method,
                redact_url(str(request.rel_url)),
                extra={
                    "route": redact_url(str(request.rel_url)),
                    "method": request.method,
                    "exception_type": type(e).__name__,
                },
            )
            response = api_error_response(
                "Internal Server Error",
                code="INTERNAL_ERROR",
                status=web.HTTPInternalServerError.status_code,
            )

        return response
