import threading
import time

from app.library.Singleton import Singleton, ThreadSafe


class TestSingleton:
    def setup_method(self):
        # Clear singleton instances before each test
        Singleton._instances.clear()
        ThreadSafe._instances.clear()

    def test_singleton_same_instance(self):

        class TestClass(metaclass=Singleton):
            def __init__(self, value=None):
                self.value = value

        instance1 = TestClass("first")
        instance2 = TestClass("second")

        assert instance1 is instance2
        # First initialization should win
        assert instance1.value == "first"
        assert instance2.value == "first"

    def test_singleton_different_classes(self):

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

        class TestClass(metaclass=ThreadSafe):
            def __init__(self, value=None):
                self.value = value

        instance1 = TestClass("first")
        instance2 = TestClass("second")

        assert instance1 is instance2
        # First initialization should win
        assert instance1.value == "first"
        assert instance2.value == "first"

    def test_threadsafe_different_classes(self):

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
        instances = []
        errors = []
        barrier = threading.Barrier(10)

        class ThreadSafeClass(metaclass=ThreadSafe):
            def __init__(self):
                self.thread_id = threading.current_thread().ident
                self.creation_time = time.time()

        def worker():
            try:
                barrier.wait(timeout=1)
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
            thread.join(timeout=1)
            assert not thread.is_alive()

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

    def test_singleton_args_kwargs(self):

        class ConfigClass(metaclass=Singleton):
            def __init__(self, name, value=None, **kwargs):
                self.name = name
                self.value = value
                self.extra = kwargs

        # First instantiation with arguments
        instance1 = ConfigClass("test", value=42, extra_param="extra")

        # Second instantiation with different arguments (should be ignored)
        instance2 = ConfigClass("different", value=100, other_param="other")

        assert instance1 is instance2
        assert instance1.name == "test"
        assert instance1.value == 42
        assert instance1.extra == {"extra_param": "extra"}

    def test_threadsafe_args_kwargs(self):

        class ConfigClass(metaclass=ThreadSafe):
            def __init__(self, name, value=None, **kwargs):
                self.name = name
                self.value = value
                self.extra = kwargs

        # First instantiation with arguments
        instance1 = ConfigClass("test", value=42, extra_param="extra")

        # Second instantiation with different arguments (should be ignored)
        instance2 = ConfigClass("different", value=100, other_param="other")

        assert instance1 is instance2
        assert instance1.name == "test"
        assert instance1.value == 42
        assert instance1.extra == {"extra_param": "extra"}


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
