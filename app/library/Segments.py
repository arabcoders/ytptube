import asyncio
import hashlib
import logging
import os
import tempfile

from .ffprobe import ffprobe
from .config import Config
from .Utils import calcDownloadPath, StreamingError

LOG = logging.getLogger("player.segments")


class Segments:
    def __init__(self, index: int, duration: float, vconvert: bool, aconvert: bool):
        config = Config.get_instance()
        self.index = int(index)
        self.duration = float(duration)
        self.vconvert = bool(vconvert)
        self.aconvert = bool(aconvert)
        self.vcodec = config.streamer_vcodec
        self.acodec = config.streamer_acodec
        # sadly due to unforeseen circumstances, we have to convert the video for now.
        self.vconvert = True
        self.aconvert = True

    async def stream(self, path: str, file: str) -> bytes:
        realFile: str = calcDownloadPath(basePath=path, folder=file, createPath=False)

        if not os.path.exists(realFile):
            raise StreamingError(f"File {realFile} does not exist.")

        try:
            ff = await ffprobe(realFile)
        except UnicodeDecodeError:
            pass

        tmpDir: str = tempfile.gettempdir()
        tmpFile = os.path.join(tmpDir, f'ytptube_stream.{hashlib.md5(realFile.encode("utf-8")).hexdigest()}')

        if not os.path.exists(tmpFile):
            os.symlink(realFile, tmpFile)

        if self.index == 0:
            startTime: float = "{:.6f}".format(0)
        else:
            startTime: float = "{:.6f}".format((self.duration * self.index))

        fargs = []
        fargs.append("-xerror")
        fargs.append("-hide_banner")
        fargs.append("-loglevel")
        fargs.append("error")

        fargs.append("-ss")
        fargs.append(str(startTime if startTime else "0.00000"))
        fargs.append("-t")
        fargs.append(str("{:.6f}".format(self.duration)))

        fargs.append("-copyts")

        fargs.append("-i")
        fargs.append(f"file:{tmpFile}")
        fargs.append("-map_metadata")
        fargs.append("-1")

        # video section.
        if ff.has_video():
            fargs.append("-pix_fmt")
            fargs.append("yuv420p")
            fargs.append("-g")
            fargs.append("52")

            fargs.append("-map")
            fargs.append("0:v:0")
            fargs.append("-strict")
            fargs.append("-2")

            fargs.append("-codec:v")
            fargs.append(self.vcodec if self.vconvert else "copy")

        # audio section.
        if ff.has_audio():
            fargs.append("-map")
            fargs.append("0:a:0")
            fargs.append("-codec:a")
            fargs.append(self.acodec if self.aconvert else "copy")

        fargs.append("-sn")

        fargs.append("-muxdelay")
        fargs.append("0")
        fargs.append("-f")
        fargs.append("mpegts")
        fargs.append("pipe:1")

        LOG.debug(f"Streaming '{realFile}' segment '{self.index}'. ffmpeg: {' '.join(fargs)}")

        proc = await asyncio.subprocess.create_subprocess_exec(
            "ffmpeg",
            *fargs,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        data, err = await proc.communicate()

        if 0 != proc.returncode:
            LOG.error(f'Failed to stream {realFile} segment {self.index}. {err.decode("utf-8")}.')
            raise StreamingError(f"Failed to stream {realFile} segment {self.index}.")

        return data
