import { describe, it, expect, beforeAll, beforeEach, afterEach, mock, spyOn } from 'bun:test';

type StorageEntry = { value: unknown };

const notificationMock = {
  info: mock(() => {}),
  success: mock(() => {}),
  warning: mock(() => {}),
  error: mock(() => {}),
  notify: mock(() => {}),
};

const runtimeConfig = {
  app: {
    baseURL: '/base-path',
  },
};

mock.module('#imports', () => ({
  useRuntimeConfig: () => runtimeConfig,
  useNotification: () => notificationMock,
}));

globalThis.useRuntimeConfig = () => runtimeConfig as any;
globalThis.useNotification = () => notificationMock as any;

const storageMap = new Map<string, StorageEntry | unknown>();

const useStorageFn = mock(<T>(key: string, defaultValue: T) => {
  if (!storageMap.has(key)) {
    storageMap.set(key, { value: defaultValue });
  }
  return storageMap.get(key);
});

mock.module('@vueuse/core', () => ({
  useStorage: useStorageFn,
}));

const clipboardWriteMock = mock(() => Promise.resolve());
const fetchMock = mock(() => Promise.resolve({ status: 200 } as Response));
const getRandomValuesMock = mock((buffer: Uint8Array) => {
  buffer.fill(1);
  return buffer;
});

const originalFetch = globalThis.fetch;
const originalClipboard = globalThis.navigator?.clipboard;
const originalCrypto = globalThis.crypto;

let utils: Awaited<typeof import('~/utils/index')>;
let fetchSpy: ReturnType<typeof spyOn> | undefined;

const resetStorage = () => {
  storageMap.clear();
  storageMap.set('random_bg', { value: true });
  storageMap.set('random_bg_opacity', { value: 0.95 });
};

beforeAll(async () => {
  utils = await import('~/utils/index');
});

beforeEach(() => {
  resetStorage();
  runtimeConfig.app.baseURL = '/base-path';
  notificationMock.info.mockClear();
  notificationMock.success.mockClear();
  notificationMock.warning.mockClear();
  notificationMock.error.mockClear();
  notificationMock.notify.mockClear();
  useStorageFn.mockClear();

  fetchMock.mockClear();
  clipboardWriteMock.mockClear();
  getRandomValuesMock.mockClear();

  if (typeof originalFetch === 'function') {
    fetchSpy = spyOn(globalThis, 'fetch');
    fetchSpy.mockImplementation(fetchMock as any);
  } else {
    (globalThis as any).fetch = fetchMock;
    fetchSpy = undefined;
  }

  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText: clipboardWriteMock },
  });

  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: { getRandomValues: getRandomValuesMock },
  });
  Object.defineProperty(window as any, 'crypto', {
    configurable: true,
    value: { getRandomValues: getRandomValuesMock },
  });
});

afterEach(() => {
  if (fetchSpy) {
    fetchSpy.mockRestore();
  } else if (!originalFetch) {
    delete (globalThis as any).fetch;
  } else {
    globalThis.fetch = originalFetch;
  }

  if (originalClipboard) {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
  } else {
    delete (navigator as any).clipboard;
  }

  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: originalCrypto,
  });
  Object.defineProperty(window as any, 'crypto', {
    configurable: true,
    value: originalCrypto,
  });

  if (document.body) {
    document.body.innerHTML = '';
    document.body.removeAttribute('style');
  }
});

describe('object access helpers', () => {
  it('ag returns nested value or default value', () => {
    const payload = { a: { b: { c: 42 } } };
    expect(utils.ag(payload, 'a.b.c')).toBe(42);
    expect(utils.ag(payload, 'a.b.x', 'fallback')).toBe('fallback');
    expect(utils.ag(payload, 'missing', () => 'fn-default')).toBe('fn-default');
  });

  it('ag_set sets nested path creating objects as needed', () => {
    const payload: Record<string, unknown> = {};
    utils.ag_set(payload, 'a.b.c', 99);
    expect(payload).toEqual({ a: { b: { c: 99 } } });
  });

  it('cleanObject removes requested keys', () => {
    const source = { id: 1, keep: true, drop: false };
    expect(utils.cleanObject(source, ['drop'])).toEqual({ id: 1, keep: true });
    expect(utils.cleanObject(source, [])).toEqual(source);
  });

  it('stripPath removes base prefix and leading slashes', () => {
    expect(utils.stripPath('/data/downloads', '/data/downloads/video.mp4')).toBe('video.mp4');
    expect(utils.stripPath('', '/var/files/test.txt')).toBe('/var/files/test.txt');
  });
});

