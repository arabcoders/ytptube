import { afterEach, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';
import { effectScope, ref } from 'vue';
import { usePlayerStartup } from '~/composables/usePlayerStartup';
import * as requests from '~/utils/playerRequests';

describe('usePlayerStartup', () => {
  let timers: Map<number, () => void>;
  let schedule: ReturnType<typeof spyOn<typeof window, 'setTimeout'>>;
  let cancel: ReturnType<typeof spyOn<typeof window, 'clearTimeout'>>;
  let scope: ReturnType<typeof effectScope>;
  let prepare: ReturnType<typeof spyOn<typeof requests, 'guardPlayerRequests'>> | undefined;

  beforeEach(() => {
    timers = new Map();
    let nextId = 0;
    schedule = spyOn(window, 'setTimeout').mockImplementation((handler) => {
      if (typeof handler !== 'function') throw new Error('Expected a timer callback');
      const id = ++nextId;
      timers.set(id, () => {
        timers.delete(id);
        handler();
      });
      return id;
    });
    cancel = spyOn(window, 'clearTimeout').mockImplementation((id) => {
      timers.delete(id);
    });
    scope = effectScope();
  });

  afterEach(() => {
    scope.stop();
    schedule.mockRestore();
    cancel.mockRestore();
    prepare?.mockRestore();
    prepare = undefined;
  });

  function setup(enabled = true, readyState = 0) {
    const video = document.createElement('video');
    Object.defineProperty(video, 'readyState', { value: readyState, configurable: true });
    const active = ref(enabled);
    const onTimeout = mock(() => {});
    const startup = scope.run(() =>
      usePlayerStartup({ video, enabled: active, onFallback: onTimeout }),
    )!;
    return { video, enabled: active, onTimeout, startup };
  }

  it('waits_for_activation', () => {
    const { video, enabled, onTimeout } = setup(false);
    video.dispatchEvent(new window.Event('loadstart'));
    expect(timers.size).toBe(0);
    enabled.value = true;
    expect(timers.size).toBe(1);
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('fallback_once', () => {
    const { video, onTimeout } = setup();
    expect(schedule.mock.calls[0]?.[1]).toBe(10000);
    video.dispatchEvent(new window.Event('loadstart'));
    video.dispatchEvent(new window.Event('progress'));
    video.dispatchEvent(new window.Event('loadstart'));
    expect(schedule).toHaveBeenCalledTimes(1);
    expect(timers.size).toBe(1);
    for (const callback of [...timers.values()]) callback();
    expect(onTimeout).toHaveBeenCalledTimes(1);
    video.dispatchEvent(new window.Event('loadstart'));
    expect(timers.size).toBe(0);
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  it.each(['loadeddata', 'canplay', 'playing'])('ignore_normal_buffering', (event) => {
    const { video, enabled, onTimeout } = setup();
    Object.defineProperty(video, 'readyState', { value: 2, configurable: true });
    video.dispatchEvent(new window.Event(event));
    Object.defineProperty(video, 'readyState', { value: 1 });
    video.dispatchEvent(new window.Event('waiting'));
    video.dispatchEvent(new window.Event('stalled'));
    video.dispatchEvent(new window.Event('loadstart'));
    enabled.value = false;
    enabled.value = true;
    expect(timers.size).toBe(0);
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('cancel_disabled_timer', () => {
    const { video, enabled, onTimeout } = setup();
    expect(timers.size).toBe(1);
    enabled.value = false;
    video.dispatchEvent(new window.Event('loadstart'));
    expect(timers.size).toBe(0);
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('cancel_disposed_timer', () => {
    const { video, onTimeout } = setup();
    expect(timers.size).toBe(1);
    scope.stop();
    video.dispatchEvent(new window.Event('loadstart'));
    expect(timers.size).toBe(0);
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('metadata_keeps_deadline', () => {
    const { video, onTimeout } = setup();
    Object.defineProperty(video, 'readyState', { value: 1 });
    video.dispatchEvent(new window.Event('loadedmetadata'));
    video.dispatchEvent(new window.Event('progress'));
    expect(timers.size).toBe(1);
    expect(schedule).toHaveBeenCalledTimes(1);
    for (const callback of [...timers.values()]) callback();
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  it('accepts_playable_data', () => {
    const { video, onTimeout } = setup();
    Object.defineProperty(video, 'readyState', { value: 2 });
    for (const callback of [...timers.values()]) callback();
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('accepts_ready_media', () => {
    const { onTimeout } = setup(true, 2);
    expect(timers.size).toBe(0);
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('releases_request_guard', async () => {
    const guard = { ready: mock(() => {}), stop: mock(() => {}) };
    prepare = spyOn(requests, 'guardPlayerRequests').mockResolvedValue(guard);
    const { startup, video, enabled } = setup(false);
    expect(await startup.prepare('/media', '/worker', new AbortController().signal)).toBe(true);
    enabled.value = true;
    Object.defineProperty(video, 'readyState', { value: 2 });
    video.dispatchEvent(new window.Event('loadeddata'));
    expect(guard.ready).toHaveBeenCalledTimes(1);
    scope.stop();
    expect(guard.stop).not.toHaveBeenCalled();
  });

  it('stops_request_guard', async () => {
    const guard = { ready: mock(() => {}), stop: mock(() => {}) };
    prepare = spyOn(requests, 'guardPlayerRequests').mockResolvedValue(guard);
    const { startup } = setup(false);
    await startup.prepare('/media', '/worker', new AbortController().signal);
    scope.stop();
    expect(guard.stop).toHaveBeenCalledTimes(1);
    expect(guard.ready).not.toHaveBeenCalled();
  });

  it('handles_request_limit', async () => {
    let limit = () => {};
    prepare = spyOn(requests, 'guardPlayerRequests').mockImplementation(
      async (_url, _script, fallback) => {
        limit = fallback;
        return { ready: () => {}, stop: () => {} };
      },
    );
    const { startup, enabled, onTimeout } = setup(false);
    await startup.prepare('/media', '/worker', new AbortController().signal);
    enabled.value = true;
    limit();
    limit();
    for (const callback of [...timers.values()]) callback();
    expect(onTimeout).toHaveBeenCalledTimes(1);
    expect(onTimeout).toHaveBeenCalledWith('request-limit');
  });

  it('handles_unavailable_worker', async () => {
    prepare = spyOn(requests, 'guardPlayerRequests').mockResolvedValue(null);
    const { startup, enabled, onTimeout } = setup(false);
    expect(await startup.prepare('/media', '/worker', new AbortController().signal)).toBe(false);
    expect(timers.size).toBe(0);
    expect(onTimeout).not.toHaveBeenCalled();
    enabled.value = true;
    expect(timers.size).toBe(1);
    for (const callback of [...timers.values()]) callback();
    expect(onTimeout).toHaveBeenCalledTimes(1);
    expect(onTimeout).toHaveBeenCalledWith('startup-timeout');
  });
});
