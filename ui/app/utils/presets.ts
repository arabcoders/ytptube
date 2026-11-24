import type { Preset } from '~/types/presets';
import { encode } from '~/utils';

export const MAX_PRESET_WORKERS = 1000;

export const isPresetWorkerLimit = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= MAX_PRESET_WORKERS;

export const exportPreset = (item: Preset): string => {
  const excludedKeys = ['id', 'default', 'raw', 'cookies', 'toggle_description'];
  const userData = Object.fromEntries(
    Object.entries(item).filter(
      ([key, value]) =>
        !excludedKeys.includes(key) && (value || (key === 'max_workers' && value === 0)),
    ),
  );

  return encode({ ...userData, _type: 'preset', _version: '2.6' });
};
