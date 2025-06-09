from pathlib import Path
from urllib.parse import quote

from .ffprobe import ffprobe
from .Utils import StreamingError, get_file_sidecar


class Playlist:
    _url: str = None

    def __init__(self, download_path: Path, url: str):
        self.url: str = url
        self.download_path: Path = download_path

    async def make(self, file: Path) -> str:
        ref: str = Path(str(file.relative_to(self.download_path)).strip("/"))

        try:
            ff = await ffprobe(file)
        except UnicodeDecodeError:
            pass

        if "duration" not in ff.metadata:
            msg = f"Unable to get '{ref}' duration."
            raise StreamingError(msg)

        playlist: list[str] = []
        playlist.append("#EXTM3U")

        subs: str = ""

        duration: float = float(ff.metadata.get("duration"))
        for sub_file in get_file_sidecar(file).get("subtitle", []):
            lang: str = sub_file["lang"]
            item: Path = sub_file["file"]
            name: str = sub_file["name"]

            subs = ',SUBTITLES="subs"'
            url = f"{self.url}api/player/m3u8/subtitle/{quote(str(ref.with_name(item.name)))}.m3u8?duration={duration}"
            playlist.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="{name}",DEFAULT=NO,AUTOSELECT=NO,FORCED=NO,LANGUAGE="{lang}",URI="{url}"'
            )

        playlist.append(f"#EXT-X-STREAM-INF:PROGRAM-ID=1{subs}")
        playlist.append(f"{self.url}api/player/m3u8/video/{quote(ref)}.m3u8")

        return "\n".join(playlist)
