# flake8: noqa: ARG002
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Protocol

SUPPORTED_CODECS: tuple[str] = ("h264_qsv", "h264_nvenc", "h264_amf", "h264_videotoolbox", "h264_vaapi", "libx264")
"Supported encoder names in order of preference."


def has_dri_devices() -> bool:
    """
    Check if there are any /dev/dri devices.

    Returns:
       bool: True if there are any /dev/dri devices, False otherwise.

    """
    try:
        dri = Path("/dev/dri")
        if not dri.exists() or not dri.is_dir():
            return False

        for _ in dri.iterdir():
            return True

        return False
    except Exception:
        return False


def ffmpeg_encoders() -> set[str]:
    """
    Return a set of available ffmpeg encoders.

    Returns:
        set[str]: A set of available ffmpeg encoder names.

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

    for name in SUPPORTED_CODECS:
        if name in out:
            encoders.add(name)

    return encoders


def select_encoder(configured: str) -> str:
    """
    Select a concrete encoder.

    Args:
        configured (str): The configured encoder name, or empty for auto-detect.

    Returns:
        str: The selected concrete encoder name.

    """
    configured = (configured or "").strip()

    avail: set[str] = ffmpeg_encoders()
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
        return []

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        return [*args, "-codec:v", self.codec_name]


class SoftwareBuilder(_BaseBuilder):
    codec_name = "libx264"

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        return super().add_video_args(["-pix_fmt", "yuv420p", *args])


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
            return ["-hwaccel", "vaapi", "-vaapi_device", str(device)]
        return []

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        ctx = ctx or {}
        new_args: list[str] = list(args)
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        if is_linux and has_dri:
            new_args += [
                # Ensure frames are in VAAPI-compatible format and uploaded
                "-vf",
                "format=nv12,hwupload",
                # Optional quality/preset flags similar to user's working config
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
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        device: str = ctx.get("vaapi_device", "/dev/dri/renderD128")
        if is_linux and has_dri:
            return ["-init_hw_device", f"qsv=hw:{device}", "-filter_hw_device", "hw"]
        return []

    def add_video_args(self, args: list[str], ctx: dict[str, Any] | None = None) -> list[str]:
        ctx = ctx or {}
        new_args: list[str] = list(args)
        is_linux: bool = bool(ctx.get("is_linux", sys.platform.startswith("linux")))
        has_dri: bool = bool(ctx.get("has_dri", False))
        if is_linux and has_dri:
            new_args += [
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=nv12,hwupload=extra_hw_frames=64",
                # Favor widely-supported constant quality path and disable LA
                "-b:v",
                "0",
                "-global_quality",
                "23",
                "-look_ahead",
                "0",
            ]
        return super().add_video_args(new_args)


def get_builder_for_codec(codec: str) -> EncoderBuilder:
    """
    Return an EncoderBuilder instance for the given concrete codec name.

    Args:
        codec (str): The concrete codec name.

    Returns:
        EncoderBuilder: An instance of the corresponding EncoderBuilder.

    """
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
    """
    Return a fallback chain for the given codec.

    Args:
        codec (str): The concrete codec name.

    Returns:
        tuple[str, ...]: A tuple of codec names representing the fallback chain.

    """
    chains: dict[str, list[str]] = {
        "h264_qsv": ["h264_vaapi", "libx264"],
        "h264_vaapi": ["libx264"],
        "h264_nvenc": ["libx264"],
        "h264_amf": ["libx264"],
        "h264_videotoolbox": ["libx264"],
        "libx264": [],
    }

    return chains.get(codec, chains["libx264"])
