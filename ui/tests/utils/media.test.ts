import { afterEach, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';
import * as utils from '~/utils';
import * as media from '~/utils/media';

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  mock.restore();
  localStorage.clear();
});

describe('media utils', () => {
  it('clamp_seekable_range', () => {
    const seekable = { length: 1, start: () => 12, end: () => 48 } as TimeRanges;
    expect(media.clampResumeTime({ duration: Number.NaN, seekable }, 4)).toBe(12);
    expect(media.clampResumeTime({ duration: Number.NaN, seekable }, 22)).toBe(22);
    expect(media.clampResumeTime({ duration: Number.NaN, seekable }, 60)).toBe(48);
  });

  it('store_resume_state', () => {
    media.save('item-1', 42);
    expect(media.read('item-1')).toBe(42);
    expect(JSON.parse(localStorage.getItem('video:item-1')!).ttl).toBe(24 * 60 * 60 * 1000);
  });

  it('clear_resume_state', () => {
    media.save('item-1', 17);
    media.clear('item-1');
    expect(media.read('item-1')).toBe(0);
  });

  it('isolates_local_users', () => {
    media.save('item-1', 8);
    media.save('item-1', 17, 'user:1');
    media.save('item-1', 22, 'user:2');
    media.clear('item-1', 'user:1');
    expect(media.read('item-1', 'user:1')).toBe(0);
    expect(media.read('item-1', 'user:2')).toBe(22);
    expect(media.read('item-1')).toBe(8);
    media.save('item-1', 50, null);
    expect(media.read('item-1', null)).toBe(0);
    expect(media.read('item-1')).toBe(8);
  });

  it('clear_resume_near_end', () => {
    expect(media.nearEnd({ currentTime: 97, duration: 100 })).toBe(true);
    expect(media.nearEnd({ currentTime: 80, duration: 100 })).toBe(false);
  });

  it('reads_remote_position', async () => {
    const request = spyOn(utils, 'request').mockResolvedValue(
      new Response(JSON.stringify({ position: 12 })),
    );
    expect(await media.readRemote('item-1')).toBe(12);
    expect(request).toHaveBeenCalledWith('/api/playback/item-1', { timeout: 5 });
  });

  it('reads_remote_empty', async () => {
    spyOn(utils, 'request').mockResolvedValue(new Response(JSON.stringify({ position: null })));
    expect(await media.readRemote('item-1')).toBeNull();
  });

  it('handles_remote_failure', async () => {
    const request = spyOn(utils, 'request').mockRejectedValueOnce(new Error('offline'));
    expect(await media.readRemote('item-1')).toBeUndefined();
    request.mockResolvedValueOnce(new Response('{}', { status: 503 }));
    expect(await media.readRemote('item-1')).toBeUndefined();
    request.mockResolvedValueOnce(new Response('invalid json'));
    expect(await media.readRemote('item-1')).toBeUndefined();
  });

  it('rejects_remote_values', async () => {
    const request = spyOn(utils, 'request');
    for (const value of [{}, { position: '12' }, { position: -1 }, { position: true }]) {
      request.mockResolvedValueOnce(new Response(JSON.stringify(value)));
      expect(await media.readRemote('item-1')).toBeUndefined();
    }
  });

  it('saves_remote_keepalive', async () => {
    const request = spyOn(utils, 'request').mockResolvedValue(new Response('{}'));
    expect(await media.saveRemote('item-1', 9)).toBe(true);
    expect(request).toHaveBeenCalledWith('/api/playback/item-1', {
      method: 'PUT',
      body: JSON.stringify({ position: 9 }),
      keepalive: true,
      timeout: 5,
    });
    expect(await media.saveRemote('item-1', null)).toBe(true);
    expect(request.mock.calls.at(-1)?.[1]?.body).toBe(JSON.stringify({ position: null }));
    request.mockResolvedValueOnce(new Response('{}', { status: 503 }));
    expect(await media.saveRemote('item-1', 9)).toBe(false);
  });
});
