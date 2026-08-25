export type DocsFile =
  | 'README.md'
  | 'FAQ.md'
  | 'API.md'
  | 'SECURITY.md'
  | 'docs/README.md'
  | 'docs/features.md'
  | 'docs/native-builds.md'
  | 'docs/task-definitions.md';

export type DocsEntry = {
  id: string;
  title: string;
  description: string;
  file: DocsFile;
  route: string;
  slug: string[];
  icon: string;
  navLabel: string;
  sidebarVisible: boolean;
};

const DOCS_ASSETS = ['sc_short.jpg', 'sc_simple.jpg'] as const;
const RAW_ASSET_PATH = 'ArabCoders/ytptube/dev/';
const DOCS_ENTRIES: DocsEntry[] = [
  {
    id: 'docs-index',
    title: 'docs.entries.index.title',
    description: 'docs.entries.index.description',
    file: 'docs/README.md',
    route: '/docs',
    slug: [],
    icon: 'i-lucide-book-open',
    navLabel: 'docs.entries.index.navLabel',
    sidebarVisible: true,
  },
  {
    id: 'docs-readme',
    title: 'docs.entries.readme.title',
    description: 'docs.entries.readme.description',
    file: 'README.md',
    route: '/docs/readme',
    slug: ['readme'],
    icon: 'i-lucide-book-open',
    navLabel: 'docs.entries.readme.navLabel',
    sidebarVisible: true,
  },
  {
    id: 'docs-features',
    title: 'docs.entries.features.title',
    description: 'docs.entries.features.description',
    file: 'docs/features.md',
    route: '/docs/features',
    slug: ['features'],
    icon: 'i-lucide-list-checks',
    navLabel: 'docs.entries.features.navLabel',
    sidebarVisible: false,
  },
  {
    id: 'docs-native-builds',
    title: 'docs.entries.nativeBuilds.title',
    description: 'docs.entries.nativeBuilds.description',
    file: 'docs/native-builds.md',
    route: '/docs/native-builds',
    slug: ['native-builds'],
    icon: 'i-lucide-download',
    navLabel: 'docs.entries.nativeBuilds.navLabel',
    sidebarVisible: false,
  },
  {
    id: 'docs-faq',
    title: 'docs.entries.faq.title',
    description: 'docs.entries.faq.description',
    file: 'FAQ.md',
    route: '/docs/faq',
    slug: ['faq'],
    icon: 'i-lucide-circle-help',
    navLabel: 'docs.entries.faq.navLabel',
    sidebarVisible: true,
  },
  {
    id: 'docs-api',
    title: 'docs.entries.api.title',
    description: 'docs.entries.api.description',
    file: 'API.md',
    route: '/docs/api',
    slug: ['api'],
    icon: 'i-lucide-code-xml',
    navLabel: 'docs.entries.api.navLabel',
    sidebarVisible: true,
  },
  {
    id: 'docs-security',
    title: 'docs.entries.security.title',
    description: 'docs.entries.security.description',
    file: 'SECURITY.md',
    route: '/docs/security',
    slug: ['security'],
    icon: 'i-lucide-shield-check',
    navLabel: 'docs.entries.security.navLabel',
    sidebarVisible: false,
  },
  {
    id: 'docs-task-definitions',
    title: 'docs.entries.taskDefinitions.title',
    description: 'docs.entries.taskDefinitions.description',
    file: 'docs/task-definitions.md',
    route: '/docs/task-definitions',
    slug: ['task-definitions'],
    icon: 'i-lucide-list-tree',
    navLabel: 'docs.entries.taskDefinitions.navLabel',
    sidebarVisible: false,
  },
];

const DOCS_BY_FILE = new Map(DOCS_ENTRIES.map((entry) => [entry.file, entry]));
const GITHUB_DOCS = 'https://github.com/arabcoders/ytptube/blob/dev/';
const RESOLVER_ORIGIN = 'https://ytptube.local';

const normalizeSlugParts = (slug?: string | string[]): string[] =>
  (Array.isArray(slug) ? slug : slug ? [slug] : [])
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);

const getDocsEntryBySlug = (slug?: string | string[]): DocsEntry | undefined => {
  const key = normalizeSlugParts(slug).join('/');
  return DOCS_ENTRIES.find((entry) => entry.slug.join('/') === key);
};

const getSourcePath = (source?: string): string =>
  source?.replace(/^\/api\/docs\//, '').replace(/^\//, '') || 'README.md';

const resolveSourceUrl = (href: string, source?: string): URL =>
  new URL(href, `${RESOLVER_ORIGIN}/${getSourcePath(source)}`);

const resolveDocsLink = (
  href: string,
  source?: string,
): { href: string; external: boolean; docRoute?: string } => {
  if (!href) {
    return { href, external: false };
  }

  if (href.startsWith('#')) {
    const route = `${window.location.pathname}${href}`;
    return { href: route, external: false, docRoute: route };
  }

  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(href)) {
    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin) {
      return { href, external: true };
    }

    const entry = DOCS_ENTRIES.find((item) => item.route === url.pathname);
    if (!entry) {
      return { href, external: true };
    }

    const route = `${entry.route}${url.hash}`;
    return { href: route, external: false, docRoute: route };
  }

  const url = resolveSourceUrl(href, source);
  const path = url.pathname.slice(1);
  const entry = DOCS_BY_FILE.get(path as DocsFile);
  if (entry) {
    const route = `${entry.route}${url.hash}`;
    return { href: route, external: false, docRoute: route };
  }

  if (DOCS_ASSETS.includes(path as (typeof DOCS_ASSETS)[number])) {
    return { href: `/api/docs/${path}`, external: false };
  }

  return {
    href: `${GITHUB_DOCS}${path}${url.search}${url.hash}`,
    external: true,
  };
};

const resolveDocsImageSrc = (href: string, source?: string): string => {
  const url = resolveSourceUrl(href, source);
  const path = url.pathname.slice(1);
  const asset =
    url.origin === 'https://raw.githubusercontent.com' && path.startsWith(RAW_ASSET_PATH)
      ? path.slice(RAW_ASSET_PATH.length)
      : path;

  return DOCS_ASSETS.includes(asset as (typeof DOCS_ASSETS)[number]) ? `/api/docs/${asset}` : href;
};

export { DOCS_ENTRIES, getDocsEntryBySlug, resolveDocsImageSrc, resolveDocsLink };
