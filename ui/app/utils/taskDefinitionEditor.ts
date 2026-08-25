import type { TaskDefinitionDocument } from '~/types/task_definitions';

export type EditorDiagnostic = { path: string; reason: string };

export type EditorField = {
  key: string;
  type: string;
  expression: string;
  attribute: string;
  postFilter: { filter: string; value: string };
};

export type EditorState = {
  name: string;
  priority: number;
  enabled: boolean;
  matchText: string;
  engineType: 'http' | 'browser';
  engineUrl: string;
  engineOptions: Record<string, unknown>;
  requestMethod: 'GET' | 'POST';
  requestUrl: string;
  requestTimeout: string;
  requestHeaders: RequestPair[];
  requestParams: RequestPair[];
  requestBodyType: 'none' | 'form' | 'json' | 'raw';
  requestBody: string;
  requestBodyPairs: RequestPair[];
  requestJsonText: string;
  requestJsonFallback: boolean;
  parseMode: 'container' | 'direct';
  containerType: 'css' | 'xpath' | 'jsonpath';
  containerSelector: string;
  fields: EditorField[];
  responseType: 'html' | 'json';
};

const objectRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

const path = (base: string, key: string): string => `${base}.${key}`;

const diagnostic = (diagnostics: EditorDiagnostic[], at: string, reason: string): void => {
  diagnostics.push({ path: at, reason });
};

const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);
const isMapKey = (value: string): boolean => Boolean(value) && !/[\r\n]/.test(value);

const checkObject = (
  value: unknown,
  at: string,
  diagnostics: EditorDiagnostic[],
): Record<string, unknown> | null => {
  const result = objectRecord(value);
  if (!result) diagnostic(diagnostics, at, 'must be an object');
  return result;
};

const checkAdditional = (
  value: Record<string, unknown>,
  at: string,
  allowed: readonly string[],
  diagnostics: EditorDiagnostic[],
): void => {
  Object.keys(value)
    .filter((key) => !allowed.includes(key))
    .forEach((key) =>
      diagnostic(diagnostics, path(at, key), 'is not supported by the visual editor'),
    );
};

const checkString = (
  value: unknown,
  at: string,
  diagnostics: EditorDiagnostic[],
  nullable = false,
  nonEmpty = false,
): void => {
  if (value === null && nullable) return;
  if (typeof value !== 'string') {
    diagnostic(diagnostics, at, nullable ? 'must be a string or null' : 'must be a string');
  } else if (nonEmpty && !value.trim()) {
    diagnostic(diagnostics, at, 'must not be empty');
  }
};

const readRule = (
  value: unknown,
  at: string,
  diagnostics: EditorDiagnostic[],
): EditorField | null => {
  const rule = objectRecord(value);
  if (!rule) {
    diagnostic(diagnostics, at, 'must be an object');
    return null;
  }
  if (typeof rule.type !== 'string') diagnostic(diagnostics, path(at, 'type'), 'must be a string');
  else if (!['css', 'xpath', 'regex', 'jsonpath'].includes(rule.type))
    diagnostic(diagnostics, path(at, 'type'), 'must be css, xpath, regex, or jsonpath');
  if (typeof rule.expression !== 'string' || !rule.expression.trim())
    diagnostic(diagnostics, path(at, 'expression'), 'must be a non-empty string');
  checkAdditional(rule, at, ['type', 'expression', 'attribute', 'post_filter'], diagnostics);
  if (rule.attribute !== undefined && rule.attribute !== null)
    checkString(rule.attribute, path(at, 'attribute'), diagnostics, false, true);
  const filter = objectRecord(rule.post_filter);
  if (rule.post_filter !== undefined && rule.post_filter !== null && !filter) {
    diagnostic(diagnostics, path(at, 'post_filter'), 'must be an object or null');
  }
  if (filter) {
    checkAdditional(filter, path(at, 'post_filter'), ['filter', 'value'], diagnostics);
    if (typeof filter.filter !== 'string' || !filter.filter.trim())
      diagnostic(diagnostics, path(at, 'post_filter.filter'), 'must be a non-empty string');
    if (filter.value !== undefined && filter.value !== null)
      checkString(filter.value, path(at, 'post_filter.value'), diagnostics, false, true);
  }
  if (typeof rule.type !== 'string') return null;
  return {
    key: '',
    type: rule.type,
    expression: typeof rule.expression === 'string' ? rule.expression : '',
    attribute: typeof rule.attribute === 'string' ? rule.attribute : '',
    postFilter: {
      filter: typeof filter?.filter === 'string' ? filter.filter : '',
      value: typeof filter?.value === 'string' ? filter.value : '',
    },
  };
};

