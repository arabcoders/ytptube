type KeyboardShortcutContext = {
  video: HTMLVideoElement
}

type video_track_element = {
  file: string,
  kind: string,
  label: string,
  lang: string,
}

type video_source_element = {
  src: string,
  type: string,
  onerror: (e: Event) => void,
}

type FFProbeTags = {
  major_brand?: string,
  minor_version?: string,
  compatible_brands?: string,
  encoder?: string,
  title?: string,
  artist?: string,
  album_artist?: string,
  album?: string,
  date?: string,
  track?: string,
  genre?: string,
}

type FFProbeMetadata = {
  filename: string,
  nb_streams: number,
  nb_programs: number,
  format_name: string,
  format_long_name: string,
  start_time: string,
  duration: string,
  size: string,
  bit_rate: string,
  tags: FFProbeTags
}

type FFProbeStream = {
  index: number,
  codec_name: string,
  codec_type: string,
  width?: number,
  height?: number,
  tags?: {
    language?: string,
    title?: string,
    handler_name?: string,
  },
  channels?: number,
  sample_rate?: string,
  bit_rate?: string,
}

type FFProbeResult = {
  metadata: FFProbeMetadata,
  video: Array<FFProbeStream>,
  audio: Array<FFProbeStream>,
  subtitle: Array<FFProbeStream>,
  attachment: Array<FFProbeStream>,
  is_video: boolean,
  is_audio: boolean,
}

type file_info = {
  title: string,
  ffprobe: FFProbeResult,
  mimetype: string,
  sidecar?: {
    image?: Array<{ file: string }>,
    text?: Array<{ file: string }>,
    subtitle?: Array<{ name: string, lang: string, file: string }>,
  },
  error?: string,
}

export type {
  video_track_element,
  video_source_element,
  FFProbeResult,
  file_info,
  KeyboardShortcutContext,
};
