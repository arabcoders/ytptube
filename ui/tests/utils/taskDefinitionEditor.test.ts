import { describe, expect, it } from 'bun:test';
import { reactive } from 'vue';

import {
  analyzeTaskDefinition,
  clearStaleFields,
  defaultEditorState,
  formatEditorDiagnostics,
  fromGui,
  getInspectUrl,
  hasAdvancedRequestOptions,
  parseImportedDocument,
  toGui,
} from '~/utils/taskDefinitionEditor';

const base = {
  name: 'alsh3r.com',
  priority: 0,
  enabled: true,
  match_url: ['https://www.alsh3r.com/poems/*'],
  definition: {
    parse: {
      items: {
        type: 'css',
        selector: '.columns .card',
        fields: {
          url: { type: 'css', expression: '.card-header a', attribute: 'href', post_filter: null },
          title: {
            type: 'css',
            expression: '.card-header a',
            attribute: 'text',
            post_filter: null,
          },
        },
      },
    },
    engine: {
      type: 'http',
      options: { impersonate: 'chrome', curl_default_headers: true, flaresolverr: false },
    },
    request: { method: 'GET', headers: {}, params: {}, body: null, timeout: null, url: null },
    response: { type: 'html' },
  },
};

describe('task definition visual analysis', () => {
  it('selects_literal_inspect_url', () => {
    expect(getInspectUrl(['https://example.com/article'])).toBe('https://example.com/article');
    expect(getInspectUrl(['https://example.com/*', 'https://example.org/item?'])).toBe('');
    expect(getInspectUrl(['https://example.com/*', 'https://example.org/feed'])).toBe(
      'https://example.org/feed',
    );
    expect(getInspectUrl(['https://example.com/article(1)'])).toBe(
      'https://example.com/article(1)',
    );
  });

  it('detects_meaningful_request_options', () => {
    expect(hasAdvancedRequestOptions(toGui(base)!)).toBe(false);

    const state = toGui(base)!;
    state.requestTimeout = '120';
    expect(hasAdvancedRequestOptions(state)).toBe(true);

    state.requestTimeout = '';
    state.engineOptions = {
      impersonate: 'chrome',
      curl_default_headers: true,
      flaresolverr: false,
    };
    state.engineType = 'browser';
    state.engineOptions.wait_timeout = 15;
    state.engineOptions.page_load_timeout = 60;
    expect(hasAdvancedRequestOptions(state)).toBe(false);
    state.engineOptions.page_load_timeout = 61;
    expect(hasAdvancedRequestOptions(state)).toBe(true);
  });

  it('accepts_nullable_defaults', () => {
    expect(analyzeTaskDefinition(base)).toEqual([]);
  });

  it('accepts_metadata_fields', () => {
    const document = structuredClone(base);
    Object.assign(document.definition.parse.items.fields, {
      thumbnail: { type: 'css', expression: 'img', attribute: 'src' },
      description: { type: 'css', expression: '.description', attribute: 'text' },
      published: { type: 'css', expression: 'time', attribute: 'datetime' },
      custom_metadata: { type: 'css', expression: '.custom', attribute: 'text' },
    });
    expect(analyzeTaskDefinition(document)).toEqual([]);
    const converted = fromGui(toGui(document)!);
    expect(Object.keys(converted.definition.parse.items?.fields ?? {})).toEqual(
      expect.arrayContaining([
        'url',
        'title',
        'thumbnail',
        'description',
        'published',
        'custom_metadata',
      ]),
    );
  });

  it('reports_all_paths', () => {
    const document = structuredClone(base);
    (document.definition.parse.items.fields.url as Record<string, unknown>).post_filter = {
      filter: 4,
    };
    (document.definition.request as Record<string, unknown>).body = { type: 'json', value: [] };
    (document.definition.request as Record<string, unknown>).method = 'GET';
    const diagnostics = analyzeTaskDefinition(document);
    expect(formatEditorDiagnostics(diagnostics)).toContain(
      '$.definition.parse.items.fields.url.post_filter.filter',
    );
    expect(formatEditorDiagnostics(diagnostics)).toContain('$.definition.request.body');
  });

  it('accepts_direct_rules', () => {
    const document = structuredClone(base);
    document.definition.parse = {
      url: { type: 'css', expression: 'a', post_filter: { filter: '(.*)', value: '1' } },
    };
    expect(analyzeTaskDefinition(document)).toEqual([]);
  });

  it('reports_schema_paths', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.extra = true;
    document.definition.extra = true;
    document.definition.engine.options.extra = true;
    document.definition.parse.items.type = 'bad';
    document.definition.parse.items.fields.url.type = 'bad';
    document.definition.parse.items.fields.url.extra = true;
    document.definition.parse.items.fields.url.post_filter = { filter: '', extra: true };
    document.definition.request.headers = { X: 4 };
    document.definition.request.params = { page: ['x'] };
    document.definition.request.body = { type: 'form', value: { page: ['x'] }, extra: true };
    document.definition.request.method = 'POST';
    document.definition.response = { type: 'bad', extra: true };
    const paths = analyzeTaskDefinition(document).map(({ path }) => path);
    expect(paths).toEqual(
      expect.arrayContaining([
        '$.extra',
        '$.definition.extra',
        '$.definition.engine.options.extra',
        '$.definition.parse.items.type',
        '$.definition.parse.items.fields.url.type',
        '$.definition.parse.items.fields.url.extra',
        '$.definition.parse.items.fields.url.post_filter.filter',
        '$.definition.parse.items.fields.url.post_filter.extra',
        '$.definition.request.headers.X',
        '$.definition.request.params.page',
        '$.definition.request.body.extra',
        '$.definition.request.body.value.page',
        '$.definition.response.type',
        '$.definition.response.extra',
      ]),
    );
  });

  it('reports_conversion_mismatches', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.definition.parse.items.selector = '.card';
    delete document.definition.parse.items.fields.url;
    document.definition.request.body = { type: 'json' };
    document.definition.request.method = 'GET';
    const diagnostics = analyzeTaskDefinition(document);
    expect(diagnostics.map(({ path }) => path)).toEqual(
      expect.arrayContaining([
        '$.definition.parse.items.fields.url',
        '$.definition.request.body.value',
        '$.definition.request.body',
      ]),
    );
  });

  it('accepts_json_values', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.definition.request.method = 'POST';
    document.definition.request.body = { type: 'json', value: [null, true, 4, 'text'] };
    expect(analyzeTaskDefinition(document)).toEqual([]);
  });

  it('accepts_browser_endpoint', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.definition.engine = { type: 'browser', options: { url: 'http://localhost/wd/hub' } };
    expect(analyzeTaskDefinition(document)).toEqual([]);
  });

  it('round_trips_visual_document', () => {
    const state = toGui(base);
    expect(state).not.toBeNull();
    const converted = fromGui(state!);
    expect(analyzeTaskDefinition(converted)).toEqual([]);
    expect(converted.definition.parse.items?.fields.url.expression).toBe('.card-header a');
  });

  it('accepts_reactive_document', () => {
    const document = reactive(structuredClone(base));
    expect(() => toGui(document)).not.toThrow();
    expect(toGui(document)?.engineOptions).toEqual(base.definition.engine.options);
  });

  it('round_trips_scalar_pairs', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.definition.request.method = 'POST';
    document.definition.request.params = { q: 'news', page: 2, verbose: true, cache: null };
    document.definition.request.body = {
      type: 'form',
      value: { name: 'feed', count: 3, active: false, note: null },
    };
    expect(analyzeTaskDefinition(document)).toEqual([]);
    const state = toGui(document);
    expect(state).not.toBeNull();
    const converted = fromGui(state!);
    expect(converted.definition.request?.params).toEqual({
      q: 'news',
      page: 2,
      verbose: true,
      cache: null,
    });
    const body = converted.definition.request?.body as { type: 'form'; value: unknown };
    expect(body.type).toBe('form');
    expect(body.value).toEqual({ name: 'feed', count: 3, active: false, note: null });
    expect(analyzeTaskDefinition(converted)).toEqual([]);
  });

  it('preserves_json_object_keys', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.definition.request.method = 'POST';
    document.definition.request.params = { ' page': 2 };
    document.definition.request.body = {
      type: 'json',
      value: { ' query': 'new', '': 'empty' },
    };
    const state = toGui(document)!;
    expect(state.requestParams[0]?.key).toBe(' page');
    expect(state.requestJsonFallback).toBe(true);
    const request = fromGui(state).definition.request;
    expect(request?.params).toEqual({ ' page': 2 });
    expect(request?.body).toEqual(document.definition.request.body);
  });

  it('round_trips_jsonpath_container', () => {
    const document = structuredClone(base) as Record<string, any>;
    document.definition.parse.items.type = 'jsonpath';
    document.definition.parse.items.selector = 'entries';
    const state = toGui(document);
    expect(state?.containerType).toBe('jsonpath');
    expect(state?.containerSelector).toBe('entries');
    const converted = fromGui(state!);
    expect(converted.definition.parse.items?.selector).toBe('entries');
  });

  it('validates_scalar_pair_input', () => {
    const state = toGui(base)!;
    state.requestParams = [{ key: 'page', value: 'abc', type: 'number' }];
    expect(() => fromGui(state)).toThrow();
    state.requestParams = [{ key: 'flag', value: 'yes', type: 'boolean' }];
    expect(() => fromGui(state)).toThrow();
    state.requestParams = [{ key: 'flag', value: 'true', type: 'boolean' }];
    expect(fromGui(state).definition.request?.params).toEqual({ flag: true });
  });

  it('serializes_http_header_toggle', () => {
    const state = toGui(base)!;
    state.engineOptions = {};
    expect(fromGui(state).definition.engine).toBeUndefined();
    state.engineOptions.curl_default_headers = false;
    expect(fromGui(state).definition.engine).toEqual({
      type: 'http',
      options: { curl_default_headers: false },
    });
  });

  it('validates_browser_wait_options', () => {
    const state = toGui(base)!;
    state.engineType = 'browser';
    state.engineUrl = 'http://localhost:9222';
    state.engineOptions = { wait_for: { type: 'xpath' } };
    const emptyWait = fromGui(state);
    expect(emptyWait.definition.engine?.options.wait_for).toBeUndefined();

    state.engineOptions.wait_for = { expression: '.ready' };
    expect(fromGui(state).definition.engine?.options.wait_for).toEqual({
      type: 'css',
      expression: '.ready',
    });

    state.engineOptions.wait_for = { type: 'xpath', expression: '//main' };
    expect(fromGui(state).definition.engine?.options.wait_for).toEqual({
      type: 'xpath',
      expression: '//main',
    });

    state.engineOptions.wait_for = { type: 'regex', expression: 'main' };
    expect(() => fromGui(state)).toThrow();
    state.engineOptions = { wait_timeout: 301 };
    expect(() => fromGui(state)).toThrow();
  });

  it('clears_stale_state', () => {
    const state = defaultEditorState();
    state.requestBody = 'raw';
    state.requestBodyPairs = [{ key: 'field', value: 'value' }];
    state.engineUrl = 'http://old-endpoint';
    state.engineOptions = { impersonate: 'chrome', stale: true };
    expect(clearStaleFields(state)).toBeUndefined();
    expect(state.requestBody).toBe('');
    expect(state.requestBodyPairs).toEqual([]);
    expect(state.engineUrl).toBe('');
    expect(state.engineOptions).toEqual({ impersonate: 'chrome' });
  });

  it('accepts_canonical_import', () => {
    const imported = parseImportedDocument({
      _type: 'task_definition',
      _version: '2.0',
      ...structuredClone(base),
    });
    expect(imported.name).toBe(base.name);
    const record = imported as unknown as Record<string, unknown>;
    expect('_version' in record).toBe(false);
    expect('_type' in record).toBe(false);
    expect(analyzeTaskDefinition(imported)).toEqual([]);
    expect(toGui(imported)).not.toBeNull();
  });

  it('rejects_old_import_version', () => {
    expect(() => parseImportedDocument({ _type: 'task_definition', _version: '1.0' })).toThrow();
  });
});
