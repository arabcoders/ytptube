import { DOCS_ENTRIES } from '~/composables/useDocs';

export type SectionId = 'downloads' | 'automation' | 'configuration' | 'tools' | 'docs';

type NavSection = {
  id: SectionId;
  label: string;
};

type NavDefinition = {
  id: string;
  section: SectionId;
  group: string;
  label: string;
  pageLabel?: string;
  breadcrumbSectionLabel?: string;
  description: string;
  icon: string;
  to: string;
  matchPath?: string;
  sidebarVisible?: boolean;
  searchable?: boolean;
  navbarTitle?: string;
  requires?: 'file_logging' | 'console_enabled';
};

export type NavItem = NavDefinition & {
  sectionLabel: string;
  pageLabel: string;
  matchPath: string;
  sidebarVisible: boolean;
  searchable: boolean;
};

export type PageShell = {
  icon: string;
  sectionLabel: string;
  pageLabel: string;
  description: string;
};

type LocationPath = {
  path: string;
  hash?: string;
};

type NavAvailability = {
  fileLogging?: boolean;
  consoleEnabled?: boolean;
};

const SECTIONS: Array<NavSection> = [
  { id: 'downloads', label: 'Downloads' },
  { id: 'automation', label: 'Automation' },
  { id: 'configuration', label: 'Configuration' },
  { id: 'tools', label: 'Tools' },
  { id: 'docs', label: 'Docs' },
];

const NavItems: Array<NavDefinition> = [
  {
    id: 'downloads',
    section: 'downloads',
    group: 'workspace',
    label: 'Queue',
    pageLabel: 'Queue',
    breadcrumbSectionLabel: 'Workspace',
    description: 'Active and queued downloads.',
    icon: 'i-lucide-download',
    to: '/',
    matchPath: '/',
  },
  {
    id: 'history',
    section: 'downloads',
    group: 'workspace',
    label: 'History',
    pageLabel: 'History',
    breadcrumbSectionLabel: 'Workspace',
    description: 'Completed, skipped, and failed downloads.',
    icon: 'i-lucide-history',
    to: '/history',
    matchPath: '/history',
    navbarTitle: 'Downloads',
  },
  {
    id: 'files',
    section: 'downloads',
    group: 'workspace',
    label: 'Files',
    pageLabel: 'Files',
    breadcrumbSectionLabel: 'Workspace',
    description: 'Browse downloaded files.',
    icon: 'i-lucide-folder-tree',
    to: '/browser',
    matchPath: '/browser',
  },
  {
    id: 'tasks',
    section: 'automation',
    group: 'automation',
    label: 'Tasks',
    pageLabel: 'Tasks',
    description: 'Queue playlist/channels for automatic download at specified intervals.',
    icon: 'i-lucide-list-todo',
    to: '/tasks',
    matchPath: '/tasks',
  },
  {
    id: 'task-definitions',
    section: 'automation',
    group: 'automation',
    label: 'Task Definitions',
    pageLabel: 'Task Definitions',
    description: 'Create definitions to turn any website into a downloadable feed of links.',
    icon: 'i-lucide-workflow',
    to: '/task_definitions',
    matchPath: '/task_definitions',
  },
  {
    id: 'presets',
    section: 'configuration',
    group: 'configuration',
    label: 'Presets',
    pageLabel: 'Presets',
    description:
      'Presets are pre-defined command options for yt-dlp that you want to apply to given download.',
    icon: 'i-lucide-sliders-horizontal',
    to: '/presets',
    matchPath: '/presets',
  },
  {
    id: 'custom-fields',
    section: 'configuration',
    group: 'configuration',
    label: 'Custom Fields',
    pageLabel: 'Custom Fields',
    description: 'Custom fields allow you to add new fields to the download form.',
    icon: 'i-lucide-braces',
    to: '/dl_fields',
    matchPath: '/dl_fields',
  },
  {
    id: 'conditions',
    section: 'configuration',
    group: 'configuration',
    label: 'Conditions',
    pageLabel: 'Conditions',
    description: 'Run yt-dlp custom match filter on returned info and apply options.',
    icon: 'i-lucide-filter',
    to: '/conditions',
    matchPath: '/conditions',
  },
  {
    id: 'notifications',
    section: 'configuration',
    group: 'configuration',
    label: 'Notifications',
    pageLabel: 'Notifications',
    description: 'Send notifications to your webhooks based on specified events or presets.',
    icon: 'i-lucide-bell',
    to: '/notifications',
    matchPath: '/notifications',
  },
  {
    id: 'logs',
    section: 'tools',
    group: 'tools',
    label: 'Logs',
    pageLabel: 'Logs',
    description: 'Scroll near the top to load older logs.',
    icon: 'i-lucide-file-text',
    to: '/logs',
    matchPath: '/logs',
    requires: 'file_logging',
  },
  {
    id: 'console',
    section: 'tools',
    group: 'tools',
    label: 'Console',
    pageLabel: 'Console',
    description: 'Run yt-dlp commands directly in a non-interactive session.',
    icon: 'i-lucide-terminal',
    to: '/console',
    matchPath: '/console',
    requires: 'console_enabled',
  },
  ...DOCS_ENTRIES.map<NavDefinition>((entry) => ({
    id: entry.id,
    section: 'docs',
    group: 'docs',
    label: entry.navLabel,
    pageLabel: entry.title,
    description: entry.description,
    icon: entry.icon,
    to: entry.route,
    matchPath: entry.route,
  })),
  {
    id: 'changelog',
    section: 'docs',
    group: 'docs',
    label: 'Changelog',
    pageLabel: 'Changelog',
    description:
      'Latest project changes, loaded remotely when available and falling back to the bundled changelog file.',
    icon: 'i-lucide-git-commit-horizontal',
    to: '/changelog',
    matchPath: '/changelog',
  },
];

