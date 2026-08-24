"""
Python wrapper for ffprobe command line tool. ffprobe must exist in the path.
"""

import asyncio
import functools
import json
import operator
import os
import shutil
import subprocess  # qa: ignore
from functools import lru_cache
from pathlib import Path

from app.features.streaming.types import FFProbeError
from app.library.logging import get_logger
from app.library.Utils import timed_lru_cache

LOG = get_logger()
FFPROBE_TIMEOUT = 30.0
PROCESS_CLEANUP_TIMEOUT = 5.0


@lru_cache(maxsize=1)
def ffprobe_bin() -> str | None:
    """
    Return the resolved path of the ffprobe binary, or None if unavailable.
    """
    return shutil.which("ffprobe")


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str | None:
    """
    Return the resolved path of the ffmpeg binary, or None if unavailable.
    """
    return shutil.which("ffmpeg")


class FFStream:
    def __init__(self, json_data: dict):
        for key, val in json_data.items():
            setattr(self, key, val)

        try:
            self.__dict__["framerate"] = round(
                functools.reduce(operator.truediv, map(int, self.__dict__.get("avg_frame_rate", "").split("/")))
            )
        except ValueError:
            self.__dict__["framerate"] = None
        except ZeroDivisionError:
            self.__dict__["framerate"] = 0

    def __repr__(self):
        if "codec_long_name" not in self.__dict__:
            self.__dict__["codec_long_name"] = self.__dict__.get("codec_name", "")

        index = self.__dict__.get("index", "?")
        codec_type = self.__dict__.get("codec_type", "unknown")
        codec_long_name = self.__dict__.get("codec_long_name", "")

        if self.is_video():
            return f"<Stream: #{index} [{codec_type}] {codec_long_name}, {self.__dict__.get('framerate')}, ({self.__dict__.get('width')}x{self.__dict__.get('height')})>"

        if self.is_audio():
            return (
                f"<Stream: #{index} [{codec_type}] {codec_long_name}, "
                f"channels: {self.__dict__.get('channels')} ({self.__dict__.get('channel_layout')}), "
                f"{self.__dict__.get('sample_rate')}Hz> "
            )

        if self.is_subtitle() or self.is_attachment():
            return f"<Stream: #{index} [{codec_type}] {codec_long_name}>"

        return f"<Stream: #{index} [{codec_type}]>"

    def is_audio(self):
        return self.__dict__.get("codec_type", None) == "audio"

    def is_video(self):
        if self.__dict__.get("codec_type", None) != "video":
            return False

        return self.__dict__.get("codec_name", None) not in ["png", "mjpeg", "gif", "bmp", "tiff", "webp"]

    def is_subtitle(self):
        return self.__dict__.get("codec_type", None) == "subtitle"

    def is_attachment(self):
        return self.__dict__.get("codec_type", None) == "attachment"

    def frame_size(self):
        """
        Returns the pixel frame size as an integer tuple (width,height) if the stream is a video stream.
        Returns None if it is not a video stream.
        """
        size = None
        if self.is_video():
            width = self.__dict__["width"]
            height = self.__dict__["height"]

            if width and height:
                try:
                    size = (int(width), int(height))
                except ValueError as e:
                    msg = f"None integer size {width}:{height}"
                    raise FFProbeError(msg) from e
        else:
            return None

        return size

    def pixel_format(self):
        """
        Returns a string representing the pixel format of the video stream. e.g. yuv420p.
        Returns none is it is not a video stream.
        """
        return self.__dict__.get("pix_fmt", None)

    def frames(self):
        """
        Returns the length of a video stream in frames. Returns 0 if not a video stream.
        """
        if self.is_video() or self.is_audio():
            try:
                frame_count = int(self.__dict__.get("nb_frames", ""))
            except ValueError as e:
                msg = "None integer frame count"
                raise FFProbeError(msg) from e
        else:
            frame_count = 0

        return frame_count

    def duration_seconds(self):
        """
        Returns the runtime duration of the video stream as a floating point number of seconds.
        Returns 0.0 if not a video stream.
        """
        if self.is_video() or self.is_audio():
            try:
                duration = float(self.__dict__.get("duration", ""))
            except ValueError as e:
                msg = "None numeric duration"
                raise FFProbeError(msg) from e
        else:
            duration = 0.0

        return duration

    def language(self):
        return self.__dict__.get("TAG:language", None)

    def codec(self):
        return self.__dict__.get("codec_name", None)

    def codec_description(self):
        return self.__dict__.get("codec_long_name", None)

    def codec_tag(self):
        return self.__dict__.get("codec_tag_string", None)

    def bit_rate(self):
        """
        Returns bit_rate as an integer in bps
        """
        try:
            return int(self.__dict__.get("bit_rate", ""))
        except ValueError as e:
            msg = "None integer bit_rate"
            raise FFProbeError(msg) from e


