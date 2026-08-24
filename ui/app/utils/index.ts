import { useStorage } from '@vueuse/core';
import type { ApiErrorPayload, convert_args_response, Paginated } from '~/types/responses';
import type { StoreItem } from '~/types/store';

const AG_SEPARATOR = '.';
const APP_TITLE = 'YTPTube';

const separators = [
  { name: 'common.sepComma', value: ',' },
  { name: 'common.sepSemicolon', value: ';' },
  { name: 'common.sepColon', value: ':' },
  { name: 'common.sepPipe', value: '|' },
  { name: 'common.sepSpace', value: ' ' },
];

const getValue = <T>(obj: (() => T) | T): T => {
  return 'function' === typeof obj ? (obj as () => T)() : obj;
};

/** Read a dot-delimited path, resolving callable defaults when the value is missing or null. */
const ag = <T = any>(obj: any, path: string, defaultValue: T | null = null): T | null => {
  const keys = path.split(AG_SEPARATOR);
  let at = obj;

  for (const key of keys) {
    if ('object' === typeof at && null !== at && key in at) {
      at = at[key];
    } else {
      return getValue(defaultValue);
    }
  }

  return getValue(null === at ? defaultValue : at);
};

/** Set a dot-delimited path, creating missing objects along the path. */
const ag_set = (obj: Record<string, any>, path: string, value: any): Record<string, any> => {
  const keys = path.split(AG_SEPARATOR);
  let at: any = obj;

  while (keys.length > 0) {
    if (1 === keys.length) {
      if ('object' === typeof at && null !== at) {
        at[keys.shift()!] = value;
      } else {
        throw new Error(`Cannot set value at this path (${path}) because it's not an object.`);
      }
    } else {
      const key = keys.shift()!;
      if (!at[key] || 'object' !== typeof at[key]) {
        at[key] = {};
      }
      at = at[key];
    }
  }

  return obj;
};

/** Replace `{path}` tags with values read from the supplied context. */
const r = (text: string, context: Record<string, any> = {}): string => {
  const tagLeft = '{';
  const tagRight = '}';

  if (!text.includes(tagLeft) || !text.includes(tagRight)) {
    return text;
  }

  const pattern = new RegExp(`${tagLeft}([\\w_.]+)${tagRight}`, 'g');
  const matches = text.match(pattern);
  if (!matches) return text;

  const replacements: Record<string, string> = {};
  matches.forEach((match) => {
    const key = match.slice(1, -1);
    replacements[match] = String(ag(context, key, ''));
  });

  for (const key in replacements) {
    text = text.replace(new RegExp(key, 'g'), String(replacements[key]));
  }

  return text;
};

const encodePath = (item: string): string => {
  if (!item) {
    return item;
  }

  return item
    .split('/')
    .map((segment) => {
      try {
        const decoded = decodeURIComponent(segment);
        const reEncoded = encodeURIComponent(decoded);

        if (reEncoded === segment) {
          return segment;
        }
      } catch {
        // Decoding failed, segment has invalid encoding
      }

      const placeholders: string[] = [];
      const _PREFIX = `_YTP${Math.random().toString(36).substring(2, 8).toUpperCase()}_`;
      const _SUFFIX = `_YTP${Math.random().toString(36).substring(2, 8).toUpperCase()}_`;

      let processed = segment.replace(/%[0-9A-Fa-f]{2}/g, (match) => {
        const index = placeholders.length;
        placeholders.push(match);
        return `${_PREFIX}${index}${_SUFFIX}`;
      });

      processed = encodeURIComponent(processed);

      const placeholderRegex = new RegExp(
        `${_PREFIX.replace(/_/g, '_')}(\\d+)${_SUFFIX.replace(/_/g, '_')}`,
        'g',
      );
      return processed.replace(
        placeholderRegex,
        (_match, index: string) => placeholders[parseInt(index)] || '',
      );
    })
    .join('/');
};

