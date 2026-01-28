import logging
import shlex
from pathlib import Path
from typing import Any

from app.features.presets.schemas import Preset
from app.features.ytdlp.utils import arg_converter
from app.library.config import Config
from app.library.Utils import calc_download_path, create_cookies_file, merge_dict

LOG: logging.Logger = logging.getLogger("ytdlp.ytdlp_opts")


class ARGSMerger:
    def __init__(self):
        self.args: list[str] = []
        "Args merger"

    def add(self, args: str) -> "ARGSMerger":
        """
        Add command options for yt-dlp.

        Args:
            args (str): The command options for yt-dlp to add

        Returns:
            YTDLPCli: The instance of the class

        """
        if not args or not isinstance(args, str) or len(args) < 2:
            return self

        _args: list[str] = shlex.split(
            # Filter out comment lines.
            "\n".join([line for line in args.split("\n") if not line.lstrip().startswith("#")])
        )

        if len(_args) > 0:
            self.args.extend(_args)

        return self

    def as_string(self) -> str:
        """
        Get all the options as a string.

        Returns:
            str: The options as a string

        """
        return str(self)

    def as_dict(self) -> dict:
        """
        Get all the options as a dict.

        Returns:
            dict: The options as a dict

        """
        return shlex.split(shlex.join(self.args))

    def as_ytdlp(self) -> dict:
        """
        Get all options as yt-dlp JSON options.

        Returns:
            dict: The options as a dict for yt-dlp

        """
        return arg_converter(args=shlex.join(self.args), level=False)

    def __str__(self) -> str:
        """
        Get all the options as a string.

        Returns:
            str: The options as a string

        """
        return shlex.join(self.args)

    @staticmethod
    def get_instance() -> "ARGSMerger":
        """
        Get the instance of the class.

        Returns:
            Presets: The instance of the class

        """
        return ARGSMerger()

    def reset(self) -> "ARGSMerger":
        """
        Reset the command options.

        Returns:
            YTDLPCli: The instance of the class

        """
        self.args = []

        return self


class YTDLPCli:
    """
    Build yt-dlp CLI command.

    Th logic is simple
    1. User provided fields have highest priority
    2. Preset provided fields have second priority
    3. Defaults have lowest priority
    """

    def __init__(self, item, config: Config | None = None):
        """
        Initialize the CLI builder.

        Args:
            item: Item request
            config (Config|None): The Config instance (optional)

        """
        from app.library.ItemDTO import Item

        if not isinstance(item, Item):
            msg = f"Expected Item instance, got {type(item).__name__}"
            raise ValueError(msg)

        self.item = item
        preset_name = item.preset if item.preset else self._config.default_preset
        self.preset: Preset | None = YTDLPCli._get_presets().get(preset_name)
        self._config: Config = config or Config.get_instance()

    @staticmethod
    def _get_presets():
        from app.features.presets.service import Presets

        return Presets.get_instance()

    def build(self) -> tuple[str, dict]:
        """
        Build the CLI command following make_command logic.

        Returns:
            tuple[str, dict]: (command_string, info_dict)

        """
        template: str | None = None
        save_path: str | None = None
        cookie_file: Path | None = None
        cli_args: ARGSMerger = ARGSMerger.get_instance()

        if self.item.cookies:
            cookie_file = create_cookies_file(self.item.cookies)

        if self.item.folder:
            save_path = str(Path(self._config.download_path) / self.item.folder.lstrip("/"))

        if self.item.template:
            template = self.item.template

        if self.preset:
            if self.preset.cookies and cookie_file is None:
                cookie_file = self.preset.get_cookies_file(config=self._config)

            if self.preset.folder and save_path is None:
                save_path = str(Path(self._config.download_path) / self.preset.folder.lstrip("/"))

            if self.preset.template and template is None:
                template = self.preset.template

            if self.preset.cli:
                cli_args.add(self._replace_vars(self.preset.cli))

        if self.item.cli:
            cli_args.add(self._replace_vars(self.item.cli))

        if not save_path:
            save_path = self._config.download_path

        if not template:
            template = self._config.output_template

        if cookie_file:
            cli_args.add(self._replace_vars(f'--cookies "{cookie_file!s}"'))

        if template:
            cli_args.add(self._replace_vars(f'--output "{template}"'))

        if save_path:
            cli_args.add(self._replace_vars(f'--paths "home:{save_path}"'))

        cli_args.add(self._replace_vars(f'--paths "temp:{self._config.temp_path}"'))

        if self.item.url:
            cli_args.add(self.item.url)

        command: str = self._replace_vars(str(cli_args))

        info: dict[str, Any] = {
            "command": command,
            "dict": cli_args.as_dict(),
            "ytdlp": cli_args.as_ytdlp(),
            "merged": {
                "template": template,
                "save_path": save_path,
                "cookie_file": str(cookie_file) if cookie_file else None,
            },
        }

        return command, info

    def _replace_vars(self, text: str) -> str:
        """
        Replace variables in the given text.

        Args:
            text (str): The text to replace variables in

        Returns:
            str: The text with variables replaced

        """
        for k, v in self._config.get_replacers().items():
            text: str = text.replace(f"%({k})s", v if isinstance(v, str) else str(v))

        return text


