from __future__ import annotations

import asyncio
import math
import os
import signal
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from app.features.streaming.library.ffprobe import ffmpeg_bin
from app.features.streaming.types import StreamingError
from app.features.streaming.utils import (
    CLEANUP_TIMEOUT,
    ENCODE_AHEAD,
    SEGMENT_DURATION,
    SEGMENT_MAX_BYTES,
    PreparationBusyError,
    ProcessExitError,
    Segments,
    binary_key,
    encoder_fallback_chain,
    release,
    select_encoder,
    settle,
    spawn,
)
from app.library.config import Config
from app.library.logging import get_logger

if TYPE_CHECKING:
    from asyncio.subprocess import Process
    from collections.abc import Awaitable, Callable

    from app.features.streaming.service import Artifact, PlayerManager, Resource

IDLE_TIMEOUT = 30.0
READ_BYTES = 65536
SEGMENT_TIMEOUT = SEGMENT_DURATION * 4 + 60
LOG = get_logger()


async def read_ranges(reader: asyncio.StreamReader, ranges: asyncio.Queue[tuple[int, float]]) -> None:
    duration = None
    extent = None
    emitted = 0
    while line := await reader.readline():
        text = line.decode("utf-8", errors="replace").strip()
        if text == "#EXTM3U":
            duration = extent = None
        elif text.startswith("#EXTINF:"):
            duration = float(text.partition(":")[2].rstrip(","))
        elif text.startswith("#EXT-X-BYTERANGE:"):
            length, offset = text.partition(":")[2].split("@")
            extent = (int(offset), int(length))
        elif text == "pipe:1" and extent is not None and duration is not None:
            offset, length = extent
            if offset + length <= emitted:
                continue
            if offset != emitted or length <= 0 or not math.isfinite(duration) or duration <= 0:
                msg = "Invalid playback muxer range."
                raise ValueError(msg)
            await ranges.put((length, duration))
            emitted += length


def _resume(proc: Process) -> None:
    if os.name != "nt" and proc.returncode is None:
        with suppress(ProcessLookupError):
            proc.send_signal(signal.SIGCONT)


