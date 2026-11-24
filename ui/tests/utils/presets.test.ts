import { expect, it } from 'bun:test';
import { decode } from '~/utils';
import { exportPreset, isPresetWorkerLimit } from '~/utils/presets';

it.each([0, 1, 1000])('exports valid limit %i', (max_workers) => {
  const exported = exportPreset({
    id: 7,
    name: 'example',
    description: '',
    folder: '',
    template: '',
    cookies: 'private',
    cli: '',
    default: false,
    priority: 0,
    max_workers,
  });

  const item = decode(exported);
  expect(item).toEqual({ _type: 'preset', _version: '2.6', name: 'example', max_workers });
  expect(isPresetWorkerLimit(max_workers)).toBe(true);
});

it.each([-1, 1.5, 1001, '2', null])('rejects invalid limit %s', (value) => {
  expect(isPresetWorkerLimit(value)).toBe(false);
});
