import { request } from '~/utils';

export type PlayerFont = { id: string; url: string };

export function playbackMediaHasNoVideo(
  video: Pick<
    HTMLVideoElement,
    'readyState' | 'paused' | 'seeking' | 'currentTime' | 'videoWidth' | 'videoHeight'
  > | null,
  hasVideo: boolean,
): boolean {
  return Boolean(
    hasVideo &&
    video &&
    video.readyState >= 2 &&
    !video.paused &&
    !video.seeking &&
    video.currentTime > 0 &&
    (video.videoWidth === 0 || video.videoHeight === 0),
  );
}

export function playbackMediaSnapshot(video: HTMLVideoElement | null) {
  if (!video) return null;
  const ranges = (value: TimeRanges) =>
    Array.from({ length: value.length }, (_, i) => [value.start(i), value.end(i)]);
  const quality = video.getVideoPlaybackQuality?.();
  return {
    current_src: video.currentSrc,
    current_time: video.currentTime,
    duration: Number.isFinite(video.duration) ? video.duration : null,
    paused: video.paused,
    seeking: video.seeking,
    ended: video.ended,
    ready_state: video.readyState,
    network_state: video.networkState,
    width: video.videoWidth,
    height: video.videoHeight,
    rate: video.playbackRate,
    seekable: ranges(video.seekable),
    buffered: ranges(video.buffered),
    frames: quality
      ? { total: quality.totalVideoFrames, dropped: quality.droppedVideoFrames }
      : null,
    error: video.error
      ? {
          code: video.error.code,
          message:
            ['', 'Playback aborted', 'Network error', 'Decode error', 'Source not supported'][
              video.error.code
            ] || 'Unknown media error',
        }
      : null,
  };
}

export async function loadPlayerFonts(
  fonts: PlayerFont[],
  signal: AbortSignal,
): Promise<() => void> {
  const faces: FontFace[] = [];
  const release = () => {
    for (const face of faces) document.fonts.delete(face);
  };
  try {
    for (const font of fonts) {
      const response = await request(font.url, { signal });
      if (!response.ok) throw new Error('Embedded subtitle font could not be loaded.');
      const metadata: { families: string[]; weight: string; style: string } | null = JSON.parse(
        response.headers.get('X-YTP-Font') || 'null',
      );
      if (!metadata?.families?.length)
        throw new Error('Embedded subtitle font has no family metadata.');
      const data = await response.arrayBuffer();
      for (const family of metadata.families) {
        const face = new FontFace(family, data, { weight: metadata.weight, style: metadata.style });
        await face.load();
        signal.throwIfAborted();
        document.fonts.add(face);
        faces.push(face);
      }
    }
    return release;
  } catch (error) {
    release();
    throw error;
  }
}
