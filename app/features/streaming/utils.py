from __future__ import annotations

import asyncio
import math
import os
import shutil
import struct
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

import anyio

from app.features.streaming.library.ffprobe import FFProbeResult, ffmpeg_bin, ffprobe
from app.features.streaming.types import StreamingError
from app.library.config import Config
from app.library.logging import get_logger
from app.library.Utils import timed_lru_cache

if TYPE_CHECKING:
    from asyncio.subprocess import Process

MAX_STDERR = 16 * 1024
SPAWN_TIMEOUT = 5.0
CLEANUP_TIMEOUT = 5.0
MAX_PROCESSES = 8
SEGMENT_DURATION = 6.0
SEGMENT_MAX_BYTES = 16 * 1024 * 1024
ENCODE_AHEAD = 2
_running: set[object] = set()
_pending: set[asyncio.Task] = set()
LOG = get_logger()


class ProcessExitError(StreamingError):
    pass


class PreparationBusyError(StreamingError):
    pass


class SegmentIndexError(StreamingError):
    pass


def segment_window(index: int, duration: float, stride: float = SEGMENT_DURATION) -> tuple[float, float]:
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(stride) or stride <= 0:
        msg = "Media duration must be finite and positive."
        raise StreamingError(msg)
    if duration / stride > 100000:
        msg = "Media duration exceeds the playlist capacity."
        raise StreamingError(msg)
    if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= math.ceil(duration / stride):
        msg_0 = "Segment index is outside the media duration."
        raise SegmentIndexError(msg_0)
    start = index * stride
    return start, min(stride, duration - start)


def font_metadata(data: bytes) -> dict:
    if len(data) < 12 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        msg = "Font family metadata is unavailable."
        raise StreamingError(msg)
    count = struct.unpack_from(">H", data, 4)[0]
    if len(data) < 12 + count * 16:
        msg = "Invalid embedded font."
        raise StreamingError(msg)
    families: list[str] = []
    weight, style = 400, "normal"
    for index in range(count):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + index * 16)
        if offset + length > len(data):
            msg = "Invalid embedded font."
            raise StreamingError(msg)
        table = data[offset : offset + length]
        if tag == b"OS/2" and length >= 64:
            weight = min(1000, max(1, struct.unpack_from(">H", table, 4)[0]))
            style = "italic" if struct.unpack_from(">H", table, 62)[0] & 1 else "normal"
        if tag != b"name" or length < 6:
            continue
        records, strings = struct.unpack_from(">HH", table, 2)
        if length < 6 + records * 12:
            continue
        for record in range(records):
            platform, _, _, name_id, size, start = struct.unpack_from(">HHHHHH", table, 6 + record * 12)
            if name_id not in (1, 16, 4) or strings + start + size > length:
                continue
            raw = table[strings + start : strings + start + size]
            name = raw.decode("utf-16-be" if platform in (0, 3) else "latin-1", errors="replace").strip()
            if name and name not in families:
                families.append(name)
    if not families:
        msg = "Font family metadata is unavailable."
        raise StreamingError(msg)
    return {"families": families[:16], "weight": str(weight), "style": style}


async def settle[T](task: asyncio.Task[T]) -> T:
    # Cleanup owns the child even if its caller is cancelled again.
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()


async def stop(proc: Process) -> None:
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    except OSError as exc:
        msg = "Media child could not be stopped. Scratch output was retained."
        raise ProcessExitError(msg) from exc
    try:
        await asyncio.wait_for(proc.wait(), CLEANUP_TIMEOUT)
    except TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        except OSError as exc:
            msg = "Media child could not be killed. Scratch output was retained."
            raise ProcessExitError(msg) from exc
        try:
            await asyncio.wait_for(proc.wait(), CLEANUP_TIMEOUT)
        except TimeoutError as exc:
            msg = "Media child exit could not be confirmed. Scratch output was retained."
            raise ProcessExitError(msg) from exc


async def _discard(reader: asyncio.StreamReader) -> None:
    while await reader.read(65536):
        pass