describe('string manipulation helpers', () => {
  it('r replaces tokens with context values', () => {
    const result = utils.r('Hello {user.name}!', { user: { name: 'YTPTube' } });
    expect(result).toBe('Hello YTPTube!');
  });

  it('iTrim trims delimiters at requested positions', () => {
    expect(utils.iTrim('--value--', '-', 'both')).toBe('value');
    expect(utils.iTrim('::value', ':', 'start')).toBe('value');
    expect(utils.iTrim('value::', ':', 'end')).toBe('value');
  });

  it('iTrim handles forward slash delimiter', () => {
    expect(utils.iTrim('//value//', '/', 'both')).toBe('value');
    expect(utils.iTrim('/value', '/', 'start')).toBe('value');
    expect(utils.iTrim('value/', '/', 'end')).toBe('value');
    expect(utils.iTrim('///multiple///', '/', 'both')).toBe('multiple');
  });

  it('iTrim handles backslash delimiter', () => {
    expect(utils.iTrim('\\\\value\\\\', '\\', 'both')).toBe('value');
    expect(utils.iTrim('\\value', '\\', 'start')).toBe('value');
    expect(utils.iTrim('value\\', '\\', 'end')).toBe('value');
  });

  it('iTrim handles hyphen delimiter', () => {
    expect(utils.iTrim('--value--', '-', 'both')).toBe('value');
    expect(utils.iTrim('-value', '-', 'start')).toBe('value');
    expect(utils.iTrim('value-', '-', 'end')).toBe('value');
    expect(utils.iTrim('---multiple---', '-', 'both')).toBe('multiple');
  });

  it('iTrim handles caret delimiter', () => {
    expect(utils.iTrim('^^value^^', '^', 'both')).toBe('value');
    expect(utils.iTrim('^value', '^', 'start')).toBe('value');
    expect(utils.iTrim('value^', '^', 'end')).toBe('value');
  });

  it('iTrim handles bracket delimiters', () => {
    expect(utils.iTrim('[[value]]', '[', 'both')).toBe('value]]');
    expect(utils.iTrim(']]value[[', ']', 'both')).toBe('value[[');
  });

  it('iTrim handles dot delimiter', () => {
    expect(utils.iTrim('..value..', '.', 'both')).toBe('value');
    expect(utils.iTrim('.value', '.', 'start')).toBe('value');
    expect(utils.iTrim('value.', '.', 'end')).toBe('value');
  });

  it('iTrim handles special regex characters', () => {
    expect(utils.iTrim('**value**', '*', 'both')).toBe('value');
    expect(utils.iTrim('++value++', '+', 'both')).toBe('value');
    expect(utils.iTrim('??value??', '?', 'both')).toBe('value');
    expect(utils.iTrim('||value||', '|', 'both')).toBe('value');
    expect(utils.iTrim('((value))', '(', 'both')).toBe('value))');
    expect(utils.iTrim('((value))', ')', 'both')).toBe('((value');
  });

  it('iTrim handles empty string', () => {
    expect(utils.iTrim('', '/', 'both')).toBe('');
  });

  it('iTrim throws error when delimiter is empty', () => {
    expect(() => utils.iTrim('value', '', 'both')).toThrow('Delimiter is required');
  });

  it('iTrim preserves middle occurrences', () => {
    expect(utils.iTrim('/path/to/file/', '/', 'both')).toBe('path/to/file');
    expect(utils.iTrim('//path//to//file//', '/', 'both')).toBe('path//to//file');
  });

  it('encodePath safely encodes components', () => {
    expect(utils.encodePath('folder#1/video name.mp4')).toBe('folder%231/video%20name.mp4');
  });

  it('encodePath handles % character correctly', () => {
    expect(utils.encodePath('How to enjoy Shin Ramyun 100%.opus')).toBe(
      'How%20to%20enjoy%20Shin%20Ramyun%20100%25.opus',
    );
  });

  it('encodePath handles multiple special characters', () => {
    expect(utils.encodePath('100% complete [HD] #1.mp4')).toBe(
      '100%25%20complete%20%5BHD%5D%20%231.mp4',
    );
  });

  it('encodePath handles paths with % character', () => {
    expect(utils.encodePath('folder/How to enjoy Shin Ramyun 100%.opus')).toBe(
      'folder/How%20to%20enjoy%20Shin%20Ramyun%20100%25.opus',
    );
  });

  it('encodePath handles already encoded strings', () => {
    expect(utils.encodePath('How%20to%20enjoy%20Shin%20Ramyun%20100%25.opus')).toBe(
      'How%20to%20enjoy%20Shin%20Ramyun%20100%25.opus',
    );
  });

  it('encodePath handles mixed encoded and unencoded', () => {
    expect(utils.encodePath('folder/file%20name 100%.mp4')).toBe('folder/file%20name%20100%25.mp4');
  });

  it('encodePath handles special characters &, =, ?', () => {
    expect(utils.encodePath('query?param=value&key=100%.mp4')).toBe(
      'query%3Fparam%3Dvalue%26key%3D100%25.mp4',
    );
  });

  it('encodePath handles empty string', () => {
    expect(utils.encodePath('')).toBe('');
  });

  it('encodePath handles simple filename', () => {
    expect(utils.encodePath('video.mp4')).toBe('video.mp4');
  });

  it('encodePath handles unicode characters', () => {
    expect(utils.encodePath('视频文件.mp4')).toBe('%E8%A7%86%E9%A2%91%E6%96%87%E4%BB%B6.mp4');
  });

  it('encodePath handles parentheses', () => {
    expect(utils.encodePath('video (1080p).mp4')).toBe('video%20(1080p).mp4');
  });

  it('removeANSIColors strips escape codes', () => {
    const sample = '\u001b[31mError\u001b[0m';
    expect(utils.removeANSIColors(sample)).toBe('Error');
  });

  it('basename returns final segment optionally trimming extension', () => {
    expect(utils.basename('/downloads/video.mp4')).toBe('video.mp4');
    expect(utils.basename('/downloads/video.mp4', '.mp4')).toBe('video');
    expect(utils.basename('', '.mp4')).toBe('');
  });

  it('dirname returns parent directory', () => {
    expect(utils.dirname('/downloads/video.mp4')).toBe('/downloads');
    expect(utils.dirname('video.mp4')).toBe('.');
    expect(utils.dirname('/file')).toBe('/');
  });

  it('formatBytes returns human readable strings', () => {
    expect(utils.formatBytes(0)).toBe('0 Bytes');
    expect(utils.formatBytes(1024)).toBe('1 KiB');
  });

  it('formatTime renders hh:mm:ss or mm:ss', () => {
    expect(utils.formatTime(59)).toBe('59');
    expect(utils.formatTime(90)).toBe('01:30');
    expect(utils.formatTime(3661)).toBe('01:01:01');
  });
});

