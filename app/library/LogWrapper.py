import logging
import weakref
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(kw_only=True)
class LogTarget:
    """
    A data class that represents a logging target with its level and type.

    Attributes:
        name (str): The name of the logging target.
        target: The logging target, which can be a logging.Logger instance or a callable.
        level (int): The logging level for the target.
        logger (bool): True if the target is a logging.Logger instance, False otherwise.
        type: The type of the target.

    """

    name: str | None = None
    target: logging.Logger|Callable
    level: int
    logger: bool


class LogWrapper:
    """
    A wrapper class for logging that allows adding multiple logging targets with different logging levels.

    Attributes:
        targets (list[dict]): A list of dictionaries where each dictionary represents a logging target with its level and type.

    Methods:
        add_target(target, level=logging.DEBUG):
            Adds a new logging target with the specified logging level.

        has_targets():
            Checks if there are any logging targets added.

        _log(level, msg, *args, **kwargs):
            Logs a message to all targets that have a logging level less than or equal to the specified level.

        debug(msg, *args, **kwargs):
            Logs a debug message to all targets.

        info(msg, *args, **kwargs):
            Logs an info message to all targets.

        warning(msg, *args, **kwargs):
            Logs a warning message to all targets.

        error(msg, *args, **kwargs):
            Logs an error message to all targets.

        critical(msg, *args, **kwargs):
            Logs a critical message to all targets.

    """

    targets: list[LogTarget] = []
    """A list of dictionaries where each dictionary represents a logging target with its level and type."""

    def __init__(self):
        self.targets: list[LogTarget] = []
        weakref.finalize(self, LogWrapper.cleanup, self)

    def add_target(self, target: logging.Logger | Callable, level: int = logging.DEBUG):
        """
        Adds a new logging target with the specified logging level.

        Args:
            target (logging.Logger|Callable): The logging target, which can be a logging.Logger instance or a Callable.
            level (int): The logging level for the target. Defaults to logging.DEBUG.

        """
        if not isinstance(target, logging.Logger | Callable):
            msg = "Target must be a logging.Logger instance or a callable."
            raise TypeError(msg)

        self.targets.append(
            LogTarget(
                name=target.name if isinstance(target, logging.Logger) else None,
                target=target,
                level=level,
                logger=isinstance(target, logging.Logger),
            )
        )

    def cleanup(self, name: str = "yt-dlp"):
        """
        Remove automatic handlers

        Args:
            name (str): The name of the logger to clean up. Defaults to "ytdlp".

        """
        mgr = logging.root.manager
        to_drop = []

        for tgt in list(self.targets):
            # only consider real Logger targets whose name
            if tgt.logger and tgt.name and tgt.name.startswith(name):
                name = tgt.name
                logger = tgt.target

                # 1) detach all handlers.
                for h in list(logger.handlers):
                    logger.removeHandler(h)

                # 2) restore default logger settings
                logger.propagate = True
                logger.setLevel(logging.NOTSET)

                # 3) purge logger & its children from the internal registry
                for key in [k for k in mgr.loggerDict if k == name or k.startswith(name + ".")]:
                    mgr.loggerDict.pop(key, None)

                to_drop.append(tgt)

        # drop those targets from our wrapper
        self.targets = [t for t in self.targets if t not in to_drop]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()

    def has_targets(self):
        """
        Checks if there are any logging targets added.

        Returns:
            bool: True if there are targets, False otherwise.

        """
        return len(self.targets) > 0

    def _log(self, level, msg, *args, **kwargs):
        """
        Logs a message to all targets that have a logging level less than or equal to the specified level.

        Args:
            level (int): The logging level of the message.
            msg (str): The message to log.
            *args: Additional positional arguments to pass to the logging method.
            **kwargs: Additional keyword arguments to pass to the logging method.

        """
        for target in self.targets:
            if level < target.level:
                continue

            if target.logger:
                target.target.log(level, msg, *args, **kwargs)
            else:
                target.target(level, msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        """
        Logs a debug message to all targets.

        Args:
            msg (str): The message to log.
            *args: Additional positional arguments to pass to the logging method.
            **kwargs: Additional keyword arguments to pass to the logging method.

        """
        self._log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """
        Logs an info message to all targets.

        Args:
            msg (str): The message to log.
            *args: Additional positional arguments to pass to the logging method.
            **kwargs: Additional keyword arguments to pass to the logging method.

        """
        self._log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """
        Logs a warning message to all targets.

        Args:
            msg (str): The message to log.
            *args: Additional positional arguments to pass to the logging method.
            **kwargs: Additional keyword arguments to pass to the logging method.

        """
        self._log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """
        Logs an error message to all targets.

        Args:
            msg (str): The message to log.
            *args: Additional positional arguments to pass to the logging method.
            **kwargs: Additional keyword arguments to pass to the logging method.

        """
        self._log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """
        Logs a critical message to all targets.

        Args:
            msg (str): The message to log.
            *args: Additional positional arguments to pass to the logging method.
            **kwargs: Additional keyword arguments to pass to the logging method.

        """
        self._log(logging.CRITICAL, msg, *args, **kwargs)
