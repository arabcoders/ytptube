import asyncio
import hashlib
import json
import math
import os
import tempfile
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from aiohttp import web
from pydantic import BaseModel, ConfigDict

from app.library.config import Config
from app.library.logging import get_logger
from app.library.Services import Services

from .Scheduler import Scheduler
from .Singleton import ThreadSafe

LOG = get_logger()


class CacheEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True, strict=True)

    value: Any
    expires_at: float | None = None
    persist: bool = False


class Persistence(Protocol):
    def load(self) -> dict[str, CacheEntry]: ...

    def save(self, entries: Mapping[str, CacheEntry]) -> None: ...

    def validate(self, entry: CacheEntry) -> None: ...

    def close(self) -> None: ...


class JsonPersistence(Persistence):
    """Versioned, atomic JSON storage for persistent cache entries."""

    VERSION = 1

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._writable = True

    def load(self) -> dict[str, CacheEntry]:
        self._writable = True
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != self.VERSION:
                if isinstance(data, dict) and isinstance(data.get("version"), int) and data["version"] > self.VERSION:
                    self._writable = False
                    LOG.warning("Ignoring cache file with unsupported version %s.", data["version"])
                else:
                    LOG.warning("Ignoring malformed cache file.")
                return {}
            entries = data.get("entries")
            if not isinstance(entries, dict):
                return {}
            result: dict[str, CacheEntry] = {}
            for key, data in entries.items():
                if not isinstance(key, str) or not isinstance(data, dict) or "value" not in data:
                    continue
                expiry = data.get("expires_at")
                if expiry is not None and (
                    not isinstance(expiry, (int, float)) or isinstance(expiry, bool) or not math.isfinite(expiry)
                ):
                    continue
                try:
                    entry = CacheEntry(
                        value=data["value"], expires_at=float(expiry) if expiry is not None else None, persist=True
                    )
                    self.validate(entry)
                except (TypeError, ValueError, OverflowError, RecursionError):
                    continue
                result[key] = entry
            return result
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            LOG.warning("Unable to read cache file; starting with an empty cache.", exc_info=True)
            return {}

    def save(self, entries: Mapping[str, CacheEntry]) -> None:
        if not self._writable:
            msg = "Cannot overwrite a cache file created by a newer version."
            raise RuntimeError(msg)
        for entry in entries.values():
            self.validate(entry)
        data = {
            "version": self.VERSION,
            "entries": {key: {"value": entry.value, "expires_at": entry.expires_at} for key, entry in entries.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as file:
                temporary = file.name
                json.dump(data, file, allow_nan=False, separators=(",", ":"))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    def validate(self, entry: CacheEntry) -> None:
        msg = "JSON persistence requires JSON-compatible cache values."
        try:
            encoded = json.dumps(entry.value, allow_nan=False)
            decoded = json.loads(encoded)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise TypeError(msg) from exc
        if decoded != entry.value or (entry.expires_at is not None and not math.isfinite(entry.expires_at)):
            raise TypeError(msg)

    def close(self) -> None:
        pass


class Cache(metaclass=ThreadSafe):
    def __init__(self, persistence: Persistence | None = None) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._persistence = persistence
        self._dirty = False
        self._generation = 0
        self._attached = False

    @staticmethod
    def get_instance() -> "Cache":
        return Cache()

    def attach(self, app: web.Application) -> None:
        if not self._attached:
            persistence = self._get_persistence()
            try:
                loaded = persistence.load()
                now = time.time()
                with self._lock:
                    changed_snapshot = False
                    for key, entry in loaded.items():
                        if entry.expires_at is None or now < entry.expires_at:
                            if key not in self._cache:
                                self._cache[key] = entry.model_copy(update={"persist": True})
                            else:
                                changed_snapshot = True
                        else:
                            changed_snapshot = True
                    if changed_snapshot:
                        self._changed_locked()
            except Exception:
                LOG.warning("Unable to restore persistent cache.", exc_info=True)
            app.on_shutdown.append(self.on_shutdown)
            self._attached = True

        Services.get_instance().add("cache", self)
        Scheduler.get_instance().add(
            timer="* * * * *", func=self.cleanup, id=f"{type(self).__name__}.{type(self).cleanup.__name__}"
        )

    async def on_shutdown(self, _: web.Application | None = None) -> None:
        await self.flush()
        if self._persistence is not None:
            try:
                await asyncio.to_thread(self._persistence.close)
            except Exception:
                LOG.warning("Unable to close cache persistence.", exc_info=True)

    def set(self, key: str, value: Any, ttl: float | None = None, *, persist: bool = False) -> None:
        entry = CacheEntry(value=value, expires_at=None if ttl is None else time.time() + ttl, persist=persist)
        if persist:
            self._get_persistence().validate(entry)
        with self._lock:
            previous = self._cache.get(key)
            was_persistent = previous.persist if previous is not None else False
            self._cache[key] = entry
            if was_persistent != persist or persist:
                self._changed_locked()

    def get(self, key: str, default: Any | None = None) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return default
            if entry.expires_at is not None and time.time() >= entry.expires_at:
                self._remove_locked(key)
                return default
            return entry.value

    def ttl(self, key: str) -> float | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.expires_at is not None and time.time() >= entry.expires_at:
                self._remove_locked(key)
                return None
            return None if entry.expires_at is None else entry.expires_at - time.time()

    def has(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.expires_at is not None and time.time() >= entry.expires_at:
                self._remove_locked(key)
                return False
            return True

    def delete(self, key: str) -> None:
        with self._lock:
            self._remove_locked(key)

    def clear(self) -> None:
        with self._lock:
            if any(entry.persist for entry in self._cache.values()):
                self._changed_locked()
            self._cache.clear()

    def hash(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    async def aset(self, key: str, value: Any, ttl: float | None = None, *, persist: bool = False) -> None:
        self.set(key, value, ttl, persist=persist)

    async def aget(self, key: str, default: Any | None = None) -> Any | None:
        return self.get(key, default)

    async def attl(self, key: str) -> float | None:
        return self.ttl(key)

    async def ahas(self, key: str) -> bool:
        return self.has(key)

    async def adelete(self, key: str) -> None:
        self.delete(key)

    async def aclear(self) -> None:
        self.clear()

    async def ahash(self, key: str) -> str:
        return self.hash(key)

    async def cleanup(self) -> None:
        with self._lock:
            now = time.time()
            expired = [
                key for key, entry in self._cache.items() if entry.expires_at is not None and now >= entry.expires_at
            ]
            for key in expired:
                self._remove_locked(key)
            if expired:
                LOG.debug("Cleaned up %s expired cache entries.", len(expired), extra={"expired_count": len(expired)})
        await self.flush()

    async def flush(self) -> None:
        await asyncio.to_thread(self._flush)

    def _flush(self) -> None:
        with self._flush_lock:
            with self._lock:
                if not self._dirty or self._persistence is None:
                    return
                generation = self._generation
                entries = {key: entry for key, entry in self._cache.items() if entry.persist}
            try:
                self._persistence.save(entries)
            except Exception:
                LOG.warning("Unable to persist cache.", exc_info=True)
                return
            with self._lock:
                if self._generation == generation:
                    self._dirty = False

    def _changed_locked(self) -> None:
        self._dirty = True
        self._generation += 1

    def _remove_locked(self, key: str) -> None:
        entry = self._cache.pop(key, None)
        if entry is not None and entry.persist:
            self._changed_locked()

    def _get_persistence(self) -> Persistence:
        if self._persistence is None:
            self._persistence = JsonPersistence(Path(Config.get_instance().config_path) / "cache.json")
        return self._persistence
