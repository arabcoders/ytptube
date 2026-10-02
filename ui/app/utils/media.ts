import { useLocalCache } from '~/utils/cache';
import { ensure_api_success, parse_api_response, request } from '~/utils';

const KEY = 'video:';
let cache: ReturnType<typeof useLocalCache> | null = null;

const getCache = (): ReturnType<typeof useLocalCache> => {
  if (!cache) {
    cache = useLocalCache();
  }

  return cache;
};

const read = (id: string | null | undefined, scope: string | null = 'shared'): number => {
  if (!id || !scope) {
    return 0;
  }

  try {
    const key = scope === 'shared' ? `${KEY}${id}` : `${KEY}${scope}:${id}`;
    const time = Number(getCache().get<number>(key));
    return Number.isFinite(time) && time > 0 ? time : 0;
  } catch {
    return 0;
  }
};

const save = (
  id: string | null | undefined,
  time: number,
  scope: string | null = 'shared',
): void => {
  if (!id || !scope || !Number.isFinite(time) || time <= 0) {
    return;
  }

  const key = scope === 'shared' ? `${KEY}${id}` : `${KEY}${scope}:${id}`;
  getCache().set(key, time, 24 * 60 * 60 * 1000);
};

const clear = (id: string | null | undefined, scope: string | null = 'shared'): void => {
  if (!id || !scope) {
    return;
  }

  const key = scope === 'shared' ? `${KEY}${id}` : `${KEY}${scope}:${id}`;
  getCache().remove(key);
};

const readRemote = async (id: string): Promise<number | null | undefined> => {
  try {
    const response = await request(`/api/playback/${id}`, { timeout: 5 });
    await ensure_api_success(response);
    const { position: value } = await parse_api_response<{ position: unknown }>(response.json());
    if (value === null) return null;
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : undefined;
  } catch {
    return undefined;
  }
};

const saveRemote = async (id: string, time: number | null): Promise<boolean> => {
  try {
    const response = await request(`/api/playback/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ position: time }),
      keepalive: true,
      timeout: 5,
    });
    await ensure_api_success(response);
    return true;
  } catch {
    return false;
  }
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
export { clampResumeTime, clear, nearEnd, read, readRemote, save, saveRemote };
