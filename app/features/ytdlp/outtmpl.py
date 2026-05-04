from __future__ import annotations

import re
import secrets
import string
from typing import TYPE_CHECKING, Any

from yt_dlp.utils._utils import STR_FORMAT_RE_TMPL, STR_FORMAT_TYPES

if TYPE_CHECKING:
    from collections.abc import Callable

OUTTMPL_RX: re.Pattern[str] = re.compile(STR_FORMAT_RE_TMPL.format("[^)]*", f"[{STR_FORMAT_TYPES}ljhqBUDS]"))
CALL_RX: re.Pattern[str] = re.compile(r"^(?P<name>ytp_[A-Za-z0-9_]+)(?P<args>(?::[A-Za-z0-9_]+)*)(?P<rest>.*)$")
OPERATORS: tuple[str, ...] = (",", "&", "|", ">", "+", "-", "*")


def random_text(args: tuple[str, ...], _info_dict: dict[str, Any], _state: dict[str, Any]) -> str:
    if not args:
        msg = "ytp_random requires a length argument. Use %(ytp_random:<length>)s."
        raise ValueError(msg)

    if len(args) > 2:
        msg = "ytp_random accepts at most 2 arguments: length and optional mode."
        raise ValueError(msg)

    try:
        length = int(args[0])
    except ValueError as exc:
        msg: str = f"ytp_random length must be an integer, got {args[0]!r}."
        raise ValueError(msg) from exc

    if length < 1:
        msg = "ytp_random length must be greater than 0."
        raise ValueError(msg)

    mode = args[1].lower() if len(args) > 1 else "mixed"
    if mode in ("mixed", "m"):
        alphabet = string.ascii_letters + string.digits
    elif mode in ("d", "digit", "digits", "int", "ints", "number", "numbers"):
        alphabet = string.digits
    elif mode in ("s", "str", "string", "strings", "alpha", "letter", "letters"):
        alphabet = string.ascii_letters
    else:
        msg = f"ytp_random mode must be one of mixed, d, or s. Got {args[1]!r}."
        raise ValueError(msg)

    return "".join(secrets.choice(alphabet) for _ in range(length))


CALLS: dict[str, Callable[[tuple[str, ...], dict[str, Any], dict[str, Any]], Any]] = {
    "ytp_random": random_text,
}


def split_call(key: str) -> tuple[str, tuple[str, ...], str] | None:
    if not key.startswith("ytp_"):
        return None

    if not (match := CALL_RX.match(key)):
        msg = f"Invalid YTPTube output template callable {key!r}."
        raise ValueError(msg)

    name: str | Any = match.group("name")
    rest: str | Any = match.group("rest") or ""
    if rest and rest[0] not in OPERATORS:
        msg = f"Invalid YTPTube output template callable {key!r}."
        raise ValueError(msg)

    if name not in CALLS:
        msg = f"Unsupported YTPTube output template callable {name!r}."
        raise ValueError(msg)

    raw_args: str | Any = match.group("args")
    args: tuple[str | Any, ...] = tuple(part for part in raw_args.split(":") if part)
    return name, args, rest


def rewrite_outtmpl(
    outtmpl: str,
    info_dict: dict[str, Any],
    cache: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    if "%(ytp_" not in outtmpl:
        return outtmpl, info_dict

    state: dict[str, Any] = {}
    values: dict[str, Any] = {} if cache is None else cache
    fields: dict[str, str] = {}
    enriched = dict(info_dict)

    def replace(match: re.Match[str]) -> str:
        if not (key := match.group("key")):
            return match.group(0)

        parsed = split_call(key)
        if not parsed:
            return match.group(0)

        name, args, rest = parsed
        call_key: str = ":".join((name, *args)) if args else name

        if call_key not in values:
            values[call_key] = CALLS[name](args, enriched, state)

        if call_key not in fields:
            fields[call_key] = f"__ytptube_outtmpl_{len(fields)}"

        synthetic_key: str = fields[call_key]
        enriched[synthetic_key] = values[call_key]
        return f"{match.group('prefix')}%({synthetic_key}{rest}){match.group('format')}"

    return OUTTMPL_RX.sub(replace, outtmpl), enriched
