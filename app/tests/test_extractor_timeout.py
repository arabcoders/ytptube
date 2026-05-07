from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from app.features.ytdlp import extractor


class _Loop:
    def __init__(self) -> None:
        self.calls: list[object | None] = []

    def run_in_executor(self, executor, func):  # noqa: ANN001
        self.calls.append(executor)
        return func


class _Pool:
    def __init__(self) -> None:
        self.semaphore = asyncio.Semaphore(1)
        self.executor = object()

    def get_semaphore(self, _config: extractor.ExtractorConfig) -> asyncio.Semaphore:
        return self.semaphore

    def get_pool(self, _config: extractor.ExtractorConfig) -> object:
        return self.executor


def test_sleep_budget() -> None:
    assert extractor._sleep_timeout({}, 70, False) == 70
    assert extractor._sleep_timeout({"sleep_interval_requests": 0}, 70, True) == 70
    assert extractor._sleep_timeout({"sleep_interval_requests": 3}, 70, True) == 130
    assert extractor._sleep_timeout({"sleep_interval_requests": 30}, 70, True) == 370


@pytest.mark.asyncio
async def test_timeout_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool()
    loop = _Loop()
    seen: list[float] = []

    async def fake_wait_for(*, fut, timeout):
        seen.append(timeout)
        raise TimeoutError

    monkeypatch.setattr(extractor.ExtractorPool, "get_instance", classmethod(lambda cls: pool))
    monkeypatch.setattr(extractor.asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(extractor.asyncio, "wait_for", fake_wait_for)

    with pytest.raises(TimeoutError):
        await extractor.fetch_info(
            config={"sleep_interval_requests": 3},
            url="https://example.com",
            extractor_config=extractor.ExtractorConfig(concurrency=1, timeout=70),
            budget_sleep=True,
        )

    assert loop.calls == [pool.executor]
    assert seen == [130]
    assert not pool.semaphore.locked()


@pytest.mark.asyncio
async def test_pool_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = _Pool()
    loop = _Loop()
    expected = ({"id": "ok"}, [])
    seen: list[float] = []

    async def fake_wait_for(*, fut, timeout):
        seen.append(timeout)
        if len(loop.calls) == 1:
            raise RuntimeError("pool failed")
        return fut()

    monkeypatch.setattr(extractor.ExtractorPool, "get_instance", classmethod(lambda cls: pool))
    monkeypatch.setattr(extractor.asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(extractor.asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(extractor, "extract_info_sync", Mock(return_value=expected))

    result = await extractor.fetch_info(
        config={"sleep_interval_requests": 3},
        url="https://example.com",
        extractor_config=extractor.ExtractorConfig(concurrency=1, timeout=70),
        budget_sleep=True,
    )

    assert result == expected
    assert loop.calls == [pool.executor, None]
    assert seen == [130, 130]
    assert not pool.semaphore.locked()
