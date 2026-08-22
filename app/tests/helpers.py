from __future__ import annotations

import atexit
import contextlib
import shutil
from contextvars import ContextVar
from pathlib import Path
from tempfile import gettempdir
from typing import TYPE_CHECKING
from uuid import uuid4

from aiohttp import web

from app.library.router import ROUTES, RouteType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator, Mapping
    from typing import Any

    from yarl import URL

    Handler = Callable[..., Awaitable[Any]]

_TMP_BASE = Path(gettempdir()) / "tests-ytptube"
_TMP_PER_RUN = _TMP_BASE / uuid4().hex
_TMP_RUNTIME = _TMP_PER_RUN / "tmp"
_CURRENT_TEST_APP: ContextVar[web.Application | None] = ContextVar("current_test_app", default=None)


def _slugify(name: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in name).strip("-") or "tmp"


def get_test_run_root() -> Path:
    _TMP_BASE.mkdir(parents=True, exist_ok=True)
    return _TMP_BASE


def get_test_per_run_root() -> Path:
    _TMP_PER_RUN.mkdir(parents=True, exist_ok=True)
    return _TMP_PER_RUN


def get_test_system_temp_root() -> Path:
    _TMP_RUNTIME.mkdir(parents=True, exist_ok=True)
    return _TMP_RUNTIME


def cleanup_test_run_root() -> None:
    if _TMP_PER_RUN.exists():
        shutil.rmtree(_TMP_PER_RUN, ignore_errors=True)


def make_in_memory_db_path(name: str) -> str:
    """Return a unique named in-memory SQLite path for test isolation."""
    slug = _slugify(name)
    return f":memory:{slug}-{uuid4().hex}"


def make_test_disk_path(*parts: str) -> Path:
    """Return a per-run temp path for tests that must write to disk."""
    _TMP_PER_RUN.mkdir(parents=True, exist_ok=True)
    path = _TMP_PER_RUN.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def make_test_temp_dir(name: str) -> Path:
    path = make_test_disk_path(f"{_slugify(name)}-{uuid4().hex}")
    path.mkdir(parents=True, exist_ok=False)
    return path


@contextlib.contextmanager
def temporary_test_dir(name: str) -> Generator[Path]:
    path = make_test_temp_dir(name)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_test_app(handlers: Mapping[str, Handler] | None = None) -> web.Application:
    """Build an aiohttp app from the currently registered production routes."""
    app = web.Application()
    handlers = {} if handlers is None else handlers
    routes = ROUTES.get(RouteType.HTTP, {})
    unknown = set(handlers) - routes.keys()
    if unknown:
        message = f"Unknown test route(s): {', '.join(sorted(unknown))}"
        raise ValueError(message)

    for name, route in routes.items():
        handler = handlers.get(name, route.handler)
        path = route.path if route.path.startswith("/") else f"/{route.path}"
        app.router.add_route(route.method, path, handler, name=name)

    return app


def url_for(
    name: str,
    /,
    *,
    app: web.Application | None = None,
    query: Mapping[str, Any] | None = None,
    **path_params: Any,
) -> URL:
    """Resolve a test route by name, optionally adding path and query parameters."""
    app = app or _CURRENT_TEST_APP.get()
    if app is None:
        message = "No test app is active; pass app= or create a test client first"
        raise RuntimeError(message)

    try:
        route = app.router[name]
    except KeyError as exc:
        message = f"Unknown test route: {name}"
        raise KeyError(message) from exc

    result = route.url_for(**path_params)
    return result.with_query(query) if query else result


def set_current_test_app(app: web.Application) -> web.Application | None:
    previous = _CURRENT_TEST_APP.get()
    _CURRENT_TEST_APP.set(app)
    return previous


def reset_current_test_app(previous: web.Application | None) -> None:
    _CURRENT_TEST_APP.set(previous)


atexit.register(cleanup_test_run_root)
