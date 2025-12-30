import logging
from unittest.mock import MagicMock, patch

import pytest

from app.library.Services import Services


class TestServices:
    """Test the Services singleton class."""

    def setup_method(self):
        """Clear services before each test."""
        Services._reset_singleton()

    def test_singleton_behavior(self):
        """Test that Services follows singleton pattern."""
        service1 = Services()
        service2 = Services()
        service3 = Services.get_instance()

        assert service1 is service2, "Multiple Services() calls should return same instance"
        assert service1 is service3, "get_instance() should return same instance"
        assert id(service1) == id(service2) == id(service3), "All references should point to same object"

    def test_add_and_get_service(self):
        """Test adding and retrieving services."""
        services = Services()
        test_service = "test_value"

        services.add("test_service", test_service)
        retrieved = services.get("test_service")

        assert retrieved == test_service, "Should retrieve the same service that was added"

    def test_get_nonexistent_service(self):
        """Test retrieving a service that doesn't exist."""
        services = Services()
        result = services.get("nonexistent")

        assert result is None, "Should return None for nonexistent service"

    def test_has_service(self):
        """Test checking if service exists."""
        services = Services()
        services.add("existing", "value")

        assert services.has("existing") is True, "Should return True for existing service"
        assert services.has("nonexistent") is False, "Should return False for nonexistent service"

    def test_remove_service(self):
        """Test removing a service."""
        services = Services()
        services.add("to_remove", "value")

        assert services.has("to_remove") is True, "Service should exist before removal"
        services.remove("to_remove")
        assert services.has("to_remove") is False, "Service should not exist after removal"

    def test_remove_nonexistent_service(self):
        """Test removing a service that doesn't exist."""
        services = Services()
        # Should not raise an exception
        services.remove("nonexistent")
        assert services.has("nonexistent") is False

    def test_clear_services(self):
        """Test clearing all services."""
        services = Services()
        services.add("service1", "value1")
        services.add("service2", "value2")

        assert len(services.get_all()) == 2, "Should have 2 services before clear"
        services.clear()
        assert len(services.get_all()) == 0, "Should have 0 services after clear"

    def test_add_all_services(self):
        """Test adding multiple services at once."""
        services = Services()
        services_dict = {"service1": "value1", "service2": "value2", "service3": "value3"}

        services.add_all(services_dict)

        assert services.get("service1") == "value1"
        assert services.get("service2") == "value2"
        assert services.get("service3") == "value3"
        assert len(services.get_all()) == 3

    def test_get_all_returns_copy(self):
        """Test that get_all returns a copy, not the original dict."""
        services = Services()
        services.add("test", "value")

        all_services = services.get_all()
        all_services["injected"] = "malicious"

        assert "injected" not in services.get_all(), "Modifying returned dict should not affect internal state"

    def test_handle_sync_with_matching_args(self):
        """Test synchronous handler with matching arguments."""
        services = Services()
        services.add("db", "database_connection")
        services.add("logger", "logger_instance")

        def test_handler(db, logger):
            return f"Handler called with {db} and {logger}"

        result = services.handle_sync(test_handler)
        expected = "Handler called with database_connection and logger_instance"
        assert result == expected

    def test_handle_sync_with_extra_kwargs(self):
        """Test synchronous handler with additional kwargs."""
        services = Services()
        services.add("db", "database_connection")

        def test_handler(db, user_id):
            return f"Handler called with {db} and {user_id}"

        result = services.handle_sync(test_handler, user_id=123)
        expected = "Handler called with database_connection and 123"
        assert result == expected

    def test_handle_sync_with_missing_args(self):
        """Test synchronous handler with missing arguments."""
        services = Services()
        services.add("db", "database_connection")

        def test_handler(db_param, missing_service_param):  # noqa: ARG001
            return "Should not reach here"

        with patch("app.library.Services.LOG") as mock_logger:
            # The current implementation still calls the handler even with missing args
            # This causes a TypeError, which is the actual current behavior
            with pytest.raises(TypeError, match=r"missing .* required positional argument"):
                services.handle_sync(test_handler)

            # Should still log error about missing arguments
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Missing arguments" in error_call
            assert "missing_service_param" in error_call

    def test_handle_sync_no_args_handler(self):
        """Test synchronous handler that takes no arguments."""
        services = Services()
        services.add("unused", "value")

        def test_handler():
            return "No args handler"

        result = services.handle_sync(test_handler)
        assert result == "No args handler"

    @pytest.mark.asyncio
    async def test_handle_async_with_matching_args(self):
        """Test asynchronous handler with matching arguments."""
        services = Services()
        services.add("db", "database_connection")
        services.add("logger", "logger_instance")

        async def test_handler(db, logger):
            return f"Async handler called with {db} and {logger}"

        result = await services.handle_async(test_handler)
        expected = "Async handler called with database_connection and logger_instance"
        assert result == expected

    @pytest.mark.asyncio
    async def test_handle_async_with_extra_kwargs(self):
        """Test asynchronous handler with additional kwargs."""
        services = Services()
        services.add("db", "database_connection")

        async def test_handler(db, user_id):
            return f"Async handler called with {db} and {user_id}"

        result = await services.handle_async(test_handler, user_id=456)
        expected = "Async handler called with database_connection and 456"
        assert result == expected

    @pytest.mark.asyncio
    async def test_handle_async_with_missing_args(self):
        """Test asynchronous handler with missing arguments."""
        services = Services()
        services.add("db", "database_connection")

        async def test_handler(db_param, missing_service_param):  # noqa: ARG001
            return "Should not reach here"

        with patch("app.library.Services.LOG") as mock_logger:
            # The current implementation still calls the handler even with missing args
            # This causes a TypeError, which is the actual current behavior
            with pytest.raises(TypeError, match=r"missing .* required positional argument"):
                await services.handle_async(test_handler)

            # Should still log error about missing arguments
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Missing arguments" in error_call
            assert "missing_service_param" in error_call

    @pytest.mark.asyncio
    async def test_handle_async_no_args_handler(self):
        """Test asynchronous handler that takes no arguments."""
        services = Services()
        services.add("unused", "value")

        async def test_handler():
            return "No args async handler"

        result = await services.handle_async(test_handler)
        assert result == "No args async handler"

    def test_handle_sync_kwargs_override_services(self):
        """Test that kwargs override services with same name."""
        services = Services()
        services.add("param", "service_value")

        def test_handler(param):
            return f"Received: {param}"

        result = services.handle_sync(test_handler, param="override_value")
        assert result == "Received: override_value"

    @pytest.mark.asyncio
    async def test_handle_async_kwargs_override_services(self):
        """Test that kwargs override services with same name in async handler."""
        services = Services()
        services.add("param", "service_value")

        async def test_handler(param):
            return f"Received: {param}"

        result = await services.handle_async(test_handler, param="override_value")
        assert result == "Received: override_value"

    def test_handle_sync_with_complex_signature(self):
        """Test synchronous handler with complex function signature."""
        services = Services()
        services.add("db", "database")
        services.add("cache", "redis")

        def complex_handler(db, cache, *args, **kwargs):
            return f"db:{db}, cache:{cache}, args:{args}, kwargs:{kwargs}"

        result = services.handle_sync(complex_handler, extra="value")
        expected = "db:database, cache:redis, args:(), kwargs:{}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_handle_async_with_complex_signature(self):
        """Test asynchronous handler with complex function signature."""
        services = Services()
        services.add("db", "database")
        services.add("cache", "redis")

        async def complex_handler(db, cache, *args, **kwargs):
            return f"db:{db}, cache:{cache}, args:{args}, kwargs:{kwargs}"

        result = await services.handle_async(complex_handler, extra="value")
        expected = "db:database, cache:redis, args:(), kwargs:{}"
        assert result == expected

    def test_service_types_preserved(self):
        """Test that different service types are preserved correctly."""
        services = Services()

        # Test various types
        string_service = "string_value"
        int_service = 42
        list_service = [1, 2, 3]
        dict_service = {"key": "value"}
        custom_object = MagicMock()

        services.add("string", string_service)
        services.add("int", int_service)
        services.add("list", list_service)
        services.add("dict", dict_service)
        services.add("object", custom_object)

        assert services.get("string") == string_service
        assert services.get("int") == int_service
        assert services.get("list") == list_service
        assert services.get("dict") == dict_service
        assert services.get("object") is custom_object

    def test_add_none_service(self):
        """Test adding None as a service value."""
        services = Services()
        services.add("none_service", None)

        assert services.has("none_service") is True
        assert services.get("none_service") is None

    def test_service_name_edge_cases(self):
        """Test edge cases for service names."""
        services = Services()

        # Empty string name
        services.add("", "empty_name_value")
        assert services.get("") == "empty_name_value"

        # Numeric string name
        services.add("123", "numeric_name")
        assert services.get("123") == "numeric_name"

        # Special characters in name
        services.add("special-chars_123!@#", "special_value")
        assert services.get("special-chars_123!@#") == "special_value"

    def test_overwrite_existing_service(self):
        """Test overwriting an existing service."""
        services = Services()
        services.add("service", "original_value")
        services.add("service", "new_value")

        assert services.get("service") == "new_value"

    def test_singleton_persistence_across_operations(self):
        """Test that singleton behavior persists across various operations."""
        # Get instance and add a service
        services1 = Services()
        services1.add("persistent", "value")

        # Get another instance and verify service exists
        services2 = Services.get_instance()
        assert services2.get("persistent") == "value"

        # Clear from one instance
        services1.clear()

        # Verify cleared in other instance
        assert services2.get("persistent") is None

    def test_handler_exception_propagation(self):
        """Test that exceptions in handlers are properly propagated."""
        services = Services()

        def failing_handler():
            msg = "Handler failed"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Handler failed"):
            services.handle_sync(failing_handler)

    @pytest.mark.asyncio
    async def test_async_handler_exception_propagation(self):
        """Test that exceptions in async handlers are properly propagated."""
        services = Services()

        async def failing_async_handler():
            msg = "Async handler failed"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="Async handler failed"):
            await services.handle_async(failing_async_handler)

    def test_handle_sync_with_callable_object(self):
        """Test handle_sync with callable object instead of function."""
        services = Services()
        services.add("data", "test_data")

        class CallableHandler:
            def __call__(self, data):
                return f"Callable received: {data}"

        handler = CallableHandler()
        result = services.handle_sync(handler)
        assert result == "Callable received: test_data"

    @pytest.mark.asyncio
    async def test_handle_async_with_callable_object(self):
        """Test handle_async with callable object instead of function."""
        services = Services()
        services.add("data", "test_data")

        class AsyncCallableHandler:
            async def __call__(self, data):
                return f"Async callable received: {data}"

        handler = AsyncCallableHandler()
        result = await services.handle_async(handler)
        assert result == "Async callable received: test_data"

    def test_inspect_signature_edge_cases(self):
        """Test that inspect.signature works correctly with edge cases."""
        services = Services()

        # Lambda function replacement
        def lambda_handler(x):
            return f"Lambda: {x}"

        services.add("x", "lambda_value")
        result = services.handle_sync(lambda_handler)
        assert result == "Lambda: lambda_value"

    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        # This test verifies the module-level logger setup
        from app.library.Services import LOG

        assert isinstance(LOG, logging.Logger)
        assert LOG.name == "app.library.Services"

    def test_service_container_isolation(self):
        """Test that services don't interfere with each other."""
        services = Services()

        # Add services with potentially conflicting names
        services.add("data", {"type": "database"})
        services.add("data_backup", {"type": "backup"})

        assert services.get("data")["type"] == "database"
        assert services.get("data_backup")["type"] == "backup"

        # Remove one, other should remain
        services.remove("data")
        assert services.get("data") is None
        assert services.get("data_backup")["type"] == "backup"

    def test_large_number_of_services(self):
        """Test handling a large number of services."""
        services = Services()

        # Add many services
        num_services = 1000
        for i in range(num_services):
            services.add(f"service_{i}", f"value_{i}")

        # Verify all exist
        assert len(services.get_all()) == num_services

        # Verify specific services
        assert services.get("service_0") == "value_0"
        assert services.get("service_500") == "value_500"
        assert services.get("service_999") == "value_999"

        # Clear should work efficiently
        services.clear()
        assert len(services.get_all()) == 0

    def test_add_all_overwrites_existing(self):
        """Test that add_all overwrites existing services."""
        services = Services()
        services.add("existing", "original")

        new_services = {"existing": "overwritten", "new": "value"}

        services.add_all(new_services)

        assert services.get("existing") == "overwritten"
        assert services.get("new") == "value"

    def test_add_all_empty_dict(self):
        """Test add_all with empty dictionary."""
        services = Services()
        services.add("existing", "value")

        services.add_all({})

        # Should not affect existing services
        assert services.get("existing") == "value"
        assert len(services.get_all()) == 1

    def test_type_var_generic_behavior(self):
        """Test that TypeVar T is handled correctly."""
        services = Services()

        # Add different types and ensure they're returned correctly
        services.add("string", "text")
        services.add("number", 42)
        services.add("boolean", True)  # noqa: FBT003

        # Type should be preserved (runtime check)
        assert isinstance(services.get("string"), str)
        assert isinstance(services.get("number"), int)
        assert isinstance(services.get("boolean"), bool)

    def test_concurrent_access_safety(self):
        """Test basic thread safety aspects of singleton."""
        import threading
        import time

        results = []

        def get_instance():
            time.sleep(0.01)  # Small delay to increase chance of race condition
            instance = Services()
            results.append(id(instance))

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_instance)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should be the same instance
        assert len(set(results)) == 1, "All threads should get the same singleton instance"

    def test_method_chaining_possibility(self):
        """Test that methods can be potentially chained."""
        services = Services()

        # While current implementation doesn't return self, test the pattern works
        services.add("test1", "value1")
        services.add("test2", "value2")
        services.remove("test1")

        assert services.get("test1") is None
        assert services.get("test2") == "value2"

    def test_edge_case_empty_handler_name(self):
        """Test handlers with minimal or no names."""
        services = Services()
        services.add("param", "value")

        # Anonymous lambda
        result = services.handle_sync(lambda param: f"anon: {param}")
        assert result == "anon: value"

        # Function with minimal signature info
        def minimal(param):
            return param

        result = services.handle_sync(minimal)
        assert result == "value"

    def test_services_state_isolation(self):
        """Test that different Services instances share state properly."""
        # This test verifies the singleton behavior more thoroughly
        s1 = Services()
        s1.add("shared", "data")

        s2 = Services.get_instance()
        assert s2.get("shared") == "data"

        s2.add("another", "value")
        assert s1.get("another") == "value"

        # Clear from s1 affects s2
        s1.clear()
        assert len(s2.get_all()) == 0
