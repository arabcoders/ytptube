export type SubtitleTrack = {
  id: string;
  lang: string;
  name: string;
  source_format: string;
  delivery_format: 'vtt' | 'ass';
  renderer: 'native' | 'assjs' | 'bitmap' | 'unsupported';
  url: string;
};
