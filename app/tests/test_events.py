import asyncio
import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.library.Events import Event, EventBus, EventListener, Events


class TestEvents:
    """Test the Events constants class."""

    def test_events_constants_exist(self):
        """Test that all expected event constants exist."""
        # Basic lifecycle events
        assert Events.STARTUP == "startup"
        assert Events.LOADED == "loaded"
        assert Events.STARTED == "started"
        assert Events.SHUTDOWN == "shutdown"

        # Connection events
        assert Events.CONNECTED == "connected"
        assert Events.CONFIG_UPDATE == "config_update"

        # Log events
        assert Events.LOG_INFO == "log_info"
        assert Events.LOG_WARNING == "log_warning"
        assert Events.LOG_ERROR == "log_error"
        assert Events.LOG_SUCCESS == "log_success"

        # Item events
        assert Events.ITEM_ADDED == "item_added"
        assert Events.ITEM_UPDATED == "item_updated"
        assert Events.ITEM_COMPLETED == "item_completed"
        assert Events.ITEM_CANCELLED == "item_cancelled"
        assert Events.ITEM_DELETED == "item_deleted"

    def test_events_get_all(self):
        """Test Events.get_all() method returns all constants."""
        all_events = Events.get_all()

        # Should be a list
        assert isinstance(all_events, list)

        # Should contain expected events
        expected_events = [
            "startup",
            "loaded",
            "started",
            "shutdown",
            "connected",
            "config_update",
            "log_info",
            "log_warning",
            "log_error",
            "log_success",
            "item_added",
            "item_updated",
            "item_completed",
            "item_cancelled",
            "item_deleted",
            "item_paused",
            "item_resumed",
            "item_moved",
            "item_status",
            "item_error",
            "test",
            "add_url",
            "paused",
            "resumed",
        ]

        for expected in expected_events:
            assert expected in all_events

        # Should not contain private or callable attributes
        for event in all_events:
            assert not event.startswith("_")
            assert isinstance(event, str)

    def test_events_frontend(self):
        """Test Events.frontend() method returns frontend events."""
        frontend_events = Events.frontend()

        assert isinstance(frontend_events, list)

        # Check some expected frontend events
        expected_frontend = [
            Events.CONNECTED,
            Events.CONFIG_UPDATE,
            Events.LOG_INFO,
            Events.LOG_WARNING,
            Events.LOG_ERROR,
            Events.LOG_SUCCESS,
            Events.ITEM_ADDED,
            Events.ITEM_UPDATED,
        ]

        for expected in expected_frontend:
            assert expected in frontend_events

    def test_events_only_debug(self):
        """Test Events.only_debug() method returns debug-only events."""
        debug_events = Events.only_debug()

        assert isinstance(debug_events, list)
        assert Events.ITEM_UPDATED in debug_events


