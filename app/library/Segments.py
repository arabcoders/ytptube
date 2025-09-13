import asyncio
import hashlib
import logging
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from aiohttp import web

from .config import Config
from .ffprobe import ffprobe

if TYPE_CHECKING:
    from asyncio.subprocess import Process

    from app.library.ffprobe import FFProbeResult

LOG: logging.Logger = logging.getLogger("player.segments")


class Segments:
    """
    Build and stream MPEG-TS segments using ffmpeg with optional on-the-fly
    transcoding. The class can auto-detect an available hardware encoder on the
    first video segment and cache that choice for subsequent segments to avoid
    repeated probing.

    Supported encoder families (preference order):
      - amd      -> h264_amf
      - nvidia   -> h264_nvenc
      - intel    -> h264_qsv
      - apple    -> h264_videotoolbox
      - software -> libx264
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

    @staticmethod
    def _encoder_map() -> dict[str, str]:
        """Return mapping from logical encoder family to ffmpeg codec name."""
        return {
            "intel": "h264_qsv",
            "nvidia": "h264_nvenc",
            "amd": "h264_amf",
            "apple": "h264_videotoolbox",
            "software": "libx264",
        }

    @staticmethod
    def _preferred_families(configured: str) -> list[str]:
        """
        Build a preference list based on configuration value.

        Accepts either a logical family name (amd|nvidia|intel|apple|software),
        a concrete ffmpeg encoder (e.g., h264_nvenc/libx264), or any other
        string. If the value is not recognized, we try GPU families first and
        fall back to software.
        """
        families: list[str] = ["intel", "nvidia", "amd", "apple", "software"]
        enc_map: dict[str, str] = Segments._encoder_map()

        # If user configured a concrete ffmpeg encoder, prioritize that and
        # include software as fallback.
        if configured in enc_map.values():
            # Map concrete to a family for consistent probing order
            family: str | None = next((k for k, v in enc_map.items() if v == configured), None)
            return [family, "software"] if family else ["software"]

        cfg_lower: str = configured.strip().lower()
        if cfg_lower in enc_map:
            # Specific family requested; then software fallback
            return [cfg_lower, "software"]

        # Unknown/legacy value (e.g., libx264 default): try GPUs first, then software
        return families

    @staticmethod
    def _ffmpeg_encoders() -> set[str]:
        """
        Return a set of available ffmpeg encoder names by parsing
        `ffmpeg -encoders` output. On any error, return an empty set to signal
        that probing failed (callers should fall back to software).
        """
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-encoders"],  # noqa: S607
                capture_output=True,
                text=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            out: str = (result.stdout or "") + (result.stderr or "")
        except Exception:
            return set()

        encoders: set[str] = set()
        if not out:
            return encoders

        # Each encoder appears as a token in the list; match known names
        for name in Segments._encoder_map().values():
            if name in out:
                encoders.add(name)

        return encoders

    @staticmethod
    def _select_encoder(preferred: Iterable[str]) -> str:
        """
        Select the first available encoder according to the preferred family
        order. Falls back to software if probing fails or none found.
        """
        enc_map: dict[str, str] = Segments._encoder_map()

        # Only on Linux, if no /dev/dri device, fall back to software.
        # On macOS/Windows, this check is not applicable.
        if sys.platform.startswith("linux") and not Segments._has_dri_devices():
            return enc_map["software"]

        available: set[str] = Segments._ffmpeg_encoders()

        # If probing failed, prefer software to minimize failure risk
        if not available:
            return enc_map["software"]

        for family in preferred:
            name: str | None = enc_map.get(family)
            if name and name in available:
                return name

        # Final fallback
        return enc_map["software"]

    @staticmethod
    def _has_dri_devices() -> bool:
        """Check if /dev/dri exists and has entries (card0, renderD128, etc)."""
        try:
            dri = Path("/dev/dri")
            if not dri.exists() or not dri.is_dir():
                return False
            for _ in dri.iterdir():
                return True
            return False
        except Exception:
            return False

    async def build_ffmpeg_args(self, file: Path) -> list[str]:
        try:
            ff: FFProbeResult = await ffprobe(file)
        except UnicodeDecodeError:
            pass

        tmpFile: Path = Path(tempfile.gettempdir()).joinpath(
            f"ytptube_stream.{hashlib.sha256(str(file).encode()).hexdigest()}"
        )

        if not tmpFile.exists():
            tmpFile.symlink_to(file, target_is_directory=False)

        startTime: str = f"{0:.6f}" if self.index == 0 else f"{self.duration * self.index:.6f}"

        fargs: list[str] = [
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

        # Decide on encoder for the first segment that actually has video
        if ff and hasattr(ff, "has_video") and ff.has_video():
            # Initialize cached encoder only once, on first video segment
            if not Segments._cache_initialized and self.index == 0 and self.vconvert:
                preferred: list[str] = Segments._preferred_families(self.vcodec)
                Segments._cached_vcodec = Segments._select_encoder(preferred)
                Segments._cache_initialized = True
                self.vcodec = Segments._cached_vcodec
                LOG.info(f"Selected streaming video encoder: {self.vcodec}")
            elif Segments._cache_initialized and Segments._cached_vcodec:
                self.vcodec = Segments._cached_vcodec

            # Base video args
            v_args: list[str] = [
                "-g",
                "52",
                "-map",
                "0:v:0",
                "-strict",
                "-2",
            ]

            # For hardware encoders, avoid forcing pix_fmt yuv420p.
            if self.vconvert:
                if self.vcodec in ("h264_nvenc", "h264_amf", "h264_videotoolbox"):
                    # Let ffmpeg pick appropriate conversions; do not force pix_fmt
                    pass
                elif self.vcodec == "h264_qsv":
                    # On Linux with /dev/dri present, initialize QSV device and ensure
                    # frames are properly aligned and uploaded to GPU.
                    if sys.platform.startswith("linux") and Segments._has_dri_devices():
                        v_args += [
                            "-init_hw_device",
                            "qsv=hw:/dev/dri/renderD128",
                            "-filter_hw_device",
                            "hw",
                            "-vf",
                            "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=nv12,hwupload=extra_hw_frames=64",
                        ]
                else:
                    # Software path: ensure broad compatibility
                    v_args = ["-pix_fmt", "yuv420p", *v_args]

            v_args += ["-codec:v", self.vcodec if self.vconvert else "copy"]
            fargs += v_args

        if ff and ff.has_audio():
            fargs += ["-map", "0:a:0", "-codec:a", self.acodec if self.aconvert else "copy"]

        fargs += ["-sn", "-muxdelay", "0", "-f", "mpegts", "pipe:1"]
        return fargs

    async def stream(self, file: Path, resp: web.StreamResponse):
        ffmpeg_args: list[str] = await self.build_ffmpeg_args(file)

        async def _run_and_stream(args: list[str]) -> tuple[bool, int, bool, str]:
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
                        chunk = await proc.stderr.read(4096)
                        if not chunk:
                            break
                        stderr_buf.extend(chunk)
                except Exception:
                    # best-effort only
                    pass

            stderr_task = asyncio.create_task(_drain_stderr())

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

        wrote, rc, client_disconnected, stderr_text = await _run_and_stream(ffmpeg_args)

        is_software: bool = self.vcodec == Segments._encoder_map()["software"]
        if not is_software and not wrote and rc != 0 and not client_disconnected:
            msg: str = stderr_text[:500] if stderr_text else "no error output"
            LOG.warning(f"Hardware encoder failed (rc={rc}): {msg}. Retrying with software (libx264).")
            Segments._cached_vcodec = Segments._encoder_map()["software"]
            Segments._cache_initialized = True

            sw_args: list[str] = list(ffmpeg_args)
            # Replace codec with software
            try:
                idx: int = sw_args.index("-codec:v")
                sw_args[idx + 1] = Segments._encoder_map()["software"]
            except ValueError:
                sw_args += ["-codec:v", Segments._encoder_map()["software"]]

            # Remove QSV-specific flags if present prior to software fallback.
            # -init_hw_device qsv=...
            try:
                while True:
                    i_idx = sw_args.index("-init_hw_device")
                    del sw_args[i_idx : min(i_idx + 2, len(sw_args))]
            except ValueError:
                pass
            # -filter_hw_device <name>
            try:
                while True:
                    f_idx = sw_args.index("-filter_hw_device")
                    del sw_args[f_idx : min(f_idx + 2, len(sw_args))]
            except ValueError:
                pass
            # -vf QSV chain
            try:
                vf_idx = sw_args.index("-vf")
                if (
                    vf_idx + 1 < len(sw_args)
                    and sw_args[vf_idx + 1]
                    == "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=nv12,hwupload=extra_hw_frames=64"
                ):
                    del sw_args[vf_idx : vf_idx + 2]
            except ValueError:
                pass

            # Ensure software path uses yuv420p
            if "-pix_fmt" in sw_args:
                try:
                    pf_idx = sw_args.index("-pix_fmt")
                    if pf_idx + 1 < len(sw_args):
                        sw_args[pf_idx + 1] = "yuv420p"
                except Exception:
                    pass
            else:
                # Insert near the start, before mapping/gop where possible
                insert_pos = 0
                if "-g" in sw_args:
                    insert_pos = max(0, sw_args.index("-g") - 2)
                sw_args[insert_pos:insert_pos] = ["-pix_fmt", "yuv420p"]

            wrote, rc, client_disconnected, _ = await _run_and_stream(sw_args)

        if not client_disconnected:
            try:
                await resp.write_eof()
            except (ConnectionResetError, RuntimeError):
                LOG.warning("Failed to write EOF; client already disconnected.")
