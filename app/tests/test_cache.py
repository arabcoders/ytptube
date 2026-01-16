"""
Tests for cache.py - Thread-safe caching utilities.

This test suite provides comprehensive coverage for the Cache class:
- Tests basic cache operations (set, get, delete, clear)
- Tests TTL (time-to-live) functionality
- Tests thread safety
- Tests cache expiration
- Tests default value handling
- Tests key existence checking
- Tests hash generation
- Tests async methods

Total test functions: 15
All cache operations and edge cases are covered.
"""

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest

from app.library.cache import Cache


class TestCache:
    """Test the Cache class."""

    def setup_method(self):
        """Set up test fixtures."""
        Cache._reset_singleton()
        self.cache = Cache()

    def test_singleton_behavior(self):
        """Test that Cache follows singleton pattern."""
        cache1 = Cache()
        cache2 = Cache()
        assert cache1 is cache2

    def test_basic_set_and_get(self):
        """Test basic cache set and get operations."""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_with_default(self):
        """Test get with default value for non-existent keys."""
        assert self.cache.get("nonexistent", "default") == "default"
        assert self.cache.get("nonexistent") is None

    def test_set_with_ttl(self):
        """Test setting values with TTL."""
        self.cache.set("temp_key", "temp_value", ttl=0.1)
        assert self.cache.get("temp_key") == "temp_value"

        # Wait for expiration
        time.sleep(0.2)
        assert self.cache.get("temp_key") is None

    def test_set_without_ttl(self):
        """Test setting values without TTL (permanent)."""
        self.cache.set("permanent_key", "permanent_value")
        assert self.cache.get("permanent_key") == "permanent_value"

        # Should still be there after some time
        time.sleep(0.1)
        assert self.cache.get("permanent_key") == "permanent_value"

    def test_has_key(self):
        """Test key existence checking."""
        assert not self.cache.has("nonexistent")

        self.cache.set("existing", "value")
        assert self.cache.has("existing")

    def test_has_key_with_expiration(self):
        """Test key existence with expired keys."""
        self.cache.set("expiring", "value", ttl=0.1)
        assert self.cache.has("expiring")

        time.sleep(0.2)
        assert not self.cache.has("expiring")

    def test_ttl_method(self):
        """Test TTL retrieval."""
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
        """Test key deletion."""
        self.cache.set("to_delete", "value")
        assert self.cache.get("to_delete") == "value"

        self.cache.delete("to_delete")
        assert self.cache.get("to_delete") is None

    def test_delete_nonexistent_key(self):
        """Test deleting non-existent key (should not raise error)."""
        self.cache.delete("nonexistent")  # Should not raise

    def test_clear_cache(self):
        """Test clearing all cache entries."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        self.cache.clear()

        assert self.cache.get("key1") is None
        assert self.cache.get("key2") is None

    def test_hash_method(self):
        """Test hash generation."""
        hash1 = self.cache.hash("test_string")
        hash2 = self.cache.hash("test_string")
        hash3 = self.cache.hash("different_string")

        # Same input should produce same hash
        assert hash1 == hash2

        # Different input should produce different hash
        assert hash1 != hash3

        # Should be valid SHA-256 hex string
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_thread_safety(self):
        """Test thread safety of cache operations."""
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
            thread.join()

        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations each

    def test_async_set(self):
        """Test async set method using asyncio.run."""

        async def async_test():
            await self.cache.aset("async_key", "async_value")
            assert self.cache.get("async_key") == "async_value"

        asyncio.run(async_test())

    def test_async_set_with_ttl(self):
        """Test async set with TTL using asyncio.run."""

        async def async_test():
            await self.cache.aset("async_temp", "async_value", ttl=0.1)
            assert self.cache.get("async_temp") == "async_value"

            await asyncio.sleep(0.2)
            assert self.cache.get("async_temp") is None

        asyncio.run(async_test())

        asyncio.run(async_test())

    def test_expired_key_cleanup_on_get(self):
        """Test that expired keys are cleaned up when accessed."""
        # Set a key with very short TTL
        self.cache.set("cleanup_test", "value", ttl=0.05)

        # Verify it's initially there
        assert self.cache.get("cleanup_test") == "value"

        # Wait for expiration
        time.sleep(0.1)

        # Getting expired key should clean it up and return None
        assert self.cache.get("cleanup_test") is None

        # Key should be removed from internal cache
        assert "cleanup_test" not in self.cache._cache

    def test_expired_key_cleanup_on_has(self):
        """Test that expired keys are cleaned up when checking existence."""
        # Set a key with very short TTL
        self.cache.set("has_cleanup", "value", ttl=0.05)

        # Verify it's initially there
        assert self.cache.has("has_cleanup")

        # Wait for expiration
        time.sleep(0.1)

        # Checking existence of expired key should clean it up
        assert not self.cache.has("has_cleanup")

        # Key should be removed from internal cache
        assert "has_cleanup" not in self.cache._cache

    def test_complex_data_types(self):
        """Test caching of complex data types."""
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
    async def test_cleanup_removes_expired_entries(self):
        """Test that _cleanup removes only expired entries."""
        # Set some keys with different TTLs
        self.cache.set("permanent", "value")
        self.cache.set("short", "value1", ttl=0.1)
        self.cache.set("medium", "value2", ttl=1.0)

        # Wait for short to expire
        time.sleep(0.15)

        # Run cleanup
        await self.cache.cleanup()

        # Verify only expired key was removed
        assert self.cache.get("permanent") == "value", "Should keep permanent key"
        assert self.cache.get("medium") == "value2", "Should keep non-expired key"
        assert self.cache.get("short") is None, "Should remove expired key"

    @pytest.mark.asyncio
    async def test_cleanup_with_no_expired_entries(self):
        """Test that _cleanup handles cache with no expired entries."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2", ttl=1.0)

        # Run cleanup when nothing is expired
        await self.cache.cleanup()

        # Verify all keys still exist
        assert self.cache.get("key1") == "value1", "Should keep non-expired key"
        assert self.cache.get("key2") == "value2", "Should keep non-expired key"

    @pytest.mark.asyncio
    async def test_cleanup_with_empty_cache(self):
        """Test that _cleanup handles empty cache without errors."""
        # Clear cache first
        self.cache.clear()

        # Should not raise any errors
        await self.cache.cleanup()

    @pytest.mark.asyncio
    async def test_attach_registers_with_services(self):
        """Test that attach method registers cache with Services and schedules cleanup."""
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
        mock_app = MagicMock()
        cache.attach(mock_app)

        # Verify cache is registered with Services
        services = Services.get_instance()
        assert services.get("cache") is cache, "Should register cache with Services"

        # Verify cleanup job is scheduled
        scheduler = Scheduler.get_instance(loop=loop)
        assert scheduler.has(f"{Cache.__name__}.{Cache.cleanup.__name__}"), "Should schedule cleanup job"


if __name__ == "__main__":
    pytest.main([__file__])
