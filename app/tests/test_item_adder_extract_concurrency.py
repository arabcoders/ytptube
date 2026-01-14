import time
import asyncio
import threading
import pytest

from app.library.config import Config
from app.library.downloads.queue_manager import DownloadQueue
from app.library.ItemDTO import Item


@pytest.mark.asyncio
async def test_extract_concurrency_limited(monkeypatch):
    """Ensure that concurrent extract_info calls are limited by the configured semaphore."""
    # Configure a low concurrency to make the timing assertions stable
    cfg = Config.get_instance()
    cfg.extract_info_concurrency = 2

    # Reset singleton so new DownloadQueue picks up updated config
    DownloadQueue._reset_singleton()
    queue = DownloadQueue.get_instance()

    sleep_time = 0.18

    # Thread-safe counters to observe concurrency usage in the executor threads
    lock = threading.Lock()
    current = {"val": 0}
    max_seen = {"max": 0}

    def fake_extract_info(config, url, **kwargs):
        # Track concurrent starts
        with lock:
            current["val"] += 1
            if current["val"] > max_seen["max"]:
                max_seen["max"] = current["val"]

        # Blocking call to simulate expensive IO/work executed in executor
        time.sleep(sleep_time)

        with lock:
            current["val"] -= 1

        return {"_type": "video", "id": url.split("/")[-1], "title": "t", "url": url}

    monkeypatch.setattr("app.library.Utils.extract_info", fake_extract_info)

    items = [Item(url=f"http://example.com/{i}") for i in range(6)]

    start = time.perf_counter()
    tasks = [asyncio.create_task(queue.add(item=item)) for item in items]

    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    # Assert we never exceeded the configured concurrency
    assert max_seen["max"] <= cfg.extract_info_concurrency, (
        f"Max concurrent extractions {max_seen['max']} exceeded limit {cfg.extract_info_concurrency}"
    )

    # Sanity timing check (relaxed to avoid flakiness)
    rounds = -(-len(items) // cfg.extract_info_concurrency)  # ceil division
    assert elapsed >= rounds * sleep_time * 0.8, (
        f"Elapsed {elapsed:.2f}s too low; expected at least {rounds * sleep_time * 0.8:.2f}s"
    )

    # Cleanup
    DownloadQueue._reset_singleton()
