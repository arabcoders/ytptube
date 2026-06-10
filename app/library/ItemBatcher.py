"""Global coalescing batcher for high-frequency WebSocket item events.

Collects dirty items keyed per item (last write wins) and flushes them
as a single list to an async emit callback at most once per *interval* seconds.

Leading-edge semantics: the very first ``add()`` after an idle period fires
immediately so single-item updates feel instant.  Subsequent adds within the
same interval are coalesced into a single trailing flush.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.library.log import get_logger

LOG = get_logger()


class ItemBatcher:
    """Coalescing batcher for WebSocket item event payloads.

    Args:
        emit: Async callable that receives a list of items and delivers them
              to all connected WebSocket clients.
        interval: Flush interval in seconds.  ``0`` or negative disables
                  batching – every ``add()`` emits immediately.
        key: Optional callable that extracts the coalescing key from an item.
             Defaults to the item's ``_id`` attribute.

    """

    def __init__(
        self,
        emit: Callable[[list], Awaitable[None]],
        interval: float = 0.5,
        key: Callable[[Any], str | None] | None = None,
    ) -> None:
        self._emit = emit
        self._interval = interval
        self._key = key
        self._pending: dict[str, Any] = {}
        self._handle: asyncio.TimerHandle | None = None
        self._last_flush: float = 0.0  # monotonic

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add(self, item: Any) -> None:
        """Add (or coalesce) an item into the pending batch.

        If the batcher is idle and the leading-edge condition is met the item
        is emitted immediately; otherwise it is queued for the next trailing
        flush.

        Args:
            item: The payload to batch. Without a ``key`` callable, this is
                  expected to expose a ``_id`` attribute.

        """
        item_id: str = (self._key(item) if self._key else getattr(item, "_id", None)) or str(id(item))

        # interval <= 0  →  always emit immediately, no batching
        if self._interval <= 0:
            await self._emit_items([item])
            return

        now = time.monotonic()

        # Leading edge: nothing queued yet and enough time has elapsed
        if not self._pending and (now - self._last_flush) >= self._interval:
            self._last_flush = now
            await self._emit_items([item])
            return

        # Coalesce into the pending dict (last write wins per _id)
        self._pending[item_id] = item

        # Schedule a trailing flush only if one is not already pending
        if self._handle is None:
            elapsed = now - self._last_flush
            remaining = max(0.0, self._interval - elapsed)
            loop = asyncio.get_running_loop()
            self._handle = loop.call_later(remaining, lambda: loop.create_task(self._flush_pending()))

    async def flush(self) -> None:
        """Cancel any scheduled flush and immediately emit all pending items.

        Intended for use during shutdown so that the last batch reaches clients
        before the WebSocket is torn down.
        """
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None

        if self._pending:
            await self._flush_pending()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _flush_pending(self) -> None:
        """Emit everything that has accumulated in ``_pending``.

        State is cleared **before** awaiting the emit so that a slow or
        failing send can never wedge the batcher.
        """
        items = list(self._pending.values())
        self._pending = {}
        self._handle = None
        self._last_flush = time.monotonic()

        if not items:
            return

        try:
            await self._emit_items(items)
        except Exception:
            LOG.exception("ItemBatcher: emit callback raised an exception; %d item(s) lost.", len(items))

    async def _emit_items(self, items: list) -> None:
        """Delegate to the provided emit callback."""
        await self._emit(items)
