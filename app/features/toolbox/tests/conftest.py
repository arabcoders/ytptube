from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from app.features.streaming.library.ffprobe import FFProbeResult
from app.features.toolbox import tools
from app.features.toolbox.schemas import TERMINAL, Job
from app.features.toolbox.service import Toolbox
from app.library.config import Config
from app.library.Services import Services
from app.library.sqlite_store import SqliteStore
from app.tests.helpers import make_in_memory_db_path

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


@pytest_asyncio.fixture
async def toolbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Toolbox]:
    SqliteStore._reset_singleton()
    store = SqliteStore(db_path=make_in_memory_db_path("toolbox"))
    config = MagicMock(spec=Config)
    config.download_path = str(tmp_path)
    config.default_pagination = 20
    work = tmp_path / "work"
    work.mkdir()
    config.temp_path = str(work)
    service = Toolbox(config=config)
    queue = Services.get_instance().get("queue")
    Services.get_instance().remove("queue")
    monkeypatch.setattr(tools, "ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(tools, "ffprobe", AsyncMock(return_value=FFProbeResult()))
    monkeypatch.setattr(service, "emit", lambda _: None)
    try:
        await asyncio.wait_for(service.start(), 5)
        yield service
    finally:
        await asyncio.wait_for(service.shutdown(), 10)
        await asyncio.wait_for(store.close(), 5)
        SqliteStore._reset_singleton()
        if queue is not None:
            Services.get_instance().add("queue", queue)
        shutil.rmtree(work)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    file = tmp_path / "video.mp4"
    file.write_bytes(b"original")
    return file


@pytest.fixture
def terminal(toolbox: Toolbox, monkeypatch: pytest.MonkeyPatch):
    events: dict[int, asyncio.Event] = {}

    def emit(job: Job) -> None:
        if job.status in TERMINAL:
            events.setdefault(job.id, asyncio.Event()).set()

    async def wait(identifier: int) -> Job:
        await asyncio.wait_for(events.setdefault(identifier, asyncio.Event()).wait(), 5)
        return await toolbox.get(identifier)

    monkeypatch.setattr(toolbox, "emit", emit)
    return wait
