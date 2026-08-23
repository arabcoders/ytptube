import { describe, expect, it } from 'bun:test';

import { getNavItems, isNavItemActive } from '~/utils/topLevelNavigation';

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
  });
});
