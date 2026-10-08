type KeyboardShortcutContext = {
  video: HTMLMediaElement;
};

type VideoTrackElement = {
  file: string;
  kind: string;
  label: string;
  lang: string;
};

type VideoSourceElement = {
  src: string;
  type: string;
  onerror: (e: Event) => void;
};

type FFProbeTags = {
  major_brand?: string;
  minor_version?: string;
  compatible_brands?: string;
  encoder?: string;
  title?: string;
  artist?: string;
  album_artist?: string;
  album?: string;
  date?: string;
  track?: string;
  genre?: string;
};

type FFProbeMetadata = {
  filename: string;
  nb_streams: number;
  nb_programs: number;
  format_name: string;
  format_long_name: string;
  start_time: string;
  duration: string;
  size: string;
  bit_rate: string;
  tags: FFProbeTags;
};

type FFProbeStream = {
  index: number;
  codec_name: string;
  codec_type: string;
  width?: number;
  height?: number;
  framerate?: number | null;
  tags?: {
    language?: string;
    title?: string;
    handler_name?: string;
  };
  channels?: number;
  channel_layout?: string;
  disposition?: { default?: number; attached_pic?: number };
  sample_rate?: string;
  bit_rate?: string;
};

type FFProbeResult = {
  metadata: FFProbeMetadata;
  video: Array<FFProbeStream>;
  audio: Array<FFProbeStream>;
  subtitle: Array<FFProbeStream>;
  attachment: Array<FFProbeStream>;
  is_video: boolean;
  is_audio: boolean;
};

type FileInfo = {
  title: string;
  ffprobe: FFProbeResult;
  mimetype: string;
  sidecar?: {
    image?: Array<{ file: string }>;
    text?: Array<{ file: string }>;
    subtitle?: Array<{ name: string; lang: string; file: string }>;
  };
  error?: string;
};

type PlayerSourceElement = {
  src: string;
  type?: string;
  onerror?: (e: Event) => void;
};

type PlayerSession = {
  player_id: string;
  title: string;
  mimetype: string;
  poster: string | null;
  media_url: string;
  generation: number[];
  expires_in: number;
  ffprobe: FFProbeResult;
  audio_stream_index: number | null;
  subtitle_track_id: string | null;
  audio_tracks: Array<{
    stream_index: number;
    lang: string;
    name: string;
    codec: string;
    channels: number | null;
    channel_layout: string;
    default: boolean;
  }>;
  subtitles: import('./subtitles').SubtitleTrack[];
  fonts: import('../utils/playback').PlayerFont[];
  stream_url: string;
};

export type {
  VideoTrackElement,
  VideoSourceElement,
  PlayerSourceElement,
  PlayerSession,
  FFProbeResult,
  FileInfo,
  KeyboardShortcutContext,
};
