import { describe, expect, it } from 'bun:test';
import { getNavItems, getSearchNavItems } from '~/utils/topLevelNavigation';
import { getPath, makeDownload, sTrim } from '~/utils';
import type { ToolboxJob } from '~/types/toolbox';
import {
  isToolboxActive,
  toolboxOptionDefaults,
  toolboxOptionFields,
  toolboxShowMessage,
  toolboxStatusColor,
} from '~/utils/toolbox';

describe('toolbox options', () => {
  it('maps primitive fields', () => {
    const { fields, unsupported } = toolboxOptionFields({
      required: ['enabled', 'count'],
      properties: {
        title: { type: 'string', title: 'Output title', description: 'Stored title.', default: '' },
        notes: { type: 'string', format: 'textarea' },
        enabled: { type: 'boolean', default: false },
        count: { type: 'integer', minimum: 0, maximum: 10, default: 0 },
        gain: { type: 'number', multipleOf: 0.5 },
        ratio: { type: 'number' },
        optional: { type: 'boolean' },
      },
    });
    expect(unsupported).toEqual([]);
    expect(fields[0]).toMatchObject({
      name: 'title',
      label: 'Output title',
      description: 'Stored title.',
      type: 'string',
      required: false,
    });
    expect(fields.slice(1).map((field) => field.type)).toEqual([
      'text',
      'bool',
      'number',
      'number',
      'number',
      'bool',
    ]);
    expect(fields[3]).toMatchObject({ min: 0, max: 10, step: 1, required: true });
    expect(fields[4]?.step).toBe(0.5);
    expect(fields[5]?.step).toBe('any');
    expect(toolboxOptionDefaults(fields)).toEqual({ title: '', enabled: false, count: 0 });
  });

  it('resolves nullable enums', () => {
    const { fields, unsupported } = toolboxOptionFields({
      $defs: {
        Mode: { type: 'string', enum: ['copy', 'encode'], title: 'Mode' },
      },
      properties: {
        mode: { anyOf: [{ $ref: '#/$defs/Mode' }, { type: 'null' }], default: null },
        codec: { $ref: '#/$defs/Mode', title: 'Codec', default: 'copy' },
        level: { type: 'integer', enum: [0, 2], default: 0 },
        enabled: { type: 'boolean', enum: [true, false], default: false },
        gain: { anyOf: [{ type: 'number', minimum: -1 }, { type: 'null' }], default: null },
        flag: { anyOf: [{ type: 'boolean' }, { type: 'null' }], default: null },
      },
    });
    expect(unsupported).toEqual([]);
    expect(fields[0]).toMatchObject({ label: 'Mode', type: 'select', nullable: true });
    expect(fields[0]?.items).toEqual([
      { label: 'copy', value: 'copy' },
      { label: 'encode', value: 'encode' },
    ]);
    expect(fields[1]?.label).toBe('Codec');
    expect(fields[2]?.items?.map((item) => item.value)).toEqual([0, 2]);
    expect(fields[3]?.items?.map((item) => item.value)).toEqual([true, false]);
    expect(fields[4]).toMatchObject({ type: 'number', nullable: true, min: -1 });
    expect(fields[5]).toMatchObject({ type: 'select', nullable: true });
    expect(toolboxOptionDefaults(fields)).toEqual({
      mode: null,
      codec: 'copy',
      level: 0,
      enabled: false,
      gain: null,
      flag: null,
    });
  });

  it('reports unsupported options', () => {
    const { fields, unsupported } = toolboxOptionFields({
      properties: {
        streams: { type: 'array', items: { type: 'integer' } },
        metadata: { type: 'object', default: {} },
        mixed: { anyOf: [{ type: 'string' }, { type: 'integer' }] },
        remote: { $ref: 'https://example.test/schema' },
        mode: { type: 'string', default: 'copy' },
      },
    });
    expect(unsupported).toEqual(['streams', 'metadata', 'mixed', 'remote']);
    expect(toolboxOptionDefaults(fields)).toEqual({ mode: 'copy' });
  });

  it('initializes fresh drafts', () => {
    const first = toolboxOptionFields({
      required: ['enabled'],
      properties: { enabled: { type: 'boolean' }, mode: { type: 'string', default: 'copy' } },
    });
    let options = toolboxOptionDefaults(first.fields);
    expect(options).toEqual({ enabled: false, mode: 'copy' });
    options.mode = 'encode';
    options = toolboxOptionDefaults(toolboxOptionFields({}).fields);
    expect(options).toEqual({});
    options = toolboxOptionDefaults(first.fields);
    expect(options).toEqual({ enabled: false, mode: 'copy' });
  });
});

