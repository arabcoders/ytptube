from __future__ import annotations

import asyncio
import hashlib
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from typing import TYPE_CHECKING

import anyio

from app.features.streaming.library.ffprobe import FFProbeResult, ffmpeg_bin, ffprobe
from app.features.streaming.library.subtitle import SOURCE_FORMATS, Subtitle, get_subtitle_tracks
from app.features.streaming.types import StreamingError
from app.features.streaming.utils import (
    SEGMENT_MAX_BYTES,
    ProcessExitError,
    Segments,
    binary_key,
    font_metadata,
    run,
    segment_window,
    settle,
)
from app.library.config import Config
from app.library.Scheduler import Scheduler
from app.library.Services import Services
from app.library.Utils import get_file

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable

    from aiohttp import web

    from app.features.streaming.library.ffprobe import FFStream

IDLE_TTL = 300.0
PLAYER_TTL = 900.0
MAX_RESOURCES = 32
MAX_PLAYERS = 64
MAX_JOBS = 8
MAX_CACHE_BYTES = 256 * 1024 * 1024
MAX_ARTIFACTS = 128
TEXT_MAX_BYTES = 4 * 1024 * 1024
FONT_MAX_BYTES = 8 * 1024 * 1024
BITMAP_CODECS = {"hdmv_pgs_subtitle", "pgssub", "dvd_subtitle", "dvb_subtitle"}
TEXT_CODECS = {"subrip", "srt", "webvtt", "mov_text", "ass", "ssa"}