export const analyzeTaskDefinition = (document: unknown): EditorDiagnostic[] => {
  const diagnostics: EditorDiagnostic[] = [];
  const entry = objectRecord(document);
  if (!entry) {
    diagnostic(diagnostics, '$', 'must be an object');
    return diagnostics;
  }
  checkAdditional(
    entry,
    '$',
    ['id', 'name', 'priority', 'enabled', 'match_url', 'created_at', 'updated_at', 'definition'],
    diagnostics,
  );
  if (!('name' in entry)) diagnostic(diagnostics, '$.name', 'is required');
  if ('id' in entry && !Number.isInteger(entry.id))
    diagnostic(diagnostics, '$.id', 'must be an integer');
  if ('name' in entry) checkString(entry.name, '$.name', diagnostics, false, true);
  if ('priority' in entry && (!Number.isInteger(entry.priority) || (entry.priority as number) < 0))
    diagnostic(diagnostics, '$.priority', 'must be a non-negative integer');
  if ('enabled' in entry && typeof entry.enabled !== 'boolean')
    diagnostic(diagnostics, '$.enabled', 'must be a boolean');
  if (!Array.isArray(entry.match_url) || entry.match_url.length === 0)
    diagnostic(diagnostics, '$.match_url', 'must be a non-empty array');
  else
    entry.match_url.forEach((value, index) =>
      checkString(value, `$.match_url[${index}]`, diagnostics, false, true),
    );
  const definition = checkObject(entry.definition, '$.definition', diagnostics);
  if (!definition) {
    return diagnostics;
  }
  checkAdditional(
    definition,
    '$.definition',
    ['parse', 'engine', 'request', 'response'],
    diagnostics,
  );
  const parse = checkObject(definition.parse, '$.definition.parse', diagnostics);
  if (!parse) {
    return diagnostics;
  }
  const items =
    parse.items === null
      ? null
      : parse.items === undefined
        ? undefined
        : checkObject(parse.items, '$.definition.parse.items', diagnostics);
  if (parse.items !== undefined && parse.items !== null && !items) return diagnostics;
  const ruleEntries = items
    ? Object.entries(objectRecord(items.fields) ?? {})
    : Object.entries(parse).filter(([key]) => key !== 'items');
  if (items) {
    checkAdditional(items, '$.definition.parse.items', ['type', 'selector', 'fields'], diagnostics);
    if (items.type !== undefined && typeof items.type !== 'string')
      diagnostic(diagnostics, '$.definition.parse.items.type', 'must be a string');
    else if (
      items.type !== undefined &&
      !['css', 'xpath', 'jsonpath'].includes(items.type as string)
    )
      diagnostic(diagnostics, '$.definition.parse.items.type', 'must be css, xpath, or jsonpath');
    if (items.selector !== undefined && items.selector !== null)
      checkString(items.selector, '$.definition.parse.items.selector', diagnostics, false, true);
    if (!objectRecord(items.fields))
      diagnostic(diagnostics, '$.definition.parse.items.fields', 'must be an object');
  }
  if (items)
    Object.keys(parse)
      .filter((key) => key !== 'items')
      .forEach((key) =>
        diagnostic(
          diagnostics,
          `$.definition.parse.${key}`,
          'cannot be mixed with parse.items in visual mode',
        ),
      );
  for (const [key, value] of ruleEntries) {
    if (!isMapKey(key))
      diagnostic(
        diagnostics,
        items ? '$.definition.parse.items.fields' : '$.definition.parse',
        'keys must be non-empty single-line strings',
      );
    readRule(
      value,
      items ? `$.definition.parse.items.fields.${key}` : `$.definition.parse.${key}`,
      diagnostics,
    );
  }
  if (items) {
    const selector = items.selector;
    if (selector !== undefined && selector !== null && typeof selector !== 'string') {
      diagnostic(diagnostics, '$.definition.parse.items.selector', 'must be a string or null');
    }
    if (selector === undefined || selector === null || selector === '')
      diagnostic(diagnostics, '$.definition.parse.items', 'requires a selector');
    const fields = objectRecord(items.fields);
    if (!fields || !('url' in fields))
      diagnostic(diagnostics, '$.definition.parse.items.fields.url', 'is required');
  } else if (items === null) {
    // A null serialized default means direct parsing, as it does in the API.
    if (!('url' in parse))
      diagnostic(diagnostics, '$.definition.parse.url', 'is required for direct parsing');
  } else if (!('url' in parse)) {
    diagnostic(diagnostics, '$.definition.parse.url', 'is required for direct parsing');
  }
  const engine = objectRecord(definition.engine);
  if (definition.engine !== undefined && !engine)
    diagnostic(diagnostics, '$.definition.engine', 'must be an object');
  const engineType = engine?.type ?? 'http';
  if (engine && !['http', 'browser'].includes(String(engineType)))
    diagnostic(diagnostics, '$.definition.engine.type', 'must be http or browser');
  if (engine) checkAdditional(engine, '$.definition.engine', ['type', 'options'], diagnostics);
  const options =
    engine?.options === undefined
      ? {}
      : checkObject(engine.options, '$.definition.engine.options', diagnostics);
  const supportedOptions =
    engineType === 'browser'
      ? ['protocol', 'url', 'wait_for', 'wait_timeout', 'page_load_timeout']
      : ['impersonate', 'curl_default_headers', 'flaresolverr'];
  if (options) {
    checkAdditional(options, '$.definition.engine.options', supportedOptions, diagnostics);
    if (engineType === 'http') {
      if ('impersonate' in options)
        checkString(
          options.impersonate,
          '$.definition.engine.options.impersonate',
          diagnostics,
          false,
          true,
        );
      for (const key of ['curl_default_headers', 'flaresolverr'])
        if (key in options && typeof options[key] !== 'boolean')
          diagnostic(diagnostics, `$.definition.engine.options.${key}`, 'must be a boolean');
    } else {
      if (options.protocol !== undefined && options.protocol !== 'cdp')
        diagnostic(diagnostics, '$.definition.engine.options.protocol', 'must be cdp');
      if (options.url === undefined)
        diagnostic(
          diagnostics,
          '$.definition.engine.options.url',
          'is required for browser engine',
        );
      else if (typeof options.url !== 'string')
        diagnostic(diagnostics, '$.definition.engine.options.url', 'must be a string');
      else {
        try {
          const url = new URL(options.url);
          if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error();
        } catch {
          diagnostic(
            diagnostics,
            '$.definition.engine.options.url',
            'must be an absolute http(s) URL',
          );
        }
      }
      const wait =
        options.wait_for === undefined || options.wait_for === null
          ? null
          : checkObject(options.wait_for, '$.definition.engine.options.wait_for', diagnostics);
      if (wait) {
        checkAdditional(
          wait,
          '$.definition.engine.options.wait_for',
          ['type', 'expression'],
          diagnostics,
        );
        if (wait.type !== undefined && typeof wait.type !== 'string')
          diagnostic(diagnostics, '$.definition.engine.options.wait_for.type', 'must be a string');
        else if (wait.type !== undefined && !['css', 'xpath'].includes(wait.type as string))
          diagnostic(
            diagnostics,
            '$.definition.engine.options.wait_for.type',
            'must be css or xpath',
          );
        checkString(
          wait.expression,
          '$.definition.engine.options.wait_for.expression',
          diagnostics,
          false,
          true,
        );
      }
      for (const key of ['wait_timeout', 'page_load_timeout'])
        if (
          key in options &&
          (!isFiniteNumber(options[key]) ||
            (options[key] as number) < 0 ||
            (options[key] as number) > 300)
        )
          diagnostic(
            diagnostics,
            `$.definition.engine.options.${key}`,
            'must be a finite number from 0 to 300',
          );
    }
  }
  const response = objectRecord(definition.response);
  if (definition.response !== undefined && !response)
    diagnostic(diagnostics, '$.definition.response', 'must be an object');
  if (response) {
    checkAdditional(response, '$.definition.response', ['type'], diagnostics);
    if (response.type !== undefined && !['html', 'json'].includes(String(response.type)))
      diagnostic(diagnostics, '$.definition.response.type', 'must be html or json');
    if (response.type !== undefined && typeof response.type !== 'string')
      diagnostic(diagnostics, '$.definition.response.type', 'must be a string');
  }
  const request = objectRecord(definition.request);
  if (definition.request !== undefined && !request)
    diagnostic(diagnostics, '$.definition.request', 'must be an object');
  if (request) {
    checkAdditional(
      request,
      '$.definition.request',
      ['method', 'url', 'headers', 'params', 'body', 'timeout'],
      diagnostics,
    );
    if (request.method !== undefined && !['GET', 'POST'].includes(String(request.method)))
      diagnostic(diagnostics, '$.definition.request.method', 'must be GET or POST');
    if (request.method !== undefined && typeof request.method !== 'string')
      diagnostic(diagnostics, '$.definition.request.method', 'must be a string');
    if (request.url !== undefined && request.url !== null)
      checkString(request.url, '$.definition.request.url', diagnostics, false, true);
    for (const key of ['headers', 'params']) {
      const map =
        request[key] === undefined
          ? {}
          : checkObject(request[key], `$.definition.request.${key}`, diagnostics);
      if (map)
        for (const [name, value] of Object.entries(map)) {
          if (!isMapKey(name))
            diagnostic(
              diagnostics,
              `$.definition.request.${key}`,
              'keys must be non-empty single-line strings',
            );
          if (key === 'headers' && typeof value !== 'string')
            diagnostic(diagnostics, `$.definition.request.headers.${name}`, 'must be a string');
          if (
            key === 'params' &&
            value !== null &&
            !['string', 'number', 'boolean'].includes(typeof value)
          )
            diagnostic(
              diagnostics,
              `$.definition.request.params.${name}`,
              'must be a string, number, boolean, or null',
            );
        }
    }
    if (request.body !== undefined && request.body !== null) {
      const body = checkObject(request.body, '$.definition.request.body', diagnostics);
      if (body) {
        checkAdditional(body, '$.definition.request.body', ['type', 'value'], diagnostics);
        if (!['form', 'json', 'raw'].includes(String(body.type)))
          diagnostic(diagnostics, '$.definition.request.body.type', 'must be form, json, or raw');
        if (request.method !== 'POST')
          diagnostic(diagnostics, '$.definition.request.body', 'requires request.method POST');
        if (!('value' in body))
          diagnostic(diagnostics, '$.definition.request.body.value', 'is required');
        else if (body.type === 'raw')
          checkString(body.value, '$.definition.request.body.value', diagnostics);
        else if (body.type === 'form') {
          const form = checkObject(body.value, '$.definition.request.body.value', diagnostics);
          if (form)
            for (const [name, value] of Object.entries(form))
              if (!isMapKey(name))
                diagnostic(
                  diagnostics,
                  '$.definition.request.body.value',
                  'keys must be non-empty single-line strings',
                );
              else if (value !== null && !['string', 'number', 'boolean'].includes(typeof value))
                diagnostic(
                  diagnostics,
                  `$.definition.request.body.value.${name}`,
                  'must be a string, number, boolean, or null',
                );
        }
      }
    }
    if (
      request.timeout !== undefined &&
      request.timeout !== null &&
      (!isFiniteNumber(request.timeout) || (request.timeout as number) < 0)
    )
      diagnostic(
        diagnostics,
        '$.definition.request.timeout',
        'must be a finite non-negative number or null',
      );
  }
  return diagnostics;
};

