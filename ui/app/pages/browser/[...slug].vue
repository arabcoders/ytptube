<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div
      class="ytp-lights-out"
      :class="lightsOut ? 'opacity-100' : 'opacity-0'"
      aria-hidden="true"
    />

    <PageHeader
      v-bind="pageShell"
      :page-label="currentDirectoryName"
      description=""
      class="[&_h1]:wrap-anywhere"
    >
      <template #icon>
        <UIcon
          :name="pageShell.icon"
          class="size-5"
          :class="isLoading ? 'animate-pulse text-info' : ''"
          role="img"
          :aria-label="isLoading ? t('common.loading') : pageShell.pageLabel"
        />
      </template>
      <template #actions>
        <UButton
          color="neutral"
          :variant="show_filter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter"
        >
          <span>{{ t('common.filter') }}</span>
        </UButton>

        <UButton
          v-if="controlEnabled"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-folder-plus"
          @click="() => void handleCreateDirectory()"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UDropdownMenu v-if="hasItems" :items="sortGroups" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            :icon="sortDirectionIcon"
            trailing-icon="i-lucide-chevron-down"
          >
            <span
              >{{ t('common.sort') }}:
              {{ sortOptions.find((option) => option.value === sort_by)?.label }}</span
            >
          </UButton>
        </UDropdownMenu>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => void reloadContent(browserPath)"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>

        <UInput
          v-if="show_filter"
          id="search"
          ref="searchInput"
          v-model.lazy="localSearch"
          type="search"
          :placeholder="t('common.filter')"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </template>
    </PageHeader>

    <nav
      :aria-label="t('common.breadcrumb')"
      class="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm text-toned"
    >
      <span>{{ pageShell.pageLabel }}</span>
      <span aria-hidden="true">/</span>
      <template v-for="item in breadcrumbTrailItems" :key="item.path">
        <button
          type="button"
          class="max-w-full wrap-anywhere text-start hover:text-primary hover:underline"
          @click="() => void handleBreadcrumbClick(item.path)"
        >
          <bdi>{{ item.name }}</bdi>
        </button>
        <span aria-hidden="true">/</span>
      </template>
      <span class="wrap-anywhere font-medium text-highlighted" aria-current="page"
        ><bdi>{{ currentDirectoryName }}</bdi></span
      >
    </nav>

    <div
      v-if="controlEnabled && hasItems"
      class="flex flex-wrap items-center justify-between gap-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="masterSelectAll ? 'i-lucide-square-check-big' : 'i-lucide-square'"
          :disabled="isLoading || filteredItems.length < 1"
          @click="toggleMasterSelection"
        >
          {{ masterSelectAll ? t('common.unselect') : t('common.select') }}
        </UButton>

        <UBadge v-if="selectedElms.length > 0" color="error" variant="soft" size="sm">
          {{ selectedElms.length }}
        </UBadge>

        <UDropdownMenu :items="bulkActionGroups" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-list"
            trailing-icon="i-lucide-chevron-down"
          >
            {{ t('common.actions') }}
          </UButton>
        </UDropdownMenu>
      </div>

      <UPagination
        v-if="pagination.total_pages > 1"
        :page="pagination.page"
        :total="pagination.total"
        :items-per-page="pagination.per_page"
        :disabled="isLoading"
        show-edges
        :sibling-count="0"
        @update:page="handlePageChange"
        size="sm"
      />
    </div>

    <div
      v-if="hasItems"
      :aria-busy="isLoading"
      class="ytp-card divide-y divide-default xl:grid xl:grid-cols-[minmax(0,1fr)_25rem_auto] xl:gap-x-4"
    >
      <article
        v-for="item in filteredItems"
        :key="item.path"
        class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 p-4 xl:col-span-3 xl:grid-cols-subgrid xl:items-center"
      >
        <div class="flex min-w-0 items-center gap-3">
          <UCheckbox
            v-if="controlEnabled"
            color="primary"
            class="shrink-0"
            :model-value="selectedElms.includes(item.path)"
            :aria-label="`${t('common.select')}: ${item.name}`"
            @update:model-value="selectedElms = setSelected(selectedElms, item.path, $event)"
          />
          <span
            class="inline-flex size-8 shrink-0 items-center justify-center rounded-md border border-default bg-elevated/40 text-toned"
          >
            <UIcon :name="itemTypeIcon(item)" class="size-4" aria-hidden="true" />
          </span>
          <a
            :href="itemHref(item)"
            class="min-w-0 wrap-anywhere text-sm font-semibold text-highlighted hover:text-primary hover:underline"
            @click.prevent="handleClick(item)"
          >
            <bdi>{{ item.name }}</bdi>
          </a>
        </div>

        <dl
          class="col-span-2 grid min-w-0 grid-cols-2 gap-3 text-sm sm:grid-cols-3 xl:col-span-1 xl:col-start-2 xl:row-start-1"
        >
          <div class="min-w-0 space-y-1">
            <dt class="text-xs text-muted">{{ t('common.type') }}</dt>
            <dd>
              <UBadge color="neutral" variant="soft" size="sm">{{ itemTypeLabel(item) }}</UBadge>
            </dd>
          </div>
          <div class="min-w-0 space-y-1">
            <dt class="text-xs text-muted">{{ t('common.size') }}</dt>
            <dd class="tabular-nums text-toned">{{ itemSizeLabel(item) }}</dd>
          </div>
          <div class="col-span-2 min-w-0 space-y-1 sm:col-span-1">
            <dt class="text-xs text-muted">{{ t('common.date') }}</dt>
            <dd class="text-toned">
              <UTooltip :text="formatDateTime(item.mtime, locale, { seconds: true })">
                <time :datetime="item.mtime">{{ relativeTime(item.mtime) }}</time>
              </UTooltip>
            </dd>
          </div>
        </dl>

        <div
          v-if="controlEnabled || item.type === 'file' || item.is_file"
          class="col-start-2 row-start-1 flex shrink-0 items-center justify-end gap-1.5 self-start xl:col-start-3 xl:self-center"
        >
          <UTooltip v-if="item.type === 'file' || item.is_file" :text="t('common.download')">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-download"
              external
              :href="downloadHref(item)"
              :download="downloadName(item)"
              :aria-label="`${t('common.download')}: ${item.name}`"
            >
              <span>{{ t('common.download') }}</span>
            </UButton>
          </UTooltip>
          <UTooltip
            v-else-if="controlEnabled && item.content_type === 'dir'"
            :text="t('files.move')"
          >
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-arrow-right-left"
              :aria-label="`${t('files.move')}: ${item.name}`"
              @click="() => void handleAction('move', item)"
            >
              <span>{{ t('files.move') }}</span>
            </UButton>
          </UTooltip>
          <UDropdownMenu
            v-if="controlEnabled || item.is_file"
            :items="itemActionGroups(item)"
            :modal="false"
            :content="{ align: 'end' }"
          >
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              icon="i-lucide-ellipsis"
              square
              :aria-label="`${t('common.actions')}: ${item.name}`"
            />
          </UDropdownMenu>
        </div>
      </article>
    </div>

    <div v-if="localSearch && !hasItems && !isLoading">
      <UEmpty
        size="sm"
        icon="i-lucide-filter"
        :title="t('common.noResults')"
        :description="t('files.noResultsFor', { query: localSearch })"
      />
    </div>

    <UAlert
      v-else-if="isLoading && !hasItems"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('files.loading')"
      :description="t('files.loadingDesc')"
      :ui="{ icon: 'animate-spin' }"
    />

    <UEmpty
      v-else-if="!hasItems"
      icon="i-lucide-folder-open"
      :title="t('files.noContent')"
      :description="t('files.empty')"
      size="sm"
    />

    <UAlert
      v-if="!controlEnabled"
      color="info"
      variant="soft"
      icon="i-lucide-info"
      :title="t('files.controlsDisabled')"
      :description="t('files.controlsDisabledDesc')"
    />

    <div v-if="pagination.total_pages > 1" class="flex justify-end">
      <UPagination
        :page="pagination.page"
        :total="pagination.total"
        :items-per-page="pagination.per_page"
        :disabled="isLoading"
        show-edges
        :sibling-count="0"
        @update:page="handlePageChange"
        size="sm"
      />
    </div>

    <UModal
      v-if="model_item && model_item.type !== 'text'"
      :open="previewOpen"
      :title="previewTitle"
      :dismissible="true"
      :ui="previewModalUi"
      @update:open="handlePreviewOpenChange"
    >
      <template #body>
        <LazyVideoPlayer
          v-if="model_item?.type === 'video'"
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="model_item"
          class="w-full"
          @closeModel="() => void requestClosePreview()"
          @playback-state-change="(playing: boolean) => (playingNow = playing)"
        />

        <ImageView
          v-else-if="model_item?.type === 'image'"
          :link="model_item.filename"
          @closeModel="closeModel"
        />
      </template>
    </UModal>

    <ToolboxCreateModal
      v-if="toolboxSource !== null"
      :file="toolboxSource"
      @close="toolboxSource = null"
      @created="showToolboxJob"
    />
    <ToolboxJobModal v-if="toolboxJob" :id="toolboxJob" @close="toolboxJob = null" />

    <LazyGetInfo
      v-if="model_item?.type === 'text'"
      :link="model_item.filename"
      :useUrl="true"
      @closeModel="closeModel"
    />
  </main>