class PlayerError(StreamingError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def generation(file: Path) -> tuple[int, ...]:
    info = file.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@dataclass(kw_only=True)
class Artifact:
    file: Path
    content_type: str
    size: int
    touched: float
    pins: int = 0
    metadata: dict | None = None


@dataclass(kw_only=True)
class Flight:
    task: asyncio.Task
    owners: dict[tuple[str, str | None], int] = field(default_factory=dict)


@dataclass(kw_only=True)
class Resource:
    id: str
    key: tuple
    file: Path
    identity: tuple[int, ...]
    sidecars: dict[str, tuple[Path, tuple[int, ...]]]
    subtitles: dict[str, dict]
    touched: float
    probe: FFProbeResult | None = None
    players: set[str] = field(default_factory=set)
    flights: dict[tuple, Flight] = field(default_factory=dict)
    artifacts: dict[tuple, Artifact] = field(default_factory=dict)
    stale: bool = False


@dataclass(kw_only=True)
class Player:
    id: str
    owner: str
    resource: Resource
    expires: float
    audio: int | None = None
    subtitle: str | None = None


class PlayerManager:
    def __init__(self, config: Config):
        self.config = config
        self.root: Path | None = None
        self.resources: dict[tuple, Resource] = {}
        self.players: dict[str, Player] = {}
        self.jobs = 0
        self.closed = False

    def attach(self, app: web.Application) -> None:
        Services.get_instance().add("players", self)
        app.on_startup.append(self.start)
        app.on_shutdown.append(self.shutdown)
        app.on_cleanup.append(self.cleanup)

    async def start(self, _: web.Application) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="ytptube-player-", dir=self.config.temp_path))
        Scheduler.get_instance().add("* * * * *", self.expire, id="player-expiry")

    def _root(self) -> Path:
        if self.closed or self.root is None:
            msg = "Player service is unavailable."
            raise PlayerError(msg, 503)
        return self.root

    def _valid(self, resource: Resource) -> bool:
        try:
            return (
                not resource.stale
                and resource.key[-1] == self._settings()
                and generation(resource.file) == resource.identity
                and all(generation(file) == identity for file, identity in resource.sidecars.values())
            )
        except OSError:
            return False

    def _settings(self) -> tuple:
        binary = ffmpeg_bin()
        return (
            self.config.streamer_vcodec,
            self.config.streamer_acodec,
            self.config.vaapi_device,
            binary_key(binary) if binary is not None else None,
        )

    async def open(self, owner: str, file: str) -> Player:
        self._root()
        await self.expire()
        path, status = get_file(self.config.download_path, file)
        if status == 404 or not path.is_file():
            msg = "Media file was not found."
            raise PlayerError(msg, 404)
        path = path.resolve()
        identity = generation(path)
        external = sorted(
            get_subtitle_tracks(path), key=lambda track: (SOURCE_FORMATS.index(track.source_format), str(track.file))
        )
        sidecars = {f"x{index}": (track.file, generation(track.file)) for index, track in enumerate(external)}
        settings = self._settings()
        key = (owner, path, identity, tuple(sidecars.values()), settings)
        if len(self.players) >= MAX_PLAYERS:
            msg = "Too many active players."
            raise PlayerError(msg, 503)
        resource = self.resources.get(key)
        if resource is None:
            if len(self.resources) >= MAX_RESOURCES:
                idle = sorted(
                    (
                        r
                        for r in self.resources.values()
                        if not r.players and not r.flights and not any(a.pins for a in r.artifacts.values())
                    ),
                    key=lambda r: r.touched,
                )
                if not idle:
                    msg = "Player resource capacity is full."
                    raise PlayerError(msg, 503)
                self._drop(idle[0])
            subtitles = {
                f"x{index}": {
                    "id": f"x{index}",
                    "lang": track.lang,
                    "name": track.name,
                    "source_format": track.source_format,
                    "delivery_format": track.delivery_format,
                    "renderer": track.renderer,
                }
                for index, track in enumerate(external)
            }
            resource = Resource(
                id=hashlib.sha256(repr(key).encode()).hexdigest(),
                key=key,
                file=path,
                identity=identity,
                sidecars=sidecars,
                subtitles=subtitles,
                touched=time.monotonic(),
            )
            self.resources[key] = resource
        player = Player(
            id=token_urlsafe(24),
            owner=owner,
            resource=resource,
            expires=time.monotonic() + PLAYER_TTL,
        )
        self.players[player.id] = player
        resource.players.add(player.id)
        opened = False
        try:
            await self.check(player)
            if resource.probe is None:

                async def probe() -> FFProbeResult:
                    return await ffprobe(path)

                resource.probe = await self._flight(player, ("probe",), probe)
            try:
                duration = float(resource.probe.metadata.get("duration", 0))
            except (TypeError, ValueError) as exc:
                msg = "Media duration is unavailable."
                raise StreamingError(msg) from exc
            segment_window(0, duration)
            if not self._valid(resource) or player.id not in self.players:
                msg = "Media changed during preparation."
                raise PlayerError(msg, 409)
            opened = True
            return player
        finally:
            if not opened:
                await self.close(player.id, owner)

    async def get(self, id: str, owner: str) -> Player:
        self._root()
        player = self.players.get(id)
        if player is None or player.owner != owner:
            msg = "Player was not found."
            raise PlayerError(msg, 404)
        await self.check(player)
        player.expires = time.monotonic() + PLAYER_TTL
        return player

    async def media(self, id: str, owner: str) -> Player:
        for resource in self.resources.values():
            if resource.id != id or resource.key[0] != owner:
                continue
            candidates = [self.players[id] for id in resource.players if id in self.players]
            now = time.monotonic()
            candidates.sort(key=lambda candidate: candidate.expires <= now)
            for candidate in candidates:
                await self.check(candidate)
                candidate.expires = time.monotonic() + PLAYER_TTL
                return candidate
        msg = "Playback resource was not found."
        raise PlayerError(msg, 404)

    async def check(self, player: Player, *, shared: bool = False) -> None:
        self._root()
        now = time.monotonic()
        if shared:
            player = next(
                (
                    candidate
                    for id in player.resource.players
                    if (candidate := self.players.get(id)) is not None
                    and candidate.owner == player.owner
                    and candidate.expires > now
                ),
                player,
            )
        if self.players.get(player.id) is not player:
            msg = "Player was closed."
            raise PlayerError(msg, 410)
        if player.expires <= now:
            await self.close(player.id, player.owner)
            msg = "Player has expired."
            raise PlayerError(msg, 410)
        if not self._valid(player.resource):
            player.resource.stale = True
            await self.expire()
            msg = "Media changed. Reopen the player."
            raise PlayerError(msg, 409)

    def select(self, player: Player, audio: object, subtitle: object) -> None:
        probe = player.resource.probe
        assert probe is not None
        if audio is not None and (
            isinstance(audio, bool) or not isinstance(audio, int) or not any(s.index == audio for s in probe.audio)
        ):
            msg = "Unknown audio track."
            raise PlayerError(msg)
        if subtitle is not None and (not isinstance(subtitle, str) or subtitle not in self.tracks(player)):
            msg = "Unknown subtitle track."
            raise PlayerError(msg)
        if subtitle is not None and self.tracks(player)[subtitle]["renderer"] == "unsupported":
            msg = "This subtitle format is not supported."
            raise PlayerError(msg)
        player.audio = audio
        player.subtitle = subtitle

    def tracks(self, player: Player) -> dict[str, dict]:
        resource = player.resource
        probe = resource.probe
        assert probe is not None
        tracks = dict(resource.subtitles)
        for stream in probe.subtitle:
            codec = str(stream.codec())
            tags = getattr(stream, "tags", {})
            ass = codec in {"ass", "ssa"}
            renderer = (
                "bitmap"
                if codec in BITMAP_CODECS
                else "assjs"
                if ass
                else "native"
                if codec in TEXT_CODECS
                else "unsupported"
            )
            id = f"e{stream.index}"
            tracks[id] = {
                "id": id,
                "lang": tags.get("language", "und"),
                "name": tags.get("title") or f"{codec} · {tags.get('language', 'und')}",
                "source_format": codec,
                "delivery_format": "ass" if ass else "vtt",
                "renderer": renderer,
            }
        return tracks

    def fonts(self, player: Player) -> list[FFStream]:
        probe = player.resource.probe
        assert probe is not None
        return [
            s
            for s in probe.attachment
            if str(getattr(s, "tags", {}).get("mimetype", "")).startswith(
                ("font/", "application/x-truetype", "application/vnd.ms-opentype", "application/x-font")
            )
        ][:16]

    def _evict(self, reserve: int) -> None:
        artifacts = [(r, key, a) for r in self.resources.values() for key, a in r.artifacts.items()]
        size = sum(a.size for _, _, a in artifacts)
        count = len(artifacts)
        for resource, key, artifact in sorted(artifacts, key=lambda entry: entry[2].touched):
            if size + reserve + self.jobs * SEGMENT_MAX_BYTES <= MAX_CACHE_BYTES and count + self.jobs < MAX_ARTIFACTS:
                return
            if artifact.pins or key in resource.flights:
                continue
            artifact.file.unlink(missing_ok=True)
            del resource.artifacts[key]
            size -= artifact.size
            count -= 1
        if size + reserve + self.jobs * SEGMENT_MAX_BYTES > MAX_CACHE_BYTES or count + self.jobs >= MAX_ARTIFACTS:
            msg = "Player scratch capacity is full."
            raise PlayerError(msg, 503)

    async def _flight[T](
        self, player: Player, key: tuple, prepare: Callable[[], Awaitable[T]], *, shared: bool = False
    ) -> T:
        resource = player.resource
        flight = resource.flights.get(key)
        if flight is None:
            if self.jobs >= MAX_JOBS:
                msg = "Player preparation is busy."
                raise PlayerError(msg, 503)
            self._evict(SEGMENT_MAX_BYTES)
            self.jobs += 1

            async def work() -> T:
                try:
                    async with asyncio.timeout(300):
                        return await prepare()
                except ProcessExitError:
                    self.closed = True
                    raise
                finally:
                    self.jobs -= 1

            flight = Flight(task=asyncio.create_task(work()))
            resource.flights[key] = flight
        owner = (player.owner, None if shared else player.id)
        flight.owners[owner] = flight.owners.get(owner, 0) + 1
        try:
            result = await asyncio.shield(flight.task)
            if isinstance(result, Artifact):
                result.pins += 1
            return result
        finally:
            count = flight.owners.get(owner, 0) - 1
            if count > 0:
                flight.owners[owner] = count
            else:
                flight.owners.pop(owner, None)
            if not flight.owners and not flight.task.done():
                flight.task.cancel()
                await settle(asyncio.create_task(self._drain([flight.task])))
            if not flight.owners and flight.task.done():
                resource.flights.pop(key, None)

    @asynccontextmanager
    async def artifact(self, player: Player, key: tuple, *, shared: bool = False) -> AsyncGenerator[Artifact]:
        await self.check(player, shared=shared)
        resource = player.resource
        artifact = resource.artifacts.get(key)
        if artifact is None:

            async def prepare() -> Artifact:
                file = await self._prepare(player, key)
                published = False
                try:
                    if not self._valid(resource):
                        msg = "Media changed during preparation."
                        raise PlayerError(msg, 409)
                    content_type = (
                        "video/mpegts"
                        if key[0] == "segment"
                        else "font/ttf"
                        if key[0] == "font"
                        else "text/x-ssa"
                        if file.suffix == ".ass"
                        else "text/vtt"
                    )
                    metadata = None
                    if key[0] == "font":
                        async with await anyio.open_file(file, "rb") as output:
                            metadata = font_metadata(await output.read(FONT_MAX_BYTES + 1))
                    artifact = Artifact(
                        file=file,
                        size=file.stat().st_size,
                        content_type=content_type,
                        touched=time.monotonic(),
                        metadata=metadata,
                    )
                    resource.artifacts[key] = artifact
                    published = True
                    return artifact
                finally:
                    if not published:
                        file.unlink(missing_ok=True)

            artifact = await self._flight(player, key, prepare, shared=shared)
        else:
            artifact.pins += 1
        try:
            await self.check(player, shared=shared)
            artifact.touched = time.monotonic()
            yield artifact
        finally:
            artifact.pins -= 1
            resource.touched = time.monotonic()

    async def _prepare(self, player: Player, key: tuple) -> Path:
        resource = player.resource
        if key[0] == "segment":
            _, index, audio, subtitle = key
            return await Segments(
                index,
                probe=resource.probe,
                audio=audio,
                subtitle=subtitle,
            ).prepare(resource.file, self._root())
        binary = ffmpeg_bin()
        if binary is None:
            msg = "ffmpeg is unavailable."
            raise PlayerError(msg, 503)
        track = self.tracks(player).get(key[1]) if key[0] == "subtitle" else None
        suffix = ".ass" if track and track["renderer"] == "assjs" else ".vtt" if track else ".font"
        with tempfile.NamedTemporaryFile(prefix="prepared-", suffix=suffix, dir=self._root(), delete=False) as output:
            file = Path(output.name)
        complete = False
        try:
            if track:
                if track["renderer"] not in {"native", "assjs"}:
                    msg = "Subtitle requires burn-in."
                    raise PlayerError(msg)
                sidecar = resource.sidecars.get(key[1])
                if sidecar:
                    if sidecar[0].stat().st_size > TEXT_MAX_BYTES:
                        msg = "Subtitle is too large."
                        raise PlayerError(msg)
                    body, _ = await Subtitle().make_delivery(sidecar[0])
                    if len(body.encode()) > TEXT_MAX_BYTES:
                        msg = "Subtitle is too large."
                        raise PlayerError(msg)
                    async with await anyio.open_file(file, "w", encoding="utf-8") as output:
                        await output.write(body)
                    complete = True
                    return file
                args = [
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(resource.file),
                    "-map",
                    f"0:{key[1][1:]}",
                    "-c:s",
                    "copy" if suffix == ".ass" else "webvtt",
                    "-f",
                    "ass" if suffix == ".ass" else "webvtt",
                    "pipe:1",
                ]
                limit = TEXT_MAX_BYTES
            else:
                stream = next((s for s in self.fonts(player) if f"f{s.index}" == key[1]), None)
                if stream is None:
                    msg = "Unknown embedded font."
                    raise PlayerError(msg, 404)
                args = [
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    f"-dump_attachment:{stream.index}",
                    "pipe:1",
                    "-i",
                    str(resource.file),
                    "-t",
                    "0",
                    "-c",
                    "copy",
                    "-f",
                    "null",
                    "-",
                ]
                limit = FONT_MAX_BYTES
            code, _, _ = await run(binary, args, deadline=60, max_bytes=limit, output=file)
            if code != 0 or file.stat().st_size == 0:
                msg = "Unable to prepare the selected track."
                raise PlayerError(msg, 502)
            complete = True
            return file
        except ProcessExitError:
            complete = True
            raise
        finally:
            if not complete:
                file.unlink(missing_ok=True)

    async def close(self, id: str, owner: str) -> None:
        player = self.players.get(id)
        if player is None or player.owner != owner:
            return
        del self.players[id]
        resource = player.resource
        resource.players.discard(id)
        resource.touched = time.monotonic()
        tasks = []
        shared = any(
            candidate.owner == owner for id in resource.players if (candidate := self.players.get(id)) is not None
        )
        for flight in resource.flights.values():
            flight.owners.pop((owner, player.id), None)
            if not shared:
                flight.owners.pop((owner, None), None)
            if not flight.owners and not flight.task.done():
                flight.task.cancel()
                tasks.append(flight.task)
        if tasks:
            await settle(asyncio.create_task(self._drain(tasks)))

    async def _drain(self, tasks: list[asyncio.Task]) -> None:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 25)

    def _drop(self, resource: Resource) -> None:
        if resource.flights or any(a.pins for a in resource.artifacts.values()):
            return
        for artifact in resource.artifacts.values():
            artifact.file.unlink(missing_ok=True)
        self.resources.pop(resource.key, None)

    async def expire(self) -> None:
        now = time.monotonic()
        for player in list(self.players.values()):
            if player.expires <= now or not self._valid(player.resource):
                await self.close(player.id, player.owner)
        for resource in list(self.resources.values()):
            if not resource.players and (not self._valid(resource) or now - resource.touched >= IDLE_TTL):
                self._drop(resource)

    async def shutdown(self, _: web.Application) -> None:
        self.closed = True
        Scheduler.get_instance().remove("player-expiry")
        self.players.clear()
        tasks = []
        for resource in self.resources.values():
            resource.players.clear()
            for flight in resource.flights.values():
                flight.owners.clear()
                if not flight.task.done():
                    flight.task.cancel()
                tasks.append(flight.task)
        if tasks:
            await settle(asyncio.create_task(self._drain(tasks)))
        for resource in self.resources.values():
            resource.flights.clear()
        await self.cleanup(_)

    async def cleanup(self, _: web.Application) -> None:
        for resource in list(self.resources.values()):
            self._drop(resource)
        # Unconfirmed child exits retain their partial output rather than removing a live child's file.
        if self.root is not None and not self.resources and not any(self.root.iterdir()):
            self.root.rmdir()
            self.root = None