export const formatEditorDiagnostics = (diagnostics: EditorDiagnostic[]): string =>
  diagnostics.map(({ path: at, reason }) => `${at}: ${reason}`).join('\n');

// This analyzer is intentionally public so import/mode-switch callers can show every known issue.
export const canUseVisualEditor = (document: unknown): boolean =>
  analyzeTaskDefinition(document).length === 0;

export type EditorMode = 'gui' | 'advanced';
export type ScalarType = 'string' | 'number' | 'boolean' | 'null';
export type RequestPair = { key: string; value: string; type: ScalarType };
export type RequestBodyType = 'none' | 'form' | 'json' | 'raw';

export class EditorInputError extends Error {
  constructor(
    public readonly code: string,
    public readonly params: Record<string, string> = {},
  ) {
    super(code);
    this.name = 'EditorInputError';
  }
}

const cloneJson = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

export const defaultField = (): EditorField => ({
  key: '',
  type: 'css',
  expression: '',
  attribute: '',
  postFilter: { filter: '', value: '' },
});

export const defaultEditorState = (): EditorState => ({
  name: '',
  priority: 0,
  enabled: true,
  matchText: '',
  engineType: 'http',
  engineUrl: '',
  engineOptions: {},
  requestMethod: 'GET',
  requestUrl: '',
  requestTimeout: '',
  requestHeaders: [],
  requestParams: [],
  requestBodyType: 'none',
  requestBody: '',
  requestBodyPairs: [],
  requestJsonText: '',
  requestJsonFallback: false,
  parseMode: 'container',
  containerType: 'css',
  containerSelector: '',
  fields: [defaultField()],
  responseType: 'html',
});

