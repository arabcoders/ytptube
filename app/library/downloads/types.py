"""Shared types and protocols for the downloads module."""

from typing import Any


class Terminator:
    """
    Sentinel class to signal termination of a status queue.

    Used to indicate that no more status updates will be sent through.
    """


StatusDict = dict[str, Any]
"""Type alias for status update dictionaries."""