/** Apply API defaults, timeout handling, and login redirection to a fetch request. */
const request = (
  url: string,
  options: RequestInit & { timeout?: number } = {},
): Promise<Response> => {
  const { timeout, ...fetchOptions } = options;

  fetchOptions.method = fetchOptions.method || 'GET';
  fetchOptions.headers = fetchOptions.headers || {};
  (fetchOptions as any).withCredentials = true;

  if (undefined === (fetchOptions.headers as Record<string, any>)['Content-Type']) {
    if (!(options?.body instanceof FormData)) {
      (fetchOptions.headers as Record<string, any>)['Content-Type'] = 'application/json';
    }
  }

  if (undefined === (fetchOptions.headers as Record<string, any>)['Accept']) {
    (fetchOptions.headers as Record<string, any>)['Accept'] = 'application/json';
  }

  if (url.startsWith('/')) {
    fetchOptions.credentials = 'same-origin';
  }

  let controller: AbortController | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;

  if (typeof timeout === 'number' && timeout > 0) {
    controller = new AbortController();
    fetchOptions.signal = controller.signal;
    timer = setTimeout(() => controller!.abort(`Request timed out.`), timeout * 1000);
  }

  return fetch(url.startsWith('/') ? uri(url) : url, fetchOptions)
    .then((response) => {
      const path = url.split('?')[0] ?? '';
      if (
        import.meta.client &&
        response.status === 401 &&
        !['/api/auth/status', '/api/auth/login', '/api/auth/setup'].includes(path)
      ) {
        void navigateTo('/login');
      }
      return response;
    })
    .finally(() => {
      if (timer) {
        clearTimeout(timer);
      }
    });
};

const removeANSIColors = (text: string): string => {
  return (
    text?.replace(
      /* eslint-disable-next-line no-control-regex */
      /[\u001b\u009b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g,
      '',
    ) ?? text
  );
};

const basename = (path: string, ext: string = ''): string => {
  if (!path) return '';
  const segments = path.replace(/\\/g, '/').split('/');
  let base = segments.pop() || '';
  while (segments.length && base === '') {
    base = segments.pop() || '';
  }
  if (ext && base.endsWith(ext) && base !== ext) {
    base = base.substring(0, base.length - ext.length);
  }
  return base;
};

const dirname = (filePath: string): string => {
  const lastIndex = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
  if (-1 === lastIndex) {
    return '.';
  }

  if (0 === lastIndex) {
    return filePath[0] ?? '.';
  }

  return filePath.substring(0, lastIndex);
};

const copyText = (str: string, notify: boolean = true, store: boolean = false): void => {
  const toast = useNotification();
  const { $i18n } = useNuxtApp();
  const t = $i18n?.t ?? ((key: string) => key);

  if (navigator.clipboard) {
    navigator.clipboard
      .writeText(str)
      .then(() => {
        if (notify) toast.success(t('common.copiedToClipboard'));
      })
      .catch((error) => {
        console.error('Failed to copy.', error);
        if (notify) toast.error(t('common.copyFailed'));
      });
    return;
  }

  const el = document.createElement('textarea');
  el.value = str;
  document.body.appendChild(el);
  el.select();
  document.execCommand('copy');
  document.body.removeChild(el);

  if (notify) {
    toast.success(t('common.copiedToClipboard'), { store });
  }
};

const iTrim = (str: string, delim: string, position: 'start' | 'end' | 'both' = 'both'): string => {
  if (!str) {
    return str;
  }

  if (!delim) {
    throw new Error('Delimiter is required');
  }

  // Escape special regex characters for use in character class
  // Characters that need escaping in character classes: \ ] ^ -
  const escapedDelim = delim.replace(/[\\^\-\]]/g, '\\$&');

  if (['both', 'start'].includes(position)) {
    str = str.replace(new RegExp(`^[${escapedDelim}]+`, 'g'), '');
  }

  if (['both', 'end'].includes(position)) {
    str = str.replace(new RegExp(`[${escapedDelim}]+$`, 'g'), '');
  }

  return str;
};

const eTrim = (str: string, delim: string): string => iTrim(str, delim, 'end');

const sTrim = (str: string, delim: string): string => iTrim(str, delim, 'start');

const ucFirst = (str: string): string => (!str ? str : str.charAt(0).toUpperCase() + str.slice(1));

const normalizePresetName = (name: string): string =>
  name.trim().toLowerCase().replace(/\s+/g, '_');

const token = (value: string): string => value.trim().split(/[\s/;()]+/u)[0] ?? '';

