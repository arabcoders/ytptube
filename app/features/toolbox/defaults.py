from app.features.toolbox.definitions import ShippedDefinition

REMUX = ShippedDefinition(
    default_key="remux",
    name="Remux into MP4",
    description="Copy streams into MP4 without re-encoding.",
    output_extension=".mp4",
    supports_overwrite=True,
    command=[
        "ffmpeg",
        "-nostdin",
        "-n",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostats",
        "-progress",
        "pipe:1",
        "-i",
        "{input}",
        "-map",
        "0",
        "-c",
        "copy",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        "-movflags",
        "+faststart",
        "{output}",
    ],
)

DEFAULT_TOOLS = (REMUX,)
