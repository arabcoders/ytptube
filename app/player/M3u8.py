import math
import os
from urllib.parse import quote
from Utils import calcDownloadPath
from .ffprobe import FFProbe


class M3u8:
    ok_vcodecs: tuple = ('h264', 'x264', 'avc',)
    ok_acodecs: tuple = ('aac', 'mp3',)

    url: str = None
    duration: float = 6.000000

    def __init__(self, url: str, segment_duration: float = None):
        self.url = url
        self.duration = float(segment_duration) if segment_duration is not None else self.duration

    async def make_stream(self, download_path: str, file: str):
        realFile: str = calcDownloadPath(basePath=download_path, folder=file, createPath=False)

        if not os.path.exists(realFile):
            raise Exception(f"File '{realFile}' does not exist.")

        try:
            ffprobe = FFProbe(realFile)
            await ffprobe.run()
        except UnicodeDecodeError as e:
            pass

        if not 'duration' in ffprobe.metadata:
            raise Exception(f"Unable to get '{realFile}' duration.")

        duration: float = float(ffprobe.metadata.get('duration'))

        m3u8 = "#EXTM3U\n"
        m3u8 += "#EXT-X-VERSION:3\n"
        m3u8 += f"#EXT-X-TARGETDURATION:{int(self.duration)}\n"
        m3u8 += "#EXT-X-MEDIA-SEQUENCE:0\n"
        m3u8 += "#EXT-X-PLAYLIST-TYPE:VOD\n"

        segmentSize: float = '{:.6f}'.format(self.duration)
        splits: int = math.ceil(duration / self.duration)

        segmentParams: dict = {}

        for stream in ffprobe.streams:
            if stream.is_video():
                if stream.codec_name not in self.ok_vcodecs:
                    segmentParams['vc'] = 1
            if stream.is_audio():
                if stream.codec_name not in self.ok_acodecs:
                    segmentParams['ac'] = 1

        for i in range(splits):
            if (i + 1) == splits:
                segmentParams.update({'sd': '{:.6f}'.format(duration - (i * self.duration))})
                m3u8 += f"#EXTINF:{segmentParams['sd']}, nodesc\n"
            else:
                m3u8 += f"#EXTINF:{segmentSize}, nodesc\n"

            m3u8 += f"{self.url}segments/{i}/{quote(file)}"
            if len(segmentParams) > 0:
                m3u8 += '?'+'&'.join([f"{key}={value}" for key, value in segmentParams.items()])
            m3u8 += "\n"

        m3u8 += "#EXT-X-ENDLIST\n"

        return m3u8

    def parseDuration(self, duration: str):
        if duration.find(':') > -1:
            duration = duration.split(':')
            duration.reverse()
            duration = sum([float(duration[i]) * (60 ** i) for i in range(len(duration))])
        else:
            duration = float(duration)

        return duration
