import json
from datetime import date
from pathlib import Path

from yt_dlp.networking.impersonate import ImpersonateTarget
from yt_dlp.utils import DateRange


class Encoder(json.JSONEncoder):
    def default(self, o):
        from app.features.downloads.items import ItemDTO

        if isinstance(o, DateRange):
            return {"start": str(o.start).replace("-", ""), "end": str(o.end).replace("-", "")}

        if isinstance(o, (Path, date, ImpersonateTarget, ValueError)):
            return str(o)

        if isinstance(o, ItemDTO):
            return o.serialize()

        if isinstance(o, object):
            if hasattr(o, "serialize"):
                return o.serialize()

            if hasattr(o, "model_dump"):
                return o.model_dump()

            if hasattr(o, "__dict__"):
                return o.__dict__

        return json.JSONEncoder.default(self, o)