</template>

<script setup lang="ts">
import ToolboxCreateModal from '~/components/ToolboxCreateModal.vue';
import ToolboxJobModal from '~/components/ToolboxJobModal.vue';
import type { DropdownMenuItem } from '@nuxt/ui';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import type { FileItem } from '~/types/filebrowser';
import { formatPageTitle } from '~/utils';
import { formatRelativeTime, type RelativeTimeInput } from '~/utils/relativeTime';
import { formatDateTime } from '~/utils/date';
import { usePageShell } from '~/composables/usePageShell';
import type { ToolboxJob } from '~/types/toolbox';
import { setSelected } from '~/utils/selection';
const { locale, t } = useI18n();

const route = useRoute();
const toast = useNotification();
const config = useYtpConfig();
const dialog = useDialog();
const browser = useBrowser();
const toolboxSource = ref<string | null>(null);
const toolboxJob = ref<number | null>(null);
const showToolboxJob = (job: ToolboxJob): void => {
  toolboxSource.value = null;
  toolboxJob.value = job.id;
};

const relativeTime = (value: RelativeTimeInput): string => formatRelativeTime(value, locale.value);
const show_filter = ref(false);
const localSearch = ref('');
const searchInput = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);

const items = browser.items;
const browserPath = browser.path;
const pagination = browser.pagination;
const isLoading = browser.isLoading;
const selectedElms = browser.selectedElms;
const masterSelectAll = browser.masterSelectAll;
const sort_by = browser.sort_by;
const sort_order = browser.sort_order;
const filteredItems = browser.filteredItems;