const normalizePath = (value?: string | null): string => {
  if (!value || value === '/') {
    return '/';
  }

  const trimmed = value.replace(/\/+$/, '');
  return trimmed === '' ? '/' : trimmed;
};

const getSectionLabel = (sectionId: SectionId): string => {
  const section = SECTIONS.find((item) => item.id === sectionId);
  return section?.label ?? sectionId;
};

const resolveEntry = (entry: NavDefinition): NavItem => ({
  ...entry,
  sectionLabel: getSectionLabel(entry.section),
  pageLabel: entry.pageLabel ?? entry.label,
  matchPath: normalizePath(entry.matchPath ?? (entry.to.split(/[?#]/)[0] || '/')),
  sidebarVisible: entry.sidebarVisible !== false,
  searchable: entry.searchable !== false,
});

const resolvedNavigation = NavItems.map((entry) => resolveEntry(entry));

const matchesAvailability = (entry: NavItem, options: NavAvailability): boolean => {
  switch (entry.requires) {
    case 'file_logging':
      return options.fileLogging === true;

    case 'console_enabled':
      return options.consoleEnabled === true;

    default:
      return true;
  }
};

export const getNavItems = (options?: NavAvailability): Array<NavItem> => {
  if (!options) {
    return resolvedNavigation;
  }

  return resolvedNavigation.filter((entry) => matchesAvailability(entry, options));
};

export const getNavSections = (): Array<NavSection> => {
  return SECTIONS;
};

export const getNavItemById = (id: string): NavItem | undefined => {
  return resolvedNavigation.find((entry) => entry.id === id);
};

export const isNavItemActive = (entry: NavItem, route: LocationPath): boolean => {
  const current = normalizePath(route.path);
  const target = normalizePath(entry.matchPath);

  if (target === '/') {
    return current === '/';
  }

  return current === target || current.startsWith(`${target}/`);
};

export const getActiveNavItem = (
  route: LocationPath,
  options?: NavAvailability,
): NavItem | undefined => {
  return getNavItems(options)
    .filter((entry) => isNavItemActive(entry, route))
    .sort((left, right) => right.matchPath.length - left.matchPath.length)[0];
};

export const getPageShell = (id: string): PageShell | undefined => {
  const entry = getNavItemById(id);
  if (!entry) {
    return undefined;
  }

  return {
    icon: entry.icon,
    sectionLabel: entry.breadcrumbSectionLabel ?? entry.sectionLabel,
    pageLabel: entry.pageLabel,
    description: entry.description,
  };
};

export const requirePageShell = (id: string): PageShell => {
  const shell = getPageShell(id);

  if (!shell) {
    throw new Error(`Missing top-level navigation shell for '${id}'`);
  }

  return shell;
};