export const cloneEditorState = (state: EditorState): EditorState => cloneJson(state);
export const addPair = (pairs: RequestPair[]): void => {
  pairs.push({ key: '', value: '', type: 'string' });
};
export const splitMatches = (text: string): string[] =>
  text
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
export const hasPairValues = (pairs: RequestPair[]): boolean =>
  pairs.some((pair) => Boolean(pair.key.trim() || pair.value));

export const hasAdvancedRequestOptions = (state: EditorState): boolean => {
  if (
    state.requestTimeout.trim() ||
    hasPairValues(state.requestParams) ||
    hasPairValues(state.requestHeaders)
  ) {
    return true;
  }

  if (state.engineType === 'http') {
    return (
      (typeof state.engineOptions.impersonate === 'string' &&
        state.engineOptions.impersonate !== 'chrome') ||
      state.engineOptions.curl_default_headers === false ||
      state.engineOptions.flaresolverr === true
    );
  }

  const wait = state.engineOptions.wait_for;
  return (
    (wait !== undefined && wait !== null && typeof wait === 'object') ||
    (typeof state.engineOptions.wait_timeout === 'number' &&
      state.engineOptions.wait_timeout !== 15) ||
    (typeof state.engineOptions.page_load_timeout === 'number' &&
      state.engineOptions.page_load_timeout !== 60)
  );
};

