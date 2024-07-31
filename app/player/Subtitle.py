import asyncio
import hashlib
import logging
import os
import tempfile
from Utils import calcDownloadPath
import pathlib

LOG = logging.getLogger('player.subtitle')


class Subtitle:
    allowedExtensions: tuple[str] = (".srt", ".vtt", ".ass",)

    async def make(self, path: str, file: str) -> bytes:
        realFile: str = calcDownloadPath(basePath=path, folder=file, createPath=False)

        rFile = pathlib.Path(realFile)

        if not rFile.exists():
            raise Exception(f"File '{file}' does not exist.")

        if not rFile.suffix in self.allowedExtensions:
            raise Exception(f"File '{file}' subtitle type is not supported.")

        if rFile.suffix is ".vtt":
            subData = ''
            with open(realFile, 'r') as f:
                subData = f.read()

            return subData

        tmpDir: str = tempfile.gettempdir()
        tmpFile = os.path.join(tmpDir, f'player.subtitle.{hashlib.md5(realFile.encode("utf-8")).hexdigest()}')

        if not os.path.exists(tmpFile):
            os.symlink(realFile, tmpFile)

        fargs = []
        fargs.append('-xerror')
        fargs.append('-hide_banner')
        fargs.append('-loglevel')
        fargs.append('error')
        fargs.append('-i')
        fargs.append(f'file:{tmpFile}')
        fargs.append('-f')
        fargs.append('webvtt')
        fargs.append('pipe:1')

        LOG.debug(f"Converting '{realFile}' into 'webvtt'. " + " ".join(fargs))

        proc = await asyncio.subprocess.create_subprocess_exec(
            'ffmpeg', *fargs,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        data, err = await proc.communicate()

        if 0 != proc.returncode:
            msg = f"Failed to convert '{realFile}' into 'webvtt'."
            LOG.error(f'{msg} {err.decode("utf-8")}.')
            raise Exception(msg)

        return data
