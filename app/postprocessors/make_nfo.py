from datetime import UTC, datetime
from pathlib import Path

from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import hyphenate_date


class NFOMaker(PostProcessor):
    """
    A Post-Processor that writes metadata to NFO file.
    """

    _MAPPING: dict = {}
    _TEMPLATE: str | None = None
    _date_fields: tuple = ("upload_date", "release_date")

    @classmethod
    def pp_key(cls) -> str:
        return "NFOMaker"

    def run(self, info: dict = None) -> tuple[list, dict]:
        if not info:
            self.to_screen("No info provided to NFO Maker.")
            return [], {}

        if not self._TEMPLATE:
            self.to_screen("NFO template not set, skipping NFO creation.")
            return [], info

        nfo_file = Path(info.get("filename")).with_suffix(".nfo")
        if nfo_file.exists():
            self.to_screen(f"NFO file '{nfo_file!s}' already exists, skipping creation.")
            return [], info

        nfo_data: dict = {}

        for nfo_name, ytdlp_name in self._MAPPING.items():
            try:
                if isinstance(ytdlp_name, str):
                    ytdlp_name = (ytdlp_name,)

                _key = None
                _value = None

                for name in ytdlp_name:
                    if name is None:
                        continue

                    _key = name
                    _value = info.get(name)
                    if _value is not None:
                        break

                if _value:
                    if _key in self._date_fields:
                        _value = hyphenate_date(_value)

                    if "description" == _key:
                        _value = _value.replace("\n", " ").replace("\r", " ").strip()

                    if _value:
                        nfo_data[nfo_name] = _value
            except Exception as e:
                if self._downloader:
                    self._downloader.report_error(f"Error processing {nfo_name} -> {ytdlp_name}: {e}")

        if len(nfo_data) < 1:
            self.to_screen("No metadata found to write to NFO file.")
            return [], info

        if "year" not in nfo_data and (k in nfo_data for k in self._date_fields):
            try:
                _date = any(nfo_data.get(k) for k in self._date_fields if k in nfo_data)
                if _date:
                    nfo_data["year"] = _date.split("-")[0]
            except Exception as e:
                self.to_screen(f"Error extracting year from date: {e}")

        file_path = Path(info["filepath"])
        status = self._write_episode_info(nfo_file, file_path, nfo_data)
        if status and nfo_file.exists():
            mtime = file_path.stat().st_mtime
            self.try_utime(str(nfo_file), mtime, mtime)

        return [], info

    def _write_episode_info(self, nfo_file: Path, real_file: Path, data: dict) -> bool:
        year, month, day = data.get("aired", "0000-00-00").split("-")
        if not (year and month and day):
            self.to_screen("Invalid aired date format, skipping NFO creation.")
            return False

        self.to_screen(f"Creating NFO file at {nfo_file!s}")
        nfo_file.touch(exist_ok=True)

        dt = datetime(int(year), int(month), int(day), tzinfo=UTC)
        data["unique_id"] = "1{:>02}{:>02}{:>04}".format(
            dt.strftime("%m"), dt.strftime("%d"), self._extend_id(real_file)
        )

        self._write(nfo_file=nfo_file, text=self._TEMPLATE, repl=data)
        return True

    @staticmethod
    def _extend_id(file: Path) -> int:
        try:
            import hashlib

            hash_object = hashlib.sha256(file.stem.lower().encode("utf-8"))
            hash_hex: str = hash_object.hexdigest()
            ascii_values: str = "".join([str(ord(c)) for c in hash_hex])
            four_digit_string: str = ascii_values[:4] if len(ascii_values) >= 4 else ascii_values.ljust(4, "9")
            return int(four_digit_string)
        except Exception:
            return 1000

    def _write(self, nfo_file: Path, text: str, repl: dict):
        from xml.sax.saxutils import escape

        for key, value in repl.items():
            if isinstance(value, str):
                repl[key] = escape(value)

        for key, value in repl.items():
            if value is None:
                continue
            text = text.replace(f"{{{key}}}", str(value))

        for key in {**self._MAPPING, **repl}:
            if f"{{{key}}}" in text:
                self.write_debug(f"Missing replacement for '{key}'.")
                text = "\n".join(line for line in text.splitlines() if f"{{{key}}}" not in line)

        try:
            if not nfo_file.parent.exists():
                nfo_file.parent.mkdir(parents=True, exist_ok=True)
            nfo_file.write_text(text, encoding="utf-8")
            self.to_screen(f"NFO file written successfully at {nfo_file!s}")
        except Exception as e:
            self.to_screen(f"Error writing NFO file: {e}")


class NFOMakerTvPP(NFOMaker):
    _MAPPING = {
        "title": "title",
        "season": ("season_number", "season", "year", None),
        "episode": ("episode_number", "episode"),
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
        """


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
        """
