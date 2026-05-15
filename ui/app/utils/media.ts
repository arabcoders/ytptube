import { useLocalCache } from '~/utils/cache';

const KEY = 'video:';
const cache = useLocalCache();

const read = (id: string | null | undefined): number => {
  if (!id) {
    return 0;
  }

  try {
    const time = Number(cache.get<number>(`${KEY}${id}`));
    return Number.isFinite(time) && time > 0 ? time : 0;
  } catch {
    return 0;
  }
};

const save = (id: string | null | undefined, time: number): void => {
  if (!id || !Number.isFinite(time) || time <= 0) {
    return;
  }

  cache.set(`${KEY}${id}`, time, 3600 * 24);
};

const clear = (id: string | null | undefined): void => {
  if (!id) {
    return;
  }

  cache.remove(`${KEY}${id}`);
};

const nearEnd = (
  target: Pick<HTMLMediaElement, 'currentTime' | 'duration'> | null,
  pad: number = 5,
): boolean => {
  if (!target) {
    return false;
  }

  const duration = target.duration;
  if (!Number.isFinite(duration) || duration <= 0) {
    return false;
  }

  const time =
    Number.isFinite(target.currentTime) && target.currentTime > 0 ? target.currentTime : 0;
  return duration - time <= pad;
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
export { clampResumeTime, clear, nearEnd, read, save };
