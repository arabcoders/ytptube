import asyncio
import hashlib
import logging
import os
import subprocess  # type: ignore
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from aiohttp import web

from .config import Config
from .ffprobe import ffprobe
from .SegmentEncoders import (
    SUPPORTED_CODECS,
    encoder_fallback_chain,
    get_builder_for_codec,
    has_dri_devices,
    select_encoder,
)

if TYPE_CHECKING:
    from asyncio.subprocess import Process

    from .ffprobe import FFProbeResult
    from .SegmentEncoders import EncoderBuilder

LOG: logging.Logger = logging.getLogger("player.segments")


class Segments:
    """
    Build and stream MPEG-TS segments using ffmpeg with optional on-the-fly
    transcoding. The class can auto-detect an available hardware encoder on the
    first video segment and cache that choice for subsequent segments to avoid
    repeated probing.
    """

    # Cache of selected video encoder across all segment instances
    _cached_vcodec: ClassVar[str | None] = None
    _cache_initialized: ClassVar[bool] = False

    def __init__(self, download_path: str, index: int, duration: float, vconvert: bool, aconvert: bool):
        config: Config = Config.get_instance()
        self.download_path: str = download_path
        "The path where files are downloaded."
        self.index = int(index)
        "The index of the segment."
        self.duration = float(duration)
        "The duration of the segment."
        self.vconvert = bool(vconvert)
        "Whether to convert video."
        self.aconvert = bool(aconvert)
        "Whether to convert audio."

        # Default to configured codec; can be replaced by auto-detection
        self.vcodec: str = config.streamer_vcodec
        "The video codec to use."
        self.acodec: str = config.streamer_acodec
        "The audio codec to use."

        # sadly due to unforeseen circumstances, we have to convert the video for now.
        self.vconvert = True
        "Whether to convert video."
        self.aconvert = True
        "Whether to convert audio."
        self.attempted: set[str] = set()
        "The set of attempted codecs."

    async def build_ffmpeg_args(self, file: Path, s_codec: str) -> list[str]:
        try:
            ff: FFProbeResult = await ffprobe(file)
        except UnicodeDecodeError:
            pass

        tmpFile: Path = Path(tempfile.gettempdir()).joinpath(
            f"ytptube_stream.{hashlib.sha256(str(file).encode()).hexdigest()}"
        )

        if not tmpFile.exists():
            try:
                tmpFile.symlink_to(file, target_is_directory=False)
            except FileExistsError:
                pass

        startTime: str = f"{0:.6f}" if self.index == 0 else f"{self.duration * self.index:.6f}"

        if self.vconvert and ff and hasattr(ff, "has_video") and ff.has_video():
            builder: EncoderBuilder = get_builder_for_codec(s_codec)
            builder_ctx: dict[str, Any] = {
                "is_linux": sys.platform.startswith("linux"),
                "has_dri": has_dri_devices(),
                "vaapi_device": Config.get_instance().vaapi_device,
            }
        else:
            builder = None
            builder_ctx = {}

        # Collect encoder-specific input/global flags that must precede the input
        input_args: list[str] = []
        if builder:
            input_args = builder.input_args(
                {
                    "is_linux": sys.platform.startswith("linux"),
                    "has_dri": has_dri_devices(),
                    "vaapi_device": Config.get_instance().vaapi_device,
                }
            )

        fargs: list[str] = [
            "-xerror",
            "-hide_banner",
            "-loglevel",
            "error",
            # input trimming before the input file
            "-ss",
            str(startTime),
            "-t",
            str(f"{self.duration:.6f}"),
            "-copyts",
            # hardware/global input options must come before -i
            *input_args,
            "-i",
            f"file:{tmpFile}",
            "-map_metadata",
            "-1",
        ]

        v_args: list[str] = []
        if builder:
            v_args = builder.add_video_args(
                ["-g", "52", "-map", "0:v:0", "-strict", "-2"],
                builder_ctx,
            )
        else:
            v_args += ["-codec:v", "copy"]

        fargs += v_args

        if ff and ff.has_audio():
            fargs += ["-map", "0:a:0", "-codec:a", self.acodec if self.aconvert else "copy"]

        fargs += ["-sn", "-muxdelay", "0", "-f", "mpegts", "pipe:1"]
        return fargs

    async def _run(self, resp: web.StreamResponse, file: Path, args: list[str]) -> tuple[bool, int, bool, str]:
        proc: Process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

        client_disconnected_local = False
        wrote_any = False
        stderr_buf = bytearray()

        async def _drain_stderr() -> None:
            try:
                assert proc.stderr is not None
                while True:
                    chunk: bytes = await proc.stderr.read(4096)
                    if not chunk:
                        break
                    stderr_buf.extend(chunk)
            except Exception:
                # best-effort only
                pass

        stderr_task: asyncio.Task[None] = asyncio.create_task(_drain_stderr())

        LOG.debug(f"Streaming '{file}' segment '{self.index}'. ffmpeg: {' '.join(args)}")

        try:
            while True:
                chunk: bytes = await proc.stdout.read(1024 * 64)
                if not chunk:
                    break
                wrote_any = True
                try:
                    await resp.write(chunk)
                except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError, ConnectionError):
                    LOG.warning("Client disconnected or connection reset while writing.")
                    client_disconnected_local = True
                    break
        except asyncio.CancelledError:
            LOG.warning("Client disconnected. Terminating ffmpeg.")
            client_disconnected_local = True
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                LOG.error("ffmpeg process did not terminate in time. Killing it.")
                proc.kill()
            raise
        except ConnectionResetError:
            LOG.warning("Connection reset by peer. Skipping further writes.")
            client_disconnected_local = True
        finally:
            # Ensure process is stopped when client disconnected, to avoid hangs
            if client_disconnected_local:
                proc.terminate()
                try:
                    rc: int = await asyncio.wait_for(proc.wait(), timeout=5)
                except TimeoutError:
                    LOG.error("ffmpeg process did not terminate in time after disconnect. Killing it.")
                    proc.kill()
                    try:
                        rc = await asyncio.wait_for(proc.wait(), timeout=5)
                    except Exception:
                        rc = -1
            else:
                # Normal termination path with a safety timeout
                try:
                    rc = await asyncio.wait_for(proc.wait(), timeout=30)
                except TimeoutError:
                    LOG.error("ffmpeg process wait timed out. Killing it.")
                    proc.kill()
                    try:
                        rc = await asyncio.wait_for(proc.wait(), timeout=5)
                    except Exception:
                        rc = -1
            try:
                await asyncio.wait_for(stderr_task, timeout=1)
            except Exception:
                pass

        return (wrote_any, rc, client_disconnected_local, stderr_buf.decode("utf-8", errors="ignore").strip())

    async def stream(self, file: Path, resp: web.StreamResponse) -> None:
        codec: str = Segments._cached_vcodec if Segments._cache_initialized else self.vcodec
        if not codec or codec not in SUPPORTED_CODECS:
            codec: str = select_encoder(self.vcodec or "")

        LOG.debug(f"Selected video codec '{codec}' for segment streaming.")

        if Segments._cached_vcodec and Segments._cache_initialized:
            codecs: list[str] = [Segments._cached_vcodec]
        else:
            codecs: list[str] = [codec, *list(encoder_fallback_chain(codec))]

        for s_codec in codecs:
            if s_codec in self.attempted:
                continue

            ffmpeg_args: list[str] = await self.build_ffmpeg_args(file, s_codec)
            _, rc, client_disconnected, stderr_text = await self._run(resp, file, ffmpeg_args)

            if 0 == rc:
                Segments._cached_vcodec = s_codec
                Segments._cache_initialized = True
                return

            if client_disconnected:
                return

            if 0 != rc:
                err: str = stderr_text[:500] if stderr_text else "no error output"
                LOG.warning(f"transcoding has failed (cmd={ffmpeg_args}) (rc={rc}): {err}. Trying fallbacks.")
                self.attempted.add(s_codec)
