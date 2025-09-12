import threading
from typing import Any


class Singleton(type):
    """
    A metaclass that creates a Singleton base class when called.
    """

    _instances: dict[type, Any] = {}
    "The singleton instances."

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

    def _reset_singleton(cls) -> None:
        """
        Clear the singleton instance for the class.
        Useful for testing purposes.
        """
        if cls in cls._instances:
            del cls._instances[cls]


class ThreadSafe(type):
    """
    A metaclass that creates a Singleton base class when called.
    """

    _instances: dict[type, Any] = {}
    "The singleton instances."

    _lock = threading.Lock()
    "A lock to ensure thread-safe singleton creation."

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

    def _reset_singleton(cls) -> None:
        """
        Clear the singleton instance for the class.
        Useful for testing purposes.
        """
        with cls._lock:
            if cls in cls._instances:
                del cls._instances[cls]
