import logging
import pathlib

import pysubs2
from pysubs2.formats.substation import SubstationFormat
from pysubs2.time import ms_to_times

from .Utils import calcDownloadPath

LOG = logging.getLogger("player.subtitle")


def ms_to_timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, m, s, ms = ms_to_times(ms)
    cs = ms // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


SubstationFormat.ms_to_timestamp = ms_to_timestamp


class Subtitle:
    allowed_extensions: tuple[str] = (
        ".srt",
        ".vtt",
        ".ass",
    )

    async def make(self, path: str, file: str) -> str:
        realFile: str = calcDownloadPath(basePath=path, folder=file, createPath=False)

        rFile = pathlib.Path(realFile)

        if not rFile.exists():
            msg = f"File '{file}' does not exist."
            raise Exception(msg)

        if rFile.suffix not in self.allowed_extensions:
            msg = f"File '{file}' subtitle type is not supported."
            raise Exception(msg)

        if rFile.suffix == ".vtt":
            with open(realFile) as f:
                return f.read()

        subs = pysubs2.load(path=str(rFile))

        if len(subs.events) < 1:
            msg = f"No subtitle events were found in '{rFile}'."
            raise Exception(msg)

        if len(subs.events) < 2:
            return subs.to_string("vtt")

        if subs.events[0].end == subs.events[len(subs.events) - 1].end:
            subs.events.pop(0)

        return subs.to_string("vtt")