async def _stop_acquired(proc: Process) -> None:
    readers = [asyncio.create_task(_discard(reader)) for reader in (proc.stdout, proc.stderr) if reader is not None]
    try:
        await stop(proc)
    finally:
        for reader in readers:
            reader.cancel()
        await _finish(readers)


def _late_spawn(task: asyncio.Task[Process]) -> None:
    _pending.discard(task)
    if task.cancelled():
        return
    try:
        proc = task.result()
    except Exception:
        return
    cleanup = asyncio.create_task(_stop_acquired(proc))
    _pending.add(cleanup)
    cleanup.add_done_callback(_late_cleanup)


def _late_cleanup(task: asyncio.Task[None]) -> None:
    _pending.discard(task)
    if not task.cancelled() and task.exception() is not None:
        LOG.error("Late media child cleanup failed; preparation capacity and scratch output remain reserved.")


async def _abort_spawn(task: asyncio.Task[Process]) -> None:
    try:
        proc = await asyncio.wait_for(asyncio.shield(task), CLEANUP_TIMEOUT)
    except TimeoutError as exc:
        # Keep ownership if acquisition is still unresolved; never remove its scratch output or release its slot.
        _pending.add(task)
        task.add_done_callback(_late_spawn)
        msg = "Media child acquisition could not be confirmed. Scratch output was retained."
        raise ProcessExitError(msg) from exc
    except (Exception, asyncio.CancelledError):
        return
    await _stop_acquired(proc)


async def spawn(binary: str, args: list[str]) -> Process:
    if len(_running) >= MAX_PROCESSES:
        msg = "Media preparation is busy."
        raise PreparationBusyError(msg)
    lease = object()
    _running.add(lease)
    task = asyncio.create_task(
        asyncio.create_subprocess_exec(
            binary,
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    )
    try:
        proc = await asyncio.wait_for(asyncio.shield(task), SPAWN_TIMEOUT)
    except BaseException:
        await settle(asyncio.create_task(_abort_spawn(task)))
        _running.remove(lease)
        raise
    _running.remove(lease)
    _running.add(proc)
    return proc


async def release(proc: Process) -> None:
    await settle(asyncio.create_task(_stop_acquired(proc)))
    _running.discard(proc)


async def run(
    binary: str,
    args: list[str],
    *,
    deadline: float,
    max_bytes: int,
    output: Path | None = None,
) -> tuple[int, bytes, str]:
    if len(_running) >= MAX_PROCESSES:
        msg = "Media preparation is busy."
        raise PreparationBusyError(msg)
    lease = object()
    _running.add(lease)
    release = True
    try:
        return await _run(binary, args, deadline=deadline, max_bytes=max_bytes, output=output)
    except ProcessExitError:
        release = False
        raise
    finally:
        if release:
            _running.remove(lease)


async def _run(
    binary: str,
    args: list[str],
    *,
    deadline: float,
    max_bytes: int,
    output: Path | None = None,
) -> tuple[int, bytes, str]:
    expires = asyncio.get_running_loop().time() + deadline
    spawn = asyncio.create_task(
        asyncio.create_subprocess_exec(
            binary,
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    )
    try:
        proc = await asyncio.wait_for(asyncio.shield(spawn), min(deadline, SPAWN_TIMEOUT))
    except BaseException:
        await settle(asyncio.create_task(_abort_spawn(spawn)))
        raise

    data = bytearray()
    stderr = bytearray()

    async def read_stdout() -> None:
        assert proc.stdout is not None
        size = 0
        if output is not None:
            async with await anyio.open_file(output, "wb") as file:
                while chunk := await proc.stdout.read(65536):
                    size += len(chunk)
                    if size > max_bytes:
                        msg = "Prepared output exceeds the size limit."
                        raise StreamingError(msg)
                    await file.write(chunk)
        else:
            while chunk := await proc.stdout.read(65536):
                if len(data) + len(chunk) > max_bytes:
                    msg = "Media metadata exceeds the size limit."
                    raise StreamingError(msg)
                data.extend(chunk)

    async def read_stderr() -> None:
        assert proc.stderr is not None
        while chunk := await proc.stderr.read(4096):
            stderr.extend(chunk)
            if len(stderr) > MAX_STDERR:
                del stderr[:-MAX_STDERR]

    readers = [asyncio.create_task(read_stdout()), asyncio.create_task(read_stderr())]
    try:
        async with asyncio.timeout_at(expires):
            await asyncio.gather(*readers)
            code = await proc.wait()
        return code, bytes(data), stderr.decode("utf-8", errors="replace")
    finally:
        try:
            await settle(asyncio.create_task(stop(proc)))
        finally:
            for task in readers:
                if not task.done():
                    task.cancel()
            await settle(asyncio.create_task(_finish(readers)))


async def _finish(tasks: list[asyncio.Task]) -> None:
    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), CLEANUP_TIMEOUT)


