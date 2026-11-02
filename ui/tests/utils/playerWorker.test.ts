import { describe, expect, it, mock } from 'bun:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('../../public/player-worker.js', import.meta.url), 'utf8');
const SCOPE = 'https://example.test/tube/';
const MEDIA = `${SCOPE}api/player/media/item/file?token=one`;

class Port {
  messages: { type: string }[] = [];
  onmessage?: (event: { data: { type: string } }) => void;
  closed = false;

  postMessage(message: { type: string }) {
    this.messages.push(message);
  }

  close() {
    this.closed = true;
  }

  send(type: string) {
    this.onmessage?.({ data: { type } });
  }
}

function worker(scope = SCOPE, script = new URL('player-worker.js', scope).href) {
  const listeners = new Map<string, (event: any) => void>();
  let now = 0;
  const fetch = mock((_request: Request) => Promise.resolve(new Response('media')));
  const claim = mock(() => Promise.resolve());
  runInNewContext(source, {
    URL,
    Response,
    Date: { now: () => now },
    fetch,
    self: {
      registration: { scope },
      location: { href: script },
      clients: { claim },
      addEventListener: (type: string, listener: (event: any) => void) => {
        listeners.set(type, listener);
      },
    },
  });

  const dispatch = (type: string, event: object) => listeners.get(type)!(event);
  const arm = (url = MEDIA, clientId = 'client-one') => {
    const port = new Port();
    dispatch('message', {
      data: { type: 'player-startup', url },
      source: { id: clientId },
      ports: [port],
    });
    return port;
  };
  const request = (url = MEDIA, clientId = 'client-one', method = 'GET') => {
    const request = new Request(url, {
      method,
      headers: { Range: 'bytes=123-456', 'If-Range': 'media-etag' },
    });
    const respondWith = mock((_response: Response | Promise<Response>) => {});
    dispatch('fetch', { request, clientId, respondWith });
    return { request, respondWith };
  };

  return {
    arm,
    claim,
    dispatch,
    fetch,
    request,
    advance: (milliseconds: number) => {
      now += milliseconds;
    },
  };
}

