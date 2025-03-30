import logging
from pathlib import Path

from .config import Config
from .Presets import Presets
from .Singleton import Singleton
from .Utils import IGNORED_KEYS, arg_converter, calc_download_path, merge_dict

LOG = logging.getLogger("YTDLPOpts")


class YTDLPOpts(metaclass=Singleton):
    _item_opts: dict = {}
    """The item options."""

    _preset_opts: dict = {}
    """The preset options."""

    _instance = None
    """The instance of the class."""

    def __init__(self):
        self._config = Config.get_instance()

    @staticmethod
    def get_instance() -> "YTDLPOpts":
        """
        Get the instance of the class.

        Returns:
            Presets: The instance of the class

        """
        if not YTDLPOpts._instance:
            YTDLPOpts._instance = YTDLPOpts()

        return YTDLPOpts._instance

    def add(self, config: dict, from_user: bool = False) -> "YTDLPOpts":
        """
        Add the options to the item options.

        Args:
            config (dict): The options to add
            from_user (bool): If the options are from the user

        Returns:
            YTDLPOpts: The instance of the class

        """
        for key, value in config.items():
            if key in IGNORED_KEYS and from_user:
                continue
            self._item_opts[key] = value

        return self

    def preset(self, name: str, with_cookies: bool = False) -> "YTDLPOpts":
        """
        Add the preset options to the item options.

        Args:
            name (str): The name of the preset
            with_cookies (bool): If the cookies should be added

        Returns:
            YTDLPOpts: The instance of the class

        """
        preset = Presets.get_instance().get(name=name)
        if not preset or "default" == name:
            return self

        if preset.cli:
            try:
                self._preset_opts = arg_converter(args=preset.cli, remove_options=True)
            except Exception as e:
                msg = f"Invalid cli options for preset '{preset.name}'. '{e!s}'."
                raise ValueError(msg) from e

        if preset.cookies and with_cookies:
            file = Path(self._config.config_path, "cookies", f"{preset.id}.txt")

            if not file.parent.exists():
                file.parent.mkdir(parents=True)

            with open(file, "w") as f:
                f.write(preset.cookies)

            self._preset_opts["cookiefile"] = str(file)

        if preset.format:
            self._preset_opts["format"] = preset.format

        if preset.template:
            self._preset_opts["outtmpl"] = {"default": preset.template, "chapter": self._config.output_template_chapter}

        if preset.folder:
            self._preset_opts["paths"] = {
                "home": calc_download_path(base_path=self._config.download_path, folder=preset.folder),
                "temp": self._config.temp_path,
            }

        if not preset.cli:
            if preset.postprocessors and isinstance(preset.postprocessors, list) and len(preset.postprocessors) > 0:
                self._preset_opts["postprocessors"] = preset.postprocessors

            if preset.args and isinstance(preset.args, dict) and len(preset.args) > 0:
                for key, value in preset.args.items():
                    if key in IGNORED_KEYS:
                        continue
                    self._preset_opts[key] = value

        return self

    def get_all(self, keep: bool = False) -> dict:
        """
        Get all the options.

        Args:
            keep (bool): If the options should be kept

        Returns:
            dict: The options

        """
        default_opts = self._config.ytdl_options
        default_opts["paths"] = {"home": self._config.download_path, "temp": self._config.temp_path}
        default_opts["outtmpl"] = {
            "default": self._config.output_template,
            "chapter": self._config.output_template_chapter,
        }

        data = merge_dict(self._item_opts, merge_dict(self._preset_opts, default_opts))

        if not keep:
            self.presets_opts = {}
            self._item_opts = {}

        if "format" in data and data["format"] in ["not_set", "default"]:
            data["format"] = None

        if "daterange" in data and isinstance(data["daterange"], dict):
            from yt_dlp.utils import DateRange

            data["daterange"] = DateRange(data["daterange"]["start"], data["daterange"]["end"])

        if "impersonate" in data and isinstance(data["impersonate"], str):
            from yt_dlp.networking.impersonate import ImpersonateTarget

            data["impersonate"] = ImpersonateTarget.from_str(data["impersonate"])

        if (
            "match_filter" in data
            and isinstance(data["match_filter"], dict)
            and "filters" in data["match_filter"]
            and len(data["match_filter"]["filters"]) > 0
        ):
            from yt_dlp.utils import match_filter_func

            data["match_filter"] = match_filter_func(data["match_filter"]["filters"])

        return data
