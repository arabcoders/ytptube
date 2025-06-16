import inspect
from typing import Any, TypeVar

from app.library.Singleton import Singleton

T = TypeVar("T")


class Services(metaclass=Singleton):
    _dct: dict[str, T] = {}

    _instance = None
    """The instance of the class."""

    @staticmethod
    def get_instance() -> "Services":
        if Services._instance is None:
            Services._instance = Services()

        return Services._instance

    def add(self, name: str, service: T):
        self._dct[name] = service

    def add_all(self, services: dict[str, T]):
        for name, service in services.items():
            self.add(name, service)

    def get(self, name: str) -> T | None:
        return self._dct.get(name)

    def has(self, name: str) -> bool:
        return name in self._dct

    def remove(self, name: str):
        if name not in self._dct:
            return

        self._dct.pop(name, None)

    def clear(self):
        self._dct.clear()

    def get_all(self) -> dict[str, T]:
        return self._dct.copy()

    async def handle_async(self, handler: callable, **kwargs) -> Any:
        context = {**self.get_all(), **kwargs}

        sig = inspect.signature(handler)
        expected_args = sig.parameters.keys()
        filtered = {k: v for k, v in context.items() if k in expected_args}
        return await handler(**filtered)

    def handle_sync(self, handler: callable, **kwargs) -> Any:
        context = {**self.get_all(), **kwargs}

        sig = inspect.signature(handler)
        expected_args = sig.parameters.keys()
        filtered = {k: v for k, v in context.items() if k in expected_args}
        return handler(**filtered)
