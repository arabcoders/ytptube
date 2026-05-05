import { describe, expect, it, mock } from 'bun:test';

describe('media utils', () => {
  it('clamp_seekable_range', async () => {
    const { clampResumeTime } = await import('~/utils/media');

    const seekable = {
      length: 1,
      start: () => 12,
      end: () => 48,
    } as TimeRanges;

    expect(clampResumeTime({ duration: Number.NaN, seekable }, 4)).toBe(12);
    expect(clampResumeTime({ duration: Number.NaN, seekable }, 22)).toBe(22);
    expect(clampResumeTime({ duration: Number.NaN, seekable }, 60)).toBe(48);
  });

  it('resume_keep_time_and_play', async () => {
    const { resumeMedia } = await import('~/utils/media');

    const play = mock(async () => {});
    const target = {
      currentTime: 0,
      duration: 100,
      seekable: { length: 0 } as TimeRanges,
      play,
    } as unknown as HTMLMediaElement;

    await resumeMedia(target, { time: 33, shouldPlay: true });

    expect(target.currentTime).toBe(33);
    expect(play).toHaveBeenCalledTimes(1);
  });

  it('read_resume_state', async () => {
    const { readResumeState } = await import('~/utils/media');

    const target = {
      currentTime: 19,
      paused: false,
      ended: false,
    } as HTMLMediaElement;

    expect(readResumeState(target)).toEqual({ time: 19, shouldPlay: true });
    expect(readResumeState(null)).toEqual({ time: 0, shouldPlay: false });
  });
});
