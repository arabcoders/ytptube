from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import hyphenate_date

if TYPE_CHECKING:
    from collections.abc import Iterable


class NFOMaker(PostProcessor):
    """
    A Post-Processor that writes metadata to an NFO file using a simple
    placeholder-based template engine.

    Mapping value semantics:
      - "field"                      -> use info["field"]
      - ("field1", "field2", ...)    -> first non-empty among fields
      - ("date_field", "%Y")         -> year from date_field
    """

    _MAPPING: dict[str, Any] = {}
    _TEMPLATE: str | None = None
    _DATE_FIELDS: tuple[str, ...] = ("upload_date", "release_date", "aired", "premiered")

    _URL_PAT = re.compile(
        r"(?i)\b(?:https?://|ftp://|www\.)\S+|\b(?!@)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?){1,}\b(?:/[^\s<>()]*)?"
    )
    _MD_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
    _TIME_LINE_PAT = re.compile(r"^\s*(?:\d+:)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[-–—•:]\s*.*)?$", re.IGNORECASE)  # noqa: RUF001
    _HASHTAGS_LINE = re.compile(r"^\s*(?:#[\w\-]+(?:\s+|$))+$")
    _MENTION_LINE = re.compile(r"^\s*@[\w.\-]{2,}\s*$")
    _PROMO_LINE_PAT = re.compile(
        r"(?i)\b("
        r"subscribe|follow|donate|patreon|paypal|sponsor|promo\s*code|coupon|discount|"
        r"business\s*inquiries?|contact\s*me|email\s*me|merch|store|shop|join\s+my|"
        r"discord|instagram|twitter|x\.com|facebook|twitch|tiktok|github|gitlab|linkedin|"
        r"snapchat|reddit|telegram|t\.me|whatsapp|link\s+in\s+bio|bit\.ly|tinyurl|goo\.gl"
        r")\b"
    )

    @classmethod
    def pp_key(cls) -> str:
        return "NFOMaker"

    def run(self, info: dict | None = None) -> tuple[list, dict]:
        if not info:
            self.to_screen("No info provided to NFO Maker.")
            return [], {}

        if not self._TEMPLATE:
            self.to_screen("NFO template not set, skipping NFO creation.")
            return [], info

        # prefer explicit final path if present, else fall back to filename
        base_path = info.get("filename")
        if not base_path:
            self.to_screen("No 'filename' provided, skipping NFO creation.")
            return [], info

        base_path = Path(base_path)

        nfo_file = base_path.with_suffix(".nfo")
        if nfo_file.exists():
            self.to_screen(f"NFO file '{nfo_file!s}' already exists, skipping creation.")
            return [], info

        try:
            nfo_data = self._collect_nfo_data(info)
        except Exception as e:
            if self._downloader:
                self._downloader.report_error(f"NFO data collection failed: {e}")
            return [], info

        if 1 > len(nfo_data):
            self.to_screen("No metadata found to write to NFO file.")
            return [], info

        # derive year from any date if missing
        if ("year" not in nfo_data) and any(k in nfo_data for k in self._DATE_FIELDS):
            try:
                first_date = next((str(nfo_data[k]) for k in self._DATE_FIELDS if nfo_data.get(k)), "")
                if first_date:
                    nfo_data["year"] = first_date.split("-")[0]
            except Exception as e:
                self.to_screen(f"Error extracting year from date: {e}")

        status = self._write_episode_info(nfo_file, base_path, nfo_data)
        if status and nfo_file.exists() and base_path.exists:
            try:
                mtime = base_path.stat().st_mtime
                self.try_utime(str(nfo_file), mtime, mtime)
            except Exception as e:
                self.to_screen(f"Failed to sync NFO mtime: {e}")

        return [], info

    def _collect_nfo_data(self, info: dict) -> dict[str, Any]:
        data: dict[str, Any] = {}

        for nfo_name, spec in self._MAPPING.items():
            try:
                values = spec if isinstance(spec, tuple) else (spec,)
                resolved_key = None
                resolved_val: Any = None

                for item in values:
                    # ("field", "%Y") -> extract/format from this field
                    if isinstance(item, tuple) and 2 == len(item) and isinstance(item[1], str):
                        field, fmt = item
                        if field is None:
                            continue
                        raw = info.get(field)
                        if raw is None:
                            continue
                        resolved_key = field
                        resolved_val = self._coerce_value(raw, fmt)
                        if resolved_val not in (None, ""):
                            break
                        continue

                    # "field" -> plain field
                    if isinstance(item, str):
                        resolved_key = item
                        resolved_val = info.get(item)
                        if resolved_val not in (None, ""):
                            break

                if resolved_val in (None, ""):
                    continue

                # normalize dates if source key is a known date
                if resolved_key in self._DATE_FIELDS:
                    resolved_val = self._normalize_date(resolved_val)

                # collapse multiline descriptions
                if "description" == resolved_key and isinstance(resolved_val, str):
                    resolved_val = self._clean_description(resolved_val)

                if resolved_val not in (None, ""):
                    data[nfo_name] = resolved_val

            except Exception as e:
                if self._downloader:
                    self._downloader.report_error(f"Error processing {nfo_name} -> {spec}: {e}")

        return data

    def _write_episode_info(self, nfo_file: Path, real_file: Path, data: dict) -> bool:
        aired = str(
            data.get("aired") or data.get("premiered") or data.get("release_date") or data.get("upload_date") or ""
        )

        aired = self._normalize_date(aired) if aired else ""
        if not aired or 3 > len(aired.split("-")):
            self.to_screen("Invalid aired/premiered date, skipping NFO creation.")
            return False

        year, month, day = aired.split("-")
        if not (year and month and day):
            self.to_screen("Invalid aired date parts, skipping NFO creation.")
            return False

        self.to_screen(f"Creating NFO file at {nfo_file!s}")
        nfo_file.parent.mkdir(parents=True, exist_ok=True)
        nfo_file.touch(exist_ok=True)

        dt = datetime(int(year), int(month), int(day), tzinfo=UTC)
        data = dict(data)  # do not mutate original
        data["unique_id"] = self._build_unique_id(dt, real_file)

        self._write(nfo_file=nfo_file, text=self._TEMPLATE or "", repl=data)
        return True

    @staticmethod
    def _build_unique_id(dt: datetime, file: Path) -> str:
        # 1MMDD + 4-digit stable hash from lowercase stem
        h = hashlib.sha256(file.stem.lower().encode("utf-8")).hexdigest()
        ascii_stream = "".join(str(ord(c)) for c in h)
        suffix = ascii_stream[:4] if 4 <= len(ascii_stream) else ascii_stream.ljust(4, "9")
        return f"1{dt.strftime('%m')}{dt.strftime('%d')}{suffix}"

    @staticmethod
    def _normalize_date(val: Any) -> str:
        """
        Parse date-like values into 'YYYY-MM-DD' format.

        Args:
            val: Any date-like value.
                Accepts:
                - 'YYYYMMDD'
                - 'YYYY-MM-DD'
                - datetime / date
        Returns:
            str: 'YYYY-MM-DD' or empty string if unparsable.

        """
        try:
            if isinstance(val, datetime):
                return val.strftime("%Y-%m-%d")
            s = str(val).strip()
            if 8 == len(s) and s.isdigit():  # YYYYMMDD
                return hyphenate_date(s)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                return s
            # try yt-dlp helper even for odd inputs
            return hyphenate_date(s)
        except Exception:
            return ""

    @staticmethod
    def _coerce_value(raw: Any, fmt: str) -> Any:
        """
        Support simple date-based formatting: ("%Y", "%m", "%d", etc.)

        Args:
            raw (Any): Raw value.
            fmt (str): Date format string.

        Returns:
            Any: Formatted value.

        """
        if raw in (None, ""):
            return raw

        if fmt and isinstance(fmt, str):
            date_s = NFOMaker._normalize_date(raw)
            if date_s:
                try:
                    dt = datetime.now(tz=UTC).strptime(date_s, "%Y-%m-%d")
                    return dt.strftime(fmt)
                except Exception:
                    return ""

        return raw

    def _write(self, nfo_file: Path, text: str, repl: dict[str, Any]) -> None:
        """
        Write the NFO file, replacing placeholders in the template.

        Args:
            nfo_file (Path): Path to the NFO file.
            text (str): Template text with placeholders.
            repl (dict[str, Any]): Replacement dictionary.

        """
        from xml.sax.saxutils import escape

        # escape XML on a copy
        safe_repl: dict[str, Any] = {}
        for k, v in repl.items():
            if isinstance(v, str):
                safe_repl[k] = escape(v)
            else:
                safe_repl[k] = v

        # replace placeholders
        rendered = text
        for key, value in safe_repl.items():
            if value is None:
                continue
            rendered = rendered.replace(f"{{{key}}}", str(value))

        # remove any unresolved placeholder lines
        unresolved_keys: Iterable[str] = set({*self._MAPPING.keys(), *safe_repl.keys()})
        pattern = re.compile(rf".*{{(?:{'|'.join(map(re.escape, unresolved_keys))})}}.*")
        rendered = "\n".join(line for line in rendered.splitlines() if not pattern.fullmatch(line))

        try:
            nfo_file.write_text(rendered, encoding="utf-8")
            self.to_screen(f"NFO file written successfully at {nfo_file!s}")
        except Exception as e:
            self.to_screen(f"Error writing NFO file: {e}")

    def _clean_description(self, text: str) -> str:
        """
        Strip links, chapters/timestamps, pure hashtags/mentions, and promo lines.
        Return a compact single-line summary suitable for NFO <plot>.
        """
        if not isinstance(text, str):
            return ""

        # normalize newlines
        lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n")]

        cleaned: list[str] = []
        for ln in lines:
            if not ln:
                continue

            # remove markdown links, keep labels
            ln = self._MD_LINK.sub(r"\1", ln)

            # drop lines that are clearly noise
            if self._TIME_LINE_PAT.match(ln):
                continue
            if self._HASHTAGS_LINE.match(ln):
                continue
            if self._MENTION_LINE.match(ln):
                continue
            if self._PROMO_LINE_PAT.search(ln):
                continue

            # strip raw/bare urls and domains
            ln = self._URL_PAT.sub("", ln)

            # collapse leftover multiple spaces and stray separators
            ln = re.sub(r"\s{2,}", " ", ln)
            ln = re.sub(r"\s*[-–—•·]+\s*$", "", ln)  # noqa: RUF001

            if ln:
                cleaned.append(ln)

        # prefer first meaningful paragraphs; cap final length
        summary = " ".join(cleaned)
        summary = re.sub(r"\s{2,}", " ", summary).strip()

        # optional minimum signal: if too short, fall back to original first sentence without links
        if 8 > len(summary.split()):
            fallback = self._URL_PAT.sub("", text)
            fallback = re.sub(r"\s{2,}", " ", fallback).strip()
            if 8 <= len(fallback.split()):
                summary = fallback

        # hard cap to keep NFO tidy
        if 1200 < len(summary):
            # cut at sentence boundary if possible
            cut = summary[:1200]
            dot = cut.rfind(". ")
            summary = cut[: dot + 1] if 0 < dot else cut.rstrip()

        return summary


