# flake8: noqa: F401
from yt_dlp.globals import postprocessors

from .make_nfo import NFOMakerMoviePP, NFOMakerTvPP

_ytptube_pps = {name: value for name, value in globals().items() if name.endswith("PP")}

postprocessors.value.update(_ytptube_pps)

__all__ = list(_ytptube_pps.values())