const browserSummary = (userAgent: string | null): string => {
  const ua = userAgent?.trim() ?? '';
  const browser = ua.match(/(Edg|OPR|Chrome|Firefox|Safari|MSIE|Trident)\/([\d.]+)/u);
  const browserName =
    browser?.[1] === 'Edg' ? 'Edge' : browser?.[1] === 'OPR' ? 'Opera' : browser?.[1];
  const browserLabel = browserName && browser?.[2] ? `${browserName} ${browser[2]}` : browserName;
  const os = ua.match(/(Windows NT|Mac OS X|Android|iPhone OS|Linux)[\s/]?([\d._-]*)/u);
  const osName =
    os?.[1] === 'Windows NT'
      ? 'Windows'
      : os?.[1] === 'Mac OS X'
        ? 'macOS'
        : os?.[1] === 'iPhone OS'
          ? 'iOS'
          : os?.[1];
  if (browserLabel && osName) return `${browserLabel} on ${osName}`;
  if (browserLabel) return browserLabel;
  if (osName) return osName;
  return token(ua) || 'Unknown browser';
};

const prettyName = (name: string): string =>
  name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const getSeparatorsName = (value: string): string => {
  const sep = separators.find((s) => s.value === value);
  if (!sep) return useNuxtApp().$i18n?.t('common.unknown') ?? 'Unknown';
  const tr = useNuxtApp().$i18n?.t ?? ((k: string) => k);
  return `${tr(sep.name)} (${value})`;
};

const convertCliOptions = async (opts: string): Promise<convert_args_response> => {
  const response = await request('/api/yt-dlp/convert', {
    method: 'POST',
    body: JSON.stringify({ args: opts }),
  });

  const data = await response.json();
  if (200 !== response.status) {
    throw new Error(await parse_api_error(data));
  }

  return data;
};

const getQueryParams = (url: string = window.location.search): Record<string, string> => {
  return Object.fromEntries(new URLSearchParams(url).entries());
};

