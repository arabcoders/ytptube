import logging
import re
from collections.abc import Awaitable
from functools import wraps

LOG: logging.Logger = logging.getLogger(__name__)


class Route:
    """
    A class to represent an HTTP route.

    Attributes:
        method (str): The HTTP method (GET, POST, etc.).
        path (str): The path for the route.
        name (str): The name of the route.
        handler (Awaitable): The function that handles the route.

    """

    def __init__(self, method: str, path: str, name: str, handler: Awaitable):
        self.method = method.upper()
        self.path = path
        self.name = name
        self.handler: Awaitable = handler


ROUTES: dict[str, Route] = {}


def make_route_name(method: str, path: str) -> str:
    method = method.lower()
    path = path.strip("/")

    segments = []
    for part in path.split("/"):
        part = re.sub(r"[^\w]", "_", part)  # remove invalid chars
        if not part:
            part = "part"
        elif part[0].isdigit():
            part = f"p_{part}"
        segments.append(part)

    return f"{method}:" + ".".join(segments or ["root"])


def route(method: str, path: str, name: str | None = None, **kwargs) -> Awaitable:
    """
    Decorator to mark a method as an HTTP route handler.

    Args:
        method (str): The HTTP method.
        path (str): The path to the route.
        name (str): The name of the route.
        kwargs: Additional keyword arguments.

    Returns:
        Awaitable: The decorated function.

    """
    if not name:
        name = make_route_name(method, path)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        ROUTES[name] = Route(method=method.upper(), path=path, name=name, handler=wrapper)
        if path.endswith("/") and "/" != path and not kwargs.get("no_slash", False):
            ROUTES[f"{name}_no_slash"] = Route(
                method=method.upper(), path=path[:-1], name=f"{name}_no_slash", handler=wrapper
            )

        return wrapper

    return decorator


def add_route(method: str, path: str, handler: Awaitable, name: str | None = None, **kwargs):
    """
    Decorator to mark a method as an HTTP route handler.

    Args:
        method (str): The HTTP method.
        path (str): The path to the route.
        name (str): The name of the route.
        handler (Awaitable): The function that handles the route.
        kwargs: Additional keyword arguments.

    """
    if not name:
        name = make_route_name(method, path)

    ROUTES[name] = Route(method=method.upper(), path=path, name=name, handler=handler)
    if path.endswith("/") and "/" != path and not kwargs.get("no_slash", False):
        ROUTES[f"{name}_no_slash"] = Route(
            method=method.upper(), path=path[:-1], name=f"{name}_no_slash", handler=handler
        )


def get_route(name: str) -> dict[str, Route] | None:
    """
    Get the route information by name.

    Args:
        name (str): The name of the route.

    Returns:
        dict: The route information, or None if not found.

    """
    return ROUTES.get(name)


def get_routes() -> dict[str, Route]:
    """
    Get all registered routes.

    Returns:
        dict[str, dict]: A dictionary of all registered routes.

    """
    return ROUTES