const controlEnabled = computed(() => Boolean(config.app.browser_control_enabled));
const pageShell = usePageShell('files');
const hasItems = computed(() => filteredItems.value.length > 0);
const hasSelected = computed(() => selectedElms.value.length > 0);
const displayedItemPaths = computed(() => filteredItems.value.map((item) => item.path));
const browserPageTitle = computed(() =>
  t('files.pageTitle', { path: sTrim(browserPath.value || '/', '/') }),
);
const currentDirectoryName = computed(
  () => breadcrumbItems.value[breadcrumbItems.value.length - 1]?.name || t('common.home'),
);
const breadcrumbTrailItems = computed(() => breadcrumbItems.value.slice(0, -1));
const sortDirectionIcon = computed(() =>
  sort_order.value === 'asc' ? 'i-lucide-arrow-down' : 'i-lucide-arrow-up',
);

const sortOptions = computed(() => [
  { value: 'type', label: t('common.type'), icon: 'i-lucide-hash' },
  { value: 'name', label: t('common.name'), icon: 'i-lucide-arrow-down-a-z' },
  { value: 'size', label: t('common.size'), icon: 'i-lucide-scale' },
  { value: 'date', label: t('common.date'), icon: 'i-lucide-calendar' },
]);

const breadcrumbItems = computed(() => makeBreadCrumb(browserPath.value));