def binary_key(binary: str) -> tuple[str, int, int, int, int, int]:
    info = Path(binary).stat()
    return binary, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


async def detect_qsv_capabilities() -> dict[str, dict[str, bool]]:
    vainfo = shutil.which("vainfo")
    if not vainfo:
        return {}

    return await _qsv(binary_key(vainfo))


@timed_lru_cache(ttl_seconds=300, max_size=8)
async def _qsv(key: tuple[str, int, int, int, int, int]) -> dict[str, dict[str, bool]]:
    try:
        _, data, error = await run(key[0], [], deadline=5, max_bytes=256 * 1024)
        out = data.decode("utf-8", errors="replace") + error
    except (PreparationBusyError, ProcessExitError):
        raise
    except (OSError, TimeoutError, StreamingError):
        return {}

    caps: dict[str, dict[str, bool]] = {}
    for line in out.splitlines():
        line: str = line.strip()
        parts: list[str] = line.split(":")
        if len(parts) < 2:
            continue
        prof, ep_str = parts[0].strip(), parts[1].strip()
        if "H264" in prof:
            codec = "h264"
        elif "HEVC" in prof:
            codec = "hevc"
        elif "VP9" in prof:
            codec = "vp9"
        else:
            continue
        if codec not in caps:
            caps[codec] = {"full": False, "lp": False}

        if "EncSlice " in ep_str:
            caps[codec]["full"] = True

        if "EncSliceLP" in ep_str:
            caps[codec]["lp"] = True

    return caps


@lru_cache(maxsize=1)
def has_dri_devices() -> bool:
    try:
        dri = Path("/dev/dri")
        if not dri.exists() or not dri.is_dir():
            return False

        for _ in dri.iterdir():
            return True

        return False
    except Exception:
        return False


async def ffmpeg_encoders() -> set[str]:
    ffmpeg = ffmpeg_bin()
    if not ffmpeg:
        return set()

    return await _encoders(binary_key(ffmpeg))


@timed_lru_cache(ttl_seconds=300, max_size=8)
async def _encoders(key: tuple[str, int, int, int, int, int]) -> set[str]:
    from app.library.config import SUPPORTED_CODECS

    try:
        _, data, error = await run(
            key[0], ["-hide_banner", "-loglevel", "error", "-encoders"], deadline=5, max_bytes=256 * 1024
        )
        out = data.decode("utf-8", errors="replace") + error
    except (PreparationBusyError, ProcessExitError):
        raise
    except (OSError, TimeoutError, StreamingError):
        return set()

    encoders: set[str] = set()

    if not out:
        return encoders

    for name in SUPPORTED_CODECS:
        if name in out:
            encoders.add(name)

    return encoders


async def select_encoder(configured: str) -> str:
    from app.library.config import SUPPORTED_CODECS

    configured = (configured or "").strip()

    avail: set[str] = await ffmpeg_encoders()
    if configured and configured in avail:
        return configured

    for name in SUPPORTED_CODECS:
        if name in avail:
            return name

    return "libx264"