describe('data conversion helpers', () => {
  it('has_data detects arrays, objects, and json strings', () => {
    expect(utils.has_data({ key: 'value' })).toBe(true);
    expect(utils.has_data('""')).toBe(false);
    expect(utils.has_data('[1,2]')).toBe(true);
    expect(utils.has_data('')).toBe(false);
  });

  it('encode and decode provide reversible transformation', () => {
    const payload = { name: 'YTPTube', count: 2 };
    const encoded = utils.encode(payload);
    expect(typeof encoded).toBe('string');
    expect(utils.decode(encoded)).toEqual(payload);
  });

  it('getQueryParams parses query strings', () => {
    expect(utils.getQueryParams('?a=1&b=two')).toEqual({ a: '1', b: 'two' });
  });

  it('uri prefixes runtime base path', () => {
    runtimeConfig.app.baseURL = '/base-path';
    expect(utils.uri('/api/test')).toBe('/base-path/api/test');
    runtimeConfig.app.baseURL = '/';
    expect(utils.uri('/api/test')).toBe('/api/test');
  });

  it('makeDownload builds expected url with folder and filename', () => {
    runtimeConfig.app.baseURL = '/base-path';
    const url = utils.makeDownload({}, { folder: 'music', filename: 'song.mp3' });
    expect(url).toBe('/base-path/api/download/music/song.mp3');
  });

  it('makeDownload handles m3u8 base path', () => {
    const url = utils.makeDownload({}, { filename: 'playlist' }, 'm3u8');
    expect(url).toBe('/base-path/api/player/m3u8/video/playlist.m3u8');
  });

  it('isDownloadSkipped detects finished skipped-download items', () => {
    expect(utils.isDownloadSkipped({ status: 'finished', download_skipped: true } as any)).toBe(true);
  });

  it('isDownloadSkipped ignores unfinished or unflagged items', () => {
    expect(utils.isDownloadSkipped({ status: 'finished', download_skipped: false } as any)).toBe(false);
    expect(utils.isDownloadSkipped({ status: 'downloading', download_skipped: true } as any)).toBe(false);
    expect(utils.isDownloadSkipped(undefined as any)).toBe(false);
  });
});

