import { beforeAll, beforeEach, describe, expect, it, mock } from 'bun:test';

const store = new Map<string, unknown>();

const cache = {
  get: mock(<T>(key: string) => (store.has(key) ? (store.get(key) as T) : null)),
  set: mock((key: string, value: unknown) => {
    store.set(key, value);
  }),
  remove: mock((key: string) => {
    store.delete(key);
  }),
};

mock.module('~/utils/cache', () => ({
  useLocalCache: () => cache,
}));

let media: Awaited<typeof import('~/utils/media')>;

beforeAll(async () => {
  media = await import('~/utils/media');
});

beforeEach(() => {
  store.clear();
  cache.get.mockClear();
  cache.set.mockClear();
  cache.remove.mockClear();
});

describe('media utils', () => {
  it('clamp_seekable_range', () => {
    const seekable = {
      length: 1,
      start: () => 12,
      end: () => 48,
    } as TimeRanges;

    expect(media.clampResumeTime({ duration: Number.NaN, seekable }, 4)).toBe(12);
    expect(media.clampResumeTime({ duration: Number.NaN, seekable }, 22)).toBe(22);
    expect(media.clampResumeTime({ duration: Number.NaN, seekable }, 60)).toBe(48);
  });

  it('store_resume_state', () => {
    media.save('item-1', 42);
    expect(media.read('item-1')).toBe(42);
  });

  it('clear_resume_state', () => {
    media.save('item-1', 17);
    media.clear('item-1');

    expect(cache.remove).toHaveBeenCalledWith('video:item-1');
    expect(media.read('item-1')).toBe(0);
  });

  it('clear_resume_near_end', () => {
    expect(media.nearEnd({ currentTime: 97, duration: 100 })).toBe(true);
    expect(media.nearEnd({ currentTime: 80, duration: 100 })).toBe(false);
  });
});
