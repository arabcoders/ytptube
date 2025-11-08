from yt_dlp.globals import postprocessors

from .nfo_maker import NFOMakerPP

_ytptube_pps: list[str] = {"NFOMakerPP": NFOMakerPP}


postprocessors.value.update(_ytptube_pps)

__all__: list = list(_ytptube_pps.values())

# Apply patch to fix MetadataParserPP assertion error
from .patch_metadata_parser import ensure_patch

ensure_patch()
