import logging
import re
from collections.abc import Awaitable, Callable
from enum import Enum
from functools import wraps
from typing import Any

LOG: logging.Logger = logging.getLogger(__name__)


# make a enum for route types
class RouteType(str, Enum):
    HTTP = "http"
    SOCKET = "socket"

    @classmethod
    def all(cls) -> list[str]:
        return [member.value for member in cls]


class Route:
    """
    A class to represent an route.

    Attributes:
        method (str): The HTTP method (GET, POST, etc.).
        path (str): The path for the route.
        name (str): The name of the route.
        handler (Callable[..., Awaitable]): The function that handles the route.

    """

    def __init__(self, method: str, path: str, name: str, handler: Callable[..., Awaitable[Any]]):
        self.method: str = method.upper()
        self.path: str = path
        self.name: str = name
        self.handler: Callable[..., Awaitable[Any]] = handler


ROUTES: dict[str, dict[str, Route]] = {}


def make_route_name(method: str, path: str) -> str:
    method = method.lower()
    path = path.strip("/")

    segments: list = []
    for part in path.split("/"):
        part = re.sub(r"[^\w]", "_", part)  # remove invalid chars
        if not part:
            part = "part"
        elif part[0].isdigit():
            part = f"p_{part}"
        segments.append(part)

    return f"{method}:" + ".".join(segments or ["root"])


def route(
    method: RouteType | str | list[str],
    path: str,
    name: str | None = None,
    **kwargs,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    Decorator to mark a method as an HTTP route handler.

    Args:
        method (RouteType|str|list[str]): The HTTP method(s).
        path (str): The path to the route.
        name (str): The name of the route.
        kwargs: Additional keyword arguments.

    Returns:
        Awaitable: The decorated function.

    """
    methods = [method] if isinstance(method, (str, RouteType)) else method

    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        for m in methods:
            route_name = name if name else make_route_name(m, path)
            route_type: str = RouteType.SOCKET if RouteType.SOCKET == m else RouteType.HTTP

            if route_type not in ROUTES:
                ROUTES[route_type] = {}

            if route_name in ROUTES.get(route_type, {}):
                route_name = f"{route_name}_{len(ROUTES[route_type]) + 1}"

            ROUTES[route_type][route_name] = Route(method=m.upper(), path=path, name=route_name, handler=wrapper)
            if "http" == route_type and path.endswith("/") and "/" != path and not kwargs.get("no_slash", False):
                ROUTES[route_type][f"{route_name}_no_slash"] = Route(
                    method=m.upper(), path=path[:-1], name=f"{route_name}_no_slash", handler=wrapper
                )

        return wrapper

    return decorator


def add_route(
    method: RouteType | str | list[str],
    path: str,
    handler: Callable[..., Awaitable[Any]],
    name: str | None = None,
    **kwargs,
):
    """
    Decorator to mark a method as an HTTP route handler.

    Args:
        method (RouteType|str|list[str]): The HTTP method(s).
        path (str): The path to the route.
        name (str): The name of the route.
        handler (Awaitable): The function that handles the route.
        kwargs: Additional keyword arguments.

    """
    methods = [method] if isinstance(method, (str, RouteType)) else method

    for m in methods:
        route_name = name if name else make_route_name(m, path)
        route_type: str = RouteType.SOCKET if RouteType.SOCKET == m else RouteType.HTTP

        if route_type not in ROUTES:
            ROUTES[route_type] = {}

        if route_name in ROUTES.get(route_type, {}):
            route_name = f"{route_name}_{len(ROUTES[route_type]) + 1}"

        ROUTES[route_type][route_name] = Route(method=m.upper(), path=path, name=route_name, handler=handler)

        if "http" == route_type and path.endswith("/") and "/" != path and not kwargs.get("no_slash", False):
            ROUTES[route_type][f"{route_name}_no_slash"] = Route(
                method=m.upper(), path=path[:-1], name=f"{route_name}_no_slash", handler=handler
            )


def get_route(route_type: RouteType, name: str) -> Route | None:
    """
    Get the route information by name.

    Args:
        route_type (RouteType): The type of the route (e.g., RouteType.HTTP, RouteType.SOCKET).
        name (str): The name of the route.

    Returns:
        dict: The route information, or None if not found.

    """
    return ROUTES.get(route_type, {}).get(name, None)


def get_routes(route_type: RouteType) -> dict[str, Route]:
    """
    Get all registered routes.

    Args:
        route_type (RouteType): The type of the route (e.g., RouteType.HTTP, RouteType.SOCKET).

    Returns:
        dict[str, dict]: A dictionary of all registered routes.

    """
    return ROUTES.get(route_type, {})