const scalarFromValue = (item: unknown): { value: string; type: ScalarType } | null => {
  if (typeof item === 'string') return { value: item, type: 'string' };
  if (typeof item === 'number' && Number.isFinite(item))
    return { value: String(item), type: 'number' };
  if (typeof item === 'boolean') return { value: String(item), type: 'boolean' };
  if (item === null) return { value: '', type: 'null' };
  return null;
};

export const readStringPairs = (value: unknown): RequestPair[] | null => {
  if (value === undefined) return [];
  if (!value || Array.isArray(value) || typeof value !== 'object') return null;
  const pairs: RequestPair[] = [];
  for (const [key, item] of Object.entries(value)) {
    if (typeof item !== 'string') return null;
    pairs.push({ key, value: item, type: 'string' });
  }
  return pairs;
};

export const readScalarPairs = (value: unknown): RequestPair[] | null => {
  if (value === undefined) return [];
  if (!value || Array.isArray(value) || typeof value !== 'object') return null;
  const pairs: RequestPair[] = [];
  for (const [key, item] of Object.entries(value)) {
    const pair = scalarFromValue(item);
    if (!pair) return null;
    pairs.push({ key, ...pair });
  }
  return pairs;
};

export const writeStringPairs = (pairs: RequestPair[], label: string): Record<string, string> => {
  const result: Record<string, string> = {};
  for (const pair of pairs) {
    const key = pair.key;
    if (!key && !pair.value) continue;
    if (!key) throw new EditorInputError('requestKeyRequired', { label });
    result[key] = pair.value;
  }
  return result;
};

const scalarFromPair = (pair: RequestPair): string | number | boolean | null => {
  if (pair.type === 'null') return null;
  if (pair.type === 'boolean') {
    if (pair.value === 'true') return true;
    if (pair.value === 'false') return false;
    throw new EditorInputError('validationPairValue', { key: pair.key });
  }
  if (pair.type === 'number') {
    const number = Number(pair.value);
    if (!Number.isFinite(number) || pair.value.trim() === '') {
      throw new EditorInputError('validationPairValue', { key: pair.key });
    }
    return number;
  }
  return pair.value;
};

export const writeScalarPairs = (
  pairs: RequestPair[],
  label: string,
): Record<string, string | number | boolean | null> => {
  const result: Record<string, string | number | boolean | null> = {};
  for (const pair of pairs) {
    const key = pair.key;
    if (!key && !pair.value) continue;
    if (!key) throw new EditorInputError('requestKeyRequired', { label });
    result[key] = scalarFromPair(pair);
  }
  return result;
};

export const staleFields = (state: EditorState): string[] => {
  const fields: string[] = [];
  const hasBody = state.requestMethod === 'POST';
  if (state.requestBody && (!hasBody || state.requestBodyType !== 'raw'))
    fields.push('requestBodyRaw');
  if (
    hasPairValues(state.requestBodyPairs) &&
    (!hasBody || !['form', 'json'].includes(state.requestBodyType))
  )
    fields.push('requestBody');
  if (state.engineType === 'http' && state.engineUrl.trim()) fields.push('browserEndpointUrl');
  const allowed =
    state.engineType === 'http'
      ? new Set(['impersonate', 'curl_default_headers', 'flaresolverr'])
      : new Set(['protocol', 'url', 'wait_for', 'wait_timeout', 'page_load_timeout']);
  for (const [key, value] of Object.entries(state.engineOptions))
    if (key !== 'url' && !allowed.has(key) && value !== undefined && value !== null && value !== '')
      fields.push(`engine.options.${key}`);
  return fields;
};

export const clearStaleFields = (state: EditorState): void => {
  const hasBody = state.requestMethod === 'POST';
  if (!hasBody || state.requestBodyType !== 'raw') state.requestBody = '';
  if (!hasBody || !['form', 'json'].includes(state.requestBodyType)) state.requestBodyPairs = [];
  if (state.engineType === 'http') state.engineUrl = '';
  const allowed =
    state.engineType === 'http'
      ? new Set(['impersonate', 'curl_default_headers', 'flaresolverr'])
      : new Set(['protocol', 'wait_for', 'wait_timeout', 'page_load_timeout']);
  state.engineOptions = Object.fromEntries(
    Object.entries(state.engineOptions).filter(([key]) => allowed.has(key)),
  );
};

