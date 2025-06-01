import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path

from aiohttp import web

from .config import Config
from .ffprobe import ffprobe

LOG = logging.getLogger("player.segments")


class Segments:
    def __init__(self, download_path: str, index: int, duration: float, vconvert: bool, aconvert: bool):
        config = Config.get_instance()
        self.download_path = download_path
        self.index = int(index)
        self.duration = float(duration)
        self.vconvert = bool(vconvert)
        self.aconvert = bool(aconvert)
        self.vcodec = config.streamer_vcodec
        self.acodec = config.streamer_acodec
        # sadly due to unforeseen circumstances, we have to convert the video for now.
        self.vconvert = True
        self.aconvert = True

    async def build_ffmpeg_args(self, file: Path) -> list[str]:
        try:
            ff = await ffprobe(file)
        except UnicodeDecodeError:
            pass

        tmpDir = tempfile.gettempdir()
        tmpFile = os.path.join(tmpDir, f"ytptube_stream.{hashlib.sha256(str(file).encode()).hexdigest()}")

        if not os.path.exists(tmpFile):
            os.symlink(file, tmpFile)

        startTime = f"{0:.6f}" if self.index == 0 else f"{self.duration * self.index:.6f}"

        fargs = [
            "-xerror",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(startTime),
            "-t",
            str(f"{self.duration:.6f}"),
            "-copyts",
            "-i",
            f"file:{tmpFile}",
            "-map_metadata",
            "-1",
        ]

        if ff and ff.has_video():
            fargs += [
                "-pix_fmt",
                "yuv420p",
                "-g",
                "52",
                "-map",
                "0:v:0",
                "-strict",
                "-2",
                "-codec:v",
                self.vcodec if self.vconvert else "copy",
            ]

        if ff and ff.has_audio():
            fargs += ["-map", "0:a:0", "-codec:a", self.acodec if self.aconvert else "copy"]

        fargs += ["-sn", "-muxdelay", "0", "-f", "mpegts", "pipe:1"]
        return fargs

    async def stream(self, file: Path, resp: web.StreamResponse):
        ffmpeg_args = await self.build_ffmpeg_args(file)

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            *ffmpeg_args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        client_disconnected = False

        LOG.debug(f"Streaming '{file}' segment '{self.index}'. ffmpeg: {' '.join(ffmpeg_args)}")

        try:
            while True:
                chunk = await proc.stdout.read(1024 * 64)
                if not chunk:
                    break
                try:
                    await resp.write(chunk)
                except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError, ConnectionError):
                    LOG.warning("Client disconnected or connection reset while writing.")
                    client_disconnected = True
                    break
        except asyncio.CancelledError:
            LOG.warning("Client disconnected. Terminating ffmpeg.")
            client_disconnected = True
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                LOG.error("ffmpeg process did not terminate in time. Killing it.")
                proc.kill()
            raise
        except ConnectionResetError:
            LOG.warning("Connection reset by peer. Skipping further writes.")
            client_disconnected = True
        finally:
            if not client_disconnected:
                try:
                    await resp.write_eof()
                except (ConnectionResetError, RuntimeError):
                    LOG.warning("Failed to write EOF; client already disconnected.")
            await proc.wait()
