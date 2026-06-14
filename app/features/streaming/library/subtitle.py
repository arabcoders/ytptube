from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import pysubs2
from pysubs2.formats.substation import SubstationFormat
from pysubs2.time import ms_to_times

from app.library.log import get_logger
from app.library.Utils import ALLOWED_SUBS_EXTENSIONS, get_file_sidecar

LOG = get_logger()

SOURCE_FORMATS: tuple[str, ...] = ("vtt", "srt", "ass")
DELIVERY_FORMATS: dict[str, str] = {
    "vtt": "vtt",
    "srt": "vtt",
    "ass": "ass",
}
RENDERERS: dict[str, str] = {
    "vtt": "native",
    "srt": "native",
    "ass": "assjs",
}
MEDIA_TYPES: dict[str, str] = {
    "vtt": "text/vtt; charset=UTF-8",
    "ass": "text/x-ssa; charset=UTF-8",
}
TEXT_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252")


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    file: Path
    lang: str
    name: str
    source_format: str
    delivery_format: str
    renderer: str


def ms_to_timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, m, s, ms = ms_to_times(ms)
    cs: int = ms // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


_substation_format: Any = SubstationFormat
_substation_format.ms_to_timestamp = ms_to_timestamp


class Subtitle:
    @staticmethod
    def normalize_format(source_format: str) -> str | None:
        fmt = source_format.strip().lower().removeprefix(".")
        if fmt not in SOURCE_FORMATS:
            return None

        return fmt

    async def read_text(self, file: Path) -> str:
        async with await anyio.open_file(file, "rb") as f:
            subtitle_bytes = await f.read()

        return self.decode_bytes(subtitle_bytes)

    @staticmethod
    def decode_bytes(subtitle_bytes: bytes) -> str:
        for encoding in TEXT_ENCODINGS:
            try:
                return subtitle_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        return subtitle_bytes.decode("utf-8", errors="replace")

    def media_type(self, file: Path) -> str:
        fmt = self.normalize_format(file.suffix)
        if fmt is None:
            msg = f"File '{file}' subtitle type is not supported."
            raise Exception(msg)

        return MEDIA_TYPES[DELIVERY_FORMATS[fmt]]

    async def make(self, file: Path) -> str:
        fmt = self.normalize_format(file.suffix)
        if fmt is None or file.suffix not in ALLOWED_SUBS_EXTENSIONS:
            msg: str = f"File '{file}' subtitle type is not supported."
            raise Exception(msg)

        if fmt == "vtt":
            return await self.read_text(file)

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

    async def make_delivery(self, file: Path) -> tuple[str, str]:
        fmt = self.normalize_format(file.suffix)
        if fmt is None or file.suffix not in ALLOWED_SUBS_EXTENSIONS:
            msg: str = f"File '{file}' subtitle type is not supported."
            raise Exception(msg)

        if fmt == "ass":
            return await self.read_text(file), self.media_type(file)

        return await self.make(file), self.media_type(file)


def get_subtitle_tracks(file: Path) -> list[SubtitleTrack]:
    sidecars = get_file_sidecar(file).get("subtitle", [])
    indexed_tracks: list[tuple[int, SubtitleTrack]] = []

    for index, item in enumerate(sidecars):
        track_file = item.get("file")
        if not isinstance(track_file, Path):
            continue

        fmt = Subtitle.normalize_format(track_file.suffix)
        if fmt is None:
            continue

        indexed_tracks.append(
            (
                index,
                SubtitleTrack(
                    file=track_file,
                    lang=str(item.get("lang") or "und"),
                    name=str(item.get("name") or track_file.name),
                    source_format=fmt,
                    delivery_format=DELIVERY_FORMATS[fmt],
                    renderer=RENDERERS[fmt],
                ),
            )
        )

    indexed_tracks.sort(key=lambda item: (SOURCE_FORMATS.index(item[1].source_format), item[0]))
    return [track for _, track in indexed_tracks]
