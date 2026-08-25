import { describe, expect, it } from 'bun:test';

import { DOCS_ENTRIES } from '~/composables/useDocs';
import { getNavItems, getSearchNavItems, isNavItemActive } from '~/utils/topLevelNavigation';

describe('documentation navigation', () => {
  it('limits permanent links', () => {
    const visible = getNavItems()
      .filter((entry) => entry.section === 'docs' && entry.sidebarVisible)
      .map((entry) => entry.id);

    expect(visible).toEqual(['docs-index', 'docs-readme', 'docs-faq', 'docs-api', 'changelog']);
  });

  it('selects nested docs', () => {
    const active = getNavItems()
      .filter((entry) => entry.section === 'docs' && entry.sidebarVisible)
      .filter((entry) => isNavItemActive(entry, { path: '/docs/readme' }))
      .map((entry) => entry.id);

    expect(active).toEqual(['docs-readme']);

    const nativeActive = getNavItems()
      .filter((entry) => entry.section === 'docs' && entry.sidebarVisible)
      .filter((entry) => isNavItemActive(entry, { path: '/docs/native-builds' }))
      .map((entry) => entry.id);

    expect(nativeActive).not.toContain('docs-index');
  });

  it('indexes all docs', () => {
    const docs = getSearchNavItems().filter((entry) => entry.id.startsWith('docs-'));

    expect(docs.map((entry) => entry.id)).toEqual(DOCS_ENTRIES.map((entry) => entry.id));
    expect(docs.find((entry) => entry.id === 'docs-native-builds')).toMatchObject({
      searchable: true,
      sidebarVisible: false,
    });
  });
});