export const toGui = (document: TaskDefinitionDocument): EditorState | null => {
  if (!document || Array.isArray(document) || typeof document !== 'object') {
    return null;
  }
  const entry = document;
  const match = entry.match_url;
  if (!Array.isArray(match) || match.some((item) => typeof item !== 'string')) {
    return null;
  }

  const definition = entry.definition;
  if (!definition || Array.isArray(definition) || typeof definition !== 'object') {
    return null;
  }

  const parse = definition.parse;
  if (!parse || Array.isArray(parse) || typeof parse !== 'object') {
    return null;
  }

  const parseRecord = parse as Record<string, unknown>;
  const items = parseRecord.items;
  const itemRecord =
    items && !Array.isArray(items) && typeof items === 'object'
      ? (items as Record<string, unknown>)
      : null;
  const fields =
    itemRecord?.fields ??
    Object.fromEntries(Object.entries(parseRecord).filter(([key]) => key !== 'items'));
  if (!fields || Array.isArray(fields) || typeof fields !== 'object') return null;

  const fieldRecord = fields as Record<string, unknown>;
  const guiFields: EditorField[] = [];
  for (const [key, value] of Object.entries(fieldRecord)) {
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      return null;
    }

    const rule = value as Record<string, unknown>;
    if (typeof rule.type !== 'string' || typeof rule.expression !== 'string') {
      return null;
    }

    if (
      Object.keys(rule).some(
        (prop) => !['type', 'expression', 'attribute', 'post_filter'].includes(prop),
      )
    ) {
      return null;
    }

    const postFilter =
      rule.post_filter && typeof rule.post_filter === 'object'
        ? (rule.post_filter as Record<string, unknown>)
        : {};
    guiFields.push({
      key,
      type: String(rule.type),
      expression: String(rule.expression),
      attribute: typeof rule.attribute === 'string' ? String(rule.attribute) : '',
      postFilter: {
        filter: typeof postFilter.filter === 'string' ? postFilter.filter : '',
        value: typeof postFilter.value === 'string' ? postFilter.value : '',
      },
    });
  }

  const engine = definition.engine as Record<string, unknown> | undefined;
  if (engine?.type !== undefined && !['http', 'browser'].includes(String(engine.type))) {
    return null;
  }
  const engineType = engine?.type === 'browser' ? 'browser' : 'http';
  const engineOptions =
    engine?.options && typeof engine.options === 'object' && !Array.isArray(engine.options)
      ? cloneJson(engine.options as Record<string, unknown>)
      : {};
  if (engineType === 'browser') {
    if (engineOptions.protocol !== undefined && engineOptions.protocol !== 'cdp') {
      return null;
    }
    engineOptions.protocol = 'cdp';
  }
  const engineUrl = engineOptions.url as string | undefined;

  if (engineUrl && engineType === 'browser' && typeof engineUrl !== 'string') {
    return null;
  }

  const request = definition.request as Record<string, unknown> | undefined;
  if (
    request &&
    Object.keys(request).some(
      (key) => !['method', 'url', 'headers', 'params', 'body', 'timeout'].includes(key),
    )
  ) {
    return null;
  }
  const requestMethod = typeof request?.method === 'string' ? String(request.method) : 'GET';
  if (!['GET', 'POST'].includes(requestMethod)) {
    return null;
  }
  const body = request?.body;
  if (body !== undefined && body !== null && requestMethod !== 'POST') {
    return null;
  }
  const requestHeaders = readStringPairs(request?.headers);
  const requestParams = readScalarPairs(request?.params);
  if (!requestHeaders || !requestParams) {
    return null;
  }

  let requestBodyType: RequestBodyType = 'none';
  let requestBody = '';
  let requestBodyPairs: RequestPair[] = [];
  if (body !== undefined && body !== null) {
    if (!body || Array.isArray(body) || typeof body !== 'object') {
      return null;
    }
    const bodyRecord = body as Record<string, unknown>;
    if (bodyRecord.type === 'raw' && typeof bodyRecord.value === 'string') {
      requestBodyType = 'raw';
      requestBody = bodyRecord.value;
    } else if (bodyRecord.type === 'form' && bodyRecord.value) {
      const formPairs = readScalarPairs(bodyRecord.value);
      if (!formPairs) {
        return null;
      }
      requestBodyType = 'form';
      requestBodyPairs = formPairs;
    } else if (bodyRecord.type === 'json' && bodyRecord.value !== undefined) {
      requestBodyType = 'json';
      if (
        bodyRecord.value &&
        !Array.isArray(bodyRecord.value) &&
        typeof bodyRecord.value === 'object' &&
        Object.keys(bodyRecord.value).every(isMapKey)
      ) {
        requestBodyPairs = Object.entries(bodyRecord.value).map(([key, value]) => ({
          key,
          value: JSON.stringify(value) ?? 'null',
          type: 'string',
        }));
      } else {
        requestBody = JSON.stringify(bodyRecord.value);
      }
    } else {
      return null;
    }
  }

  const timeout = request?.timeout;
  if (
    timeout !== undefined &&
    timeout !== null &&
    (typeof timeout !== 'number' || !Number.isFinite(timeout))
  ) {
    return null;
  }
  const selectorType = String(itemRecord?.type ?? 'css') as EditorState['containerType'];
  const selectorSource = itemRecord?.selector as string | undefined;
  if (items !== undefined && (!selectorSource || typeof selectorSource !== 'string')) {
    return null;
  }

  return {
    name: typeof entry.name === 'string' ? entry.name : '',
    priority: Number(entry.priority ?? 0) || 0,
    enabled: typeof entry.enabled === 'boolean' ? entry.enabled : true,
    matchText: match.join('\n'),
    engineType,
    engineUrl: engineType === 'browser' ? String(engineUrl ?? '') : '',
    engineOptions,
    parseMode: itemRecord ? 'container' : 'direct',
    requestMethod: requestMethod as 'GET' | 'POST',
    requestUrl: typeof request?.url === 'string' ? String(request.url) : '',
    requestTimeout: timeout === undefined || timeout === null ? '' : String(timeout),
    requestBodyType,
    requestBody,
    requestBodyPairs,
    requestJsonText: requestBodyType === 'json' && requestBodyPairs.length === 0 ? requestBody : '',
    requestJsonFallback: requestBodyType === 'json' && requestBodyPairs.length === 0,
    requestParams,
    requestHeaders,
    containerType: selectorType,
    containerSelector: selectorSource ?? '',
    fields: guiFields.length ? guiFields : [defaultField()],
    responseType:
      definition.response &&
      typeof definition.response === 'object' &&
      (definition.response as Record<string, unknown>).type === 'json'
        ? 'json'
        : 'html',
  };
};