class EncoderBuilder(Protocol):
    def input_args(self, ctx: dict[str, Any] | None = None) -> list[str]:
        """Encoder-specific input/global args that must appear before '-i'."""

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        """Append encoder-specific video/output args and return the list."""


class _BaseBuilder:
    codec_name: str

    def input_args(self, ctx: dict[str, Any] | None = None) -> list[str]:
        _ = ctx
        return []

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        _ = ctx
        return [*args, "-codec:v", self.codec_name]


class SoftwareBuilder(_BaseBuilder):
    codec_name = "libx264"

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        return super().add_video_args(["-pix_fmt", "yuv420p", *args], ctx)


class NvencBuilder(_BaseBuilder):
    codec_name = "h264_nvenc"


class AmfBuilder(_BaseBuilder):
    codec_name = "h264_amf"


class AppleVideoToolboxBuilder(_BaseBuilder):
    codec_name = "h264_videotoolbox"


class VaapiBuilder(_BaseBuilder):
    codec_name = "h264_vaapi"

    def input_args(self, ctx: dict[str, Any] | None = None) -> list[str]:
        ctx = ctx or {}
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        device: str = ctx.get("vaapi_device", "/dev/dri/renderD128")
        if is_linux and has_dri:
            if ctx.get("software_decode"):
                return ["-vaapi_device", str(device)]
            return ["-hwaccel", "vaapi", "-vaapi_device", str(device)]
        return []

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        ctx = ctx or {}
        new_args: list[str] = list(args)
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        if is_linux and has_dri:
            new_args += [
                "-vf",
                "format=nv12,hwupload",
                "-crf",
                "23",
                "-preset:v",
                "fast",
                "-level",
                "4.1",
                "-profile:v",
                "main",
            ]
        return super().add_video_args(new_args)


class QsvBuilder(_BaseBuilder):
    codec_name = "h264_qsv"

    def input_args(self, ctx: dict[str, Any] | None = None) -> list[str]:
        ctx = ctx or {}
        args = []
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        device: str = ctx.get("vaapi_device", "/dev/dri/renderD128")
        if is_linux and has_dri:
            if ctx.get("software_decode"):
                return ["-init_hw_device", f"qsv=hw:{device}", "-filter_hw_device", "hw"]
            args: list[str] = [
                "-init_hw_device",
                f"qsv=hw:{device}",
                "-hwaccel",
                "qsv",
                "-hwaccel_output_format",
                "qsv",
                "-filter_hw_device",
                "hw",
            ]

        return args

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        ctx = ctx or {}
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        if is_linux and has_dri:
            if ctx.get("qsv", {}).get("full", False):
                return [
                    *args,
                    "-vf",
                    "vpp_qsv=w=trunc(iw/2)*2:h=trunc(ih/2)*2:format=nv12",
                    "-codec:v",
                    self.codec_name,
                    "-global_quality",
                    "24",
                    "-rc_mode",
                    "cqp",
                ]
            return [
                *args,
                "-vf",
                "vpp_qsv=w=trunc(iw/2)*2:h=trunc(ih/2)*2:format=nv12",
                "-codec:v",
                self.codec_name,
                "-low_power",
                "1",
                "-rc_mode",
                "cbr",
                "-b:v",
                "3M",
                "-maxrate",
                "3M",
                "-bufsize",
                "6M",
            ]

        return super().add_video_args(args, ctx)


def get_builder_for_codec(codec: str) -> EncoderBuilder:
    soft = SoftwareBuilder()
    return {
        "libx264": soft,
        "h264_nvenc": NvencBuilder(),
        "h264_amf": AmfBuilder(),
        "h264_qsv": QsvBuilder(),
        "h264_videotoolbox": AppleVideoToolboxBuilder(),
        "h264_vaapi": VaapiBuilder(),
    }.get(codec, soft)


def encoder_fallback_chain(codec: str) -> tuple[str, ...]:
    chains: dict[str, list[str]] = {
        "h264_qsv": ["h264_vaapi", "libx264"],
        "h264_vaapi": ["libx264"],
        "h264_nvenc": ["libx264"],
        "h264_amf": ["libx264"],
        "h264_videotoolbox": ["libx264"],
        "libx264": [],
    }

    return tuple(chains.get(codec, chains["libx264"]))