class NFOMakerTvPP(NFOMaker):
    _MAPPING = {
        "title": "title",
        "season": ("season_number", "season", "year", ("release_date", "%Y"), ("upload_date", "%Y")),
        "episode": ("episode_number", "episode", ("release_date", "%m%d"), ("upload_date", "%m%d"), "unique_id"),
        "aired": ("release_date", "upload_date"),
        "author": "uploader",
        "plot": "description",
        "id": "id",
        "extractor": "extractor",
    }
    _TEMPLATE = """
<episodedetails>
  <title>{title}</title>
  <season>{season}</season>
  <episode>{episode}</episode>
  <aired>{aired}</aired>
  <uniqueid type="cmdb">{unique_id}</uniqueid>
  <uniqueid type="{extractor}">{id}</uniqueid>
  <plot>{plot}</plot>
</episodedetails>
""".strip("\n")


class NFOMakerMoviePP(NFOMaker):
    _MAPPING = {
        "title": "title",
        "plot": "description",
        "runtime": "duration",
        "thumb": "thumbnail",
        "id": "id",
        "country": "language",
        "aired": ("release_date", "upload_date"),
        "extractor": "extractor",
        "year": ("release_year", "year"),
        "author": "uploader",
        "trailer": "webpage_url",
    }
    _TEMPLATE = """
<movie>
  <title>{title}</title>
  <plot>{plot}</plot>
  <runtime>{runtime}</runtime>
  <thumb aspect="poster" preview="{thumb}">{thumb}</thumb>
  <id>{id}</id>
  <uniqueid type="cmdb">{unique_id}</uniqueid>
  <uniqueid type="{extractor}" default="true">{id}</uniqueid>
  <country>{country}</country>
  <premiered>{aired}</premiered>
  <year>{year}</year>
  <trailer>{trailer}</trailer>
</movie>
""".strip("\n")