export const fromGui = (state: EditorState): TaskDefinitionDocument => {
  if (!state.name.trim()) {
    throw new EditorInputError('validationNameRequired');
  }

  const matches = splitMatches(state.matchText);
  if (!matches.length) {
    throw new EditorInputError('validationMatchRequired');
  }

  if (state.parseMode === 'container' && !state.containerSelector.trim()) {
    throw new EditorInputError('validationSelectorRequired');
  }

  const formattedFields: Record<string, Record<string, unknown>> = {};
  state.fields.forEach((field) => {
    if (!field.key) {
      return;
    }

    if (!field.expression.trim()) {
      throw new EditorInputError('validationExpressionRequired', { key: field.key });
    }

    formattedFields[field.key] = {
      type: field.type || 'css',
      expression: field.expression,
      ...(field.attribute ? { attribute: field.attribute } : {}),
      ...(field.postFilter.filter
        ? {
            post_filter: {
              filter: field.postFilter.filter,
              ...(field.postFilter.value ? { value: field.postFilter.value } : {}),
            },
          }
        : {}),
    };
  });

  if (!Object.keys(formattedFields).length) {
    throw new EditorInputError('validationFieldsRequired');
  }
  if (!formattedFields.url) {
    throw new EditorInputError('validationUrlFieldRequired');
  }

  if (state.engineType === 'browser' && !state.engineUrl.trim()) {
    throw new EditorInputError('validationBrowserEndpointRequired');
  }

  const definition: Record<string, unknown> = {
    parse:
      state.parseMode === 'direct'
        ? formattedFields
        : {
            items: {
              type: state.containerType,
              selector: state.containerSelector,
              fields: formattedFields,
            },
          },
  };

  if (state.responseType !== 'html') definition.response = { type: state.responseType };

  const engineOptions = Object.fromEntries(
    Object.entries(state.engineOptions).filter(([key]) =>
      state.engineType === 'http'
        ? ['impersonate', 'curl_default_headers', 'flaresolverr'].includes(key)
        : ['protocol', 'wait_for', 'wait_timeout', 'page_load_timeout'].includes(key),
    ),
  );
  if (state.engineType === 'browser') {
    const wait = engineOptions.wait_for;
    if (wait !== undefined) {
      if (wait === null) {
        delete engineOptions.wait_for;
      } else if (typeof wait !== 'object' || Array.isArray(wait)) {
        throw new EditorInputError('validationWaitFor');
      } else {
        const waitRecord = wait as Record<string, unknown>;
        const expression = waitRecord.expression;
        const type = waitRecord.type ?? 'css';
        if (
          expression === undefined ||
          expression === null ||
          (typeof expression === 'string' && !expression.trim())
        ) {
          delete engineOptions.wait_for;
        } else if (typeof expression !== 'string' || !['css', 'xpath'].includes(String(type))) {
          throw new EditorInputError('validationWaitFor');
        } else {
          engineOptions.wait_for = {
            type,
            expression: waitRecord.expression,
          };
        }
      }
    }
    for (const key of ['wait_timeout', 'page_load_timeout']) {
      const timeout = engineOptions[key];
      if (
        timeout !== undefined &&
        (typeof timeout !== 'number' || !Number.isFinite(timeout) || timeout < 0 || timeout > 300)
      ) {
        throw new EditorInputError('validationBrowserTimeout');
      }
    }
  }
  if (state.engineType === 'browser' && state.engineUrl) {
    engineOptions.protocol = 'cdp';
    engineOptions.url = state.engineUrl;
  }

  if (state.engineType !== 'http' || Object.keys(engineOptions).length) {
    definition.engine = {
      type: state.engineType,
      options: engineOptions,
    };
  }

  const request: Record<string, unknown> = {};
  if (state.requestUrl) {
    request.url = state.requestUrl;
  }

  if (state.requestMethod && state.requestMethod !== 'GET') {
    request.method = state.requestMethod;
  }

  const params = writeScalarPairs(state.requestParams, 'queryParameters');
  if (Object.keys(params).length) {
    request.params = params;
  }

  const headers = writeStringPairs(state.requestHeaders, 'requestHeaders');
  if (Object.keys(headers).length) {
    request.headers = headers;
  }

  if (state.requestTimeout.trim()) {
    const timeout = Number(state.requestTimeout);
    if (!Number.isFinite(timeout) || timeout < 0) {
      throw new EditorInputError('validationRequestTimeout');
    }
    request.timeout = timeout;
  }

  if (state.requestMethod === 'POST' && state.requestBodyType === 'raw') {
    request.body = { type: 'raw', value: state.requestBody };
  } else if (state.requestMethod === 'POST' && state.requestBodyType === 'form') {
    request.body = {
      type: 'form',
      value: writeScalarPairs(state.requestBodyPairs, 'requestBody'),
    };
  } else if (state.requestMethod === 'POST' && state.requestBodyType === 'json') {
    if (state.requestJsonFallback) {
      let value: unknown;
      try {
        value = JSON.parse(state.requestJsonText);
      } catch {
        throw new EditorInputError('validationJsonValue', { key: 'requestBody' });
      }
      request.body = { type: 'json', value };
    } else {
      const body: Record<string, unknown> = {};
      for (const pair of state.requestBodyPairs) {
        const key = pair.key;
        if (!key && !pair.value) {
          continue;
        }
        if (!key) {
          throw new EditorInputError('requestKeyRequired', { label: 'requestBody' });
        }
        try {
          body[key] = JSON.parse(pair.value);
        } catch {
          throw new EditorInputError('validationJsonValue', { key });
        }
      }
      request.body = { type: 'json', value: body };
    }
  }
  if (Object.keys(request).length) {
    definition.request = request;
  }

  return {
    name: state.name.trim(),
    priority: Number(state.priority) || 0,
    enabled: state.enabled,
    match_url: matches,
    definition: definition as unknown as TaskDefinitionDocument['definition'],
  };
};

