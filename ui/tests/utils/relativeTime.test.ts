import { describe, expect, it } from 'bun:test';
import { formatRelativeTime } from '~/utils/relativeTime';

describe('relativeTime', () => {
  it('formats_arabic', () => {
    const value = new Date(Date.now() - 60 * 1000);

    expect(formatRelativeTime(value, 'ar')).toContain('دقيقة');
  });

  it('formats_english', () => {
    const value = new Date(Date.now() - 60 * 1000);

    expect(formatRelativeTime(value, 'en')).toContain('minute');
  });
});
