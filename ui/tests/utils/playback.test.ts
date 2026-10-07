import { describe, expect, it } from 'bun:test';
import { playbackMediaHasNoVideo } from '~/utils/playback';

describe('playback diagnostics', () => {
  it('detect_missing_video', () => {
    const video = {
      readyState: 2,
      paused: false,
      seeking: false,
      currentTime: 3,
      videoWidth: 0,
      videoHeight: 0,
    };
    expect(playbackMediaHasNoVideo(video, true)).toBe(true);
    expect(playbackMediaHasNoVideo(video, false)).toBe(false);
    expect(playbackMediaHasNoVideo({ ...video, seeking: true }, true)).toBe(false);
    expect(playbackMediaHasNoVideo({ ...video, paused: true }, true)).toBe(false);
  });
});