class FFProbeResult:
    def __init__(self):
        self.metadata: dict = {}
        self.video: list[FFStream] = []
        self.audio: list[FFStream] = []
        self.subtitle: list[FFStream] = []
        self.attachment: list[FFStream] = []

    @property
    def is_video(self):
        return self.has_video()

    @property
    def is_audio(self):
        return self.has_audio()

    def get(self, key: str, default=None):
        return getattr(self, key) if hasattr(self, key) else default

    def streams(self) -> list[FFStream]:
        return self.video + self.audio + self.subtitle + self.attachment

    def has_video(self):
        return len(self.video) > 0

    def has_audio(self):
        return len(self.audio) > 0

    def has_subtitle(self):
        return len(self.subtitle) > 0

    def __repr__(self):
        return "<FFprobe: {metadata}, {video}, {audio}, {subtitle}, {attachment}>".format(**vars(self))

    def deserialize(self, data: dict):
        self.metadata = data.get("metadata", {})
        self.video = [FFStream(v) for v in data.get("video", [])]
        self.audio = [FFStream(a) for a in data.get("audio", [])]
        self.subtitle = [FFStream(s) for s in data.get("subtitle", [])]
        self.attachment = [FFStream(a) for a in data.get("attachment", [])]

    def serialize(self) -> dict:
        return {
            "metadata": self.metadata,
            "video": [v.__dict__ for v in self.video],
            "audio": [a.__dict__ for a in self.audio],
            "subtitle": [s.__dict__ for s in self.subtitle],
            "attachment": [a.__dict__ for a in self.attachment],
            "is_video": self.has_video(),
            "is_audio": self.has_audio(),
        }


@timed_lru_cache(ttl_seconds=300, max_size=128)
async def ffprobe(file: Path | str) -> FFProbeResult:
    """
    Run ffprobe on a file and return the parsed data as a dictionary.

    Args:
        file (str): The path to the media file.

    Returns:
        dict: A dictionary containing the parsed data.

    """
    f = Path(file) if isinstance(file, str) else file

    if not f.exists():
        msg = f"No such media file '{file}'."
        raise OSError(msg)

    binary = ffprobe_bin()
    if binary is None:
        msg = "ffprobe not found."
        raise FFProbeError(msg)

    args: list[str] = ["-v", "quiet", "-of", "json", "-show_streams", "-show_format", str(f)]

    p = await asyncio.create_subprocess_exec(
        binary,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    try:
        data, err = await asyncio.wait_for(p.communicate(), timeout=FFPROBE_TIMEOUT)
    except (TimeoutError, asyncio.CancelledError):
        p.kill()
        try:
            await asyncio.wait_for(asyncio.shield(p.communicate()), timeout=PROCESS_CLEANUP_TIMEOUT)
        except (TimeoutError, asyncio.CancelledError, OSError):
            LOG.warning("ffprobe did not finish cleanup.")
        raise
    if not isinstance(p.returncode, int):
        msg = "ffprobe exited without a return code."
        raise FFProbeError(msg)
    exitCode: int = p.returncode
    if 0 == exitCode:
        parsed: dict = json.loads(data.decode("utf-8"))
    else:
        msg: str = f"ffprobe returned with non-0 exit code. '{err.decode('utf-8')}'"
        raise FFProbeError(msg)

    result = FFProbeResult()
    result.metadata = parsed.get("format", {})

    for raw_stream in parsed.get("streams", []):
        stream = FFStream(raw_stream)
        if stream.is_audio():
            result.audio.append(stream)
        elif stream.is_video():
            result.video.append(stream)
        elif stream.is_subtitle():
            result.subtitle.append(stream)
        elif stream.is_attachment():
            result.attachment.append(stream)

    return result
