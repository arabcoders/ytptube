import { describe, expect, it } from 'bun:test';

import { DOCS_ENTRIES } from '~/composables/useDocs';
import {
  getActiveNavItem,
  getNavItems,
  getSearchNavItems,
  getSidebarSections,
  isNavItemActive,
} from '~/utils/topLevelNavigation';

describe('sidebar groups', () => {
  it('groups visible pages', () => {
    const sections = getSidebarSections({ fileLogging: false, consoleEnabled: false });

    expect(sections.map((section) => section.id)).toEqual([
      'downloads',
      'automation',
      'configuration',
      'tools',
      'docs',
    ]);
    expect(sections.every((section) => section.icon && section.items.length > 0)).toBe(true);
    expect(sections.flatMap((section) => section.items.map((item) => item.id))).toEqual(
      getNavItems({ fileLogging: false, consoleEnabled: false })
        .filter((entry) => entry.sidebarVisible)
        .map((entry) => entry.id),
    );
  });

  it('filters optional tools', () => {
    const tools = (fileLogging: boolean, consoleEnabled: boolean) =>
      getSidebarSections({ fileLogging, consoleEnabled })
        .find((section) => section.id === 'tools')!
        .items.map((entry) => entry.id);

    expect(tools(false, false)).not.toContain('logs');
    expect(tools(false, false)).not.toContain('console');
    expect(tools(true, false)).toContain('logs');
    expect(tools(true, false)).not.toContain('console');
    expect(tools(false, true)).not.toContain('logs');
    expect(tools(false, true)).toContain('console');
  });

  it('locates nested groups', () => {
    expect(getActiveNavItem({ path: '/tasks/12' })?.section).toBe('automation');
    expect(getActiveNavItem({ path: '/docs/native-builds' })?.section).toBe('docs');
    expect(
      getSidebarSections()
        .find((section) => section.id === 'docs')!
        .items.map((entry) => entry.id),
    ).not.toContain('docs-native-builds');
  });
});

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

describe('tools navigation', () => {
  it('routes limits page', () => {
    const limits = getNavItems().find((entry) => entry.id === 'limits');

    expect(limits).toMatchObject({
      section: 'tools',
      label: 'app.limits',
      pageLabel: 'app.downloadLimits',
      to: '/limits',
      matchPath: '/limits',
      sidebarVisible: true,
      searchable: true,
    });
    expect(isNavItemActive(limits!, { path: '/limits' })).toBe(true);
  });
});
