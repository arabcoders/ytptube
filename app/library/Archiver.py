import logging
import os
import threading
import time
from pathlib import Path

from app.library.Singleton import ThreadSafe

LOG: logging.Logger = logging.getLogger("Archiver")


class _Entry:
    """
    Internal cache entry for a single archive file.

    Attributes:
        ids (set[str]): Cached IDs contained in the archive file.
        size (int): Last known file size from os.stat.
        mtime (float): Last known modification time from os.stat.
        loaded (bool): Whether the entry has been loaded from disk at least once.

    """

    def __init__(self) -> None:
        self.ids: set[str] = set()
        self.size: int = -1
        self.mtime: float = -1.0
        self.loaded: bool = False


class Archiver(metaclass=ThreadSafe):
    """
    Global archive cache for yt-dlp download archive files.

    Caches IDs per file in memory for fast membership checks. When read stat
    checks are enabled, the cache is refreshed on read if the file's size or
    mtime changed. The add and delete operations write to disk and then update
    the in-memory cache and metadata accordingly.
    """

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._cache: dict[str, _Entry] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._stats_check: bool = False
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "Archiver":
        return cls()

    def _key(self, file: str | Path) -> str:
        """
        Return a normalized absolute path key for the archive file.

        Args:
            file (str|Path): The archive file path.

        Returns:
            str: The absolute, resolved file path to be used as cache key.

        """
        p: Path = Path(file) if not isinstance(file, Path) else file
        return str(p.resolve())

    def _get_lock(self, key: str) -> threading.RLock:
        """
        Get or create a per-file lock.

        Args:
            key (str): The normalized file key as returned by _key().

        Returns:
            threading.RLock: The lock for this key.

        """
        with self._global_lock:
            if key not in self._locks:
                self._locks[key] = threading.RLock()
            return self._locks[key]

    def invalidate(self, file: str | Path) -> None:
        """
        Drop any cached entry for the given archive file.

        Args:
            file (str|Path): The archive file path.

        """
        key: str = self._key(file)
        with self._global_lock:
            self._cache.pop(key, None)

    def _stat(self, key: str) -> os.stat_result | None:
        """
        Safely stat a file path key.

        Args:
            key (str): The normalized file key.

        Returns:
            os.stat_result|None: The stat result, or None on error.

        """
        try:
            return os.stat(key)
        except OSError:
            return None

    def _ensure_loaded(self, key: str) -> _Entry:
        """
        Ensure a cache entry is present and up to date.

        When read stat checks are enabled, the file is reloaded if its size or
        modification time differs from the last cached values. Otherwise the
        existing cache entry is used.

        Args:
            key (str): The normalized file key.

        Returns:
            _Entry: The cache entry for the file.

        """
        entry: _Entry | None = self._cache.get(key)
        if entry and entry.loaded:
            if not self._stats_check:
                return entry

            st: os.stat_result | None = self._stat(key)

            if not st:
                self._cache[key] = _Entry()
                return self._cache[key]

            if entry.size == st.st_size and entry.mtime == st.st_mtime:
                return entry

        lock: threading.RLock = self._get_lock(key)
        with lock:
            entry = self._cache.get(key) or _Entry()
            st = self._stat(key) if self._stats_check else None
            if self._stats_check and not st:
                entry.ids = set()
                entry.size = -1
                entry.mtime = -1
                entry.loaded = True
                self._cache[key] = entry
                return entry

            if self._stats_check and st and entry.loaded and entry.size == st.st_size and entry.mtime == st.st_mtime:
                return entry

            start: float = time.perf_counter()
            ids: set[str] = set()
            try:
                with open(key, encoding="utf-8") as f:
                    for line in f:
                        s = line.strip()
                        if not s or len(s.split()) < 2:
                            continue
                        ids.add(s)
            except OSError as e:
                LOG.error(f"Failed to read archive file '{key}': {e!s}")
                ids = set()

            try:
                elapsed_ms: float = (time.perf_counter() - start) * 1000.0
                LOG.debug(f"_ensure_loaded took {elapsed_ms:.2f}ms (loaded={len(ids)})")
            except Exception:
                pass

            entry.ids = ids
            if st:
                entry.size = st.st_size
                entry.mtime = st.st_mtime
            entry.loaded = True
            self._cache[key] = entry
            return entry

    def read(self, file: str | Path, ids: list[str] | None = None) -> list[str]:
        """
        Read IDs from the archive cache, loading once if needed.

        Args:
            file (str|Path): The archive file path.
            ids (list[str]|None): Optional IDs to filter by; when None or empty,
                all cached IDs are returned (order not guaranteed).

        Returns:
            list[str]: The IDs present in the archive, optionally filtered.

        """
        if not file:
            return []

        key: str = self._key(file)
        entry: _Entry = self._ensure_loaded(key)

        if not ids:
            return list(entry.ids)

        ids_set: set[str] = {s.strip() for s in ids if str(s).strip() and len(str(s).strip().split()) >= 2}
        if not ids_set:
            return []

        return [s for s in (str(x).strip() for x in ids) if s and len(s.split()) >= 2 and s in entry.ids]

    def has(self, file: str | Path) -> bool:
        """
        Check if the archive contains any IDs.

        Args:
            file (str|Path): The archive file path.

        Returns:
            bool: True if the archive has at least one ID, False otherwise.

        """
        if not file:
            return False

        key: str = self._key(file)
        entry: _Entry = self._ensure_loaded(key)
        return bool(entry.ids)

    def add(self, file: str | Path, ids: list[str], skip_check: bool = False) -> bool:
        """
        Append IDs to an archive and update the cache.

        Args:
            file (str|Path): The archive file path.
            ids (list[str]): IDs to append; invalid or duplicate IDs are ignored.
            skip_check (bool): If True, do not check for existing IDs in the cache.

        Returns:
            bool: True if any new IDs were appended, False otherwise.

        """
        if not file or not ids:
            return False

        key: str = self._key(file)
        lock: threading.RLock = self._get_lock(key)
        with lock:
            entry: _Entry = self._ensure_loaded(key)

            new_ids: list[str] = []
            for raw in ids:
                s: str = str(raw).strip()
                if not s or len(s.split()) < 2:
                    continue
                if not skip_check and s in entry.ids:
                    continue
                if s in new_ids:
                    continue
                new_ids.append(s)

            if not new_ids:
                return False

            path = Path(key)
            try:
                if not path.parent.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    from yt_dlp.utils import locked_file

                    with locked_file(str(path), "a", encoding="utf-8") as f:
                        f.write("".join(f"{x}\n" for x in new_ids))
                except Exception:
                    with path.open("a", encoding="utf-8") as f:
                        f.write("".join(f"{x}\n" for x in new_ids))

            except OSError as e:
                LOG.error(f"Failed to write to archive file '{key}': {e!s}")
                return False

            entry.ids.update(new_ids)
            st: os.stat_result | None = self._stat(key)
            if st:
                entry.size, entry.mtime = st.st_size, st.st_mtime

            return True

    def delete(self, file: str | Path, ids: list[str]) -> bool:
        """
        Remove IDs from an archive and update the cache.

        Args:
            file (str|Path): The archive file path.
            ids (list[str]): IDs to remove; invalid lines are ignored.

        Returns:
            bool: True on success (including no-op), False on error.

        """
        if not file or not ids:
            return False

        key: str = self._key(file)
        lock: threading.RLock = self._get_lock(key)
        with lock:
            path = Path(key)
            if not path.exists():
                return False

            entry: _Entry = self._cache.get(key) or _Entry()
            remove_ids: set[str] = {x.strip() for x in ids if str(x).strip() and len(str(x).strip().split()) >= 2}
            if not remove_ids:
                return True

            kept_lines: list[str] = []
            changed = False
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        s: str = line.strip()
                        if not s or len(s.split()) < 2:
                            changed = True
                            continue
                        if s in remove_ids:
                            changed = True
                            continue
                        kept_lines.append(line)
            except OSError as e:
                LOG.error(f"Failed reading archive for delete '{key}': {e!s}")
                return False

            if not changed:
                return True

            try:
                try:
                    from yt_dlp.utils import locked_file

                    with locked_file(str(path), "w", encoding="utf-8") as f:
                        f.writelines(kept_lines)
                except Exception:
                    with path.open("w", encoding="utf-8") as f:
                        f.writelines(kept_lines)
            except OSError as e:
                LOG.error(f"Failed writing archive after delete '{key}': {e!s}")
                return False

            if entry.loaded:
                entry.ids.difference_update(remove_ids)

            st: os.stat_result | None = self._stat(key)
            if st:
                entry.size, entry.mtime = st.st_size, st.st_mtime

            self._cache[key] = entry

            return True

    # Global configuration
    @classmethod
    def set_skip_read_stat_checks(cls, skip: bool = True) -> None:
        """
        Control os.stat checks on read paths for external change detection.

        When skip is True, Archiver assumes exclusive control of archive files
        and skips stat() comparisons during reads. Writes always refresh
        metadata regardless of this setting.

        Args:
            skip (bool): If True, skip read-time stat checks.

        """
        inst = cls.get_instance()
        with inst._global_lock:
            inst._stats_check = not skip
