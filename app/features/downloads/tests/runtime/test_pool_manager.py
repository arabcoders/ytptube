from __future__ import annotations

import asyncio
from types import CoroutineType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.features.downloads.items import ItemDTO
from app.features.downloads.runtime import pool_manager
from app.features.downloads.runtime.core import Download
from app.features.presets.schemas import Preset


@pytest.mark.asyncio
async def test_preset_worker_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    presets = {
        "proxy": Preset(id=1, name="proxy", max_workers=1),
        "home": Preset(id=2, name="home", max_workers=2),
    }
    monkeypatch.setattr(ItemDTO, "get_preset", lambda info: presets[info.preset])
    monkeypatch.setattr(ItemDTO, "get_extractor", lambda info: info.url)
    limits = {name: asyncio.Semaphore(3) for name in ("youtube", "vimeo")}
    monkeypatch.setattr(pool_manager, "get_extractor_limit", lambda name, *_: limits[name])
    monkeypatch.setattr(pool_manager.EventBus, "get_instance", Mock())

    entries = {}
    for name, preset, extractor in [
        ("proxy-first", "proxy", "youtube"),
        ("proxy-next", "proxy", "vimeo"),
        ("home-first", "home", "youtube"),
        ("home-second", "home", "youtube"),
        ("home-next", "home", "vimeo"),
        ("live", "proxy", "youtube"),
        ("forced", "proxy", "youtube"),
    ]:
        info = ItemDTO(id=name, title=name, url=extractor, preset=preset, folder="")
        info.force_start = name == "forced"
        entry = Download(info=info)
        entry.is_live = name == "live"
        entries[entry.id] = entry

    store = Mock(items=entries.items, has_downloads=lambda: bool(entries), put=AsyncMock())
    pool = pool_manager.PoolManager(queue=Mock(queue=store), config=Mock(max_workers=4, max_workers_per_extractor=3))
    tasks: list[asyncio.Task[None]] = []
    scanned = asyncio.Event()
    advance = asyncio.Event()
    finish_proxy = asyncio.Event()

    async def download(id: str, entry: Download) -> None:
        if entry.info.id == "proxy-first":
            await asyncio.wait_for(finish_proxy.wait(), timeout=3)
        else:
            await asyncio.wait_for(asyncio.Event().wait(), timeout=3)
        entries.pop(id)

    def start(coro: CoroutineType, *, name: str) -> asyncio.Task[None]:
        task = asyncio.create_task(coro, name=name)
        tasks.append(task)
        return task

    async def checkpoint(_: float) -> None:
        scanned.set()
        await asyncio.wait_for(advance.wait(), timeout=3)
        advance.clear()

    run = AsyncMock(side_effect=download)
    monkeypatch.setattr(Download, "started", lambda entry: any(call.args[1] is entry for call in run.call_args_list))
    monkeypatch.setattr(pool, "_download_file", run)
    monkeypatch.setattr(
        pool_manager,
        "asyncio",
        SimpleNamespace(create_task=start, sleep=checkpoint, Task=asyncio.Task, Semaphore=asyncio.Semaphore),
    )
    scheduler = asyncio.create_task(pool._download_pool())
    try:
        await asyncio.wait_for(scanned.wait(), timeout=2)
        assert [call.args[1].info.id for call in run.call_args_list] == [
            "proxy-first",
            "home-first",
            "home-second",
            "live",
            "forced",
        ]

        finish_proxy.set()
        await asyncio.wait_for(tasks[0], timeout=2)
        scanned.clear()
        advance.set()
        await asyncio.wait_for(scanned.wait(), timeout=2)
        assert [call.args[1].info.id for call in run.call_args_list[5:]] == ["proxy-next"]

        presets["home"] = Preset(id=2, name="home", max_workers=0)
        scanned.clear()
        advance.set()
        await asyncio.wait_for(scanned.wait(), timeout=2)
        assert [call.args[1].info.id for call in run.call_args_list[6:]] == ["home-next"]
    finally:
        scheduler.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.wait_for(asyncio.gather(scheduler, *tasks, return_exceptions=True), timeout=2)
