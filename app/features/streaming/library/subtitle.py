import logging
from pathlib import Path

import anyio
import pysubs2
from pysubs2.formats.substation import SubstationFormat
from pysubs2.time import ms_to_times

from app.library.Utils import ALLOWED_SUBS_EXTENSIONS

LOG: logging.Logger = logging.getLogger("player.subtitle")


def ms_to_timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, m, s, ms = ms_to_times(ms)
    cs: int = ms // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


SubstationFormat.ms_to_timestamp = ms_to_timestamp


class Subtitle:
    async def make(self, file: Path) -> str:
        if file.suffix not in ALLOWED_SUBS_EXTENSIONS:
            msg: str = f"File '{file}' subtitle type is not supported."
            raise Exception(msg)

        if file.suffix == ".vtt":
            async with await anyio.open_file(file) as f:
                return await f.read()

        subs: pysubs2.SSAFile = pysubs2.load(path=str(file))

        if len(subs.events) < 1:
            msg = f"No subtitle events were found in '{file}'."
            raise Exception(msg)

        if len(subs.events) < 2:
            return subs.to_string("vtt")

        try:
            if subs.events[0].end == subs.events[len(subs.events) - 1].end:
                subs.events.pop(0)
        except Exception:
            pass

        return subs.to_string("vtt")
