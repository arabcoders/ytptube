import json
from datetime import date
from pathlib import Path

from yt_dlp.utils import DateRange


class Encoder(json.JSONEncoder):
    """
    This class is used to serialize objects to JSON.
    The only difference between this and the default JSONEncoder is that this one
    will call the __dict__ method of an object if it exists.
    """

    def default(self, o):
        if isinstance(o, Path):
            return str(o)

        if isinstance(o, DateRange):
            return {"start": str(o.start).replace("-", ""), "end": str(o.end).replace("-", "")}

        if isinstance(o, date):
            return str(o)

        if isinstance(o, object):
            if hasattr(o, "serialize"):
                return o.serialize()

            if hasattr(o, "__dict__"):
                return o.__dict__

        return json.JSONEncoder.default(self, o)