export const parseImportedDocument = (payload: unknown): TaskDefinitionDocument => {
  if (!payload || Array.isArray(payload) || typeof payload !== 'object') {
    throw new EditorInputError('validationImportPayload');
  }

  const record = payload as Record<string, unknown>;
  if ('_type' in record && record._type !== undefined && record._type !== 'task_definition') {
    throw new EditorInputError('invalidImportDefinition');
  }

  const version = record._version as string | undefined;
  if (version !== '2.0') {
    throw new EditorInputError('unsupportedVersion');
  }

  const document = JSON.parse(JSON.stringify(record)) as Record<string, unknown>;
  delete document._type;
  delete document._version;
  return document as unknown as TaskDefinitionDocument;
};

/** Return the first absolute HTTP(S) match URL without wildcard or pattern syntax. */
export const getInspectUrl = (matchUrls: readonly string[]): string => {
  for (const matchUrl of matchUrls) {
    if (
      (matchUrl.startsWith('/') && matchUrl.endsWith('/')) ||
      matchUrl.includes('*') ||
      matchUrl.includes('?') ||
      matchUrl.includes('[')
    ) {
      continue;
    }
    try {
      const url = new URL(matchUrl);
      if (url.protocol === 'http:' || url.protocol === 'https:') return matchUrl;
    } catch {
      // Continue looking for a literal absolute URL.
    }
  }
  return '';
};
