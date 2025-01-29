import hashlib
import threading
import time
from typing import Any

from .Singleton import ThreadSafe


class Cache(metaclass=ThreadSafe):
    def __init__(self) -> None:
        """
        Initialize the Cache.
        """
        # Prevent reinitialization in singleton context.
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._cache: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.Lock()
        self._initialized = True

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """
        Synchronously set a value in the cache with an optional time-to-live.
        If ttl is None, the entry never expires.
        """
        expire_at = None if ttl is None else time.time() + ttl
        with self._lock:
            self._cache[key] = (value, expire_at)

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """
        Synchronously retrieve a value from the cache if it exists and hasn't expired.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return default

            value, expire_at = entry
            if expire_at is not None and time.time() >= expire_at:
                del self._cache[key]
                return default
            return value

    def has(self, key: str) -> bool:
        """
        Synchronously check if a key exists in the cache and hasn't expired.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False

            _, expire_at = entry
            if expire_at is not None and time.time() >= expire_at:
                del self._cache[key]
                return False
            return True

    def delete(self, key: str) -> None:
        """
        Synchronously remove a key from the cache if it exists.
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """
        Synchronously clear all items from the cache.
        """
        with self._lock:
            self._cache.clear()

    def hash(self, key: str) -> str:
        """
        Generate a SHA-256 hash for the given input string.

        :param key (str): The string to hash.
        :return: A hexadecimal SHA-256 hash of the input string.
        """
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    # Asynchronous counterparts for non-blocking interfaces
    async def aset(self, key: str, value: Any, ttl: float | None = None) -> None:
        """
        Asynchronously set a value in the cache.
        """
        self.set(key, value, ttl)

    async def aget(self, key: str, default: Any | None = None) -> Any | None:
        """
        Asynchronously retrieve a value from the cache.
        """
        return self.get(key, default)

    async def ahas(self, key: str) -> bool:
        """
        Asynchronously check if a key exists in the cache.
        """
        return self.has(key)

    async def adelete(self, key: str) -> None:
        """
        Asynchronously remove a key from the cache.
        """
        self.delete(key)

    async def aclear(self) -> None:
        """
        Asynchronously clear all items from the cache.
        """
        self.clear()

    async def ahash(self, key: str) -> str:
        """
        Asynchronously generate a SHA-256 hash for the given input string.
        """
        return self.hash(key=key)