const makeDownload = (
  config: any,
  item: StoreItem | { folder?: string; filename: string },
  base: string = 'api/download',
  playlist: boolean = false,
): string => {
  let baseDir = 'api/player/m3u8/video/';
  if ('m3u8' !== base) {
    baseDir = `${base}/`;
  }

  if (item.folder) {
    baseDir += item.folder.replace(/#/g, '%23') + '/';
  }

  if (!item.filename) {
    return '';
  }

  const url = `/${sTrim(baseDir, '/')}${encodePath(item.filename)}`;
  return uri('m3u8' === base || true === playlist ? `${url}.m3u8` : url);
};

const SIZE_UNIT_KEYS = [
  'common.bytes',
  'common.kib',
  'common.mib',
  'common.gib',
  'common.tib',
  'common.pib',
  'common.eib',
  'common.zib',
  'common.yib',
] as const;

const formatBytes = (bytes: number, decimals: number = 2, t?: (key: string) => string): string => {
  if (!+bytes) {
    return t ? `0 ${t('common.bytes')}` : '0 Bytes';
  }
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const unit = t ? t(SIZE_UNIT_KEYS[i]!) : sizes[i];
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${unit}`;
};

const has_data = (item: any): boolean => {
  if (!item) {
    return false;
  }

  if ('string' === typeof item) {
    try {
      item = JSON.parse(item);
    } catch {
      return true;
    }
  }

  try {
    if ('object' === typeof item) return Object.keys(item).length > 0;
    return item.length > 0;
  } catch (e) {
    console.error(e);
    return false;
  }
};

const toggleClass = (target: HTMLElement, className: string | string[]): void => {
  if (Array.isArray(className)) {
    className.forEach((cls) => toggleClass(target, cls));
    return;
  }

  if (target.classList.contains(className)) {
    target.classList.remove(className);
  } else {
    target.classList.add(className);
  }
};

const cleanObject = <T extends Record<string, any>>(item: T, fields: string[] = []): Partial<T> => {
  if (!item || typeof item !== 'object' || fields.length < 1) return item;
  const cleaned: Partial<T> = {};
  for (const key of Object.keys(item)) {
    if (!fields.includes(key)) {
      cleaned[key as keyof T] = item[key];
    }
  }
  return cleaned;
};

const uri = (u: string): string => {
  const runtimeConfig = useRuntimeConfig();

  if (!u || '/' === runtimeConfig.app.baseURL || !u.startsWith('/')) {
    return u;
  }

  if (u.startsWith(runtimeConfig.app.baseURL)) {
    return u;
  }

  return `${eTrim(runtimeConfig.app.baseURL, '/')}/${sTrim(u, '/')}`;
};

const formatTime = (seconds: number): string => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const pad = (n: number): string => n.toString().padStart(2, '0');

  if (hrs > 0) {
    return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
  }

  if (mins > 0) {
    return `${pad(mins)}:${pad(secs)}`;
  }

  return `${secs}`;
};

const sleep = (seconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, seconds * 1000));

/** Waits for a truthy result and returns false when the timeout expires. */
// eslint-disable-next-line @typescript-eslint/no-unsafe-function-type
const awaiter = async (test: Function, timeout_ms: number = 20 * 1000, frequency: number = 200) => {
  if (typeof test != 'function') {
    throw new Error('test should be a function in awaiter(test, [timeout_ms], [frequency])');
  }

  const isNotTruthy = (val: any) =>
    val === undefined || val === false || val === null || val.length === 0;
  const endTime: number = Date.now() + timeout_ms;

  let result = test();

  while (isNotTruthy(result)) {
    if (Date.now() > endTime) {
      return false;
    }
    await sleep(frequency);
    result = test();
  }

  return result;
};

const encode = (obj: Record<string, any>): string => {
  const jsonStr = JSON.stringify(obj);
  const utf8Bytes = new TextEncoder().encode(jsonStr);
  const binary = String.fromCharCode(...utf8Bytes);
  const base64 = btoa(binary);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

const decode = (str: string): object => {
  const base64 = str
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(str.length + ((4 - (str.length % 4)) % 4), '=');

  const binary = atob(base64);
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  const jsonStr = new TextDecoder().decode(bytes);
  return JSON.parse(jsonStr);
};

let opacityLockCount = 0;

const getStorageValue = <T>(key: string, defaultValue: T, missingValue: T = defaultValue): T => {
  const stored = useStorage<T>(key, defaultValue);
  if (!stored || typeof stored !== 'object' || !('value' in stored)) {
    return missingValue;
  }

  return (stored.value === undefined ? defaultValue : stored.value) as T;
};

const setBodyOpacity = (value: string): boolean => {
  const body = document.querySelector('body');
  if (!body) {
    return false;
  }

  body.style.opacity = value;
  return true;
};

const clearBodyOpacity = (): boolean => {
  const body = document.querySelector('body');
  if (!body) {
    return false;
  }

  body.style.removeProperty('opacity');
  return true;
};

const syncOpacity = (): boolean => {
  if (!getStorageValue<boolean>('random_bg', true, false)) {
    opacityLockCount = 0;
    return clearBodyOpacity();
  }

  if (opacityLockCount > 0) {
    return setBodyOpacity('1.0');
  }

  return setBodyOpacity(String(getStorageValue<number>('random_bg_opacity', 0.95)));
};

const disableOpacity = (): boolean => {
  if (!getStorageValue<boolean>('random_bg', true, false)) {
    opacityLockCount = 0;
    return false;
  }

  opacityLockCount += 1;
  return setBodyOpacity('1.0');
};

const enableOpacity = (): boolean => {
  if (!getStorageValue<boolean>('random_bg', true, false)) {
    opacityLockCount = 0;
    return false;
  }

  opacityLockCount = Math.max(0, opacityLockCount - 1);
  return syncOpacity();
};

const stripPath = (base_path: string, real_path: string): string => {
  if (!base_path) {
    return real_path;
  }

  return real_path.replace(base_path, '').replace(/^\//, '');
};
const shortPath = (path: string, prefix: string = '...'): string => {
  if (typeof path !== 'string') {
    return path;
  }

  const hasTrailingSlash = /\/$/.test(path);
  const clean = path.replace(/\/+$/, '');
  const parts = clean.split('/').filter(Boolean);

  if (parts.length <= 1) {
    return path;
  }

  return `${prefix}/${parts.at(-1)}${hasTrailingSlash ? '/' : ''}`;
};

const isDownloadSkipped = (
  item: Pick<StoreItem, 'status' | 'download_skipped'> | null | undefined,
): boolean => Boolean(item && item.status === 'finished' && item.download_skipped);

/**
 * Recursively test if a value (including nested objects/arrays) contains a query string.
 * - Plain queries match keys or values (case-insensitive).
 * - key:value queries require the value to be under a matching key in the path.
 *
 * @param value - Value to search within.
 * @param query - Raw query string.
 * @param seen - Optional WeakSet to prevent circular reference loops.
 * @param kv - Internal: parsed key/value pair when using key:value mode.
 * @param keyMatched - Internal: whether current recursion path matched the key.
 */
const deepIncludes = (
  value: unknown,
  query: string,
  seen: WeakSet<object> = new WeakSet(),
  kv: { key: string; val: string } | null = null,
  keyMatched: boolean = false,
): boolean => {
  const normalized = query.trim().toLowerCase();
  if (!normalized || null === value || undefined === value) {
    return false;
  }

  const pair =
    kv ??
    (() => {
      const idx = normalized.indexOf(':');
      if (idx <= 0 || idx >= normalized.length - 1) {
        return null;
      }
      const key = normalized.slice(0, idx).trim();
      const val = normalized.slice(idx + 1).trim();
      if (!key || !val) {
        return null;
      }
      return { key, val };
    })();

  const matchPrimitive = (val: unknown, q: string): boolean =>
    String(val).toLowerCase().includes(q);

  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    if (!pair) {
      return matchPrimitive(value, normalized);
    }
    return keyMatched && matchPrimitive(value, pair.val);
  }

  if (Array.isArray(value)) {
    return value.some((entry) => deepIncludes(entry, normalized, seen, pair, keyMatched));
  }

  if ('object' === typeof value) {
    const obj = value as Record<string, unknown>;
    if (seen.has(obj)) {
      return false;
    }
    seen.add(obj);
    for (const [key, val] of Object.entries(obj)) {
      const keyLower = key.toLowerCase();

      if (!pair && keyLower.includes(normalized)) {
        return true;
      }

      const nextKeyMatched = pair ? keyMatched || keyLower.includes(pair.key) : keyMatched;
      if (deepIncludes(val, normalized, seen, pair, nextKeyMatched)) {
        return true;
      }
    }
  }

  return false;
};

const getPath = (basePath: string, item: StoreItem): string => {
  if (!item.folder && ((!item.filename && item.download_dir === basePath) || !item.download_dir)) {
    return shortPath(basePath);
  }

  if (!item?.filename) {
    return stripPath(
      eTrim(basePath, '/'),
      '/' + sTrim(eTrim(item.download_dir || item.folder, '/'), '/'),
    );
  }

  return stripPath(
    eTrim(basePath, '/'),
    '/' + eTrim(item.download_dir, '/') + '/' + sTrim(item.filename, '/'),
  );
};

const getRemoteImage = (item: StoreItem, fallback: boolean = true): string => {
  if (item?.extras?.thumbnail) {
    return uri(item.extras.thumbnail);
  }

  return fallback ? uri('/images/placeholder.png') : '';
};

const getHistoryImage = (item: StoreItem, fallback: boolean = true): string => {
  if (item._id && item.filename) {
    return uri(`/api/history/${encodeURIComponent(item._id)}/thumbnail`);
  }

  return getRemoteImage(item, fallback);
};

const getImage = (basePath: string, item: StoreItem, fallback: boolean = true): string => {
  if (item.sidecar?.image && item.sidecar.image.length > 0) {
    return uri(
      '/api/download/' + encodeURIComponent(stripPath(basePath, item.sidecar.image[0]?.file || '')),
    );
  }

  return getRemoteImage(item, fallback);
};

const parse_list_response = async <T>(json: unknown): Promise<Paginated<T>> => {
  if ('function' === typeof (json as any).then) {
    json = await (json as Promise<unknown>);
  }

  if (!json || 'object' !== typeof json) {
    return {
      items: [],
      pagination: {
        page: 1,
        per_page: 20,
        total: 0,
        total_pages: 0,
        has_next: false,
        has_prev: false,
      },
    };
  }

  const payload = json as Paginated<T>;
  const items = Array.isArray(payload.items) ? payload.items : [];

  const pagination = {
    page: Number(payload.pagination?.page ?? 1),
    per_page: Number(payload.pagination?.per_page ?? 20),
    total: Number(payload.pagination?.total ?? 0),
    total_pages: Number(payload.pagination?.total_pages ?? 0),
    has_next: Boolean(payload.pagination?.has_next ?? false),
    has_prev: Boolean(payload.pagination?.has_prev ?? false),
  };

  return { items: items as T[], pagination };
};

const parse_api_response = async <T>(json: unknown): Promise<T> => {
  if ('function' === typeof (json as any).then) {
    json = await (json as Promise<unknown>);
  }
  return json as T;
};

const parse_api_error = async (json: unknown): Promise<string> => {
  if ('function' === typeof (json as any).then) {
    json = await (json as Promise<unknown>);
  }

  const { $i18n } = useNuxtApp();
  const t = $i18n?.t ?? ((key: string) => key);
  const te = ($i18n as { te?: (key: string) => boolean } | undefined)?.te ?? (() => false);

  if (!json || 'object' !== typeof json) {
    return t('common.unknownError');
  }

  const payload = json as {
    error?: string;
    message?: string;
    code?: string;
    params?: Record<string, string | number | boolean | null>;
    detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
  };

  let extra_detail = '';

  if (Array.isArray(payload.detail)) {
    const errors = payload.detail.map((err: any) => {
      if ('object' === typeof err && err.loc && err.msg) {
        const field = Array.isArray(err.loc) ? err.loc[err.loc.length - 1] : 'unknown';
        return `${field}: ${err.msg}`;
      }
      return String(err);
    });
    extra_detail = errors.join(', ');
  } else if (typeof payload.detail === 'string' && payload.detail.trim()) {
    extra_detail = payload.detail.trim();
  }

  let message = '';

  if (payload.code) {
    const key = `errors.${payload.code}`;
    if (te(key)) {
      const params = Object.fromEntries(
        Object.entries(payload.params ?? {}).map(([paramKey, value]) => {
          if (typeof value === 'string' && value.startsWith('api.') && te(value)) {
            return [paramKey, t(value)];
          }

          return [paramKey, value];
        }),
      );
      message = String(t(key, params));
    }
  }

  if (!message) {
    message = payload.message || payload.error || '';
  }

  const details: string[] = [];
  const addDetail = (value: string | undefined): void => {
    const detail = value?.trim();
    if (detail && detail !== message && !details.includes(detail)) {
      details.push(detail);
    }
  };

  addDetail(payload.error);
  addDetail(extra_detail);

  if (message) {
    return [message, ...details].join(' - ');
  }

  if (details.length > 0) {
    return details.join(' - ');
  }

  return t('common.unknownError');
};

class ApiError extends Error {
  readonly status: number;
  readonly payload: ApiErrorPayload | null;
  readonly fields: Record<string, string>;

  constructor(
    message: string,
    options: {
      status?: number;
      payload?: ApiErrorPayload | null;
      cause?: unknown;
    } = {},
  ) {
    super(message, { cause: options.cause });
    this.name = 'ApiError';
    this.status = options.status ?? 0;
    this.payload = options.payload ?? null;
    this.fields = {};

    if (Array.isArray(this.payload?.detail)) {
      for (const item of this.payload.detail) {
        const field = item.loc?.at(-1);
        if (field !== undefined && item.msg) {
          this.fields[String(field)] = item.msg;
        }
      }
    }
  }
}

const to_api_error = (error: unknown): ApiError => {
  if (error instanceof ApiError) {
    return error;
  }

  const { $i18n } = useNuxtApp();
  const t = $i18n?.t ?? ((key: string) => key);
  const message = error instanceof Error ? error.message : t('common.unknownError');
  return new ApiError(message, { cause: error });
};

const ensure_api_success = async (response: Response): Promise<void> => {
  if (response.ok) {
    return;
  }

  let payload: ApiErrorPayload | null = null;
  try {
    payload = (await response.clone().json()) as ApiErrorPayload;
  } catch {
    // The status still provides useful context when the response has no JSON body.
  }

  throw new ApiError(await parse_api_error(payload), {
    status: response.status,
    payload,
  });
};

const formatPageTitle = (title?: string | null): string => {
  const normalized = title?.trim();

  if (!normalized || normalized === APP_TITLE) {
    return APP_TITLE;
  }

  return `${normalized} | ${APP_TITLE}`;
};

export {
  APP_TITLE,
  separators,
  convertCliOptions,
  getSeparatorsName,
  iTrim,
  eTrim,
  sTrim,
  ucFirst,
  normalizePresetName,
  browserSummary,
  prettyName,
  getValue,
  ag,
  ag_set,
  r,
  copyText,
  encodePath,
  request,
  removeANSIColors,
  basename,
  dirname,
  getQueryParams,
  makeDownload,
  formatBytes,
  has_data,
  toggleClass,
  cleanObject,
  uri,
  formatTime,
  sleep,
  awaiter,
  encode,
  decode,
  syncOpacity,
  disableOpacity,
  enableOpacity,
  stripPath,
  shortPath,
  isDownloadSkipped,
  deepIncludes,
  getPath,
  getImage,
  getHistoryImage,
  getRemoteImage,
  parse_list_response,
  parse_api_response,
  parse_api_error,
  ApiError,
  to_api_error,
  ensure_api_success,
  formatPageTitle,
};