describe('dom and browser helpers', () => {
  it('copyText uses clipboard API and notifies success', async () => {
    utils.copyText('sample');

    await Promise.resolve();

    expect(clipboardWriteMock).toHaveBeenCalledWith('sample');

    await Promise.resolve();

    expect(notificationMock.success).toHaveBeenCalledWith('Text copied to clipboard.');
  });

  it('disableOpacity toggles body opacity when enabled', () => {
    const result = utils.disableOpacity();
    expect(result).toBe(true);
    expect(document.body.style.opacity).toBe('1');
  });

  it('disableOpacity returns false when background disabled', () => {
    document.body.removeAttribute('style');
    storageMap.clear();
    const originalOpacity = document.body.style.opacity;
    useStorageFn.mockImplementation((key: string, defaultValue: any) => {
      if (key === 'random_bg') {
        return null;
      }
      if (!storageMap.has(key)) {
        storageMap.set(key, { value: defaultValue });
      }
      return storageMap.get(key);
    });

    const result = utils.disableOpacity();
    expect(result).toBe(false);
    expect(document.body.getAttribute('style')).toBeNull();
    expect(document.body.style.opacity || '').toBe(originalOpacity || '');
  });

  it('enableOpacity applies stored opacity value', () => {
    utils.disableOpacity();
    useStorageFn.mockImplementation((key: string, defaultValue: any) => {
      if (!storageMap.has(key)) {
        storageMap.set(key, { value: defaultValue });
      }
      return storageMap.get(key);
    });

    storageMap.set('random_bg_opacity', { value: 0.75 });
    const result = utils.enableOpacity();
    expect(result).toBe(true);
    expect(document.body.style.opacity).toBe('0.75');
  });

  it('syncOpacity keeps full opacity while a lock is active', () => {
    utils.disableOpacity();
    storageMap.set('random_bg_opacity', { value: 0.35 });

    const result = utils.syncOpacity();

    expect(result).toBe(true);
    expect(document.body.style.opacity).toBe('1');
  });

  it('syncOpacity clears body opacity when background is disabled', () => {
    document.body.style.opacity = '0.8';
    storageMap.set('random_bg', { value: false });

    const result = utils.syncOpacity();

    expect(result).toBe(true);
    expect(document.body.style.opacity).toBe('');
  });
});

describe('network and id helpers', () => {
  it('request prefixes relative urls and sets defaults', async () => {
    const responseMock = { status: 200 } as Response;
    fetchMock.mockResolvedValue(responseMock);

    const response = await utils.request('/api/test');

    expect(response).toBe(responseMock);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/base-path/api/test');
    expect(options?.method).toBe('GET');
    expect(options?.credentials).toBe('same-origin');
    expect((options?.headers as Record<string, string>)['Content-Type']).toBe('application/json');
    expect((options?.headers as Record<string, string>)['Accept']).toBe('application/json');
    expect((options as Record<string, unknown>).withCredentials).toBe(true);
  });

  it('convertCliOptions posts payload and returns parsed json', async () => {
    const jsonMock = mock().mockResolvedValue({ success: true });
    const responseMock = { status: 200, json: jsonMock };
    fetchMock.mockResolvedValue(responseMock);

    const result = await utils.convertCliOptions('--help');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/base-path/api/yt-dlp/convert');
    expect(options?.method).toBe('POST');
    expect(options?.body).toBe(JSON.stringify({ args: '--help' }));
    expect(jsonMock).toHaveBeenCalled();
    expect(result).toEqual({ success: true });
  });

  it('convertCliOptions throws on non-200 response', async () => {
    const jsonMock = mock().mockResolvedValue({ error: 'fail' });
    const responseMock = { status: 400, json: jsonMock };
    fetchMock.mockResolvedValue(responseMock);

    await expect(utils.convertCliOptions('--bad')).rejects.toThrow('Error: (400): fail');
  });

});

describe('async helpers', () => {
  it('awaiter resolves when test becomes truthy', async () => {
    const values = [false, false, 'done'];
    const result = await utils.awaiter(() => values.shift(), 500, 0.01);
    expect(result).toBe('done');
  });

  it('awaiter returns false when timeout reached', async () => {
    const result = await utils.awaiter(() => false, 50, 0.01);
    expect(result).toBe(false);
  });
});