const sortGroups = computed<DropdownMenuItem[][]>(() => [
  sortOptions.value.map((option) => ({
    label:
      sort_by.value === option.value
        ? `${option.label} (${sort_order.value === 'asc' ? 'ASC' : 'DESC'})`
        : option.label,
    icon: option.icon,
    color: sort_by.value === option.value ? 'primary' : 'neutral',
    onSelect: () => void handleChangeSort(option.value),
  })),
]);

const bulkActionGroups = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: t('common.moveSelected'),
      icon: 'i-lucide-arrow-right-left',
      color: 'primary',
      disabled: !hasSelected.value || isLoading.value,
      onSelect: () => void handleMoveSelected(),
    },
    {
      label: t('common.deleteSelected'),
      icon: 'i-lucide-trash',
      disabled: !hasSelected.value || isLoading.value,
      onSelect: () => void handleDeleteSelected(),
    },
  ],
]);

const itemActionGroups = (item: FileItem): DropdownMenuItem[][] => {
  const actions: DropdownMenuItem[] = [];

  if (item.is_file) {
    actions.push({
      label: t('toolbox.title'),
      icon: 'i-lucide-wrench',
      onSelect: () => {
        toolboxSource.value = item.path;
      },
    });
  }

  if (controlEnabled.value) {
    actions.push({
      label: t('common.rename'),
      icon: 'i-lucide-pencil',
      onSelect: () => void handleAction('rename', item),
    });
  }

  if (controlEnabled.value && item.content_type !== 'dir') {
    actions.push({
      label: t('files.move'),
      icon: 'i-lucide-arrow-right-left',
      onSelect: () => void handleAction('move', item),
    });
  }

  const groups = actions.length ? [actions] : [];
  if (controlEnabled.value) {
    groups.push([
      {
        label: t('common.delete'),
        icon: 'i-lucide-trash',
        color: 'error',
        onSelect: () => void handleAction('delete', item),
      },
    ]);
  }

  return groups;
};

const initialPath = (() => {
  const slug = route.params.slug;
  if (Array.isArray(slug) && slug.length > 0) {
    return '/' + slug.join('/');
  }
  return '/';
})();

const isUpdating = ref(false);

const model_item = ref<any | null>(null);
const playingNow = ref(false);
const previewOpen = computed<boolean>({
  get: () => Boolean(model_item.value),
  set: (value: boolean) => {
    if (value) {
      return;
    }

    closeModel();
  },
});

const previewTitle = computed(() => {
  if (!model_item.value) {
    return '';
  }

  switch (model_item.value.type) {
    case 'video':
      return t('files.preview');
    case 'text':
      return t('common.fileContents');
    case 'image':
      return t('common.imagePreviewAlt');
    default:
      return t('files.preview');
  }
});

const previewModalUi = computed(() => {
  if (model_item.value?.type === 'video') {
    return {
      content: lightsOut.value ? 'sm:max-w-5xl shadow-2xl' : 'sm:max-w-5xl',
      body: 'p-0',
    };
  }

  if (model_item.value?.type === 'image') {
    return { content: 'sm:max-w-5xl', body: 'p-4' };
  }

  return { content: 'sm:max-w-4xl', body: 'p-0' };
});
const lightsOut = computed(() => Boolean(model_item.value?.type === 'video' && playingNow.value));

