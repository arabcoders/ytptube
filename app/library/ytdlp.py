import yt_dlp

import app.postprocessors  # noqa: F401


class YTDLP(yt_dlp.YoutubeDL):
    _interrupted = False

    def _delete_downloaded_files(self, *args, **kwargs):
        if self._interrupted:
            self.to_screen("[info] Cancelled — skipping temp cleanup.")
            return None

        return super()._delete_downloaded_files(*args, **kwargs)