describe('toolbox statuses', () => {
  it('shows skip reason', () => {
    const t = (key: string) => `translated:${key}`;
    const skipped: ToolboxJob = {
      id: 1,
      tool: 'custom-copy',
      file: 'shows/episode.mp4',
      extra: { overwrite_source: true, options: {} },
      status: 'skipped',
      created_at: '2026-10-31T10:00:00Z',
      started_at: '2026-10-31T10:00:01Z',
      finished_at: '2026-10-31T10:00:02Z',
      progress: null,
      message: 'Skipped: the input already matches the target format.',
      result: null,
      error: null,
      error_code: null,
      log: '',
    };
    expect(isToolboxActive(skipped)).toBe(false);
    expect(toolboxStatusColor(skipped.status)).toBe('neutral');
    expect(toolboxShowMessage(skipped, t)).toBe(true);
    expect(toolboxShowMessage({ ...skipped, message: 'Skipped.' }, t)).toBe(false);
    expect(toolboxShowMessage({ ...skipped, message: 'translated:common.skipped!' }, t)).toBe(
      false,
    );
  });
});

describe('toolbox links', () => {
  it('uses download directory', () => {
    const filename = 'episode 50% + ? & 😀.mp4';
    expect(
      sTrim(
        getPath('/downloads', {
          folder: 'configured/folder',
          download_dir: '/downloads/shows/日本語 #1',
          filename,
        }),
        '/',
      ),
    ).toBe(`shows/日本語 #1/${filename}`);
    expect(
      sTrim(
        getPath('/downloads', {
          folder: 'configured/folder',
          download_dir: '/downloads',
          filename,
        }),
        '/',
      ),
    ).toBe(filename);
    expect(
      sTrim(
        getPath('/downloads', {
          folder: 'configured/folder',
          download_dir: 'shows/日本語 #1',
          filename,
        }),
        '/',
      ),
    ).toBe(`shows/日本語 #1/${filename}`);
    expect(sTrim(`/shows/日本語 #1/${filename}`, '/')).toBe(`shows/日本語 #1/${filename}`);
  });

  it('uses deployment base', () => {
    const original = globalThis.useRuntimeConfig;
    try {
      globalThis.useRuntimeConfig = (() => ({
        app: { baseURL: '/media/' },
      })) as typeof useRuntimeConfig;
      const output = sTrim(
        getPath('/downloads', {
          folder: 'configured/folder',
          download_dir: '/downloads/shows/日本語 #1',
          filename: 'episode 50% + ? & 😀.mp4',
        }),
        '/',
      );
      const download = new URL(makeDownload({}, { filename: output }), 'https://example.test');
      expect(decodeURIComponent(download.pathname)).toBe(`/media/api/download/${output}`);
      expect(download.search).toBe('');
      expect(download.hash).toBe('');
      globalThis.useRuntimeConfig = (() => ({ app: { baseURL: '/' } })) as typeof useRuntimeConfig;
      const rootDownload = new URL(makeDownload({}, { filename: output }), 'https://example.test');
      expect(decodeURIComponent(rootDownload.pathname)).toBe(`/api/download/${output}`);
      expect(rootDownload.search).toBe('');
      expect(rootDownload.hash).toBe('');
    } finally {
      globalThis.useRuntimeConfig = original;
    }
  });

  it('indexes toolbox navigation', () => {
    const toolbox = getNavItems().find((item) => item.id === 'toolbox');
    expect(toolbox).toMatchObject({ to: '/toolbox', section: 'tools', sidebarVisible: true });
    expect(getSearchNavItems()).toContainEqual(toolbox);
  });
});
