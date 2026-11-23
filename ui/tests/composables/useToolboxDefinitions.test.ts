import { afterEach, beforeEach, describe, expect, it, spyOn } from 'bun:test';
import { useToolboxDefinitions } from '~/composables/useToolboxDefinitions';
import type { ToolboxDefinition, ToolboxDefinitionInput } from '~/types/toolbox';
import * as utils from '~/utils';
import {
  buildToolboxDefinition,
  exportToolboxDefinition,
  importToolboxDefinition,
  makeToolboxDraft,
} from '~/utils/toolboxDefinitions';

const draft: ToolboxDefinitionInput = {
  name: 'Copy media',
  description: '',
  output_extension: '.mkv',
  supports_overwrite: false,
  command: ['program', ' spaced argument ', '', '{input}', '{output}'],
  env: { LABEL: '  literal=value  \n', EMPTY: '' },
  params: {
    enabled: { default: false },
    count: { default: 0, min: 0, max: 10 },
    ratio: { default: 0.5, min: 0.25 },
    mode: { default: '', choices: [' spaced ', ''] },
  },
};
const custom: ToolboxDefinition = { ...draft, id: 42, default: false };
const builtIn: ToolboxDefinition = { ...draft, name: 'Shipped tool', id: 2, default: true };

describe('toolbox import and export', () => {
  it('round trips command defaults', () => {
    const exported = exportToolboxDefinition(custom);
    expect(exported).not.toBeNull();
    expect(utils.decode(exported!)).toEqual({
      ...draft,
      _type: 'toolbox_definition',
      _version: '1.0',
    });
    const imported = importToolboxDefinition(` ${exported} `);
    expect(imported).toEqual(draft);
    expect(buildToolboxDefinition(makeToolboxDraft(imported))).toEqual({ value: draft });
  });

  it('rejects wrong payload shapes', () => {
    expect(importToolboxDefinition('not an export')).toBeNull();
    expect(importToolboxDefinition(utils.encode({ ...draft, _type: 'preset' }))).toBeNull();
    expect(
      importToolboxDefinition(
        utils.encode({ ...draft, _type: 'toolbox_definition', command: 'program --output' }),
      ),
    ).toBeNull();
    expect(
      importToolboxDefinition(
        utils.encode({ ...draft, _type: 'toolbox_definition', env: { LEVEL: 1 } }),
      ),
    ).toBeNull();
    expect(
      importToolboxDefinition(
        utils.encode({ ...draft, _type: 'toolbox_definition', params: { enabled: {} } }),
      ),
    ).toBeNull();
  });

  it('rejects legacy tool IDs', () => {
    expect(
      importToolboxDefinition(
        utils.encode({ ...draft, _type: 'toolbox_definition', id: 'copy-media' }),
      ),
    ).toBeNull();
  });

  it('exports only custom tools', () => {
    expect(exportToolboxDefinition(builtIn)).toBeNull();
  });
});

describe('toolbox definition draft', () => {
  it('leaves rules to server', () => {
    const form = makeToolboxDraft(draft);
    form.name = '';
    form.output_extension = 'mp4';
    form.env.push({ key: 'TB_OUT', value: '' });
    form.params[1]!.min = 0.25;
    form.params[3]!.choices.push('');
    form.params[3]!.choice = undefined;
    const { value } = buildToolboxDefinition(form);
    expect(JSON.parse(JSON.stringify(value))).toMatchObject({
      name: '',
      output_extension: 'mp4',
      env: { TB_OUT: '' },
      params: { count: { default: 0, min: 0.25 } },
    });
    expect(JSON.parse(JSON.stringify(value?.params.mode))).toEqual({
      choices: [' spaced ', '', ''],
    });
  });

  it('preserves edited argument order', () => {
    const form = makeToolboxDraft(draft);
    form.args = ['{input}', '', ' spaced argument ', '{output}'];
    expect(buildToolboxDefinition(form).value?.command).toEqual(['program', ...form.args]);
  });

  it('prevents duplicate map keys', () => {
    const form = makeToolboxDraft(draft);
    form.env.push({ key: 'LABEL', value: 'another value' });
    expect(buildToolboxDefinition(form)).toEqual({
      duplicate: { key: 'LABEL', field: 'env.2.key' },
    });
    form.env.pop();
    form.params[1]!.name = 'enabled';
    expect(buildToolboxDefinition(form)).toEqual({
      duplicate: { key: 'enabled', field: 'params.1.name' },
    });
  });
});

describe('toolbox definition requests', () => {
  const api = useToolboxDefinitions();
  let requests: ReturnType<typeof spyOn<typeof utils, 'request'>>;

  beforeEach(() => {
    requests = spyOn(utils, 'request');
  });
  afterEach(() => {
    requests.mockRestore();
  });

  it('clones a shipped tool', async () => {
    requests.mockResolvedValueOnce(Response.json(builtIn));
    requests.mockResolvedValueOnce(Response.json(custom, { status: 201 }));
    const form = makeToolboxDraft(await api.get(builtIn.id));
    form.name = draft.name;
    const copy = buildToolboxDefinition(form);
    expect(copy.value).toEqual(draft);
    expect(await api.save(copy.value!)).toEqual(custom);
    expect(requests.mock.calls).toEqual([
      ['/api/toolbox/definitions/2', { timeout: 20 }],
      ['/api/toolbox/definitions', { method: 'POST', body: JSON.stringify(draft), timeout: 20 }],
    ]);
  });

  it('updates the original ID', async () => {
    requests.mockResolvedValueOnce(Response.json(custom));
    expect(await api.save(draft, custom.id)).toEqual(custom);
    expect(requests.mock.calls[0]).toEqual([
      '/api/toolbox/definitions/42',
      { method: 'PUT', body: JSON.stringify(draft), timeout: 20 },
    ]);
  });

  it('uses stored definition IDs', async () => {
    requests.mockResolvedValueOnce(Response.json(custom));
    requests.mockResolvedValueOnce(new Response(null, { status: 204 }));
    expect(await api.get(custom.id)).toEqual(custom);
    await api.remove(custom.id);
    expect(requests.mock.calls).toEqual([
      ['/api/toolbox/definitions/42', { timeout: 20 }],
      ['/api/toolbox/definitions/42', { method: 'DELETE', timeout: 20 }],
    ]);
  });

  it('lists custom tools', async () => {
    const data = {
      items: [{ id: 42, name: 'Copy media', description: '', default: false }],
      pagination: {
        page: 2,
        per_page: 50,
        total: 51,
        total_pages: 2,
        has_next: false,
        has_prev: true,
      },
    };
    requests.mockResolvedValueOnce(Response.json(data));
    expect(await api.list(2)).toEqual(data);
    expect(requests.mock.calls[0]?.[0]).toBe('/api/toolbox/definitions?page=2&per_page=50');
  });

  it('loads all import choices', async () => {
    const items = [
      { id: 42, name: 'Copy media', description: '', default: false },
      { id: 2, name: 'Shipped tool', description: '', default: true },
    ];
    for (const [index, item] of items.entries()) {
      requests.mockResolvedValueOnce(
        Response.json({
          items: [item],
          pagination: {
            page: index + 1,
            per_page: 1,
            total: 2,
            total_pages: 2,
            has_next: index === 0,
            has_prev: index > 0,
          },
        }),
      );
    }
    expect(await api.listForImport()).toEqual(items);
    expect(requests.mock.calls.map(([url]) => url)).toEqual([
      '/api/toolbox/definitions?page=1&per_page=50&include_defaults=true',
      '/api/toolbox/definitions?page=2&per_page=50&include_defaults=true',
    ]);
  });
});
