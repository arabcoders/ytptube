from pathlib import Path

from .config import Config
from .Presets import Presets
from .Singleton import Singleton
from .Utils import IGNORED_KEYS, calc_download_path, merge_dict


class YTDLPOpts(metaclass=Singleton):
    item_opts: dict = {}
    preset_opts: dict = {}

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

    def add(self, config: dict, from_user: bool = False):
        for key, value in config.items():
            if key in IGNORED_KEYS and from_user:
                continue
            self.item_opts[key] = value

        return self

    def preset(self, name: str, with_cookies: bool = False) -> "YTDLPOpts":
        preset = Presets.get_instance().get(name=name)
        if not preset or "default" == name:
            return self

        if preset.cookies and with_cookies:
            file = Path(self._config.config_path, "cookies", f"{preset.id}.txt")

            if not file.parent.exists():
                file.parent.mkdir(parents=True)

            with open(file, "w") as f:
                f.write(preset.cookies)

            self.preset_opts["cookiefile"] = str(file)

        if preset.format:
            self.preset_opts["format"] = preset.format

        if preset.template:
            self.preset_opts["outtmpl"] = {"default": preset.template, "chapter": self._config.output_template_chapter}

        if preset.folder:
            self.preset_opts["paths"] = {
                "home": calc_download_path(base_path=self._config.download_path, folder=preset.folder),
                "temp": self._config.temp_path,
            }

        if preset.postprocessors and isinstance(preset.postprocessors, list) and len(preset.postprocessors) > 0:
            self.preset_opts["postprocessors"] = preset.postprocessors

        if preset.args and isinstance(preset.args, dict) and len(preset.args) > 0:
            for key, value in preset.args.items():
                if key in IGNORED_KEYS:
                    continue
                self.preset_opts[key] = value

        return self

    def get_all(self, keep: bool = False) -> dict:
        default_opts = self._config.ytdl_options
        default_opts["paths"] = {"home": self._config.download_path, "temp": self._config.temp_path}
        default_opts["outtmpl"] = {
            "default": self._config.output_template,
            "chapter": self._config.output_template_chapter,
        }

        if "format" in default_opts or "format" in self.item_opts:
            return merge_dict(default_opts, self.item_opts)

        data = merge_dict(merge_dict(self.preset_opts, default_opts), self.item_opts)

        if not keep:
            self.presets_opts = {}
            self.item_opts = {}

        if "impersonate" in data:
            from yt_dlp.networking.impersonate import ImpersonateTarget

            data["impersonate"] = ImpersonateTarget.from_str(data["impersonate"])

        return data
