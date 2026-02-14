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


class NFOMakerPP(PostProcessor):
    """
    A Post-Processor that writes metadata to an NFO file using a simple
    placeholder-based template engine.

    Mapping value semantics:
      - "field"                      -> use info["field"]
      - ("field1", "field2", ...)    -> first non-empty among fields
      - ("date_field", "%Y")         -> year from date_field
    """

    _DATE_FIELDS: tuple[str, ...] = ("upload_date", "release_date", "aired", "premiered")

    _URL_PAT = re.compile(
        r"(?i)\b(?:https?://|ftp://|www\.)\S+|\b(?!@)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?){1,}\b(?:/[^\s<>()]*)?"
    )
    _MD_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
    _TIME_LINE_PAT = re.compile(r"^\s*(?:\d+:)?\d{1,2}:\d{2}(?::\d{2})?(?:\s*[-–—•:]\s*.*)?$", re.IGNORECASE)
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
    _args: dict[str, Any] = {}
    _MODE: dict = {
        "tv": {
            "mapping": {
                "title": "title",
                "season": ("season_number", "season", "year", ("release_date", "%Y"), ("upload_date", "%Y")),
                "episode": (
                    "episode_number",
                    "episode",
                    ("release_date", "%m%d"),
                    ("upload_date", "%m%d"),
                    "unique_id",
                ),
                "aired": ("release_date", "upload_date"),
                "author": "uploader",
                "plot": "description",
                "id": "id",
                "extractor": "extractor",
            },
            "template": """
<episodedetails>
  <title>{title}</title>
  <season>{season}</season>
  <episode>{episode}</episode>
  <aired>{aired}</aired>
  <uniqueid type="cmdb">{unique_id}</uniqueid>
  <uniqueid type="{extractor}">{id}</uniqueid>
  <plot>{plot}</plot>
</episodedetails>
""".strip("\n"),
        },
        "movie": {
            "mapping": {
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
            },
            "template": """
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
""".strip("\n"),
        },
    }

    mode: str = "tv"
    "The NFO mode to use. Either 'tv' or 'movie'. Default is 'tv'."

    prefix: bool = True
    "Prefix episodes with 1 for better sorting."

    def __init__(self, downloader, mode: str = "tv", prefix: bool = True) -> None:
        PostProcessor.__init__(self, downloader)
        self.mode = str(mode).lower()
        self.prefix = prefix in (True, "true", "1", 1)

    @classmethod
    def pp_key(cls) -> str:
        return "NFOMaker"

    def run(self, info: dict | None = None) -> tuple[list, dict]:
        if "fail" == self.mode:
            msg = "Intentionally failing due to mode=fail."
            raise Exception(msg)

        if not info:
            self.report_warning("No info provided to NFO Maker.")
            return [], {}

        base_path = info.get("filename")
        if not base_path:
            self.report_warning("No 'filename' provided, skipping NFO creation.")
            return [], info

        result = NFOMakerPP.generate_nfo(
            info_dict=info,
            filepath=base_path,
            mode=self.mode,
            overwrite=False,
            prefix=self.prefix,
            logger=getattr(self, "_downloader", None) or None,
        )

        if not result.get("success"):
            self.report_warning(result.get("message", "NFO generation failed"))
            return [], info

        try:
            nfo_path = Path(base_path).with_suffix(".nfo")
            if nfo_path.exists() and Path(base_path).exists():
                try:
                    mtime: float = Path(base_path).stat().st_mtime
                    self.try_utime(str(nfo_path), mtime, mtime)
                except Exception as e:
                    self.report_warning(f"Failed to sync NFO mtime: {e}")
        except Exception:
            pass

        return [], info

    @staticmethod
    def generate_nfo(
        *,
        info_dict: dict,
        filepath: str | Path,
        mode: str = "tv",
        overwrite: bool = False,
        prefix: bool = True,
        logger: Any | None = None,
    ) -> dict[str, Any]:
        """
        Public helper to generate an NFO outside the PostProcessor cycle.

        Returns:
            dict: {"success": bool, "message": str, "nfo_file": Optional[str]}

        """
        try:
            if not info_dict:
                return {"success": False, "message": "no metadata provided"}

            mode = str(mode).lower()
            if mode not in NFOMakerPP._MODE:
                return {"success": False, "message": f"invalid mode '{mode}'"}

            base_path = Path(filepath)
            nfo_file = base_path.with_suffix(".nfo")
            if nfo_file.exists() and not overwrite:
                return {"success": False, "message": "NFO file already exists"}

            nfo_data = NFOMakerPP._collect_nfo_data(info_dict, mode, None)
            if 1 > len(nfo_data):
                return {"success": False, "message": "no metadata found to write to NFO file"}

            # derive year from any date if missing
            if ("year" not in nfo_data) and any(k in nfo_data for k in NFOMakerPP._DATE_FIELDS):
                try:
                    first_date: str = next((str(nfo_data[k]) for k in NFOMakerPP._DATE_FIELDS if nfo_data.get(k)), "")
                    if first_date:
                        nfo_data["year"] = first_date.split("-", maxsplit=1)[0]
                except Exception:
                    pass

            ok = NFOMakerPP._write_file(logger, nfo_file, base_path, nfo_data, prefix, mode)
            if ok and nfo_file.exists():
                return {"success": True, "message": "NFO file created", "nfo_file": str(nfo_file)}

            return {"success": False, "message": "failed to write NFO"}

        except Exception as e:
            if logger and hasattr(logger, "exception"):
                logger.exception(f"generate_nfo failed: {e}")
            return {"success": False, "message": f"generate_nfo failed: {e!s}"}

    @staticmethod
    def _collect_nfo_data(info: dict, mode: str, downloader: Any | None = None) -> dict[str, Any]:
        """
        Collect replacement data for templates without depending on an instance.

        Arguments:
            info: extracted info dict
            mode: 'tv' or 'movie'
            downloader: optional downloader/logger to report errors

        """
        data: dict[str, Any] = {}

        for nfo_name, spec in NFOMakerPP._MODE[mode].get("mapping", {}).items():
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
                        resolved_val = NFOMakerPP._coerce_value(raw, fmt)
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
                if resolved_key in NFOMakerPP._DATE_FIELDS:
                    resolved_val = NFOMakerPP._normalize_date(resolved_val)

                # collapse multiline descriptions
                if "description" == resolved_key and isinstance(resolved_val, str):
                    resolved_val = NFOMakerPP._clean_description(resolved_val)

                if resolved_val not in (None, ""):
                    data[nfo_name] = resolved_val

            except Exception as e:
                if downloader:
                    try:
                        downloader.report_error(f"Error processing {nfo_name} -> {spec}: {e}")
                    except Exception:
                        pass

        return data

    @staticmethod
    def _write_file(reporter: Any | None, nfo_file: Path, real_file: Path, data: dict, prefix: bool, mode: str) -> bool:
        """
        Write episode/movie NFO using independent parameters.

        reporter: object with optional methods `to_screen(msg)` and `report_warning(msg)`; if a logger is given uses .info/.warning
        prefix: whether to prefix episode numbers
        mode: 'tv' or 'movie'

        """
        aired = str(
            data.get("aired") or data.get("premiered") or data.get("release_date") or data.get("upload_date") or ""
        )

        aired = NFOMakerPP._normalize_date(aired) if aired else ""
        if not aired or 3 > len(aired.split("-")):
            if reporter and hasattr(reporter, "report_warning"):
                reporter.report_warning("Invalid aired/premiered date, skipping NFO creation.")
            elif reporter and hasattr(reporter, "warning"):
                reporter.warning("Invalid aired/premiered date, skipping NFO creation.")
            return False

        year, month, day = aired.split("-")
        if not (year and month and day):
            if reporter and hasattr(reporter, "report_warning"):
                reporter.report_warning("Invalid aired date parts, skipping NFO creation.")
            elif reporter and hasattr(reporter, "warning"):
                reporter.warning("Invalid aired date parts, skipping NFO creation.")
            return False

        if reporter and hasattr(reporter, "to_screen"):
            reporter.to_screen(f"Creating {mode} NFO file at {nfo_file!s}")
        elif reporter and hasattr(reporter, "info"):
            reporter.info(f"Creating {mode} NFO file at {nfo_file!s}")

        nfo_file.parent.mkdir(parents=True, exist_ok=True)
        nfo_file.touch(exist_ok=True)

        dt = datetime(int(year), int(month), int(day), tzinfo=UTC)
        data = dict(data)  # do not mutate original
        data["unique_id"] = NFOMakerPP._build_unique_id(dt, real_file)

        NFOMakerPP._write(
            reporter,
            nfo_file=nfo_file,
            text=NFOMakerPP._MODE[mode].get("template", ""),
            repl=data,
            prefix=prefix,
            mode=mode,
        )
        return True

    @staticmethod
    def _build_unique_id(dt: datetime, file: Path) -> str:
        # 1MMDD + 4-digit stable hash from lowercase stem
        h: str = hashlib.sha256(file.stem.lower().encode("utf-8")).hexdigest()
        ascii_stream = "".join(str(ord(c)) for c in h)
        suffix: str = ascii_stream[:4] if 4 <= len(ascii_stream) else ascii_stream.ljust(4, "9")
        return f"1{dt.strftime('%m%d')}{suffix}"

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
            date_s = NFOMakerPP._normalize_date(raw)
            if date_s:
                try:
                    dt = datetime.now(tz=UTC).strptime(date_s, "%Y-%m-%d")
                    return dt.strftime(fmt)
                except Exception:
                    return ""

        return raw

    @staticmethod
    def _write(reporter: Any | None, nfo_file: Path, text: str, repl: dict[str, Any], prefix: bool, mode: str) -> None:
        """
        Write rendered template to disk; independent of PostProcessor instance.

        reporter: optional object with `to_screen`/`report_warning` or a logger with `info`/`warning`.
        prefix: whether to prefix episodes
        mode: 'tv' or 'movie'

        """
        safe_repl: dict[str, Any] = {}
        for k, v in repl.items():
            safe_repl[k] = NFOMakerPP._escape_text(v)

        rendered = text
        for key, value in safe_repl.items():
            if value is None:
                continue

            if prefix and key in ("episode",):
                try:
                    value: str = f"1{value}"
                except Exception:
                    pass

            rendered = rendered.replace(f"{{{key}}}", str(value))

        mapping = NFOMakerPP._MODE[mode].get("mapping", {})
        unresolved_keys: Iterable[str] = set({*mapping, *safe_repl.keys()})
        pattern: re.Pattern[str] = re.compile(rf".*{{(?:{'|'.join(map(re.escape, unresolved_keys))})}}.*")
        rendered: str = "\n".join(line for line in rendered.splitlines() if not pattern.fullmatch(line))

        try:
            nfo_file.write_text(rendered, encoding="utf-8")
            if reporter and hasattr(reporter, "to_screen"):
                reporter.to_screen(f"NFO file written successfully at {nfo_file!s}")
            elif reporter and hasattr(reporter, "info"):
                reporter.info(f"NFO file written successfully at {nfo_file!s}")
        except Exception as e:
            if reporter and hasattr(reporter, "report_warning"):
                reporter.report_warning(f"Error writing NFO file: {e}")
            elif reporter and hasattr(reporter, "warning"):
                reporter.warning(f"Error writing NFO file: {e}")

    @staticmethod
    def _escape_text(text: Any) -> Any:
        """
        Escape text for XML.

        Args:
            text (str): Text to escape.

        Returns:
            Any: Escaped text if input is str, else original value.

        """
        from xml.sax.saxutils import escape

        return escape(text) if isinstance(text, str) else text

    @staticmethod
    def _clean_description(text: str) -> str:
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
            ln = NFOMakerPP._MD_LINK.sub(r"\1", ln)

            # drop lines that are clearly noise
            if NFOMakerPP._TIME_LINE_PAT.match(ln):
                continue
            if NFOMakerPP._HASHTAGS_LINE.match(ln):
                continue
            if NFOMakerPP._MENTION_LINE.match(ln):
                continue
            if NFOMakerPP._PROMO_LINE_PAT.search(ln):
                continue

            # strip raw/bare urls and domains
            ln = NFOMakerPP._URL_PAT.sub("", ln)

            # collapse leftover multiple spaces and stray separators
            ln = re.sub(r"\s{2,}", " ", ln)
            ln = re.sub(r"\s*[-–—•·]+\s*$", "", ln)

            if ln:
                cleaned.append(ln)

        # prefer first meaningful paragraphs; cap final length
        summary = " ".join(cleaned)
        summary = re.sub(r"\s{2,}", " ", summary).strip()

        # optional minimum signal: if too short, fall back to original first sentence without links
        if 8 > len(summary.split()):
            fallback = NFOMakerPP._URL_PAT.sub("", text)
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
