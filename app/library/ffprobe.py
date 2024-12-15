"""
Python wrapper for ffprobe command line tool. ffprobe must exist in the path.
"""
import asyncio
import functools
import json
import operator
import os


class FFProbeError(Exception):
    pass


class FFStream:
    """
    An object representation of an individual stream in a multimedia file.
    """

    def __init__(self, json_data: dict):
        for key, val in json_data.items():
            setattr(self, key, val)

        try:
            self.__dict__['framerate'] = round(
                functools.reduce(
                    operator.truediv, map(int, self.__dict__.get('avg_frame_rate', '').split('/'))
                )
            )
        except ValueError:
            self.__dict__['framerate'] = None
        except ZeroDivisionError:
            self.__dict__['framerate'] = 0

    def __repr__(self):
        if not 'codec_long_name' in self.__dict__:
            self.codec_long_name = self.__dict__.get('codec_name', '')

        if self.is_video():
            return f"<Stream: #{self.index} [{self.codec_type}] {self.codec_long_name}, {self.framerate}, ({self.width}x{self.height})>"

        if self.is_audio():
            return f"<Stream: #{self.index} [{self.codec_type}] {self.codec_long_name}, channels: {self.channels} ({self.channel_layout}), " "{sample_rate}Hz> "

        if self.is_subtitle() or self.is_attachment():
            return f"<Stream: #{self.index} [{self.codec_type}] {self.codec_long_name}>"

        return f"<Stream: #{self.index} [{self.codec_type}]>"

    def is_audio(self):
        """
        Is this stream labelled as an audio stream?
        """
        return self.__dict__.get('codec_type', None) == 'audio'

    def is_video(self):
        """
        Is the stream labelled as a video stream.
        """
        return self.__dict__.get('codec_type', None) == 'video'

    def is_subtitle(self):
        """
        Is the stream labelled as a subtitle stream.
        """
        return self.__dict__.get('codec_type', None) == 'subtitle'

    def is_attachment(self):
        """
        Is the stream labelled as a attachment stream.
        """
        return self.__dict__.get('codec_type', None) == 'attachment'

    def frame_size(self):
        """
        Returns the pixel frame size as an integer tuple (width,height) if the stream is a video stream.
        Returns None if it is not a video stream.
        """
        size = None
        if self.is_video():
            width = self.__dict__['width']
            height = self.__dict__['height']

            if width and height:
                try:
                    size = (int(width), int(height))
                except ValueError:
                    raise FFProbeError("None integer size {}:{}".format(width, height))
        else:
            return None

        return size

    def pixel_format(self):
        """
        Returns a string representing the pixel format of the video stream. e.g. yuv420p.
        Returns none is it is not a video stream.
        """
        return self.__dict__.get('pix_fmt', None)

    def frames(self):
        """
        Returns the length of a video stream in frames. Returns 0 if not a video stream.
        """
        if self.is_video() or self.is_audio():
            try:
                frame_count = int(self.__dict__.get('nb_frames', ''))
            except ValueError:
                raise FFProbeError('None integer frame count')
        else:
            frame_count = 0

        return frame_count

    def duration_seconds(self):
        """
        Returns the runtime duration of the video stream as a floating point number of seconds.
        Returns 0.0 if not a video stream.
        """
        if self.is_video() or self.is_audio():
            try:
                duration = float(self.__dict__.get('duration', ''))
            except ValueError:
                raise FFProbeError('None numeric duration')
        else:
            duration = 0.0

        return duration

    def language(self):
        """
        Returns language tag of stream. e.g. eng
        """
        return self.__dict__.get('TAG:language', None)

    def codec(self):
        """
        Returns a string representation of the stream codec.
        """
        return self.__dict__.get('codec_name', None)

    def codec_description(self):
        """
        Returns a long representation of the stream codec.
        """
        return self.__dict__.get('codec_long_name', None)

    def codec_tag(self):
        """
        Returns a short representative tag of the stream codec.
        """
        return self.__dict__.get('codec_tag_string', None)

    def bit_rate(self):
        """
        Returns bit_rate as an integer in bps
        """
        try:
            return int(self.__dict__.get('bit_rate', ''))
        except ValueError:
            raise FFProbeError('None integer bit_rate')


class FFProbe:
    """
    FFProbe wraps the ffprobe command and pulls the data into an object form::
        metadata=FFProbe('multimedia-file.mov')
    """
    audio: list[FFStream] = []
    attachment: list[FFStream] = []
    streams: list[FFStream] = []
    subtitle: list[FFStream] = []
    video: list[FFStream] = []
    metadata: dict = {}
    path_to_video: str = ''

    def __init__(self, path_to_video):
        self.path_to_video = path_to_video

    async def run(self):
        try:
            with open(os.devnull, 'w') as tempf:
                await asyncio.create_subprocess_exec(
                    "ffprobe", "-h", stdout=tempf, stderr=tempf
                )
        except FileNotFoundError:
            raise IOError('ffprobe not found.')

        if not os.path.isfile(self.path_to_video):
            raise IOError(f"No such media file '{self.path_to_video}'.")

        args = [
            '-v', 'quiet',
            '-of', 'json',
            '-show_streams',
            '-show_format',
            self.path_to_video,
        ]
        p = await asyncio.create_subprocess_exec(
            'ffprobe', *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        exitCode = await p.wait()

        data, err = await p.communicate()
        if 0 == exitCode:
            parsed: dict = json.loads(data.decode('utf-8'))
        else:
            raise FFProbeError(f"FFProbe return with non-0 exit code. '{err.decode('utf-8')}'")

        stream = False
        self.streams = []
        self.video = []
        self.audio = []
        self.subtitle = []
        self.attachment = []

        for stream in parsed.get('streams', []):
            self.streams.append(FFStream(stream))

        self.metadata = parsed.get('format', {})

        for stream in self.streams:
            if stream.is_audio():
                self.audio.append(stream)
            elif stream.is_video():
                self.video.append(stream)
            elif stream.is_subtitle():
                self.subtitle.append(stream)
            elif stream.is_attachment():
                self.attachment.append(stream)

    def __repr__(self):
        return "<FFprobe: {metadata}, {video}, {audio}, {subtitle}, {attachment}>".format(**vars(self))
