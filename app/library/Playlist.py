from pathlib import Path
from urllib.parse import quote

from .ffprobe import ffprobe
from .Utils import StreamingError, get_sidecar_subtitles


class Playlist:
    _url: str = None

    def __init__(self, download_path: str, url: str):
        self.url = url
        self.download_path = download_path

    async def make(self, file: Path) -> str:
        ref = str(file).replace(self.download_path, "").strip("/")

        try:
            ff = await ffprobe(file)
        except UnicodeDecodeError:
            pass

        if "duration" not in ff.metadata:
            msg = f"Unable to get '{ref}' duration."
            raise StreamingError(msg)

        playlist = []
        playlist.append("#EXTM3U")

        subs = ""

        duration: float = float(ff.metadata.get("duration"))
        for sub_file in get_sidecar_subtitles(file):
            lang = sub_file["lang"]
            item = sub_file["file"]
            name = sub_file["name"]

            subs = ',SUBTITLES="subs"'
            url = f"{self.url}api/player/m3u8/subtitle/{quote(str(Path(ref).with_name(item.name)))}.m3u8?duration={duration}"
            playlist.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="{name}",DEFAULT=NO,AUTOSELECT=NO,FORCED=NO,LANGUAGE="{lang}",URI="{url}"'
            )

        playlist.append(f"#EXT-X-STREAM-INF:PROGRAM-ID=1{subs}")
        playlist.append(f"{self.url}api/player/m3u8/video/{quote(ref)}.m3u8")

        return "\n".join(playlist)
