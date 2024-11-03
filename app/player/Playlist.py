import glob
import pathlib
import re
from urllib.parse import quote
from Utils import calcDownloadPath, checkId
import pathlib
from .ffprobe import FFProbe
from .Subtitle import Subtitle
from aiohttp.web import Response


class Playlist:
    _url: str = None

    def __init__(self, url: str):
        self.url = url

    async def make(self, download_path: str, file: str) -> str | Response:
        rFile = pathlib.Path(calcDownloadPath(basePath=download_path, folder=file, createPath=False))

        if not rFile.exists():
            possibleFile = checkId(download_path, rFile)
            if not possibleFile:
                raise Exception(f"File '{rFile}' does not exist.")

            return Response(status=302, headers={
                'Location': f"{self.url}player/playlist/{quote(possibleFile.replace(download_path, '').strip('/'))}.m3u8"
            })

        try:
            ffprobe = FFProbe(rFile)
            await ffprobe.run()
        except UnicodeDecodeError as e:
            pass

        if not 'duration' in ffprobe.metadata:
            raise Exception(f"Unable to get '{rFile}' duration.")

        duration: float = float(ffprobe.metadata.get('duration'))

        playlist = []
        playlist.append("#EXTM3U")

        subs = ""

        index = 0
        for item in self.getSideCarFiles(rFile):
            if not item.suffix in Subtitle.allowedExtensions:
                continue

            index += 1
            lang: str = "und"
            lg = re.search(r'\.(?P<lang>\w{2,3})\.\w{3}$', item.name)
            if lg:
                lang = lg.groupdict().get('lang')

            subs = ',SUBTITLES="subs"'

            url = f"{self.url}player/m3u8/subtitle/{quote(str(pathlib.Path(file).with_name(item.name)))}.m3u8?duration={duration}"
            name = f"{item.suffix[1:].upper()} ({index}) - {lang}"
            playlist.append(
                f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="{name}",DEFAULT=NO,AUTOSELECT=NO,FORCED=NO,LANGUAGE="{lang}",URI="{url}"')

        playlist.append(f'#EXT-X-STREAM-INF:PROGRAM-ID=1{subs}')
        playlist.append(f"{self.url}player/m3u8/video/{quote(file)}.m3u8")

        return '\n'.join(playlist)

    def getSideCarFiles(self, file: pathlib.Path) -> list[pathlib.Path]:
        """
        Get sidecar files for the given file.

        :param file: File to get sidecar files for.
        :return: List of sidecar files.
        """
        files = []

        for sub_file in file.parent.glob(f"{glob.escape(file.stem)}.*"):
            if sub_file == file or sub_file.is_file() is False or sub_file.stem.startswith('.'):
                continue

            files.append(sub_file)

        return files
