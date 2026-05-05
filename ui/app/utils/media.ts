type ResumeState = {
  time: number;
  shouldPlay: boolean;
};

const clampResumeTime = (
  target: Pick<HTMLMediaElement, 'duration' | 'seekable'>,
  time: number,
): number => {
  if (!Number.isFinite(time) || time <= 0) {
    return 0;
  }

  const seekable = target.seekable;
  if (seekable && seekable.length > 0) {
    const last = seekable.length - 1;
    const start = seekable.start(last);
    const end = seekable.end(last);

    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return 0;
    }

    return Math.min(Math.max(time, start), end);
  }

  const duration = target.duration;
  if (Number.isFinite(duration) && duration > 0) {
    return Math.min(time, Math.max(duration - 0.25, 0));
  }

  return time;
};

const readResumeState = (target: HTMLMediaElement | null): ResumeState => {
  if (!target) {
    return { time: 0, shouldPlay: false };
  }

  const time =
    Number.isFinite(target.currentTime) && target.currentTime > 0 ? target.currentTime : 0;
  return {
    time,
    shouldPlay: !target.paused && !target.ended,
  };
};

const resumeMedia = async (target: HTMLMediaElement | null, state: ResumeState): Promise<void> => {
  if (!target) {
    return;
  }

  const nextTime = clampResumeTime(target, state.time);
  if (nextTime > 0) {
    try {
      target.currentTime = nextTime;
    } catch {}
  }

  if (state.shouldPlay) {
    try {
      await target.play();
    } catch {}
  }
};

export { clampResumeTime, readResumeState, resumeMedia };
export type { ResumeState };
