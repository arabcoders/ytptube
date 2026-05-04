export type SubtitleTrack = {
  lang: string;
  name: string;
  source_format: 'vtt' | 'srt' | 'ass';
  delivery_format: 'vtt' | 'ass';
  renderer: 'native' | 'assjs';
  url: string;
};

export type SubtitleManifestResponse = {
  subtitles: SubtitleTrack[];
};