describe('player worker', () => {
  it.each([
    ['https://example.test/', 'https://example.test/player-worker.js'],
    ['https://example.test/tube/', 'https://example.test/tube/player-worker.js'],
    ['https://example.test/apps/ytptube/', 'https://example.test/apps/ytptube/player-worker.js'],
    ['https://example.test/', 'https://example.test/apps/ytptube/player-worker.js'],
  ])('guards base paths', (scope, script) => {
    const instance = worker(scope, script);
    const media = new URL('api/player/media/item/file', script).href;
    const port = instance.arm(media);
    for (let index = 0; index < 17; index += 1) instance.request(media);
    expect(instance.fetch).toHaveBeenCalledTimes(16);
    expect(port.messages).toEqual([{ type: 'armed' }, { type: 'fallback' }]);
  });

  it('claims lifecycle', async () => {
    const instance = worker();
    const waitUntil = mock((_promise: Promise<void>) => {});
    instance.dispatch('activate', { waitUntil });
    expect(instance.claim).toHaveBeenCalledTimes(1);
    expect(waitUntil).toHaveBeenCalledTimes(1);
    await Promise.all(waitUntil.mock.calls.map(([promise]) => promise));
  });

  it('caps original requests', async () => {
    const instance = worker();
    const port = instance.arm();
    expect(port.messages).toEqual([{ type: 'armed' }]);

    for (let index = 0; index < 16; index += 1) {
      const event = instance.request();
      expect(event.respondWith).toHaveBeenCalledTimes(1);
      expect(instance.fetch.mock.calls[index]?.[0]).toBe(event.request);
      expect(instance.fetch.mock.calls[index]?.[0].headers.get('Range')).toBe('bytes=123-456');
      expect(instance.fetch.mock.calls[index]?.[0].headers.get('If-Range')).toBe('media-etag');
      expect((await event.respondWith.mock.calls[0]![0]).status).toBe(200);
    }

    for (let index = 0; index < 8; index += 1) {
      const event = instance.request();
      expect(event.respondWith).toHaveBeenCalledTimes(1);
      expect((await event.respondWith.mock.calls[0]![0]).type).toBe('error');
      expect(instance.fetch).toHaveBeenCalledTimes(16);
    }
    expect(port.messages).toEqual([{ type: 'armed' }, { type: 'fallback' }]);
  });

  it('releases ready guard', () => {
    const instance = worker();
    const port = instance.arm();
    instance.request();
    port.send('ready');
    expect(port.closed).toBe(true);
    for (let index = 0; index < 20; index += 1) {
      expect(instance.request().respondWith).not.toHaveBeenCalled();
    }
    expect(instance.fetch).toHaveBeenCalledTimes(1);
  });

  it('isolates guarded requests', () => {
    const instance = worker();
    instance.arm();
    const unrelated = [
      instance.request(MEDIA, 'client-two'),
      instance.request(MEDIA, ''),
      instance.request(MEDIA, 'client-one', 'HEAD'),
      instance.request(MEDIA, 'client-one', 'POST'),
      instance.request(`${SCOPE}api/player/media/other/file`),
      instance.request(`${SCOPE}api/player/media/item/file?token=two`),
      instance.request(`${SCOPE}api/player/media/item/hls/playlist.m3u8`),
      instance.request(`${SCOPE}api/config`),
    ];
    for (const event of unrelated) {
      expect(event.respondWith).not.toHaveBeenCalled();
    }
    expect(instance.fetch).not.toHaveBeenCalled();
    instance.request();
    expect(instance.fetch).toHaveBeenCalledTimes(1);

    const other = instance.arm(MEDIA, 'client-two');
    for (let index = 0; index < 17; index += 1) {
      instance.request();
    }
    instance.request(MEDIA, 'client-two');
    expect(instance.fetch).toHaveBeenCalledTimes(17);
    expect(other.messages).toEqual([{ type: 'armed' }]);
  });

  it('retains blocked tombstone', async () => {
    const instance = worker();
    const port = instance.arm();
    for (let index = 0; index < 17; index += 1) {
      instance.request();
    }
    port.send('stop');
    expect(port.closed).toBe(true);
    const event = instance.request();
    expect((await event.respondWith.mock.calls[0]![0]).type).toBe('error');
    expect(instance.fetch).toHaveBeenCalledTimes(16);
    expect(port.messages).toEqual([{ type: 'armed' }, { type: 'fallback' }]);
  });

  it('accepts late readiness', () => {
    const instance = worker();
    const port = instance.arm();
    for (let index = 0; index < 17; index += 1) {
      instance.request();
    }
    port.send('ready');
    expect(port.closed).toBe(true);
    expect(instance.request().respondWith).not.toHaveBeenCalled();
    expect(instance.fetch).toHaveBeenCalledTimes(16);
  });

  it('stops unblocked guard', () => {
    const instance = worker();
    const port = instance.arm();
    port.send('stop');
    expect(port.closed).toBe(true);
    expect(instance.request().respondWith).not.toHaveBeenCalled();
  });

  it('rejects invalid messages', () => {
    const instance = worker();
    const valid = { data: { type: 'player-startup', url: MEDIA }, source: { id: 'client-one' } };
    const invalid = [
      { ...valid, data: null },
      { ...valid, data: { type: 'other', url: MEDIA } },
      { ...valid, data: { type: 'player-startup', url: 42 } },
      { ...valid, source: null },
      { ...valid, source: { id: '' } },
      { ...valid, source: { id: 42 } },
      ...[
        '/tube/api/player/media/item/file',
        'not a url',
        'https://other.test/tube/api/player/media/item/file',
        'https://example.test/api/player/media/item/file',
        'https://example.test/tube-other/api/player/media/item/file',
        `${SCOPE}api/player/media/item/file/extra`,
        `${SCOPE}api/player/media/item/hls/playlist.m3u8`,
        `${SCOPE}api/player/media//file`,
      ].map((url) => ({ ...valid, data: { type: 'player-startup', url } })),
    ];
    for (const message of invalid) {
      const port = new Port();
      instance.dispatch('message', { ...message, ports: [port] });
      expect(port.messages).toEqual([]);
    }
    instance.dispatch('message', valid);
    instance.dispatch('message', { ...valid, ports: [] });
    expect(instance.request().respondWith).not.toHaveBeenCalled();
  });

  it('ignores stale cleanup', () => {
    const instance = worker();
    const old = instance.arm();
    instance.request();
    const current = instance.arm();
    expect(old.closed).toBe(true);
    old.send('ready');
    old.send('stop');
    for (let index = 0; index < 17; index += 1) {
      instance.request();
    }
    expect(instance.fetch).toHaveBeenCalledTimes(17);
    expect(current.messages).toEqual([{ type: 'armed' }, { type: 'fallback' }]);
    expect(current.closed).toBe(false);
  });

  it('rearms blocked guard', () => {
    const instance = worker();
    const old = instance.arm();
    for (let index = 0; index < 17; index += 1) {
      instance.request();
    }
    const current = instance.arm();
    old.send('stop');
    for (let index = 0; index < 16; index += 1) {
      instance.request();
    }
    expect(instance.fetch).toHaveBeenCalledTimes(32);
    expect(current.messages).toEqual([{ type: 'armed' }]);
    instance.request();
    expect(instance.fetch).toHaveBeenCalledTimes(32);
    expect(current.messages).toEqual([{ type: 'armed' }, { type: 'fallback' }]);
  });

  it('expires stale entries', () => {
    const instance = worker();
    const port = instance.arm();
    for (let index = 0; index < 17; index += 1) {
      instance.request();
    }
    instance.advance(60_000);
    instance.arm(`${SCOPE}api/player/media/new/file`);
    expect(port.closed).toBe(true);
    expect(instance.request().respondWith).not.toHaveBeenCalled();
  });
});
