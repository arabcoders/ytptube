import glob
import re
from pathlib import Path
from urllib.parse import quote

from aiohttp.web import HTTPFound, Response

from .ffprobe import ffprobe
from .Subtitle import Subtitle
from .Utils import StreamingError, calc_download_path, check_id


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

        duration: float = float(ff.metadata.get("duration"))

        playlist = []
        playlist.append("#EXTM3U")

        subs = ""

        index = 0
        for item in self.get_sidecar_files(rFile):
            if item.suffix not in Subtitle.allowed_extensions:
                continue

            index += 1
            lang: str = "und"
            lg = re.search(r"\.(?P<lang>\w{2,3})\.\w{3}$", item.name)
            if lg:
                lang = lg.groupdict().get("lang")

            subs = ',SUBTITLES="subs"'

            url = f"{self.url}api/player/m3u8/subtitle/{quote(str(Path(file).with_name(item.name)))}.m3u8?duration={duration}"
            name = f"{item.suffix[1:].upper()} ({index}) - {lang}"
            playlist.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="{name}",DEFAULT=NO,AUTOSELECT=NO,FORCED=NO,LANGUAGE="{lang}",URI="{url}"'
            )

        playlist.append(f"#EXT-X-STREAM-INF:PROGRAM-ID=1{subs}")
        playlist.append(f"{self.url}api/player/m3u8/video/{quote(file)}.m3u8")

        return "\n".join(playlist)

    def get_sidecar_files(self, file: Path) -> list[Path]:
        """
        Get sidecar files for the given file.

        :param file: File to get sidecar files for.
        :return: List of sidecar files.
        """
        files = []

        for sub_file in file.parent.glob(f"{glob.escape(file.stem)}.*"):
            if sub_file == file or sub_file.is_file() is False or sub_file.stem.startswith("."):
                continue

            files.append(sub_file)

        return files