const buildStateUrl = (dir: string, page?: number): string => {
  const params = new URLSearchParams();
  const p = page ?? pagination.value.page;
  if (p > 1) {
    params.set('page', String(p));
  }
  if (sort_by.value !== 'name') {
    params.set('sort_by', sort_by.value);
  }
  if (sort_order.value !== 'asc') {
    params.set('sort_order', sort_order.value);
  }
  if (localSearch.value) {
    params.set('search', localSearch.value);
  }

  const queryString = params.toString();
  const normalizedDir = dir.replace(/^\/+/, '').replace(/\/+$/, '');
  const basePath = normalizedDir ? `/browser/${encodePath(normalizedDir)}` : '/browser';
  return queryString ? `${basePath}?${queryString}` : basePath;
};

const syncFromUrl = (): { page: number } => {
  const query = route.query;
  const page = parseInt(query.page as string, 10) || 1;

  browser.restoreSort(query.sort_by, query.sort_order);
  browser.setSearchValue('');
  localSearch.value = '';
  show_filter.value = false;

  if (query.search && typeof query.search === 'string') {
    browser.setSearchValue(query.search);
    localSearch.value = query.search;
    show_filter.value = true;
  }

  return { page };
};

watch(
  displayedItemPaths,
  (paths) => {
    if (!masterSelectAll.value) {
      return;
    }

    selectedElms.value = [...paths];
  },
  { immediate: true },
);

watch(selectedElms, (value) => {
  const paths = displayedItemPaths.value;
  masterSelectAll.value = paths.length > 0 && paths.every((path) => value.includes(path));
});

watch(localSearch, async (value) => {
  if (isUpdating.value) {
    return;
  }

  await browser.setSearch(value);
  updateUrl(browserPath.value, 1);
});

const closeModel = (): void => {
  playingNow.value = false;
  model_item.value = null;
};

const { handleOpenChange: handlePreviewOpenChange, requestClose: requestClosePreview } =
  useDirtyCloseGuard(previewOpen, {
    dirty: computed(() => Boolean(model_item.value?.type === 'video' && playingNow.value)),
    preferenceKey: 'player',
    title: t('common.closePlayer'),
    message: t('common.closePlayerDesc'),
    confirmText: t('common.closePlayer'),
    cancelText: t('common.keepPlaying'),
    onDiscard: async () => {
      closeModel();
    },
  });

const clearFilter = (): void => {
  localSearch.value = '';
  browser.setSearchValue('');
  show_filter.value = false;
};

const handleBreadcrumbClick = async (path: string): Promise<void> => {
  clearFilter();
  await reloadContent(path);
};

const itemHref = (item: FileItem): string => {
  return item.content_type === 'dir'
    ? uri(`/browser/${encodePath(item.path)}`)
    : downloadHref(item);
};

const downloadHref = (item: FileItem): string => {
  return makeDownload({}, { filename: item.path, folder: '' });
};

const downloadName = (item: FileItem): string => {
  return item.name.split('/').reverse()[0] || item.name;
};

const itemSizeLabel = (item: FileItem): string => {
  return item.type === 'file' ? formatBytes(item.size, 2, t) : itemTypeLabel(item);
};

useHead(() => ({
  title: formatPageTitle(decodeURIComponent(browserPageTitle.value)),
}));

const updateUrl = (dir: string, page?: number): void => {
  const normalizedDir = dir.replace(/^\/+/, '').replace(/\/+$/, '');
  const displayDir = normalizedDir ? normalizedDir : '/';
  const title = t('files.pageTitle', { path: sTrim(displayDir, '/') });
  const stateUrl = buildStateUrl(dir, page);
  const fullUrl = window.location.origin + stateUrl;

  if (fullUrl !== window.location.href) {
    history.replaceState({ path: normalizedDir || '/', title }, title, stateUrl);
  }
};

