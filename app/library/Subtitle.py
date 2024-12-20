import logging
from .Utils import calcDownloadPath
import pathlib
import pysubs2
from pysubs2.time import ms_to_times
from pysubs2.formats.substation import SubstationFormat

LOG = logging.getLogger("player.subtitle")


def ms_to_timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, m, s, ms = ms_to_times(ms)
    cs = ms // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


SubstationFormat.ms_to_timestamp = ms_to_timestamp


class Subtitle:
    allowedExtensions: tuple[str] = (
        ".srt",
        ".vtt",
        ".ass",
    )

    async def make(self, path: str, file: str) -> str:
        realFile: str = calcDownloadPath(basePath=path, folder=file, createPath=False)

        rFile = pathlib.Path(realFile)

        if not rFile.exists():
            raise Exception(f"File '{file}' does not exist.")

        if rFile.suffix not in self.allowedExtensions:
            raise Exception(f"File '{file}' subtitle type is not supported.")

        if rFile.suffix == ".vtt":
            subData = ""
            with open(realFile, "r") as f:
                subData = f.read()

            return subData

        subs = pysubs2.load(path=str(rFile))

        if len(subs.events) < 1:
            raise Exception(f"No subtitle events were found in '{rFile}'.")

        if len(subs.events) < 2:
            return subs.to_string("vtt")

        if subs.events[0].end == subs.events[len(subs.events) - 1].end:
            subs.events.pop(0)

        return subs.to_string("vtt")
