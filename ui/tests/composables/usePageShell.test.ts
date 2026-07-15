import { describe, expect, it } from 'bun:test';

let locale = 'en';

globalThis.useI18n = () => ({
  locale: {
    get value() {
      return locale;
    },
  },
  t: (key: string) => `${locale}:${key}`,
});

const { usePageShell } = await import('~/composables/usePageShell');

describe('usePageShell', () => {
  it('updates_locale', () => {
    locale = 'en';
    const shell = usePageShell('downloads');

    expect(shell.pageLabel).toBe('en:common.queue');
    expect(shell.description).toBe('en:queue.description');

    locale = 'ar';

    expect(shell.pageLabel).toBe('ar:common.queue');
    expect(shell.description).toBe('ar:queue.description');
  });
});
