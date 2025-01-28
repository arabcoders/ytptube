import math
import os
from urllib.parse import quote

from .ffprobe import ffprobe
from .Utils import StreamingError, calc_download_path


class M3u8:
    duration: float = 6.000000

    ok_vcodecs: tuple = ("h264", "x264", "avc")
    ok_acodecs: tuple = ("aac", "m4a", "mp3")

    def __init__(self, url: str, segment_duration: float | None = None):
        self.url = url
        self.duration = float(segment_duration) if segment_duration is not None else self.duration

    async def make_stream(self, download_path: str, file: str) -> str:
        realFile: str = calc_download_path(base_path=download_path, folder=file, create_path=False)

        if not os.path.exists(realFile):
            error = f"File '{realFile}' does not exist."
            raise StreamingError(error)

        try:
            ff = await ffprobe(realFile)
        except UnicodeDecodeError:
            pass

        if "duration" not in ff.metadata:
            error = f"Unable to get '{realFile}' play duration."
            raise StreamingError(error)

        duration: float = float(ff.metadata.get("duration"))

        m3u8 = []

        m3u8.append("#EXTM3U")
        m3u8.append("#EXT-X-VERSION:3")
        m3u8.append(f"#EXT-X-TARGETDURATION:{int(self.duration)}")
        m3u8.append("#EXT-X-MEDIA-SEQUENCE:0")
        m3u8.append("#EXT-X-PLAYLIST-TYPE:VOD")

        segmentSize: float = f"{self.duration:.6f}"
        splits: int = math.ceil(duration / self.duration)

        segmentParams: dict = {}

        for stream in ff.streams():
            if stream.is_video() and stream.codec_name not in self.ok_vcodecs:
                segmentParams["vc"] = 1
            if stream.is_audio() and stream.codec_name not in self.ok_acodecs:
                segmentParams["ac"] = 1

        for i in range(splits):
            if (i + 1) == splits:
                segmentSize = f"{duration - (i * self.duration):.6f}"
                segmentParams.update({"sd": segmentSize})

            m3u8.append(f"#EXTINF:{segmentSize},")

            url = f"{self.url}api/player/segments/{i}/{quote(file)}.ts"
            if len(segmentParams) > 0:
                url += "?" + "&".join([f"{key}={value}" for key, value in segmentParams.items()])

            m3u8.append(url)

        m3u8.append("#EXT-X-ENDLIST")

        return "\n".join(m3u8)

    async def make_subtitle(self, download_path: str, file: str, duration: float) -> str:
        realFile: str = calc_download_path(base_path=download_path, folder=file, create_path=False)

        if not os.path.exists(realFile):
            error = f"File '{realFile}' does not exist."
            raise StreamingError(error)

        m3u8 = []

        m3u8.append("#EXTM3U")
        m3u8.append("#EXT-X-VERSION:3")
        m3u8.append(f"#EXT-X-TARGETDURATION:{int(self.duration)}")
        m3u8.append("#EXT-X-MEDIA-SEQUENCE:0")
        m3u8.append("#EXT-X-PLAYLIST-TYPE:VOD")
        m3u8.append(f"#EXTINF:{duration},")
        m3u8.append(f"{self.url}api/player/subtitle/{quote(file)}.vtt")
        m3u8.append("#EXT-X-ENDLIST")

        return "\n".join(m3u8)
