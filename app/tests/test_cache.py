import asyncio
import json
import threading
from unittest.mock import MagicMock

import pytest

from app.library.cache import Cache, CacheEntry, JsonPersistence


@pytest.fixture
def advance_clock(monkeypatch: pytest.MonkeyPatch):
    now = [1000.0]
    monkeypatch.setattr("app.library.cache.time.time", lambda: now[0])

    def advance(seconds: float) -> None:
        now[0] += seconds

    return advance


class TestCache:
    def setup_method(self):
        Cache._reset_singleton()
        self.cache = Cache()

    def test_singleton_behavior(self):
        cache1 = Cache()
        cache2 = Cache()
        assert cache1 is cache2

    def test_basic_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_persistence_roundtrip(self, tmp_path):
        persistence = JsonPersistence(tmp_path / "cache.json")
        self.cache.set("key", {"value": 1}, ttl=60, persist=True)
        self.cache._persistence = persistence
        asyncio.run(self.cache.flush())

        Cache._reset_singleton()
        restored = Cache(persistence)
        restored.attach(MagicMock(on_shutdown=[]))
        assert restored.get("key") == {"value": 1}

    def test_nonpersistent_not_saved(self, tmp_path):
        persistence = JsonPersistence(tmp_path / "cache.json")
        self.cache._persistence = persistence
        self.cache.set("memory", "value")
        self.cache.set("disk", "value", persist=True)

        asyncio.run(self.cache.flush())

        assert persistence.load() == {"disk": CacheEntry(value="value", persist=True)}

    def test_set_removes_persistence(self, tmp_path):
        persistence = JsonPersistence(tmp_path / "cache.json")
        self.cache._persistence = persistence
        self.cache.set("key", "disk", persist=True)
        asyncio.run(self.cache.flush())

        self.cache.set("key", "memory")
        asyncio.run(self.cache.flush())

        assert persistence.load() == {}

    def test_expiration_restore(self, tmp_path):
        persistence = JsonPersistence(tmp_path / "cache.json")
        self.cache._persistence = persistence
        self.cache.set("expired", "value", ttl=-1, persist=True)
        asyncio.run(self.cache.flush())

        Cache._reset_singleton()
        restored = Cache(persistence)
        restored.attach(MagicMock(on_shutdown=[]))
        assert not restored.has("expired")

    def test_json_rejection(self):
        for value in (object(), ("tuple",), {1: "non-string-key"}, float("inf")):
            with pytest.raises(TypeError):
                self.cache.set("object", value, persist=True)
        assert not self.cache.has("object")

        with pytest.raises(TypeError):
            self.cache.set("object", "value", ttl=float("inf"), persist=True)

    def test_persistence_deletes(self, tmp_path):
        persistence = JsonPersistence(tmp_path / "cache.json")
        self.cache._persistence = persistence
        self.cache.set("key", "value", persist=True)
        self.cache.delete("key")
        asyncio.run(self.cache.flush())
        assert persistence.load() == {}

    def test_persistence_clear(self, tmp_path):
        persistence = JsonPersistence(tmp_path / "cache.json")
        self.cache._persistence = persistence
        self.cache.set("key", "value", persist=True)
        asyncio.run(self.cache.flush())
        self.cache.clear()
        asyncio.run(self.cache.flush())
        assert persistence.load() == {}

    def test_persistence_versions(self, tmp_path):
        path = tmp_path / "cache.json"
        path.write_text('{"version": 99, "entries": {"key": {"value": "value"}}}')
        persistence = JsonPersistence(path)
        assert persistence.load() == {}
        with pytest.raises(RuntimeError, match="newer version"):
            persistence.save({"key": CacheEntry(value="replacement", persist=True)})
        assert json.loads(path.read_text())["version"] == 99

    def test_malformed_file_ignored(self, tmp_path):
        path = tmp_path / "cache.json"
        path.write_text("not-json")

        assert JsonPersistence(path).load() == {}

    @pytest.mark.asyncio
    async def test_flush_serializes_updates(self):
        class BlockingPersistence:
            def __init__(self) -> None:
                self.started = threading.Event()
                self.release = threading.Event()
                self.snapshots = []

            def load(self):
                return {}

            def save(self, entries):
                if not self.snapshots:
                    self.started.set()
                    self.release.wait(timeout=1)
                self.snapshots.append(dict(entries))

            def validate(self, entry):
                pass

            def close(self):
                pass

        persistence = BlockingPersistence()
        self.cache._persistence = persistence
        self.cache.set("first", 1, persist=True)
        first = asyncio.create_task(self.cache.flush())
        tasks = [first]
        try:
            assert await asyncio.to_thread(persistence.started.wait, 1)
            self.cache.set("second", 2, persist=True)
            tasks.append(asyncio.create_task(self.cache.flush()))
            persistence.release.set()
            await asyncio.gather(*tasks)
        finally:
            persistence.release.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        assert persistence.snapshots[-1] == {
            "first": CacheEntry(value=1, persist=True),
            "second": CacheEntry(value=2, persist=True),
        }

    def test_get_with_default(self):
        assert self.cache.get("nonexistent", "default") == "default"
        assert self.cache.get("nonexistent") is None

    def test_set_with_ttl(self, advance_clock):
        self.cache.set("temp_key", "temp_value", ttl=0.1)
        assert self.cache.get("temp_key") == "temp_value"

        advance_clock(0.2)
        assert self.cache.get("temp_key") is None

    def test_set_no_ttl(self, advance_clock):
        self.cache.set("permanent_key", "permanent_value")
        assert self.cache.get("permanent_key") == "permanent_value"

        advance_clock(10)
        assert self.cache.get("permanent_key") == "permanent_value"

    def test_has_key(self):
        assert not self.cache.has("nonexistent")

        self.cache.set("existing", "value")
        assert self.cache.has("existing")

    def test_has_key_with_expiration(self, advance_clock):
        self.cache.set("expiring", "value", ttl=0.1)
        assert self.cache.has("expiring")

        advance_clock(0.2)
        assert not self.cache.has("expiring")

    def test_ttl_method(self):
        # Key without TTL
        self.cache.set("permanent", "value")
        assert self.cache.ttl("permanent") is None

        # Key with TTL
        self.cache.set("temporary", "value", ttl=1.0)
        ttl = self.cache.ttl("temporary")
        assert ttl is not None
        assert 0.5 < ttl <= 1.0

        # Non-existent key
        assert self.cache.ttl("nonexistent") is None

    def test_delete_key(self):
        self.cache.set("to_delete", "value")
        assert self.cache.get("to_delete") == "value"

        self.cache.delete("to_delete")
        assert self.cache.get("to_delete") is None

    def test_delete_nonexistent_key(self):
        self.cache.delete("nonexistent")  # Should not raise

    def test_clear_cache(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        self.cache.clear()

        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None

    def test_hash_method(self):
        hash1 = self.cache.hash("test_string")
        hash2 = self.cache.hash("test_string")
        hash3 = self.cache.hash("different_string")

        # Same input should produce same hash
        assert hash1 == hash2

        # Different input should produce different hash
        assert hash1 != hash3

        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_thread_safety(self):
        results = []
        errors = []

        def worker(worker_id):
            try:
                for i in range(10):
                    key = f"worker_{worker_id}_key_{i}"
                    value = f"worker_{worker_id}_value_{i}"

                    self.cache.set(key, value)
                    retrieved = self.cache.get(key)

                    if retrieved == value:
                        results.append(f"{worker_id}_{i}_success")
                    else:
                        errors.append(f"{worker_id}_{i}_mismatch: {retrieved} != {value}")
            except Exception as e:
                errors.append(f"Worker {worker_id} error: {e}")

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=1)
            assert not thread.is_alive()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations each

    def test_async_set(self):

        async def async_test():
            await self.cache.aset("async_key", "async_value")
            assert self.cache.get("async_key") == "async_value"

        asyncio.run(async_test())

    def test_async_set_with_ttl(self, advance_clock):

        async def async_test():
            await self.cache.aset("async_temp", "async_value", ttl=0.1)
            assert self.cache.get("async_temp") == "async_value"

            advance_clock(0.2)
            assert self.cache.get("async_temp") is None

        asyncio.run(async_test())

    def test_expired_key_cleanup_get(self, advance_clock):
        # Set a key with very short TTL
        self.cache.set("cleanup_test", "value", ttl=0.05)

        # Verify it's initially there
        assert self.cache.get("cleanup_test") == "value"

        advance_clock(0.1)

        # Getting expired key should clean it up and return None
        assert self.cache.get("cleanup_test") is None

        # Key should be removed from internal cache
        assert "cleanup_test" not in self.cache._cache

    def test_expired_key_cleanup_has(self, advance_clock):
        # Set a key with very short TTL
        self.cache.set("has_cleanup", "value", ttl=0.05)

        # Verify it's initially there
        assert self.cache.has("has_cleanup")

        advance_clock(0.1)

        # Checking existence of expired key should clean it up
        assert not self.cache.has("has_cleanup")

        # Key should be removed from internal cache
        assert "has_cleanup" not in self.cache._cache

    def test_complex_data_types(self):
        # Test list
        test_list = [1, 2, {"nested": "dict"}]
        self.cache.set("list_key", test_list)
        assert self.cache.get("list_key") == test_list

        # Test dict
        test_dict = {"key": "value", "nested": {"list": [1, 2, 3]}}
        self.cache.set("dict_key", test_dict)
        assert self.cache.get("dict_key") == test_dict

        # Test custom object
        class CustomObject:
            def __init__(self, value):
                self.value = value

            def __eq__(self, other):
                return isinstance(other, CustomObject) and self.value == other.value

            def __hash__(self):
                return hash(self.value)

        custom_obj = CustomObject("test_value")
        self.cache.set("object_key", custom_obj)
        retrieved = self.cache.get("object_key")
        assert retrieved == custom_obj

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_entries(self, advance_clock):
        # Set some keys with different TTLs
        self.cache.set("permanent", "value")
        self.cache.set("short", "value1", ttl=0.1)
        self.cache.set("medium", "value2", ttl=1.0)

        advance_clock(0.15)

        # Run cleanup
        await self.cache.cleanup()

        # Verify only expired key was removed
        assert self.cache.get("permanent") == "value", "Should keep permanent key"
        assert self.cache.get("medium") == "value2", "Should keep non-expired key"
        assert self.cache.get("short") is None, "Should remove expired key"

    @pytest.mark.asyncio
    async def test_cleanup_no_expired_entries(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2", ttl=1.0)

        # Run cleanup when nothing is expired
        await self.cache.cleanup()

        # Verify all keys still exist
        assert self.cache.get("key1") == "value1", "Should keep non-expired key"
        assert self.cache.get("key2") == "value2", "Should keep non-expired key"

    @pytest.mark.asyncio
    async def test_attach_registers_with_services(self):
        from app.library.Scheduler import Scheduler
        from app.library.Services import Services

        # Reset singletons
        Cache._reset_singleton()
        Scheduler._reset_singleton()
        Services._reset_singleton()

        # Get event loop for scheduler
        loop = asyncio.get_event_loop()

        # Create cache and attach
        cache = Cache.get_instance()
        scheduler = Scheduler.get_instance(loop=loop)
        try:
            mock_app = MagicMock(on_shutdown=[])
            cache.attach(mock_app)

            services = Services.get_instance()
            assert services.get("cache") is cache, "Should register cache with Services"
            assert scheduler.has(f"{Cache.__name__}.{Cache.cleanup.__name__}"), "Should schedule cleanup job"
            assert cache.on_shutdown in mock_app.on_shutdown
        finally:
            await asyncio.wait_for(cache.on_shutdown(None), timeout=1)
            await asyncio.wait_for(scheduler.on_shutdown(MagicMock()), timeout=1)
            Cache._reset_singleton()
            Scheduler._reset_singleton()
            Services._reset_singleton()


if __name__ == "__main__":
    pytest.main([__file__])
