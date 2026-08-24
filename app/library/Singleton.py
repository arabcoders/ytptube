import threading
from typing import Any


class Singleton(type):
    _instances: dict[type, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

    def _reset_singleton(cls) -> None:
        if cls in cls._instances:
            del cls._instances[cls]


class ThreadSafe(type):
    _instances: dict[type, Any] = {}

    _lock = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

    def _reset_singleton(cls) -> None:
        with cls._lock:
            if cls in cls._instances:
                del cls._instances[cls]
