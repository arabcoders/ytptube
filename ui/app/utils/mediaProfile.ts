import type { StoreItem } from '~/types/store';

const formatCodec = (codec?: string): string => {
  if (!codec) {
    return '';
  }

  const names: Record<string, string> = {
    aac: 'AAC',
    av1: 'AV1',
    h264: 'H.264',
    hevc: 'HEVC',
    opus: 'Opus',
    vp9: 'VP9',
  };

  return names[codec] || codec.toUpperCase();
};

const bitrateLabel = (bitrate?: number | string): string => {
  const value = Number(bitrate);

  if (!Number.isFinite(value) || value <= 0) {
    return '';
  }

  return `${Math.round(value / 1000)} kbps`;
};

export const mediaProfileLabel = (item: StoreItem): string => {
  const profile = item.extras?.media_profile;

  if (!profile) {
    return '';
  }

  const video = profile.video;

  if (video?.height) {
    const fps = video.fps && video.fps >= 50 ? Math.round(video.fps) : '';
    return [formatCodec(video.codec), `${video.height}p${fps}`].filter(Boolean).join(' / ');
  }

  const audio = profile.audio;

  if (audio) {
    return [formatCodec(audio.codec), bitrateLabel(audio.bitrate)].filter(Boolean).join(' / ');
  }

  return '';
};
