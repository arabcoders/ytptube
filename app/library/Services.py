import inspect
import logging
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar, get_args, get_origin, get_type_hints

from app.library.Singleton import Singleton

T = TypeVar("T")
LOG: logging.Logger = logging.getLogger(__name__)


def _unwrap_annotation(ann: Any) -> Any:
    if ann is inspect._empty:
        return inspect._empty

    origin = get_origin(ann)

    # Annotated[T, ...] -> T
    if origin is Annotated:
        args = get_args(ann)
        return args[0] if args else ann

    # Optional[T] / Union[T, None] / T | None -> T
    if origin is None:
        return ann

    if str(origin) in ("typing.Union", "types.UnionType"):
        args = [a for a in get_args(ann) if a is not type(None)]
        if len(args) == 1:
            return args[0]
        return ann

    return ann


@dataclass(frozen=True)
class ServiceEntry:
    name: str
    declared_type: type | None
    instance: Any


class Services(metaclass=Singleton):
    def __init__(self):
        self._services: list[ServiceEntry] = []

    @staticmethod
    def get_instance() -> "Services":
        return Services()

    def add(self, name: str, service: Any, declared_type: type | None = None) -> "Services":
        """
        Add a service by name.

        Args:
            name: The name of the service.
            service: The service instance.
            declared_type: The declared type of the service (optional).

        Returns:
            Services: The Services instance (for chaining).

        """
        if declared_type is None and service is not None:
            declared_type = type(service)

        self.remove(name)
        self._services.append(ServiceEntry(name=name, declared_type=declared_type, instance=service))
        return self

    def add_all(self, services: dict[str, Any]):
        for name, svc in services.items():
            self.add(name, svc)

    def remove(self, name: str):
        self._services = [e for e in self._services if e.name != name]

    def clear(self):
        self._services.clear()

    def get(self, name: str) -> Any | None:
        for e in reversed(self._services):
            if e.name == name:
                return e.instance
        return None

    def has(self, name: str) -> bool:
        return any(e.name == name for e in self._services)

    def get_all(self) -> list[ServiceEntry]:
        return self._services.copy()

    def get_by_type(self, expected_type: Any) -> Any | None:
        expected_type = _unwrap_annotation(expected_type)
        if expected_type is inspect._empty or not isinstance(expected_type, type):
            return None

        exact: list[Any] = [e.instance for e in self._services if e.declared_type is expected_type]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            msg: str = (
                f"Ambiguous dependency for type {expected_type.__name__}: {len(exact)} exact matches. Resolve by name."
            )
            raise LookupError(msg)

        candidates: list[Any] = [e.instance for e in self._services if isinstance(e.instance, expected_type)]
        if len(candidates) == 0:
            return None

        if len(candidates) > 1:
            msg: str = (
                f"Ambiguous dependency for type {expected_type.__name__}: "
                f"{len(candidates)} candidates. Resolve by name."
            )
            raise LookupError(msg)

        return candidates[0]

    def _build_call_args(self, handler: callable, overrides: dict[str, Any]) -> dict[str, Any]:
        sig: inspect.Signature = inspect.signature(handler)

        try:
            type_hints: dict[str, Any] = get_type_hints(handler)
        except Exception:
            type_hints = {}

        resolved: dict[str, Any] = {}

        for name, param in sig.parameters.items():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            if name in overrides:
                resolved[name] = overrides[name]
                continue

            by_name: Any | None = self.get(name)
            if by_name is not None:
                resolved[name] = by_name
                continue

            ann: Any | None = type_hints.get(name, param.annotation)
            by_type: Any | None = self.get_by_type(ann)
            if by_type is not None:
                resolved[name] = by_type
                continue

            if param.default is not inspect._empty:
                continue

        missing_required: list[str] = []
        for name, param in sig.parameters.items():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue

            if param.default is not inspect._empty:
                continue

            if name not in resolved:
                missing_required.append(name)

        if missing_required:
            LOG.error(
                "Missing arguments for handler '%s': %s",
                getattr(handler, "__name__", str(handler)),
                missing_required,
            )

        return resolved

    async def handle_async(self, handler: callable, **kwargs) -> Any:
        resolved: dict[str, Any] = self._build_call_args(handler, kwargs)
        return await handler(**resolved)

    def handle_sync(self, handler: callable, **kwargs) -> Any:
        resolved: dict[str, Any] = self._build_call_args(handler, kwargs)
        return handler(**resolved)
