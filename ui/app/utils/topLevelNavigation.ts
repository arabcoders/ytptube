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
  { id: 'downloads', label: 'common.downloads' },
  { id: 'automation', label: 'app.nav.sections.automation' },
  { id: 'configuration', label: 'app.nav.sections.configuration' },
  { id: 'tools', label: 'app.nav.sections.tools' },
  { id: 'docs', label: 'app.nav.sections.docs' },
];

const NavItems: Array<NavDefinition> = [
  {
    id: 'downloads',
    section: 'downloads',
    group: 'workspace',
    label: 'common.queue',
    pageLabel: 'common.queue',
    breadcrumbSectionLabel: 'app.nav.breadcrumbs.workspace',
    description: 'queue.description',
    icon: 'i-lucide-download',
    to: '/',
    matchPath: '/',
  },
  {
    id: 'history',
    section: 'downloads',
    group: 'workspace',
    label: 'common.history',
    pageLabel: 'common.history',
    breadcrumbSectionLabel: 'app.nav.breadcrumbs.workspace',
    description: 'history.description',
    icon: 'i-lucide-history',
    to: '/history',
    matchPath: '/history',
    navbarTitle: 'common.downloads',
  },
  {
    id: 'files',
    section: 'downloads',
    group: 'workspace',
    label: 'app.nav.labels.files',
    pageLabel: 'app.nav.labels.files',
    breadcrumbSectionLabel: 'app.nav.breadcrumbs.workspace',
    description: 'files.description',
    icon: 'i-lucide-folder-tree',
    to: '/browser',
    matchPath: '/browser',
  },
  {
    id: 'tasks',
    section: 'automation',
    group: 'automation',
    label: 'app.nav.labels.tasks',
    pageLabel: 'app.nav.labels.tasks',
    description: 'tasks.description',
    icon: 'i-lucide-list-todo',
    to: '/tasks',
    matchPath: '/tasks',
  },
  {
    id: 'task-definitions',
    section: 'automation',
    group: 'automation',
    label: 'app.nav.labels.taskDefinitions',
    pageLabel: 'app.nav.labels.taskDefinitions',
    description: 'taskDefinitions.description',
    icon: 'i-lucide-workflow',
    to: '/task_definitions',
    matchPath: '/task_definitions',
  },
  {
    id: 'presets',
    section: 'configuration',
    group: 'configuration',
    label: 'common.presets',
    pageLabel: 'common.presets',
    description: 'presets.description',
    icon: 'i-lucide-sliders-horizontal',
    to: '/presets',
    matchPath: '/presets',
  },
  {
    id: 'custom-fields',
    section: 'configuration',
    group: 'configuration',
    label: 'common.customFieldsAction',
    pageLabel: 'common.customFieldsAction',
    description: 'customFields.description',
    icon: 'i-lucide-braces',
    to: '/dl_fields',
    matchPath: '/dl_fields',
  },
  {
    id: 'conditions',
    section: 'configuration',
    group: 'configuration',
    label: 'app.nav.labels.conditions',
    pageLabel: 'app.nav.labels.conditions',
    description: 'conditions.description',
    icon: 'i-lucide-filter',
    to: '/conditions',
    matchPath: '/conditions',
  },
  {
    id: 'notifications',
    section: 'configuration',
    group: 'configuration',
    label: 'common.notifications',
    pageLabel: 'common.notifications',
    description: 'notificationsPage.description',
    icon: 'i-lucide-bell',
    to: '/notifications',
    matchPath: '/notifications',
  },
  {
    id: 'logs',
    section: 'tools',
    group: 'tools',
    label: 'app.nav.labels.logs',
    pageLabel: 'app.nav.labels.logs',
    description: 'logs.description',
    icon: 'i-lucide-file-text',
    to: '/logs',
    matchPath: '/logs',
    requires: 'file_logging',
  },
  {
    id: 'console',
    section: 'tools',
    group: 'tools',
    label: 'app.nav.labels.console',
    pageLabel: 'app.nav.labels.console',
    description: 'console.description',
    icon: 'i-lucide-terminal',
    to: '/console',
    matchPath: '/console',
    requires: 'console_enabled',
  },
  {
    id: 'status',
    section: 'tools',
    group: 'tools',
    label: 'common.status',
    pageLabel: 'common.status',
    description: 'status.description',
    icon: 'i-lucide-activity',
    to: '/status',
    matchPath: '/status',
  },
  {
    id: 'diagnostics',
    section: 'tools',
    group: 'tools',
    label: 'app.nav.labels.diagnostics',
    pageLabel: 'app.nav.labels.diagnostics',
    description: 'diagnostics.description',
    icon: 'i-lucide-stethoscope',
    to: '/diagnostics',
    matchPath: '/diagnostics',
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
    label: 'app.nav.labels.changelog',
    pageLabel: 'app.nav.labels.changelog',
    description: 'changelog.description',
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
