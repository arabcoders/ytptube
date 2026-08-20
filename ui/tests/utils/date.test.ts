import { describe, expect, it } from 'bun:test';
import {
  formatDateOnly,
  formatDateTime,
  formatLongDateTime,
  formatUtc,
  humanizeDuration,
  parseDate,
  toIsoString,
} from '~/utils/date';

describe('date', () => {
  it('parses_compact', () => {
    expect(formatDateOnly('20260811', 'en')).toBe('08/11/2026');
    expect(formatDateOnly('2026-08-11', 'en')).toBe('08/11/2026');
    expect(parseDate('20261340')).toBeNull();
  });

  it('formats_local', () => {
    const date = new Date(2026, 7, 11, 5, 6, 7);

    expect(formatDateTime(date, 'en', { seconds: true, timeZone: false })).toContain('08/11/2026');
    expect(formatLongDateTime(date, 'en')).toContain('August');
    expect(formatDateTime(date, 'ar-u-nu-arab', { seconds: true })).toMatch(/[٠-٩]/);
  });

  it('formats_utc', () => {
    const value = 1786449967;

    expect(formatUtc(value)).toBe('2026-08-11T12:06:07Z');
    expect(toIsoString(value)).toBe('2026-08-11T12:06:07.000Z');
  });

  it('humanizes_duration', () => {
    expect(humanizeDuration(44, 'en')).toBe('44 seconds');
    expect(humanizeDuration(45, 'en')).toBe('1 minute');
    expect(humanizeDuration(90, 'en')).toBe('2 minutes');
    expect(humanizeDuration(3600, 'en')).toBe('1 hour');
    expect(humanizeDuration(5400, 'en')).toBe('2 hours');
    expect(humanizeDuration(-5400, 'en')).toBe('2 hours');
    expect(humanizeDuration(90, 'ar')).toContain('دقيقت');
  });

  it('rejects_invalid', () => {
    expect(parseDate('invalid')).toBeNull();
    expect(formatDateTime('invalid', 'en')).toBe('');
  });
});
