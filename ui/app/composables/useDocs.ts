export type DocsFile = 'README.md' | 'FAQ.md' | 'API.md';

export type DocsEntry = {
  id: string;
  title: string;
  description: string;
  file: DocsFile;
  route: string;
  slug: string[];
  icon: string;
  navLabel: string;
};

const DOCS_ASSETS = ['sc_short.jpg', 'sc_simple.jpg'] as const;

const DOCS_ENTRIES: DocsEntry[] = [
  {
    id: 'readme',
    title: 'README',
    description: 'Project overview',
    file: 'README.md',
    route: '/docs/readme',
    slug: ['readme'],
    icon: 'i-lucide-book-open',
    navLabel: 'README',
  },
  {
    id: 'faq',
    title: 'FAQ',
    description: 'Answers for setup details, task handlers, and common issues.',
    file: 'FAQ.md',
    route: '/docs/faq',
    slug: ['faq'],
    icon: 'i-lucide-circle-help',
    navLabel: 'FAQ',
  },
  {
    id: 'docs-api',
    title: 'API',
    description: 'HTTP API reference and endpoint behavior.',
    file: 'API.md',
    route: '/docs/api',
    slug: ['api'],
    icon: 'i-lucide-code-xml',
    navLabel: 'API',
  },
];

const DOCS_ROUTE_BY_FILE = new Map(DOCS_ENTRIES.map((entry) => [entry.file, entry.route]));
const normalizeSlugParts = (slug?: string | string[]): string[] => {
  if (!slug) {
    return [];
  }

  return (Array.isArray(slug) ? slug : [slug])
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
};

const getDocsEntryBySlug = (slug?: string | string[]): DocsEntry | undefined => {
  const parts = normalizeSlugParts(slug);

  if (parts.length === 0) {
    return DOCS_ENTRIES[0];
  }

  const key = parts.join('/');

  if (key === 'readme') {
    return DOCS_ENTRIES[0];
  }

  return DOCS_ENTRIES.find((entry) => entry.slug.join('/') === key);
};

const getDocsNavigationEntries = () =>
  DOCS_ENTRIES.map((entry) => ({
    id: entry.id,
    label: entry.navLabel,
    icon: entry.icon,
    to: entry.route,
  }));

const extractKnownDocsTarget = (href: string): { name: string; hash: string } | undefined => {
  if (!href || href.startsWith('#')) {
    return undefined;
  }

  try {
    const parsed = new URL(href, window?.origin || 'http://localhost');
    const segments = parsed.pathname.split('/').filter(Boolean);
    const name = segments.at(-1) || '';

    if (
      DOCS_ROUTE_BY_FILE.has(name as DocsFile) ||
      DOCS_ASSETS.includes(name as (typeof DOCS_ASSETS)[number])
    ) {
      return { name, hash: parsed.hash || '' };
    }
  } catch {}

  return undefined;
};

const resolveDocsLink = (href: string): { href: string; external: boolean; docRoute?: string } => {
  if (!href) {
    return { href, external: false };
  }

  if (href.startsWith('#')) {
    const route = window?.location?.pathname || '';
    const currentRoute = `${route}${href}`;
    return { href: currentRoute, external: false, docRoute: currentRoute };
  }

  try {
    const parsed = new URL(href, window?.origin || 'http://localhost');
    const currentPath = window?.location?.pathname || '';

    if (
      parsed.origin === (window?.origin || parsed.origin) &&
      parsed.hash &&
      parsed.pathname === currentPath
    ) {
      const currentRoute = `${parsed.pathname}${parsed.hash}`;
      return { href: currentRoute, external: false, docRoute: currentRoute };
    }
  } catch {}

  const match = extractKnownDocsTarget(href);
  if (!match) {
    return { href, external: true };
  }

  const docsRoute = DOCS_ROUTE_BY_FILE.get(match.name as DocsFile);
  if (docsRoute) {
    const route = `${docsRoute}${match.hash}`;
    return {
      href: route,
      external: false,
      docRoute: route,
    };
  }

  return {
    href: `/api/docs/${match.name}`,
    external: false,
  };
};

const resolveDocsImageSrc = (href: string): string => {
  const match = extractKnownDocsTarget(href);
  if (!match) {
    return href;
  }

  if (DOCS_ASSETS.includes(match.name as (typeof DOCS_ASSETS)[number])) {
    return `/api/docs/${match.name}`;
  }

  return href;
};

export {
  DOCS_ENTRIES,
  getDocsEntryBySlug,
  getDocsNavigationEntries,
  resolveDocsImageSrc,
  resolveDocsLink,
};
