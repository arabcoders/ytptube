import { describe, expect, it } from 'bun:test';
import {
  buildYtdlpGroupItems,
  normalizeYtdlpGroupFilter,
  YTDLP_ALL_GROUPS,
} from '~/utils/ytdlpOptions';

describe('ytdlpOptions helpers', () => {
  it('uses a non-empty sentinel value for the all-groups option', () => {
    const items = buildYtdlpGroupItems(['root', 'video']);

    expect(items[0]).toEqual({ label: 'All groups', value: YTDLP_ALL_GROUPS });
    expect(items.every((item) => item.value !== '')).toBe(true);
  });

  it('normalizes the all-groups sentinel back to an empty filter', () => {
    expect(normalizeYtdlpGroupFilter(YTDLP_ALL_GROUPS)).toBe('');
    expect(normalizeYtdlpGroupFilter('root')).toBe('root');
  });
});
