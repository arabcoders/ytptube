"""
Tests for Singleton.py - Singleton metaclass utilities.

This test suite provides comprehensive coverage for the singleton metaclasses:
- Tests Singleton metaclass behavior
- Tests ThreadSafe metaclass behavior
- Tests thread safety of ThreadSafe metaclass
- Tests that different classes get different instances
- Tests that same class gets same instance

Total test functions: 8
All singleton patterns and edge cases are covered.
"""

import threading
import time

from app.library.Singleton import Singleton, ThreadSafe


class TestSingleton:
    """Test the Singleton metaclass."""

    def setup_method(self):
        """Set up test fixtures by clearing singleton instances."""
        # Clear singleton instances before each test
        Singleton._instances.clear()
        ThreadSafe._instances.clear()

    def test_singleton_same_instance(self):
        """Test that Singleton returns same instance for same class."""
        class TestClass(metaclass=Singleton):
            def __init__(self, value=None):
                self.value = value

        instance1 = TestClass("first")
        instance2 = TestClass("second")

        # Should be the same instance
        assert instance1 is instance2
        # First initialization should win
        assert instance1.value == "first"
        assert instance2.value == "first"

    def test_singleton_different_classes(self):
        """Test that Singleton creates different instances for different classes."""
        class ClassA(metaclass=Singleton):
            def __init__(self):
                self.name = "A"

        class ClassB(metaclass=Singleton):
            def __init__(self):
                self.name = "B"

        instance_a1 = ClassA()
        instance_a2 = ClassA()
        instance_b1 = ClassB()
        instance_b2 = ClassB()

        # Same class should return same instance
        assert instance_a1 is instance_a2
        assert instance_b1 is instance_b2

        # Different classes should return different instances
        assert instance_a1 is not instance_b1
        assert instance_a1.name == "A"
        assert instance_b1.name == "B"

    def test_threadsafe_same_instance(self):
        """Test that ThreadSafe returns same instance for same class."""
        class TestClass(metaclass=ThreadSafe):
            def __init__(self, value=None):
                self.value = value

        instance1 = TestClass("first")
        instance2 = TestClass("second")

        # Should be the same instance
        assert instance1 is instance2
        # First initialization should win
        assert instance1.value == "first"
        assert instance2.value == "first"

    def test_threadsafe_different_classes(self):
        """Test that ThreadSafe creates different instances for different classes."""
        class ClassA(metaclass=ThreadSafe):
            def __init__(self):
                self.name = "A"

        class ClassB(metaclass=ThreadSafe):
            def __init__(self):
                self.name = "B"

        instance_a1 = ClassA()
        instance_a2 = ClassA()
        instance_b1 = ClassB()
        instance_b2 = ClassB()

        # Same class should return same instance
        assert instance_a1 is instance_a2
        assert instance_b1 is instance_b2

        # Different classes should return different instances
        assert instance_a1 is not instance_b1
        assert instance_a1.name == "A"
        assert instance_b1.name == "B"

    def test_threadsafe_thread_safety(self):
        """Test that ThreadSafe is actually thread-safe."""
        instances = []
        errors = []

        class ThreadSafeClass(metaclass=ThreadSafe):
            def __init__(self):
                # Add a small delay to increase chance of race condition
                time.sleep(0.01)
                self.thread_id = threading.current_thread().ident
                self.creation_time = time.time()

        def worker():
            try:
                instance = ThreadSafeClass()
                instances.append(instance)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads trying to create instances simultaneously
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=worker)
            threads.append(thread)

        # Start all threads at roughly the same time
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(instances) == 10

        # All instances should be the same object
        first_instance = instances[0]
        for instance in instances[1:]:
            assert instance is first_instance

        # Only one creation should have happened
        assert hasattr(first_instance, "thread_id")
        assert hasattr(first_instance, "creation_time")

    def test_singleton_inheritance(self):
        """Test singleton behavior with inheritance."""
        class BaseClass(metaclass=Singleton):
            def __init__(self):
                self.base_value = "base"

        class ChildClass(BaseClass):
            def __init__(self):
                super().__init__()
                self.child_value = "child"

        # Each class should have its own singleton instance
        base1 = BaseClass()
        base2 = BaseClass()
        child1 = ChildClass()
        child2 = ChildClass()

        # Same class instances should be identical
        assert base1 is base2
        assert child1 is child2

        # Different class instances should be different
        assert base1 is not child1

        # Check values
        assert base1.base_value == "base"
        assert child1.base_value == "base"
        assert child1.child_value == "child"

    def test_threadsafe_inheritance(self):
        """Test threadsafe singleton behavior with inheritance."""
        class BaseClass(metaclass=ThreadSafe):
            def __init__(self):
                self.base_value = "base"

        class ChildClass(BaseClass):
            def __init__(self):
                super().__init__()
                self.child_value = "child"

        # Each class should have its own singleton instance
        base1 = BaseClass()
        base2 = BaseClass()
        child1 = ChildClass()
        child2 = ChildClass()

        # Same class instances should be identical
        assert base1 is base2
        assert child1 is child2

        # Different class instances should be different
        assert base1 is not child1

        # Check values
        assert base1.base_value == "base"
        assert child1.base_value == "base"
        assert child1.child_value == "child"

    def test_singleton_with_args_and_kwargs(self):
        """Test singleton behavior with various constructor arguments."""
        class ConfigClass(metaclass=Singleton):
            def __init__(self, name, value=None, **kwargs):
                self.name = name
                self.value = value
                self.extra = kwargs

        # First instantiation with arguments
        instance1 = ConfigClass("test", value=42, extra_param="extra")

        # Second instantiation with different arguments (should be ignored)
        instance2 = ConfigClass("different", value=100, other_param="other")

        # Should be same instance with original values
        assert instance1 is instance2
        assert instance1.name == "test"
        assert instance1.value == 42
        assert instance1.extra == {"extra_param": "extra"}

    def test_threadsafe_with_args_and_kwargs(self):
        """Test threadsafe singleton behavior with various constructor arguments."""
        class ConfigClass(metaclass=ThreadSafe):
            def __init__(self, name, value=None, **kwargs):
                self.name = name
                self.value = value
                self.extra = kwargs

        # First instantiation with arguments
        instance1 = ConfigClass("test", value=42, extra_param="extra")

        # Second instantiation with different arguments (should be ignored)
        instance2 = ConfigClass("different", value=100, other_param="other")

        # Should be same instance with original values
        assert instance1 is instance2
        assert instance1.name == "test"
        assert instance1.value == 42
        assert instance1.extra == {"extra_param": "extra"}


if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