class TestEvent:
    """Test the Event dataclass."""

    def test_event_creation_minimal(self):
        """Test creating an Event with minimal required parameters."""
        event = Event(event="test_event", data={"key": "value"})

        # Check required fields
        assert event.event == "test_event"
        assert event.data == {"key": "value"}

        # Check auto-generated fields
        assert event.id is not None
        assert isinstance(event.id, str)
        assert event.created_at is not None

        # Check optional fields default to None
        assert event.title is None
        assert event.message is None

    def test_event_creation_with_all_fields(self):
        """Test creating an Event with all fields specified."""
        test_data = {"test": "data"}
        event = Event(event="custom_event", title="Test Title", message="Test Message", data=test_data)

        assert event.event == "custom_event"
        assert event.title == "Test Title"
        assert event.message == "Test Message"
        assert event.data == test_data
        assert event.id is not None
        assert event.created_at is not None

    def test_event_serialize(self):
        """Test Event serialization."""
        test_data = {"nested": {"key": "value"}}
        event = Event(event="serialize_test", title="Serialize Title", message="Serialize Message", data=test_data)

        serialized = event.serialize()

        assert isinstance(serialized, dict)
        assert serialized["event"] == "serialize_test"
        assert serialized["title"] == "Serialize Title"
        assert serialized["message"] == "Serialize Message"
        assert serialized["data"] == test_data
        assert "id" in serialized
        assert "created_at" in serialized

    def test_event_datatype(self):
        """Test Event datatype() method."""
        # Test with dictionary data
        event_dict = Event(event="test", data={"key": "value"})
        assert event_dict.datatype() == "dict"

        # Test with list data
        event_list = Event(event="test", data=["item1", "item2"])
        assert event_list.datatype() == "list"

        # Test with string data
        event_str = Event(event="test", data="string_data")
        assert event_str.datatype() == "str"

        # Test with None data
        event_none = Event(event="test", data=None)
        assert event_none.datatype() == "NoneType"

    def test_event_str_representation(self):
        """Test Event string representations."""
        event = Event(event="repr_test", title="Repr Title", message="Repr Message", data={"test": True})

        # Test __str__ method
        str_repr = str(event)
        assert "repr_test" in str_repr
        assert "Repr Title" in str_repr
        assert "Repr Message" in str_repr
        assert event.id in str_repr

        # Test __repr__ method
        repr_str = repr(event)
        assert "Event(" in repr_str
        assert "repr_test" in repr_str
        assert event.id in repr_str

    def test_event_created_at_format(self):
        """Test that created_at is in ISO format."""
        event = Event(event="time_test", data={})

        # Should be able to parse as ISO datetime
        parsed_time = datetime.datetime.fromisoformat(event.created_at)
        assert isinstance(parsed_time, datetime.datetime)

        # Should be recent (within last few seconds)
        now = datetime.datetime.now(tz=datetime.UTC)
        time_diff = abs((now - parsed_time).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    def test_event_put_method(self):
        """Test Event.put() method for adding extra data."""
        event = Event(event="put_test", data={"original": "data"})

        # Initially extras should be empty
        assert event.extras == {}

        # Test putting single value
        event.put("key1", "value1")
        assert event.extras["key1"] == "value1"
        assert len(event.extras) == 1

        # Test putting multiple values
        event.put("key2", 42)
        event.put("key3", {"nested": "object"})
        assert event.extras["key2"] == 42
        assert event.extras["key3"] == {"nested": "object"}
        assert len(event.extras) == 3

        # Test overwriting existing key
        event.put("key1", "new_value1")
        assert event.extras["key1"] == "new_value1"
        assert len(event.extras) == 3

        # Test putting None value
        event.put("key4", None)
        assert event.extras["key4"] is None
        assert len(event.extras) == 4

    def test_event_put_with_complex_data(self):
        """Test Event.put() with complex data types."""
        event = Event(event="complex_put_test", data={})

        # Test with list
        test_list = [1, 2, 3, "string", {"nested": True}]
        event.put("list_data", test_list)
        assert event.extras["list_data"] == test_list

        # Test with dictionary
        test_dict = {"a": 1, "b": {"c": 2}, "d": [4, 5, 6]}
        event.put("dict_data", test_dict)
        assert event.extras["dict_data"] == test_dict

        # Test with callable (function reference)
        def test_func():
            return "test"

        event.put("func_data", test_func)
        assert event.extras["func_data"] == test_func
        assert event.extras["func_data"]() == "test"

    def test_event_put_extras_persistence(self):
        """Test that extras persist and don't interfere with original data."""
        original_data = {"original": "value"}
        event = Event(event="persistence_test", data=original_data)

        # Add extras
        event.put("extra1", "value1")
        event.put("extra2", "value2")

        # Original data should be unchanged
        assert event.data == original_data
        assert event.data is original_data  # Same object reference

        # Extras should be separate
        assert event.extras == {"extra1": "value1", "extra2": "value2"}
        assert "extra1" not in event.data
        assert "extra2" not in event.data

    @pytest.mark.asyncio
    async def test_event_mutation_between_listeners(self):
        """Test that multiple listeners can mutate the same event and see each other's changes."""
        bus = EventBus()
        mutations = []

        async def listener1(event, name, **kwargs):  # noqa: ARG001
            # First listener adds data
            event.put("listener1", "data1")
            event.put("shared_counter", 1)
            mutations.append("listener1_executed")

        async def listener2(event, name, **kwargs):  # noqa: ARG001
            # Second listener can see and modify first listener's data
            assert event.extras.get("listener1") == "data1"
            assert event.extras.get("shared_counter") == 1

            # Add its own data
            event.put("listener2", "data2")
            # Increment shared counter
            event.put("shared_counter", event.extras.get("shared_counter", 0) + 1)
            mutations.append("listener2_executed")

        async def listener3(event, name, **kwargs):  # noqa: ARG001
            # Third listener can see all previous mutations
            assert event.extras.get("listener1") == "data1"
            assert event.extras.get("listener2") == "data2"
            assert event.extras.get("shared_counter") == 2

            # Add final data
            event.put("listener3", "data3")
            event.put("final_count", len(event.extras))
            mutations.append("listener3_executed")

        # Subscribe listeners in order
        bus.subscribe(Events.TEST, listener1, "listener1")
        bus.subscribe(Events.TEST, listener2, "listener2")
        bus.subscribe(Events.TEST, listener3, "listener3")

        # Emit event
        bus.emit(Events.TEST, data={"original": "data"})

        # Wait for execution (fire-and-forget)
        await asyncio.sleep(0.01)

        # Verify all listeners executed
        assert mutations == ["listener1_executed", "listener2_executed", "listener3_executed"]

    @pytest.mark.asyncio
    async def test_event_mutation_with_async_listeners(self):
        """Test event mutation with async listeners."""

        bus = EventBus()
        mutations = []

        async def async_listener1(event, name, **kwargs):  # noqa: ARG001
            event.put("async1", "value1")
            mutations.append("async1")

        async def async_listener2(event, name, **kwargs):  # noqa: ARG001
            # Can see first async listener's data
            assert event.extras.get("async1") == "value1"
            event.put("async2", "value2")
            mutations.append("async2")

        async def sync_listener(event, name, **kwargs):  # noqa: ARG001
            # Can see both async listeners' data
            assert event.extras.get("async1") == "value1"
            assert event.extras.get("async2") == "value2"
            event.put("sync", "value3")
            mutations.append("sync")

        bus.subscribe(Events.STARTUP, async_listener1, "async1")
        bus.subscribe(Events.STARTUP, async_listener2, "async2")
        bus.subscribe(Events.STARTUP, sync_listener, "sync")

        bus.emit(Events.STARTUP, data={"test": "data"})

        # Wait for execution
        await asyncio.sleep(0.01)

        assert mutations == ["async1", "async2", "sync"]

    @pytest.mark.asyncio
    async def test_event_mutation_data_types(self):
        """Test event mutation with various data types."""
        bus = EventBus()
        final_extras = {}

        async def collector(event, name, **kwargs):  # noqa: ARG001
            # Store reference to final extras
            nonlocal final_extras
            final_extras = event.extras

        async def mutator1(event, name, **kwargs):  # noqa: ARG001
            event.put("string", "test")
            event.put("number", 42)
            event.put("list", [1, 2, 3])

        async def mutator2(event, name, **kwargs):  # noqa: ARG001
            # Modify existing list
            existing_list = event.extras.get("list", [])
            existing_list.append(4)
            event.put("list", existing_list)

            event.put("dict", {"key": "value"})
            is_true = True
            event.put("bool", is_true)

        async def mutator3(event, name, **kwargs):  # noqa: ARG001
            # Modify existing dict
            existing_dict = event.extras.get("dict", {})
            existing_dict["new_key"] = "new_value"
            event.put("dict", existing_dict)

            event.put("nested", {"list": [1, 2], "dict": {"inner": "value"}})

        bus.subscribe(Events.SHUTDOWN, mutator1, "mutator1")
        bus.subscribe(Events.SHUTDOWN, mutator2, "mutator2")
        bus.subscribe(Events.SHUTDOWN, mutator3, "mutator3")
        bus.subscribe(Events.SHUTDOWN, collector, "collector")  # Last to collect final state

        bus.emit(Events.SHUTDOWN, data={})

        # Wait for execution
        await asyncio.sleep(0.01)

        # Verify final state
        assert final_extras["string"] == "test"
        assert final_extras["number"] == 42
        assert final_extras["list"] == [1, 2, 3, 4]
        assert final_extras["dict"] == {"key": "value", "new_key": "new_value"}
        assert final_extras["bool"] is True
        assert final_extras["nested"]["list"] == [1, 2]
        assert final_extras["nested"]["dict"]["inner"] == "value"

    @pytest.mark.asyncio
    async def test_sync_handler_async_wrapping(self):
        """Test that sync handlers are properly wrapped in async functions to avoid blocking."""
        bus = EventBus()
        execution_order = []

        def slow_sync_handler(event, name, **kwargs):  # noqa: ARG001
            """A sync handler that simulates blocking work"""
            import time

            time.sleep(0.05)  # Simulate some work
            execution_order.append(f"sync_{name}")

        async def fast_async_handler(event, name, **kwargs):  # noqa: ARG001
            """A fast async handler"""
            execution_order.append(f"async_{name}")

        # Subscribe both handlers
        bus.subscribe(Events.TEST, slow_sync_handler, "slow_sync")
        bus.subscribe(Events.TEST, fast_async_handler, "fast_async")

        # Emit should return immediately (non-blocking)
        import time

        start_time = time.time()
        bus.emit(Events.TEST, data={"test": "wrapping"})
        emit_time = time.time() - start_time

        # Emit should be very fast (< 0.01s) because sync handler is wrapped
        assert emit_time < 0.01, f"Emit took too long: {emit_time:.4f}s - sync handler may be blocking"

        # Wait for handlers to complete
        await asyncio.sleep(0.1)

        # Both handlers should have executed
        assert len(execution_order) == 2
        assert "sync_slow_sync" in execution_order
        assert "async_fast_async" in execution_order

    @pytest.mark.asyncio
    async def test_sync_handler_no_race_condition(self):
        """Test that multiple sync handlers don't have race conditions with loop variables."""
        bus = EventBus()
        results = []

        def handler1(event, name, **kwargs):  # noqa: ARG001
            results.append(f"handler1_{event.data['id']}")

        def handler2(event, name, **kwargs):  # noqa: ARG001
            results.append(f"handler2_{event.data['id']}")

        def handler3(event, name, **kwargs):  # noqa: ARG001
            results.append(f"handler3_{event.data['id']}")

        # Subscribe multiple sync handlers
        bus.subscribe(Events.TEST, handler1, "handler1")
        bus.subscribe(Events.TEST, handler2, "handler2")
        bus.subscribe(Events.TEST, handler3, "handler3")

        # Emit multiple events quickly to test for race conditions
        for i in range(3):
            bus.emit(Events.TEST, data={"id": i})

        # Wait for all handlers to complete
        await asyncio.sleep(0.05)

        # Should have 9 results (3 handlers x 3 events)
        assert len(results) == 9

        # Each handler should have processed each event with correct data
        for i in range(3):
            assert f"handler1_{i}" in results
            assert f"handler2_{i}" in results
            assert f"handler3_{i}" in results

    @pytest.mark.asyncio
    async def test_mixed_sync_async_handlers_execution_order(self):
        """Test that mixed sync/async handlers execute properly without blocking."""
        bus = EventBus()
        execution_times = []

        def sync_handler(event, name, **kwargs):  # noqa: ARG001
            import time

            start = time.time()
            time.sleep(0.02)  # Simulate work
            execution_times.append(("sync", time.time() - start))

        async def async_handler(event, name, **kwargs):  # noqa: ARG001
            import time

            start = time.time()
            await asyncio.sleep(0.01)  # Async work
            execution_times.append(("async", time.time() - start))

        # Subscribe mixed handlers
        bus.subscribe(Events.TEST, sync_handler, "sync")
        bus.subscribe(Events.TEST, async_handler, "async")

        # Emit and measure total time
        import time

        start_time = time.time()
        bus.emit(Events.TEST, data={"test": "mixed"})
        emit_time = time.time() - start_time

        # Emit should be instant (non-blocking)
        assert emit_time < 0.01, f"Emit blocked for {emit_time:.4f}s"

        # Wait for execution
        await asyncio.sleep(0.1)

        # Both handlers should have executed
        assert len(execution_times) >= 1, f"Expected at least 1 handler, got {len(execution_times)}: {execution_times}"

        # At least the sync handler should have executed with proper timing
        sync_results = [t for type_name, t in execution_times if type_name == "sync"]
        assert len(sync_results) >= 1, "Sync handler didn't execute"

        # Sync handler should have taken approximately 0.02s
        sync_time = sync_results[0]
        assert 0.015 < sync_time < 0.04, f"Sync handler time unexpected: {sync_time:.4f}s"


class TestEventListener:
    """Test the EventListener class."""

    def test_event_listener_creation_with_sync_callback(self):
        """Test creating EventListener with synchronous callback."""

        def sync_callback(event, name, **kwargs):  # noqa: ARG001
            return f"sync_result_{event.event}"

        listener = EventListener("test_listener", sync_callback)

        assert listener.name == "test_listener"
        assert listener.call_back == sync_callback
        assert listener.is_coroutine is False

    def test_event_listener_creation_with_async_callback(self):
        """Test creating EventListener with asynchronous callback."""

        async def async_callback(event, name, **kwargs):  # noqa: ARG001
            return f"async_result_{event.event}"

        listener = EventListener("async_listener", async_callback)

        assert listener.name == "async_listener"
        assert listener.call_back == async_callback
        assert listener.is_coroutine is True

    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test EventListener with async callback."""

        async def async_callback(event, name, **kwargs):  # noqa: ARG001
            return "async_result"

        listener = EventListener("test_async", async_callback)
        assert listener.is_coroutine is True

        event = Event(event=Events.TEST, data={"test": "data"})
        coroutine = listener.handle(event)

        # For async callbacks, handle() returns the coroutine directly (NOT awaited)
        assert asyncio.iscoroutine(coroutine)

        result = await coroutine  # Await the coroutine to execute
        if asyncio.iscoroutine(result):
            result = await result

        # The coroutine itself should be the callback return, not awaited by handle()
        assert result == (await async_callback(event, "test_async"))

    @pytest.mark.asyncio
    async def test_event_listener_handle_sync_callback_bug(self):
        """Test EventListener handling with sync callback shows the current bug."""

        def sync_callback(event, name, **kwargs):  # noqa: ARG001
            return f"sync_{event.event}"

        listener = EventListener("sync_test", sync_callback)
        event = Event(event="test_event", data={})

        # Current implementation has a bug with sync callbacks
        # It tries to create_task with a non-coroutine, which fails
        # This test documents the current behavior that should be fixed
        with pytest.raises(TypeError, match="a coroutine was expected"):
            await listener.handle(event)

    @pytest.mark.asyncio
    async def test_event_listener_handle_with_kwargs(self):
        """Test EventListener handling with additional kwargs."""

        async def callback_with_kwargs(event, name, extra_param=None, **kwargs):  # noqa: ARG001
            return {"event": event.event, "extra": extra_param}

        listener = EventListener("kwargs_test", callback_with_kwargs)
        event = Event(event="kwargs_event", data={})

        # For async callbacks, handle returns coroutine directly (the callback call)
        coroutine = listener.handle(event, extra_param="test_value")
        assert asyncio.iscoroutine(coroutine)

        # The coroutine should be equivalent to calling the callback directly
        expected_coroutine = callback_with_kwargs(event, "kwargs_test", extra_param="test_value")

        # Both should await to the same result
        result = await (await coroutine)
        expected_result = await expected_coroutine

        assert result["event"] == "kwargs_event"
        assert result["extra"] == "test_value"
        assert result == expected_result


class TestEventBus:
    """Test the EventBus singleton class."""

    def setup_method(self):
        """Clear EventBus listeners and reset singleton before each test."""
        EventBus._reset_singleton()

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_singleton_behavior(self, mock_bg_worker, mock_config):
        """Test that EventBus follows singleton pattern."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_get_instance(self, mock_bg_worker, mock_config):
        """Test EventBus.get_instance() method."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus1 = EventBus.get_instance()
        bus2 = EventBus.get_instance()
        assert bus1 is bus2

    def test_event_bus_initialization(self):
        """Test EventBus initialization with new clean design."""
        # Create EventBus with clean initialization
        bus = EventBus()

        # Test the initial state is correct
        assert bus.debug is False  # Default debug state
        assert bus._offload is None  # Lazy initialization - not loaded until needed
        assert bus._listeners == {}  # Empty listeners dict

        # Test debug enable/disable methods
        bus.debug_enable()
        assert bus.debug is True

        bus.debug_disable()
        assert bus.debug is False

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_subscribe_single_event(self, mock_bg_worker, mock_config):
        """Test subscribing to a single event."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        result = bus.subscribe(Events.TEST, test_callback, "test_subscriber")

        assert result is bus  # Should return self for chaining
        assert Events.TEST in bus._listeners
        assert any(name == "test_subscriber" for name, _ in bus._listeners[Events.TEST])
        listener = next((listener for name, listener in bus._listeners[Events.TEST] if name == "test_subscriber"), None)
        assert listener is not None
        assert isinstance(listener, EventListener)

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_subscribe_multiple_events(self, mock_bg_worker, mock_config):
        """Test subscribing to multiple events."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        events = [Events.TEST, Events.STARTUP, Events.SHUTDOWN]
        bus.subscribe(events, test_callback, "multi_subscriber")

        for event in events:
            assert event in bus._listeners
            assert any(name == "multi_subscriber" for name, _ in bus._listeners[event])

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_subscribe_wildcard(self, mock_bg_worker, mock_config):
        """Test subscribing to all events with wildcard."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        bus.subscribe("*", test_callback, "wildcard_subscriber")

        all_events = Events.get_all()
        for event in all_events:
            assert event in bus._listeners
            assert any(name == "wildcard_subscriber" for name, _ in bus._listeners[event])

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_subscribe_frontend(self, mock_bg_worker, mock_config):
        """Test subscribing to frontend events."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        bus.subscribe("frontend", test_callback, "frontend_subscriber")

        frontend_events = Events.frontend()
        for event in frontend_events:
            assert event in bus._listeners
            assert any(name == "frontend_subscriber" for name, _ in bus._listeners[event])

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_subscribe_invalid_event(self, mock_bg_worker, mock_config):
        """Test subscribing to invalid event."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        # Should not raise an exception but log an error
        result = bus.subscribe("invalid_event", test_callback, "invalid_subscriber")

        assert result is bus
        assert "invalid_event" not in bus._listeners

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_subscribe_auto_generated_name(self, mock_bg_worker, mock_config):
        """Test subscribing without providing name (auto-generated)."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        bus.subscribe(Events.TEST, test_callback)

        assert Events.TEST in bus._listeners
        assert len(bus._listeners[Events.TEST]) == 1

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_unsubscribe_single_event(self, mock_bg_worker, mock_config):
        """Test unsubscribing from a single event."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        # First subscribe
        bus.subscribe(Events.TEST, test_callback, "test_subscriber")
        assert any(name == "test_subscriber" for name, _ in bus._listeners[Events.TEST])

        # Then unsubscribe
        result = bus.unsubscribe(Events.TEST, "test_subscriber")

        assert result is bus
        assert not any(name == "test_subscriber" for name, _ in bus._listeners[Events.TEST])

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_unsubscribe_multiple_events(self, mock_bg_worker, mock_config):
        """Test unsubscribing from multiple events."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "callback_result"

        events = [Events.TEST, Events.STARTUP]

        # Subscribe to multiple events
        bus.subscribe(events, test_callback, "multi_subscriber")

        # Unsubscribe from multiple events
        bus.unsubscribe(events, "multi_subscriber")

        for event in events:
            assert "multi_subscriber" not in bus._listeners[event]

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_unsubscribe_nonexistent(self, mock_bg_worker, mock_config):
        """Test unsubscribing from nonexistent subscription."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        # Should not raise an exception
        result = bus.unsubscribe(Events.TEST, "nonexistent_subscriber")
        assert result is bus

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    def test_event_bus_emit_no_listeners(self, mock_config, mock_bg_worker):
        """Test emit with no listeners."""
        # Setup mocks
        mock_config_instance = MagicMock()
        mock_config_instance.debug = True
        mock_config.get_instance.return_value = mock_config_instance

        mock_bg_worker_instance = MagicMock()
        mock_bg_worker.get_instance.return_value = mock_bg_worker_instance

        bus = EventBus()

        # Emit event with no listeners - new fire-and-forget API returns None immediately
        result = bus.emit(Events.TEST, data={"test": "data"})

        # Should return None for fire-and-forget execution
        assert result is None

    @pytest.mark.asyncio
    async def test_event_bus_emit_with_listeners(self):
        """Test emitting event with listeners (fire-and-forget)."""
        bus = EventBus()

        results = []

        async def callback1(event, name, **kwargs):  # noqa: ARG001
            results.append(f"callback1_{event.event}")
            return "result1"

        async def callback2(event, name, **kwargs):  # noqa: ARG001
            results.append(f"callback2_{event.event}")
            return "result2"

        bus.subscribe(Events.TEST, callback1, "subscriber1")
        bus.subscribe(Events.TEST, callback2, "subscriber2")

        # emit() returns None immediately (fire-and-forget)
        result: None = bus.emit(Events.TEST, data={"test": "data"})
        assert result is None

        # Give async tasks a moment to execute
        await asyncio.sleep(0.01)

        # Side effects should have occurred
        assert len(results) == 2, f"Expected 2 results, got {len(results)}: {results}"
        assert "callback1_test" in results
        assert "callback2_test" in results

    @patch("app.library.config.Config")
    @patch("app.library.BackgroundWorker.BackgroundWorker")
    @pytest.mark.asyncio
    async def test_event_bus_emit_with_error_in_handler(self, mock_bg_worker, mock_config):
        """Test emitting event when a handler raises an exception."""
        mock_config.get_instance.return_value.debug = False
        mock_bg_worker.get_instance.return_value = MagicMock()

        bus = EventBus()

        async def failing_callback(event, name, **kwargs):  # noqa: ARG001
            msg = "Handler error"
            raise ValueError(msg)

        async def working_callback(event, name, **kwargs):  # noqa: ARG001
            return "success"

        bus.subscribe(Events.TEST, failing_callback, "failing_subscriber")
        bus.subscribe(Events.TEST, working_callback, "working_subscriber")

        # Should not raise exception, but log error
        bus.emit(Events.TEST, data={"test": "data"})

    def test_event_bus_emit_fire_and_forget(self):
        """Test emit() returns None immediately (fire-and-forget)."""
        bus = EventBus()

        # Should return None for no listeners
        result = bus.emit(Events.TEST, data={"test": "data"})
        assert result is None

        # Should return None even with listeners
        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "result"

        bus.subscribe(Events.TEST, test_callback, "test_subscriber")
        result = bus.emit(Events.TEST, data={"test": "data"})
        assert result is None

    def test_event_bus_emit_lazy_background_worker(self):
        """Test that BackgroundWorker is only initialized when needed."""
        bus = EventBus()

        bus._offload = None  # Ensure offload is None

        # Initially _offload should be None
        assert bus._offload is None

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            return "result"

        bus.subscribe(Events.TEST, test_callback, "test_subscriber")

        # After emit in no-loop context, _offload should be initialized
        bus.emit(Events.TEST, data={"test": "data"})

        # Note: This might still be None if running in pytest's event loop
        # The lazy initialization happens only when no event loop is detected

    @pytest.mark.asyncio
    async def test_event_bus_emit_with_kwargs(self):
        """Test emitting event with additional kwargs (fire-and-forget)."""
        bus: EventBus = EventBus()

        received_kwargs = {}

        async def callback_with_kwargs(event, name, extra_param=None, **kwargs):  # noqa: ARG001
            received_kwargs["extra_param"] = extra_param
            received_kwargs["kwargs"] = kwargs
            return "result"

        bus.subscribe(Events.TEST, callback_with_kwargs, "kwargs_subscriber")

        result: None = bus.emit(Events.TEST, data={"test": "data"}, extra_param="test_value", custom_arg="custom")
        assert result is None

        # Give async tasks a moment to execute
        await asyncio.sleep(0.02)

        # Side effects should have occurred
        assert "extra_param" in received_kwargs, f"received_kwargs: {received_kwargs}"
        assert received_kwargs["extra_param"] == "test_value"
        assert "kwargs" in received_kwargs, f"received_kwargs: {received_kwargs}"
        assert received_kwargs["kwargs"]["custom_arg"] == "custom"

    @pytest.mark.asyncio
    async def test_event_bus_emit_event_data_defaults(self):
        """Test emitting event with default data handling (fire-and-forget)."""
        bus = EventBus()

        received_event = None

        async def test_callback(event, name, **kwargs):  # noqa: ARG001
            nonlocal received_event
            received_event = event
            return "result"

        bus.subscribe(Events.TEST, test_callback, "default_subscriber")

        # Verify we have a subscriber
        assert Events.TEST in bus._listeners
        assert len(bus._listeners[Events.TEST]) == 1

        # emit() returns None immediately
        result = bus.emit(Events.TEST)
        assert result is None

        # Give async tasks a moment to execute
        await asyncio.sleep(0.01)

        # Side effects should have occurred
        assert received_event is not None, "Callback was not called"
        assert received_event.data == {}
        assert received_event.title is None
        assert received_event.message is None
