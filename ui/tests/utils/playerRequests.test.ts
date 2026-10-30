import { afterEach, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';
import { guardPlayerRequests } from '~/utils/playerRequests';

class Port {
  peer: Port | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  postMessage = mock((data: unknown) => this.peer?.onmessage?.({ data }));
  close = mock(() => {});
}

describe('player request guard', () => {
  const secure = Object.getOwnPropertyDescriptor(window, 'isSecureContext');
  const serviceWorker = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker');
  const originalChannel = globalThis.MessageChannel;
  let channel: { port1: Port; port2: Port };
  let worker: { scriptURL: string; postMessage: ReturnType<typeof mock> };
  let container: EventTarget & {
    controller: typeof worker | null;
    register: ReturnType<typeof mock>;
  };
  let ack: boolean;
  let timers: Map<number, () => void>;
  let schedule: ReturnType<typeof spyOn<typeof window, 'setTimeout'>>;
  let cancel: ReturnType<typeof spyOn<typeof window, 'clearTimeout'>>;

  beforeEach(() => {
    ack = true;
    channel = { port1: new Port(), port2: new Port() };
    channel.port1.peer = channel.port2;
    channel.port2.peer = channel.port1;
    globalThis.MessageChannel = function MockChannel() {
      return channel;
    } as unknown as typeof MessageChannel;
    worker = {
      scriptURL: 'http://localhost/player-worker.js',
      postMessage: mock(() => {
        if (ack) channel.port2.postMessage({ type: 'armed' });
      }),
    };
    container = Object.assign(new window.EventTarget(), {
      controller: worker as typeof worker | null,
      register: mock(() => Promise.resolve({})),
    });
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
    Object.defineProperty(navigator, 'serviceWorker', { value: container, configurable: true });
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
  });

  afterEach(() => {
    schedule.mockRestore();
    cancel.mockRestore();
    globalThis.MessageChannel = originalChannel;
    if (secure) Object.defineProperty(window, 'isSecureContext', secure);
    else Reflect.deleteProperty(window, 'isSecureContext');
    if (serviceWorker) Object.defineProperty(navigator, 'serviceWorker', serviceWorker);
    else Reflect.deleteProperty(navigator, 'serviceWorker');
  });

  const prepare = (onFallback = mock(() => {}), signal = new AbortController().signal) =>
    guardPlayerRequests('/api/player/media/id/file', '/player-worker.js', onFallback, signal);

  it('waits_for_control', async () => {
    container.controller = null;
    const pending = prepare();
    expect(worker.postMessage).not.toHaveBeenCalled();
    container.controller = worker;
    container.dispatchEvent(new window.Event('controllerchange'));
    const guard = await pending;
    expect(guard).not.toBeNull();
    expect(worker.postMessage).toHaveBeenCalledWith(
      { type: 'player-startup', url: 'http://localhost/api/player/media/id/file' },
      [channel.port2],
    );
    guard?.stop();
  });

  it('waits_for_ack', async () => {
    ack = false;
    let armed = false;
    const pending = prepare().then((guard) => {
      armed = true;
      return guard;
    });
    await Promise.resolve();
    expect(armed).toBe(false);
    channel.port2.postMessage({ type: 'armed' });
    const guard = await pending;
    expect(armed).toBe(true);
    expect(timers.size).toBe(0);
    guard?.stop();
  });

  it('reports_limit_once', async () => {
    const onFallback = mock(() => {});
    const guard = await prepare(onFallback);
    channel.port2.postMessage({ type: 'fallback' });
    channel.port2.postMessage({ type: 'fallback' });
    expect(onFallback).toHaveBeenCalledTimes(1);
    guard?.stop();
    channel.port2.postMessage({ type: 'fallback' });
    expect(onFallback).toHaveBeenCalledTimes(1);
  });

  it('releases_ready_guard', async () => {
    const onFallback = mock(() => {});
    const guard = await prepare(onFallback);
    guard?.ready();
    guard?.stop();
    expect(channel.port1.postMessage).toHaveBeenCalledTimes(1);
    expect(channel.port1.postMessage).toHaveBeenCalledWith({ type: 'ready' });
    expect(channel.port1.close).toHaveBeenCalledTimes(1);
    channel.port2.postMessage({ type: 'fallback' });
    expect(onFallback).not.toHaveBeenCalled();
  });

  it('aborts_pending_guard', async () => {
    ack = false;
    const controller = new AbortController();
    const pending = prepare(undefined, controller.signal);
    controller.abort();
    expect(await pending).toBeNull();
    expect(timers.size).toBe(0);
    expect(channel.port1.close).toHaveBeenCalledTimes(1);
  });

  it('bounds_worker_wait', async () => {
    ack = false;
    const pending = prepare();
    expect(schedule.mock.calls[0]?.[1]).toBe(3000);
    for (const callback of [...timers.values()]) callback();
    expect(await pending).toBeNull();
    expect(channel.port1.close).toHaveBeenCalledTimes(1);
  });

  it('handles_control_loss', async () => {
    const onFallback = mock(() => {});
    const guard = await prepare(onFallback);
    container.controller = null;
    container.dispatchEvent(new window.Event('controllerchange'));
    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(channel.port1.close).toHaveBeenCalledTimes(1);
    guard?.stop();
  });

  it('handles_registration_failure', async () => {
    container.controller = null;
    container.register.mockRejectedValue(new Error('Unavailable'));
    expect(await prepare()).toBeNull();
    expect(timers.size).toBe(0);
  });

  it('retains_controlled_guard', async () => {
    container.register.mockRejectedValue(new Error('Offline'));
    const guard = await prepare();
    await Promise.resolve();
    expect(channel.port1.close).not.toHaveBeenCalled();
    guard?.stop();
  });

  it('skips_insecure_context', async () => {
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
    expect(await prepare()).toBeNull();
    expect(container.register).not.toHaveBeenCalled();
  });

  it.each(['/', '/tube/', '/apps/ytptube/'])('supports_base_path', async (base) => {
    worker.scriptURL = `http://localhost${base}player-worker.js`;
    const guard = await guardPlayerRequests(
      `${base}api/player/media/id/file`,
      `${base}player-worker.js`,
      () => {},
      new AbortController().signal,
    );
    expect(guard).not.toBeNull();
    expect(container.register).toHaveBeenCalledWith(worker.scriptURL, {
      scope: base,
      updateViaCache: 'none',
    });
    guard?.stop();
  });
});