class Encoding:
    def __init__(self, manager: PlayerManager, resource: Resource, audio: int | None, subtitle: int | None):
        self.manager = manager
        self.resource = resource
        self.audio = audio
        self.subtitle = subtitle
        self.lock = asyncio.Lock()
        self.changed = asyncio.Event()
        self.demanded = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.error: Exception | None = None
        self.demand = 0
        self.next_index = 0
        self.closed = False

    async def get(self, index: int, validate: Callable[[], Awaitable[None]]) -> Artifact:
        async with self.lock:
            try:
                return await self.prepare(index, validate)
            except BaseException:
                await self.stop()
                raise

    async def prepare(self, index: int, validate: Callable[[], Awaitable[None]]) -> Artifact:
        self.check_open()
        key = self._key(index)
        cached = self.resource.artifacts.get(key)
        if cached is not None:
            return cached
        running = self.task is not None and not self.task.done()
        if not running or not self.next_index <= index <= self.demand + ENCODE_AHEAD + 1:
            await self.stop()
            self.check_open()
            cached = self.resource.artifacts.get(key)
            if cached is not None:
                return cached
            self.error = None
            self.demand = self.next_index = index
            self.task = asyncio.create_task(self.run(validate))
        self.demand = max(index, self.demand)
        self.demanded.set()
        while True:
            self.changed.clear()
            self.check_open()
            cached = self.resource.artifacts.get(key)
            if cached is not None:
                return cached
            if self.error is not None:
                raise self.error
            if self.task is None or self.task.done():
                msg = "Unable to prepare the media segment."
                raise StreamingError(msg)
            await self.changed.wait()

    async def run(self, validate: Callable[[], Awaitable[None]]) -> None:
        try:
            self.check_open()
            from app.features.streaming.service import MAX_JOBS

            binary = self._begin(MAX_JOBS)
            self.manager.jobs += 1
            released = True
            try:
                await self._encode(binary, validate)
            except ProcessExitError:
                # An unconfirmed child keeps its process slot, matching the spawn helper.
                released = False
                self.manager.closed = True
                raise
            finally:
                if released:
                    self.manager.jobs -= 1
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.error = exc
        finally:
            self.changed.set()

    def _begin(self, max_jobs: int) -> str:
        if self.manager.jobs >= max_jobs:
            msg = "Media preparation is busy."
            raise PreparationBusyError(msg)
        binary = ffmpeg_bin()
        if binary is None:
            msg = "ffmpeg is unavailable."
            raise StreamingError(msg)
        return binary

    async def _encode(self, binary: str, validate: Callable[[], Awaitable[None]]) -> None:
        from app.features.streaming.service import PlayerError

        config = Config.get_instance()
        key = (binary_key(binary) if Path(binary).exists() else (binary,), config.streamer_vcodec, config.vaapi_device)
        cached = Segments._encoders.get(key)
        selected = (
            cached[0] if cached and cached[1] > time.monotonic() else await select_encoder(config.streamer_vcodec)
        )
        start = self.next_index
        for codec in list(dict.fromkeys([selected, *encoder_fallback_chain(selected)])):
            try:
                await self.encode(binary, codec, validate)
            except ProcessExitError:
                raise
            except PreparationBusyError:
                raise
            except PlayerError:
                raise
            except (OSError, TimeoutError, StreamingError) as exc:
                LOG.warning("Segment encoder '%s' failed: %s", codec, type(exc).__name__)
                if self.next_index != start:
                    break
                continue
            if self.next_index == start:
                continue
            if len(Segments._encoders) >= 16:
                Segments._encoders.clear()
            Segments._encoders[key] = (codec, time.monotonic() + 300)
            return
        msg = "Unable to prepare the media segment."
        raise StreamingError(msg)

    async def encode(self, binary: str, codec: str, validate: Callable[[], Awaitable[None]]) -> None:
        from app.features.streaming.service import Artifact, PlayerError

        args = await Segments(
            self.next_index,
            probe=self.resource.probe,
            audio=self.audio,
            subtitle=self.subtitle,
        ).build_ffmpeg_args(self.resource.file, codec)
        proc = await spawn(binary, args)
        assert proc.stdout is not None
        assert proc.stderr is not None
        stdout, stderr = proc.stdout, proc.stderr
        ranges: asyncio.Queue[tuple[int, float]] = asyncio.Queue(maxsize=4)
        metadata = asyncio.create_task(read_ranges(stderr, ranges))
        reading = asyncio.create_task(stdout.read(READ_BYTES))
        boundary = asyncio.create_task(ranges.get())
        buffer = bytearray()
        extent: tuple[int, float] | None = None
        artifact_file: Path | None = None
        eof = False
        unreaped = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + SEGMENT_TIMEOUT
        try:
            while True:
                if extent is not None and len(buffer) >= extent[0]:
                    length, _ = extent
                    async with asyncio.timeout(max(0, deadline - loop.time())):
                        await validate()
                    if not self.manager._valid(self.resource):
                        msg = "Media changed during preparation."
                        raise PlayerError(msg, 409)
                    data = bytes(buffer[:length])
                    del buffer[:length]
                    self.manager._evict(SEGMENT_MAX_BYTES)
                    with tempfile.NamedTemporaryFile(
                        prefix="segment-", suffix=".ts", dir=self.manager._root(), delete=False
                    ) as output:
                        artifact_file = Path(output.name)
                    async with await anyio.open_file(artifact_file, "wb") as output:
                        await output.write(data)
                    key = self._key(self.next_index)
                    previous = self.resource.artifacts.get(key)
                    if previous is not None and (previous.pins or key in self.resource.flights):
                        artifact_file.unlink(missing_ok=True)
                    else:
                        if previous is not None:
                            previous.file.unlink(missing_ok=True)
                        self.resource.artifacts[key] = Artifact(
                            file=artifact_file,
                            content_type="video/mpegts",
                            size=len(data),
                            touched=time.monotonic(),
                        )
                    artifact_file = None
                    self.next_index += 1
                    self.changed.set()
                    deadline = loop.time() + SEGMENT_TIMEOUT
                    extent = None
                    boundary = asyncio.create_task(ranges.get())
                    if self.next_index > self.demand + ENCODE_AHEAD:
                        self.demanded.clear()
                        if os.name != "nt" and proc.returncode is None:
                            with suppress(ProcessLookupError):
                                proc.send_signal(signal.SIGSTOP)
                        try:
                            async with asyncio.timeout(IDLE_TIMEOUT):
                                await self.demanded.wait()
                        except TimeoutError:
                            return
                        finally:
                            _resume(proc)
                        deadline = loop.time() + SEGMENT_TIMEOUT
                    continue
                if boundary.done() and extent is None:
                    extent = boundary.result()
                    if extent[0] > SEGMENT_MAX_BYTES:
                        msg = "Prepared output exceeds the size limit."
                        raise StreamingError(msg)
                    continue
                if len(buffer) > SEGMENT_MAX_BYTES + READ_BYTES:
                    msg = "Prepared output exceeds the size limit."
                    raise StreamingError(msg)
                if metadata.done():
                    if metadata.exception() is not None:
                        msg = "Invalid playback muxer metadata."
                        raise StreamingError(msg) from metadata.exception()
                    if eof and ranges.empty() and extent is None:
                        async with asyncio.timeout(max(0, deadline - loop.time())):
                            code = await proc.wait()
                        if buffer or code != 0:
                            msg = "Unable to prepare the media segment."
                            raise StreamingError(msg)
                        return
                if reading.done() and not eof:
                    chunk = reading.result()
                    if chunk:
                        buffer.extend(chunk)
                        reading = asyncio.create_task(stdout.read(READ_BYTES))
                    else:
                        eof = True
                    continue
                waiting = [task for task in (reading, boundary, metadata) if not task.done()]
                if not waiting:
                    msg = "Incomplete media segment."
                    raise StreamingError(msg)
                done, _ = await asyncio.wait(
                    waiting, timeout=max(0, deadline - loop.time()), return_when=asyncio.FIRST_COMPLETED
                )
                if not done:
                    raise TimeoutError
        except ProcessExitError:
            unreaped = True
            raise
        finally:

            async def cleanup() -> None:
                for task in (reading, boundary, metadata):
                    task.cancel()
                try:
                    await asyncio.wait_for(
                        asyncio.gather(reading, boundary, metadata, return_exceptions=True), CLEANUP_TIMEOUT
                    )
                finally:
                    _resume(proc)
                    await release(proc)

            try:
                await settle(asyncio.create_task(cleanup()))
            except ProcessExitError:
                unreaped = True
                raise
            finally:
                if artifact_file is not None and not unreaped:
                    artifact_file.unlink(missing_ok=True)

    async def close(self) -> None:
        self.closed = True
        self.changed.set()
        await self.stop()

    async def stop(self) -> None:
        task = self.task
        if task is not None:
            if not task.done():
                task.cancel()
            try:
                await settle(task)
            except asyncio.CancelledError:
                if not task.cancelled():
                    raise
            if self.task is task:
                self.task = None
        if isinstance(self.error, ProcessExitError):
            raise self.error

    def check_open(self) -> None:
        if self.closed:
            from app.features.streaming.service import PlayerError

            msg = "Media preparation was closed."
            raise PlayerError(msg, 409)

    def _key(self, index: int) -> tuple:
        return ("segment", index, self.audio, self.subtitle)
