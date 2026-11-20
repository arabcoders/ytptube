import { describe, expect, it } from 'bun:test';

import {
  DOCS_ENTRIES,
  getDocsEntryBySlug,
  getDocsGroups,
  resolveDocsImageSrc,
  resolveDocsLink,
} from '~/composables/useDocs';

describe('docs resolver', () => {
  it('groups every guide', () => {
    const groups = getDocsGroups();
    const entries = groups.flatMap((group) => group.entries);

    expect(groups.map((group) => group.id)).toEqual(['start', 'guides', 'reference']);
    expect(entries.map((entry) => entry.id).sort()).toEqual(
      DOCS_ENTRIES.filter((entry) => entry.id !== 'docs-index')
        .map((entry) => entry.id)
        .sort(),
    );
    for (const entry of entries) {
      expect(getDocsEntryBySlug(entry.slug)?.route).toBe(entry.route);
    }
  });

  it('distinguishes index and root readme', () => {
    expect(getDocsEntryBySlug()?.file).toBe('docs/README.md');
    expect(getDocsEntryBySlug('readme')?.file).toBe('README.md');
    expect(getDocsEntryBySlug('native-builds')?.file).toBe('docs/native-builds.md');
    expect(getDocsEntryBySlug('authentication')?.file).toBe('docs/authentication.md');
    expect(getDocsEntryBySlug('authentication')?.sidebarVisible).toBe(false);
    expect(getDocsEntryBySlug('media-handlers')?.file).toBe('docs/media-handlers.md');
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
    expect(resolveDocsLink('media-handlers.md', '/api/docs/docs/README.md').docRoute).toBe(
      '/docs/media-handlers',
    );
    expect(resolveDocsLink('docs/media-handlers.md', '/api/docs/FAQ.md').docRoute).toBe(
      '/docs/media-handlers',
    );
    expect(resolveDocsLink('docs/media-handlers.md#setup', '/api/docs/README.md').docRoute).toBe(
      '/docs/media-handlers#setup',
    );
    expect(resolveDocsLink('native-builds.md', '/api/docs/docs/README.md').docRoute).toBe(
      '/docs/native-builds',
    );
    expect(resolveDocsLink('docs/authentication.md', '/api/docs/FAQ.md').docRoute).toBe(
      '/docs/authentication',
    );
    expect(resolveDocsLink('docs/authentication.md', '/api/docs/API.md').docRoute).toBe(
      '/docs/authentication',
    );
  });

  it('opens contribution links locally', () => {
    expect(resolveDocsLink('CONTRIBUTING.md', '/api/docs/README.md')).toEqual({
      href: '/docs/contributing',
      external: false,
      docRoute: '/docs/contributing',
    });
    expect(resolveDocsLink('../CONTRIBUTING.md', '/api/docs/docs/README.md').docRoute).toBe(
      '/docs/contributing',
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
    expect(resolveDocsLink('../LICENSE', '/api/docs/docs/README.md').href).toBe(
      'https://github.com/arabcoders/ytptube/blob/dev/LICENSE',
    );
    expect(resolveDocsLink('#section', '/api/docs/docs/README.md').href).toBe('/#section');
  });
});
