import { describe, expect, it } from 'bun:test';

import { getDocsEntryBySlug, resolveDocsImageSrc, resolveDocsLink } from '~/composables/useDocs';

globalThis.window = {
  origin: 'http://localhost',
  location: { pathname: '/docs' },
} as Window & typeof globalThis;

describe('docs resolver', () => {
  it('distinguishes index and root readme', () => {
    expect(getDocsEntryBySlug()?.file).toBe('docs/README.md');
    expect(getDocsEntryBySlug('readme')?.file).toBe('README.md');
  });

  it('resolves relative docs links', () => {
    expect(resolveDocsLink('../README.md#quick-start', '/api/docs/docs/README.md').docRoute).toBe(
      '/docs/readme#quick-start',
    );
    expect(resolveDocsLink('task-definitions.md', '/api/docs/docs/README.md').docRoute).toBe(
      '/docs/task-definitions',
    );
    expect(resolveDocsLink('features.md', '/api/docs/docs/README.md').docRoute).toBe(
      '/docs/features',
    );
  });

  it('resolves assets and unknown links', () => {
    expect(resolveDocsImageSrc('../sc_short.jpg', '/api/docs/docs/README.md')).toBe(
      '/api/docs/sc_short.jpg',
    );
    expect(
      resolveDocsImageSrc(
        'https://raw.githubusercontent.com/ArabCoders/ytptube/dev/sc_short.jpg',
        '/api/docs/README.md',
      ),
    ).toBe('/api/docs/sc_short.jpg');
    expect(resolveDocsLink('../CONTRIBUTING.md', '/api/docs/docs/README.md').href).toBe(
      'https://github.com/arabcoders/ytptube/blob/dev/CONTRIBUTING.md',
    );
    expect(resolveDocsLink('#section', '/api/docs/docs/README.md').href).toBe('/docs#section');
  });
});
