import logging
from pathlib import Path

from .config import Config
from .Presets import Presets
from .Singleton import Singleton
from .Utils import REMOVE_KEYS, arg_converter, calc_download_path, load_cookies, merge_dict

LOG = logging.getLogger("YTDLPOpts")


class YTDLPOpts(metaclass=Singleton):
    _item_opts: dict = {}
    """The item options."""

    _preset_opts: dict = {}
    """The preset options."""

    _item_cli: list = []
    """The item cli options."""

    _preset_cli: str = ""
    """The preset cli options."""

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

    def add_cli(self, args: str, from_user: int | bool = False) -> "YTDLPOpts":
        """
        Parse and add yt-dlp cli options to the item options.

        Args:
            args (str): The cli options to add
            from_user (bool): If the options are from the user

        Returns:
            YTDLPOpts: The instance of the class

        """
        if not args or len(args) < 2 or not isinstance(args, str):
            return self

        try:
            arg_converter(args=args, level=from_user)
        except Exception as e:
            msg = f"Invalid cli options for were given. '{e!s}'."
            raise ValueError(msg) from e

        self._item_cli.append(args)

        return self

    def add(self, config: dict, from_user: bool = False) -> "YTDLPOpts":
        """
        Add the options to the item options.

        Args:
            config (dict): The options to add
            from_user (bool): If the options are from the user

        Returns:
            YTDLPOpts: The instance of the class

        """
        bad_options = {}
        if from_user:
            bad_options = {k: v for d in REMOVE_KEYS for k, v in d.items()}

        removed_options = []

        for key, value in config.items():
            if from_user and key in bad_options:
                removed_options.append(bad_options[key])
                continue

            self._item_opts[key] = value

        if len(removed_options) > 0:
            LOG.warning("Removed the following options: '%s'.", ", ".join(removed_options))

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
        preset = Presets.get_instance().get(name)
        if not preset or "default" == name:
            return self

        if preset.cli:
            try:
                arg_converter(args=preset.cli, level=True)
                self._preset_opts = {}
                self._preset_cli = preset.cli
            except Exception as e:
                msg = f"Invalid cli options for preset '{preset.name}'. '{e!s}'."
                raise ValueError(msg) from e

        if preset.cookies and with_cookies:
            file = Path(self._config.config_path, "cookies", f"{preset.id}.txt")

            if not file.parent.exists():
                file.parent.mkdir(parents=True)

            with open(file, "w") as f:
                f.write(preset.cookies)

            load_cookies(file)

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

        return self

    def get_all(self, keep: bool = False) -> dict:
        """
        Get all the options.

        Args:
            keep (bool): If the options should be kept

        Returns:
            dict: The options

        """
        default_opts = {}
        default_opts["paths"] = {"home": self._config.download_path, "temp": self._config.temp_path}
        default_opts["outtmpl"] = {
            "default": self._config.output_template,
            "chapter": self._config.output_template_chapter,
        }

        if not isinstance(self._item_cli, list):
            self._item_cli = []

        merge = []
        if self._config._ytdlp_cli_mutable and len(self._config._ytdlp_cli_mutable) > 1:
            merge.append(self._config._ytdlp_cli_mutable)

        if self._preset_cli and len(self._preset_cli) > 1:
            merge.append(self._preset_cli)

        if len(merge) > 0:
            # prepend the cli options to the list
            self._item_cli = merge + self._item_cli

        user_cli = {}

        if len(self._item_cli) > 0:
            try:
                removed_options = []
                user_cli = arg_converter(args="\n".join(self._item_cli), level=True, removed_options=removed_options)

                if len(removed_options) > 0:
                    LOG.warning("Removed the following options: '%s'.", ", ".join(removed_options))
            except Exception as e:
                msg = f"Invalid cli options were given. '{e!s}'."
                raise ValueError(msg) from e

        data = merge_dict(user_cli, merge_dict(self._item_opts, merge_dict(self._preset_opts, default_opts)))

        if not keep:
            self.presets_opts = {}
            self._item_opts = {}
            self._item_cli = []
            self._preset_cli = ""

        if "format" in data:
            if data["format"] in ["not_set", "default", "best"]:
                data["format"] = None

            if data["format"] == "-best":
                data["format"] = data["format"][1:]

        LOG.debug(f"Parsed yt-dlp options are: '{data!s}'.")

        return data