class Segments:
    _encoders: ClassVar[dict[tuple, tuple[str, float]]] = {}

    def __init__(
        self,
        index: int,
        *,
        probe: FFProbeResult | None = None,
        audio: int | None = None,
        subtitle: int | None = None,
    ):
        config = Config.get_instance()
        self.index = index
        self.probe = probe
        self.audio = audio
        self.subtitle = subtitle
        self.acodec = config.streamer_acodec

    async def build_ffmpeg_args(self, file: Path, s_codec: str) -> list[str]:
        ff = self.probe or await ffprobe(file)
        duration = float(ff.metadata["duration"])
        start, _ = segment_window(self.index, duration)
        if self.audio is not None and not any(stream.index == self.audio for stream in ff.audio):
            msg = "Unknown audio stream."
            raise StreamingError(msg)
        if self.subtitle is not None and not any(stream.index == self.subtitle for stream in ff.subtitle):
            msg = "Unknown subtitle stream."
            raise StreamingError(msg)
        ctx = {
            "is_linux": sys.platform.startswith("linux"),
            "has_dri": has_dri_devices(),
            "vaapi_device": Config.get_instance().vaapi_device,
            "qsv": {},
        }
        if "qsv" in s_codec:
            caps = await detect_qsv_capabilities()
            ctx["qsv"] = caps.get("h264", {"full": False, "lp": False})
        builder = get_builder_for_codec(s_codec) if ff.has_video() else None
        video_index = ff.video[0].index if ff.has_video() else None
        bitmap = self.subtitle is not None and ff.has_video()
        ctx["software_decode"] = bitmap
        input_args = builder.input_args(ctx) if builder else []
        args = [
            "-xerror",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.6f}",
            "-t",
            f"{duration - start:.6f}",
            "-readrate",
            "1",
            "-readrate_initial_burst",
            f"{SEGMENT_DURATION * (ENCODE_AHEAD + 1):.6f}",
            *input_args,
            "-i",
            f"file:{file}",
            "-map_metadata",
            "-1",
        ]
        if builder:
            video = [
                "-flags",
                "+cgop",
                "-bf",
                "0",
                "-force_key_frames",
                f"expr:gte(t,n_forced*{SEGMENT_DURATION:.6f})",
            ]
            if s_codec == "libx264":
                video += ["-x264-params", "open-gop=0:scenecut=0"]
            elif s_codec == "h264_nvenc":
                video += ["-forced-idr", "1"]
            if bitmap:
                video_args = builder.add_video_args(video, ctx)
                filters = "overlay"
                if "-vf" in video_args:
                    offset = video_args.index("-vf")
                    filter_args = video_args[offset + 1]
                    del video_args[offset : offset + 2]
                    if "qsv" in s_codec:
                        filters += ",format=nv12,hwupload"
                    filters += f",{filter_args}"
                args += [
                    "-filter_complex",
                    f"[0:{video_index}][0:{self.subtitle}]{filters}[v]",
                    "-map",
                    "[v]",
                    *video_args,
                ]
            else:
                args += builder.add_video_args([*video, "-map", f"0:{video_index}", "-strict", "-2"], ctx)
        if ff.has_audio():
            default = next(
                (stream for stream in ff.audio if getattr(stream, "disposition", {}).get("default")), ff.audio[0]
            )
            args += ["-map", f"0:{self.audio if self.audio is not None else default.index}", "-codec:a", self.acodec]
        return [
            *args,
            "-sn",
            "-dn",
            "-output_ts_offset",
            f"{start:.6f}",
            "-f",
            "hls",
            "-hls_time",
            f"{SEGMENT_DURATION:.6f}",
            "-hls_list_size",
            "2",
            "-hls_flags",
            "single_file+independent_segments",
            "-hls_segment_filename",
            "pipe:1",
            "pipe:2",
        ]
