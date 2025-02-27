from pathlib import Path
from urllib.parse import quote

from aiohttp.web import HTTPFound, Response

from .ffprobe import ffprobe
from .Utils import StreamingError, calc_download_path, check_id, get_sidecar_subtitles


class Playlist:
    _url: str = None

    def __init__(self, url: str):
        self.url = url

    async def make(self, download_path: str, file: str) -> str | Response:
        rFile = Path(calc_download_path(base_path=download_path, folder=file, create_path=False))

        if not rFile.exists():
            possibleFile = check_id(file=rFile)
            if not possibleFile:
                msg = f"File '{rFile}' does not exist."
                raise StreamingError(msg)

            return Response(
                status=HTTPFound.status_code,
                headers={
                    "Location": f"{self.url}api/player/playlist/{quote(str(possibleFile).replace(download_path, '').strip('/'))}.m3u8"
                },
            )

        try:
            ff = await ffprobe(rFile)
        except UnicodeDecodeError:
            pass

        if "duration" not in ff.metadata:
            msg = f"Unable to get '{rFile}' duration."
            raise StreamingError(msg)

        playlist = []
        playlist.append("#EXTM3U")

        subs = ""

        duration: float = float(ff.metadata.get("duration"))
        for sub_file in get_sidecar_subtitles(rFile):
            lang = sub_file["lang"]
            item = sub_file["file"]
            name = sub_file["name"]

            subs = ',SUBTITLES="subs"'
            url = f"{self.url}api/player/m3u8/subtitle/{quote(str(Path(file).with_name(item.name)))}.m3u8?duration={duration}"
            playlist.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="{name}",DEFAULT=NO,AUTOSELECT=NO,FORCED=NO,LANGUAGE="{lang}",URI="{url}"'
            )

        playlist.append(f"#EXT-X-STREAM-INF:PROGRAM-ID=1{subs}")
        playlist.append(f"{self.url}api/player/m3u8/video/{quote(file)}.m3u8")

        return "\n".join(playlist)
