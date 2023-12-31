import hashlib
import logging
import os
import subprocess
import tempfile
from Utils import calcDownloadPath
from Config import Config

log = logging.getLogger('segments')

class Segments:
    config: Config = None
    download_path: str = None
    segment_duration: int
    segment_index: int
    vconvert: bool
    aconvert: bool

    def __init__(self, config: Config, segment_index: int, segment_duration: float, vconvert: bool, aconvert: bool):
        self.config = config
        self.download_path = self.config.download_path
        self.segment_duration = float(segment_duration)
        self.segment_index = int(segment_index)
        self.vconvert = bool(vconvert)
        self.aconvert = bool(aconvert)

    async def stream(self, file: str) -> bytes:
        realFile: str = calcDownloadPath(
            basePath=self.download_path,
            folder=file,
            createPath=False
        )

        if not os.path.exists(realFile):
            raise Exception(f"File {realFile} does not exist.")

        tmpDir: str = tempfile.gettempdir()
        tmpFile = os.path.join(
            tmpDir, f'ytptube_stream.{hashlib.md5(realFile.encode("utf-8")).hexdigest()}')

        if not os.path.exists(tmpFile):
            os.symlink(realFile, tmpFile)

        if self.segment_index == 0:
            startTime: float = '{:.6f}'.format(0)
        else:
            startTime: float = '{:.6f}'.format(
                (self.segment_duration * self.segment_index
                 ))

        ffmpegCmd = []
        ffmpegCmd.append('ffmpeg')
        ffmpegCmd.append('-xerror')
        ffmpegCmd.append('-hide_banner')
        ffmpegCmd.append('-loglevel')
        ffmpegCmd.append('error')

        ffmpegCmd.append('-ss')
        ffmpegCmd.append(str(startTime if startTime else '0.00000'))
        ffmpegCmd.append('-t')
        ffmpegCmd.append(str('{:.6f}'.format(self.segment_duration)))

        ffmpegCmd.append('-copyts')

        ffmpegCmd.append('-i')
        ffmpegCmd.append(f'file:{tmpFile}')
        ffmpegCmd.append('-map_metadata')
        ffmpegCmd.append('-1')

        ffmpegCmd.append('-pix_fmt')
        ffmpegCmd.append('yuv420p')
        ffmpegCmd.append('-g')
        ffmpegCmd.append('52')

        ffmpegCmd.append('-map')
        ffmpegCmd.append('0:v:0')
        ffmpegCmd.append('-strict')
        ffmpegCmd.append('-2')

        ffmpegCmd.append('-codec:v')
        ffmpegCmd.append('libx264' if self.vconvert else 'copy')
        if self.vconvert:
            ffmpegCmd.append('-crf')
            ffmpegCmd.append('23')
            ffmpegCmd.append('-preset:v')
            ffmpegCmd.append('fast')
            ffmpegCmd.append('-level')
            ffmpegCmd.append('4.1')
            ffmpegCmd.append('-profile:v')
            ffmpegCmd.append('baseline')

        # audio section.
        ffmpegCmd.append('-map')
        ffmpegCmd.append('0:a:0')
        ffmpegCmd.append('-codec:a')
        ffmpegCmd.append('aac' if self.aconvert else 'copy')
        if self.aconvert:
            ffmpegCmd.append('-b:a')
            ffmpegCmd.append('192k')
            ffmpegCmd.append('-ar')
            ffmpegCmd.append('22050')
            ffmpegCmd.append('-ac')
            ffmpegCmd.append('2')

        ffmpegCmd.append('-sn')

        ffmpegCmd.append('-muxdelay')
        ffmpegCmd.append('0')
        ffmpegCmd.append('-f')
        ffmpegCmd.append('mpegts')
        ffmpegCmd.append('pipe:1')

        log.debug(
            f'Streaming {realFile} segment {self.segment_index}.' + ' '.join(ffmpegCmd))
        proc = subprocess.run(ffmpegCmd, stdout=subprocess.PIPE)

        return proc.stdout
