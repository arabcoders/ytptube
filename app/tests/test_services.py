import pytest

from app.library.Services import ServiceEntry, Services


class TestServices:
    def setup_method(self):
        Services._reset_singleton()

    def test_add_and_get_service(self):
        services = Services()
        test_service = "test_value"

        services.add("test_service", test_service)
        retrieved = services.get("test_service")

        assert retrieved == test_service, "Should retrieve the same service that was added"

    def test_get_nonexistent_service(self):
        services = Services()
        result = services.get("nonexistent")

        assert result is None, "Should return None for nonexistent service"

    def test_has_service(self):
        services = Services()
        services.add("existing", "value")

        assert services.has("existing") is True, "Should return True for existing service"
        assert services.has("nonexistent") is False, "Should return False for nonexistent service"

    def test_remove_service(self):
        services = Services()
        services.add("to_remove", "value")

        assert services.has("to_remove") is True, "Service should exist before removal"
        services.remove("to_remove")
        assert services.has("to_remove") is False, "Service should not exist after removal"

    def test_remove_nonexistent_service(self):
        services = Services()
        services.remove("nonexistent")
        assert services.has("nonexistent") is False

    def test_clear_services(self):
        services = Services()
        services.add("service1", "value1")
        services.add("service2", "value2")

        assert len(services.get_all()) == 2, "Should have 2 services before clear"
        services.clear()
        assert len(services.get_all()) == 0, "Should have 0 services after clear"

    def test_add_all_services(self):
        services = Services()
        services_dict = {"service1": "value1", "service2": "value2", "service3": "value3"}

        services.add_all(services_dict)

        assert services.get("service1") == "value1"
        assert services.get("service2") == "value2"
        assert services.get("service3") == "value3"
        assert len(services.get_all()) == 3

    def test_get_all_copy(self):
        services = Services()
        services.add("test", "value")

        all_services = services.get_all()
        all_services.append(ServiceEntry(name="injected", declared_type=str, instance="malicious"))

        assert services.get("injected") is None, "Modifying returned dict should not affect internal state"

    def test_handle_sync_matching_args(self):
        services = Services()
        services.add("db", "database_connection")
        services.add("logger", "logger_instance")

        def test_handler(db, logger):
            return f"Handler called with {db} and {logger}"

        result = services.handle_sync(test_handler)
        expected = "Handler called with database_connection and logger_instance"
        assert result == expected

    def test_handle_sync_extra_kwargs(self):
        services = Services()
        services.add("db", "database_connection")

        def test_handler(db, user_id):
            return f"Handler called with {db} and {user_id}"

        result = services.handle_sync(test_handler, user_id=123)
        expected = "Handler called with database_connection and 123"
        assert result == expected

    def test_handle_sync_missing_args(self):
        services = Services()
        services.add("db", "database_connection")

        def test_handler(db_param, missing_service_param):  # noqa: ARG001
            return "Should not reach here"

        with pytest.raises(TypeError, match=r"missing .* required positional argument"):
            services.handle_sync(test_handler)

    def test_sync_no_args_handler(self):
        services = Services()
        services.add("unused", "value")

        def test_handler():
            return "No args handler"

        result = services.handle_sync(test_handler)
        assert result == "No args handler"

    @pytest.mark.asyncio
    async def test_handle_async_matching_args(self):
        services = Services()
        services.add("db", "database_connection")
        services.add("logger", "logger_instance")

        async def test_handler(db, logger):
            return f"Async handler called with {db} and {logger}"

        result = await services.handle_async(test_handler)
        expected = "Async handler called with database_connection and logger_instance"
        assert result == expected

    @pytest.mark.asyncio
    async def test_handle_async_extra_kwargs(self):
        services = Services()
        services.add("db", "database_connection")

        async def test_handler(db, user_id):
            return f"Async handler called with {db} and {user_id}"

        result = await services.handle_async(test_handler, user_id=456)
        expected = "Async handler called with database_connection and 456"
        assert result == expected

    @pytest.mark.asyncio
    async def test_handle_async_missing_args(self):
        services = Services()
        services.add("db", "database_connection")

        async def test_handler(db_param, missing_service_param):  # noqa: ARG001
            return "Should not reach here"

        with pytest.raises(TypeError, match=r"missing .* required positional argument"):
            await services.handle_async(test_handler)

    @pytest.mark.asyncio
    async def test_async_no_args_handler(self):
        services = Services()
        services.add("unused", "value")

        async def test_handler():
            return "No args async handler"

        result = await services.handle_async(test_handler)
        assert result == "No args async handler"

    def test_sync_kwargs_override_services(self):
        services = Services()
        services.add("param", "service_value")

        def test_handler(param):
            return f"Received: {param}"

        result = services.handle_sync(test_handler, param="override_value")
        assert result == "Received: override_value"

    @pytest.mark.asyncio
    async def test_async_kwargs_override_services(self):
        services = Services()
        services.add("param", "service_value")

        async def test_handler(param):
            return f"Received: {param}"

        result = await services.handle_async(test_handler, param="override_value")
        assert result == "Received: override_value"

    def test_handle_sync_complex_signature(self):
        services = Services()
        services.add("db", "database")
        services.add("cache", "redis")

        def complex_handler(db, cache, *args, **kwargs):
            return f"db:{db}, cache:{cache}, args:{args}, kwargs:{kwargs}"

        result = services.handle_sync(complex_handler, extra="value")
        expected = "db:database, cache:redis, args:(), kwargs:{}"
        assert result == expected

    @pytest.mark.asyncio
    async def test_handle_async_complex_signature(self):
        services = Services()
        services.add("db", "database")
        services.add("cache", "redis")

        async def complex_handler(db, cache, *args, **kwargs):
            return f"db:{db}, cache:{cache}, args:{args}, kwargs:{kwargs}"

        result = await services.handle_async(complex_handler, extra="value")
        expected = "db:database, cache:redis, args:(), kwargs:{}"
        assert result == expected

    def test_add_none_service(self):
        services = Services()
        services.add("none_service", None)

        assert services.has("none_service") is True
        assert services.get("none_service") is None

    def test_overwrite_existing_service(self):
        services = Services()
        services.add("service", "original_value")
        services.add("service", "new_value")

        assert services.get("service") == "new_value"

    def test_handler_exception_propagation(self):
        services = Services()

        def failing_handler():
            msg = "Handler failed"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Handler failed"):
            services.handle_sync(failing_handler)

    @pytest.mark.asyncio
    async def test_async_handler_exception_propagation(self):
        services = Services()

        async def failing_async_handler():
            msg = "Async handler failed"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="Async handler failed"):
            await services.handle_async(failing_async_handler)

    def test_handle_sync_callable_object(self):
        services = Services()
        services.add("data", "test_data")

        class CallableHandler:
            def __call__(self, data):
                return f"Callable received: {data}"

        handler = CallableHandler()
        result = services.handle_sync(handler)
        assert result == "Callable received: test_data"

    @pytest.mark.asyncio
    async def test_handle_async_callable_object(self):
        services = Services()
        services.add("data", "test_data")

        class AsyncCallableHandler:
            async def __call__(self, data):
                return f"Async callable received: {data}"

        handler = AsyncCallableHandler()
        result = await services.handle_async(handler)
        assert result == "Async callable received: test_data"

    def test_inspect_signature_edge_cases(self):
        services = Services()

        # Lambda function replacement
        def lambda_handler(x):
            return f"Lambda: {x}"

        services.add("x", "lambda_value")
        result = services.handle_sync(lambda_handler)
        assert result == "Lambda: lambda_value"

    def test_service_container_isolation(self):
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

    def test_add_all_overwrites_existing(self):
        services = Services()
        services.add("existing", "original")

        new_services = {"existing": "overwritten", "new": "value"}

        services.add_all(new_services)

        assert services.get("existing") == "overwritten"
        assert services.get("new") == "value"

    def test_add_all_empty_dict(self):
        services = Services()
        services.add("existing", "value")

        services.add_all({})

        assert services.get("existing") == "value"
        assert len(services.get_all()) == 1

    def test_concurrent_access_safety(self):
        import threading

        results = []
        barrier = threading.Barrier(10)

        def get_instance():
            barrier.wait(timeout=1)
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
            thread.join(timeout=1)
            assert not thread.is_alive()

        # All should be the same instance
        assert len(set(results)) == 1, "All threads should get the same singleton instance"