class YTDLPOpts:
    def __init__(self):
        self._config: Config = Config.get_instance()
        "The config instance."
        self._item_opts: dict = {}
        "The item options."
        self._preset_opts: dict = {}
        "The preset options."
        self._item_cli: list = []
        "The command options for yt-dlp from item."
        self._preset_cli: str = ""
        "The command options for yt-dlp from preset."

    @staticmethod
    def get_instance() -> "YTDLPOpts":
        """
        Get the instance of the class.

        Returns:
            Presets: The instance of the class

        """
        return YTDLPOpts().reset()

    def add_cli(self, args: str, from_user: int | bool = False) -> "YTDLPOpts":
        """
        Parse and add command options for yt-dlp to the item options.

        Args:
            args (str): The command options for yt-dlp to add
            from_user (bool): If the options are from the user

        Returns:
            YTDLPOpts: The instance of the class

        """
        if not args or not isinstance(args, str) or len(args) < 2:
            return self

        try:
            arg_converter(args=args, level=from_user)
        except Exception as e:
            msg = f"Invalid command options for yt-dlp were given. '{e!s}'."
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
        bad_options: dict = {}
        if from_user:
            from app.features.ytdlp.utils import _DATA

            bad_options: dict[str, str] = {k: v for d in _DATA.REMOVE_KEYS for k, v in d.items()}

        for key, value in config.items():
            if from_user and key in bad_options:
                continue

            self._item_opts[key] = value

        return self

    def preset(self, name: str) -> "YTDLPOpts":
        """
        Add the preset options to the item options.

        Args:
            name (str): The name of the preset

        Returns:
            YTDLPOpts: The instance of the class

        """
        preset: Preset | None = YTDLPCli._get_presets().get(name)
        if not preset:
            return self

        if preset.cli:
            try:
                arg_converter(args=preset.cli, level=True)
                self._preset_opts = {}
                self._preset_cli = preset.cli
            except Exception as e:
                msg: str = f"Invalid preset '{preset.name}' command options for yt-dlp. '{e!s}'."
                raise ValueError(msg) from e

        if preset.cookies:
            try:
                file: Path | None = preset.get_cookies_file(config=self._config)
                if file and file.exists():
                    self._preset_opts["cookiefile"] = str(file)
            except ValueError as e:
                LOG.error(f"Failed to load '{preset.name}' cookies. {e!s}")

        if preset.template:
            self._preset_opts["outtmpl"] = {"default": preset.template, "chapter": self._config.output_template_chapter}

        if preset.folder:
            self._preset_opts["paths"] = {
                "home": calc_download_path(base_path=Path(self._config.download_path), folder=preset.folder),
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
        default_opts: dict = {}
        default_opts["paths"] = {"home": self._config.download_path, "temp": self._config.temp_path}
        default_opts["outtmpl"] = {
            "default": self._config.output_template,
            "chapter": self._config.output_template_chapter,
        }

        if not isinstance(self._item_cli, list):
            self._item_cli = []

        merge: list[str] = []
        if self._preset_cli and len(self._preset_cli) > 1:
            merge.append(self._preset_cli)

        if len(merge) > 0:
            # prepend the yt-dlp command options to the list
            self._item_cli = merge + self._item_cli

        user_cli: dict = {}

        if len(self._item_cli) > 0:
            try:
                user_cli = "\n".join(self._item_cli)
                for k, v in self._config.get_replacers().items():
                    user_cli = user_cli.replace(f"%({k})s", v if isinstance(v, str) else str(v))

                user_cli: dict = arg_converter(args=user_cli, level=True)
            except Exception as e:
                msg = f"Invalid command options for yt-dlp were given. '{e!s}'."
                raise ValueError(msg) from e

        data: dict = merge_dict(user_cli, merge_dict(self._item_opts, merge_dict(self._preset_opts, default_opts)))

        if not keep:
            self.reset()

        if "format" in data:
            if data["format"] in ["not_set", "default", "best"]:
                data["format"] = None

            if data["format"] == "-best":
                data["format"] = data["format"][1:]

        if self._config.debug:
            LOG.debug(f"Final yt-dlp options: '{data!s}'.")

        return data

    def reset(self) -> "YTDLPOpts":
        """
        Reset the item options.

        Returns:
            YTDLPOpts: The instance of the class

        """
        self._item_opts = {}
        self._item_cli = []
        self._preset_cli = ""
        self._preset_opts = {}

        return self