const handleClick = (item: FileItem): void => {
  if (['video', 'audio'].includes(item.content_type)) {
    model_item.value = {
      type: 'video',
      filename: item.path,
      folder: '',
      extras: {},
    };
    return;
  }

  if (['text', 'subtitle', 'metadata'].includes(item.content_type)) {
    model_item.value = {
      type: 'text',
      filename: makeDownload(config, { filename: item.path }),
      folder: '',
      extras: {},
    };
    return;
  }

  if (item.content_type === 'image') {
    model_item.value = {
      type: 'image',
      filename: makeDownload(config, { filename: item.path }),
      folder: '',
      extras: {},
    };
    return;
  }

  if (item.content_type === 'dir') {
    if (localSearch.value) {
      clearFilter();
    }

    void reloadContent(item.path);
    return;
  }

  window.location.href = makeDownload(config, { filename: item.path, folder: '', extras: {} });
};

const reloadContent = async (dir: string = '/', fromMounted: boolean = false): Promise<void> => {
  isUpdating.value = true;

  try {
    const page = fromMounted ? syncFromUrl().page : 1;
    const success = await browser.loadContents(dir, page);

    if (fromMounted && !success) {
      return;
    }

    updateUrl(dir, page);
  } finally {
    isUpdating.value = false;
  }
};

const handlePageChange = async (page: number): Promise<void> => {
  await browser.changePage(page);
  updateUrl(browserPath.value, page);
};

const handleChangeSort = async (by: string): Promise<void> => {
  await browser.changeSort(by);
  updateUrl(browserPath.value, 1);
};

const event_handler = (event: PopStateEvent): void => {
  if (!event.state) {
    return;
  }

  void reloadContent(event.state.path, true);
};

onMounted(async () => {
  window.addEventListener('popstate', event_handler);
  await reloadContent(initialPath, true);
});

onBeforeUnmount(() => window.removeEventListener('popstate', event_handler));

const makeBreadCrumb = (path: string): { name: string; link: string; path: string }[] => {
  const baseLink = '/';
  const normalizedPath = path.replace(/^\/+/, '').replace(/\/+$/, '');
  const links = [
    {
      name: t('common.home'),
      link: baseLink,
      path: baseLink,
    },
  ];

  if (!normalizedPath) {
    return links;
  }

  const parts = normalizedPath.split('/').filter(Boolean);
  parts.forEach((part, index) => {
    const nextPath = baseLink + parts.slice(0, index + 1).join('/');
    links.push({
      name: part,
      link: nextPath,
      path: nextPath,
    });
  });

  return links;
};

const itemTypeIcon = (item: FileItem): string => {
  if (item.type === 'link') {
    return 'i-lucide-link';
  }

  if (item.content_type === 'dir') {
    return 'i-lucide-folder';
  }

  if (['video', 'audio'].includes(item.content_type)) {
    return 'i-lucide-film';
  }

  if (['text', 'subtitle', 'metadata'].includes(item.content_type)) {
    return 'i-lucide-file-text';
  }

  if (item.content_type === 'image') {
    return 'i-lucide-image';
  }

  return 'i-lucide-file';
};

const itemTypeLabel = (item: FileItem): string => {
  if (item.type === 'link') {
    return t('files.link');
  }

  if (item.content_type === 'dir') {
    return t('files.folder');
  }

  if (['video', 'audio', 'text', 'subtitle', 'metadata', 'image'].includes(item.content_type)) {
    return t(`files.${item.content_type}`);
  }

  return item.type === 'file' ? t('common.file') : t('files.link');
};

