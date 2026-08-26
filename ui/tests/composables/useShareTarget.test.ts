import { describe, expect, it } from 'bun:test';

import { isShareTarget, parseShareUrls, removeShareQuery } from '~/composables/useShareTarget';

describe('share target', () => {
  it('requires_marker', () => {
    expect(isShareTarget({ share: '1' })).toBe(true);
    expect(isShareTarget({ url: 'https://example.com' })).toBe(false);
    expect(parseShareUrls({ url: 'https://example.com' })).toEqual([]);
  });

  it('parses_ordered_urls', () => {
    expect(
      parseShareUrls({
        share: '1',
        title: 'Watch https://example.com/a.',
        text: ['also https://example.com/b, and https://example.com/a'],
        url: 'javascript://no.example https://example.com/c)',
      }),
    ).toEqual(['https://example.com/a', 'https://example.com/b', 'https://example.com/c']);
  });

  it('removes_share_values', () => {
    expect(
      removeShareQuery({ share: '1', title: 'title', text: 'text', url: 'url', other: 'keep' }),
    ).toEqual({ other: 'keep' });
  });
});
