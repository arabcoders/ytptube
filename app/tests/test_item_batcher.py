"""Unit tests for app.library.ItemBatcher."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.library.ItemBatcher import ItemBatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_item(id_: str = "id1", title: str = "Test") -> SimpleNamespace:
    """Return a minimal stand-in for ItemDTO with a ``_id`` attribute."""
    return SimpleNamespace(_id=id_, title=title)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestItemBatcher:
    """Tests for ItemBatcher leading-edge and trailing-flush semantics."""

    @pytest.mark.asyncio
    async def test_leading_edge_emits_immediately(self) -> None:
        """First add after idle fires immediately as a one-item list."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=0.05)
        item = make_item("id1")
        await batcher.add(item)

        assert len(emitted) == 1
        assert emitted[0] == [item]

    @pytest.mark.asyncio
    async def test_rapid_adds_same_id_coalesces_to_last(self) -> None:
        """Multiple adds with same _id within interval → one flush, last item wins."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=0.1)

        # Consume the leading-edge slot
        item_a = make_item("id1", "first")
        await batcher.add(item_a)
        assert len(emitted) == 1

        # Now add more within the interval – these should batch
        item_b = make_item("id1", "second")
        item_c = make_item("id1", "third")
        await batcher.add(item_b)
        await batcher.add(item_c)

        # Allow the trailing flush to fire
        await asyncio.sleep(0.15)

        assert len(emitted) == 2
        flush_items = emitted[1]
        assert len(flush_items) == 1
        assert flush_items[0].title == "third"

    @pytest.mark.asyncio
    async def test_multiple_different_ids_flushed_together(self) -> None:
        """Adds for N different IDs within interval → one flush with N items."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=0.1)

        # Consume the leading-edge slot for id1
        await batcher.add(make_item("id1"))
        assert len(emitted) == 1

        # Queue id2, id3 within the interval
        item2 = make_item("id2")
        item3 = make_item("id3")
        await batcher.add(item2)
        await batcher.add(item3)

        await asyncio.sleep(0.15)

        assert len(emitted) == 2
        flush_items = emitted[1]
        ids = {i._id for i in flush_items}
        assert ids == {"id2", "id3"}

    @pytest.mark.asyncio
    async def test_only_one_timer_scheduled(self) -> None:
        """Only one timer handle is created while a flush is pending."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=0.1)

        # Consume the leading edge
        await batcher.add(make_item("id1"))

        # Add several more to build up the batch
        await batcher.add(make_item("id2"))
        handle_after_first = batcher._handle

        await batcher.add(make_item("id3"))
        handle_after_second = batcher._handle

        # The same handle object should be reused (not replaced)
        assert handle_after_first is handle_after_second

        await asyncio.sleep(0.15)

    @pytest.mark.asyncio
    async def test_emit_exception_clears_state_and_allows_next_add(self) -> None:
        """A failing emit callback is logged but leaves the batcher functional."""
        emit_count = 0

        async def emit(items: list) -> None:
            nonlocal emit_count
            emit_count += 1
            if emit_count == 2:
                raise RuntimeError("simulated flush failure")

        batcher = ItemBatcher(emit=emit, interval=0.1)
        await batcher.add(make_item("id1"))  # leading edge ok (count=1)

        # Trigger trailing flush that will fail (count=2)
        await batcher.add(make_item("id2"))
        await asyncio.sleep(0.15)  # trailing flush fires → raises → caught

        # State must be cleared; next add should work as a fresh leading-edge
        await asyncio.sleep(0.05)  # ensure _last_flush is old enough
        await batcher.add(make_item("id3"))  # leading edge ok (count=3)

        assert emit_count == 3
        # Batcher handle must be None (no dangling timer)
        assert batcher._handle is None

    @pytest.mark.asyncio
    async def test_flush_cancels_timer_and_emits_pending(self) -> None:
        """flush() cancels a scheduled timer and emits remaining items."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=10.0)  # very long interval

        # Consume leading edge
        await batcher.add(make_item("id1"))
        assert len(emitted) == 1

        # Queue an item that would normally wait 10 s
        item2 = make_item("id2")
        await batcher.add(item2)
        assert batcher._handle is not None

        # flush() must fire immediately
        await batcher.flush()

        assert batcher._handle is None
        assert len(emitted) == 2
        assert emitted[1] == [item2]

    @pytest.mark.asyncio
    async def test_flush_noop_when_empty(self) -> None:
        """flush() on an idle batcher does not call emit."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=0.05)
        await batcher.flush()

        assert emitted == []

    @pytest.mark.asyncio
    async def test_interval_zero_emits_every_add_immediately(self) -> None:
        """interval=0 → every add emits immediately as a single-item list."""
        emitted: list[list] = []

        async def emit(items: list) -> None:
            emitted.append(items)

        batcher = ItemBatcher(emit=emit, interval=0)

        for i in range(5):
            await batcher.add(make_item(f"id{i}"))

        assert len(emitted) == 5
        for i, batch in enumerate(emitted):
            assert len(batch) == 1
            assert batch[0]._id == f"id{i}"