const toggleFilter = async (): Promise<void> => {
  show_filter.value = !show_filter.value;

  if (!show_filter.value) {
    clearFilter();
    return;
  }

  await nextTick();
  searchInput.value?.inputRef?.value?.focus?.({ preventScroll: true });
};

const toggleMasterSelection = (): void => {
  if (masterSelectAll.value) {
    selectedElms.value = [];
    masterSelectAll.value = false;
    return;
  }

  selectedElms.value = [...displayedItemPaths.value];
  masterSelectAll.value = true;
};

const handleCreateDirectory = async (): Promise<void> => {
  if (!controlEnabled.value) {
    return;
  }

  const { status, value: newDir } = await dialog.promptDialog({
    title: t('files.createDir'),
    message: t('files.createDirDesc', { path: browserPath.value || '/' }),
    confirmText: t('files.create'),
    cancelText: t('common.cancel'),
  });

  if (status !== true || !newDir) {
    return;
  }

  const success = await browser.createDirectory(browserPath.value, newDir);
  if (success) {
    await reloadContent(browserPath.value, true);
  }
};

const handleAction = async (action: string, item: FileItem): Promise<void> => {
  if (!controlEnabled.value) {
    return;
  }

  if (action === 'rename') {
    const { status, value: newName } = await dialog.promptDialog({
      title: t('common.rename'),
      message: t('files.renameItemDesc', { name: item.name }),
      initial: item.name,
      confirmText: t('common.rename'),
      cancelText: t('common.cancel'),
    });

    if (status !== true) {
      return;
    }

    const success = await browser.renameItem(item, newName);
    if (success) {
      await reloadContent(browserPath.value, true);
    }
    return;
  }

  if (action === 'delete') {
    const message = item.is_dir
      ? t('files.deleteItemDesc', { name: item.name })
      : t('files.deleteFileDesc', { name: item.name });

    const { status } = await dialog.confirmDialog({
      title: t('common.deleteConfirmation'),
      message,
      confirmText: t('common.delete'),
      cancelText: t('common.cancel'),
      confirmColor: 'error',
    });

    if (status !== true) {
      return;
    }

    await browser.deleteItem(item);
    return;
  }

  if (action === 'move') {
    const { status, value: newPath } = await dialog.promptDialog({
      title: t('files.moveItem'),
      message: t('files.moveItemDesc', { name: item.name }),
      initial: item.path.replace(/[^/]+$/, '') || '/',
      confirmText: t('files.move'),
      cancelText: t('common.cancel'),
    });

    if (status !== true) {
      return;
    }

    const success = await browser.moveItem(item, newPath);
    if (success) {
      await reloadContent(browserPath.value, true);
    }
  }
};

const handleDeleteSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noItemsSelected'));
    return;
  }

  const message =
    t('files.deleteItemsConfirm') +
    '\n\n' +
    selectedElms.value
      .map((selectedPath) => {
        const item = items.value.find((entry) => entry.path === selectedPath);
        if (!item) {
          return '';
        }

        return `${itemTypeLabel(item)}: ${item.name}`;
      })
      .filter(Boolean)
      .join('\n');

  const { status } = await dialog.confirmDialog({
    title: t('common.deleteConfirmation'),
    message,
    confirmText: t('common.delete'),
    cancelText: t('common.cancel'),
    confirmColor: 'error',
  });

  if (status !== true) {
    selectedElms.value = [];
    return;
  }

  await browser.deleteSelected();
};

const handleMoveSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noItemsSelected'));
    return;
  }

  const { status, value: newPath } = await dialog.promptDialog({
    title: t('files.moveItems'),
    message: t('files.moveItemsDesc'),
    initial: browserPath.value || '/',
    confirmText: t('files.move'),
    confirmColor: 'error',
    cancelText: t('common.cancel'),
  });

  if (status !== true || !newPath || newPath === browserPath.value) {
    selectedElms.value = [];
    return;
  }

  await browser.moveSelected(newPath);
};
</script>
