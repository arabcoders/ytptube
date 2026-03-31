<template>
  <div class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-2">
        <div class="flex flex-wrap items-center gap-2 text-sm text-toned">
          <nav aria-label="Breadcrumb" class="min-w-0">
            <ol class="flex flex-wrap items-center gap-1.5">
              <template v-for="(item, index) in breadcrumbItems" :key="item.path">
                <li v-if="index > 0" aria-hidden="true" class="text-muted">/</li>
                <li>
                  <a
                    v-if="index !== breadcrumbItems.length - 1"
                    :href="buildStateUrl(item.path)"
                    class="rounded px-1 py-0.5 text-left text-default hover:text-highlighted"
                    @click="handleBreadcrumbClick($event, item.path)"
                  >
                    {{ item.name }}
                  </a>
                  <span v-else class="rounded px-1 py-0.5 font-medium text-highlighted">
                    {{ item.name }}
                  </span>
                </li>
              </template>
            </ol>
          </nav>

          <UIcon
            v-if="isLoading"
            name="i-lucide-loader-circle"
            class="size-4 animate-spin text-info"
          />
        </div>

        <p class="text-sm text-toned">
          {{ browserPath }}
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="show_filter" class="relative w-full sm:w-72">
          <span
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-toned"
          >
            <UIcon name="i-lucide-filter" class="size-4" />
          </span>
          <input
            id="search"
            ref="searchInput"
            v-model.lazy="localSearch"
            type="search"
            placeholder="Filter"
            class="w-full rounded-md border border-default bg-elevated py-2 pr-3 pl-9 text-sm text-default outline-none transition focus:border-primary"
          />
        </div>

        <UButton
          color="neutral"
          :variant="show_filter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter"
        >
          <span v-if="!isMobile">Filter</span>
        </UButton>

        <UButton
          v-if="controlEnabled"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-folder-plus"
          @click="() => void handleCreateDirectory()"
        >
          <span v-if="!isMobile">New Folder</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          @click="toggleDisplayStyle"
        >
          <span v-if="!isMobile">{{ display_style === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UDropdownMenu v-if="hasItems" :items="sortGroups" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-arrow-up-down"
            trailing-icon="i-lucide-chevron-down"
          >
            <span v-if="!isMobile">Sort</span>
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
          <span v-if="!isMobile">Reload</span>
        </UButton>
      </div>
    </div>

    <div
      v-if="controlEnabled && hasItems"
      class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default bg-default px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-check'"
          :disabled="isLoading || filteredItems.length < 1"
          @click="masterSelectAll = !masterSelectAll"
        >
          {{ masterSelectAll ? 'Unselect' : 'Select' }}
        </UButton>

        <UBadge v-if="selectedElms.length > 0" color="error" variant="soft" size="sm">
          {{ selectedElms.length }}
        </UBadge>

        <UButton
          color="info"
          variant="outline"
          size="sm"
          icon="i-lucide-arrow-right-left"
          :disabled="!hasSelected || isLoading"
          @click="() => void handleMoveSelected()"
        >
          Move
        </UButton>

        <UButton
          color="error"
          variant="outline"
          size="sm"
          icon="i-lucide-trash"
          :disabled="!hasSelected || isLoading"
          @click="() => void handleDeleteSelected()"
        >
          Delete
        </UButton>
      </div>

      <p class="text-sm text-toned">
        Page {{ pagination.page }} of {{ pagination.total_pages || 1 }}
      </p>
    </div>

    <Pager
      v-if="pagination.total_pages > 1"
      :page="pagination.page"
      :last_page="pagination.total_pages"
      :isLoading="isLoading"
      @navigate="handlePageChange"
    />

    <div
      v-if="display_style === 'list' && hasItems"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-345 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th v-if="controlEnabled" class="w-16">Select</th>
              <th :class="controlEnabled ? 'w-20' : 'w-24'">
                #
                <UIcon
                  v-if="sort_by === 'type'"
                  :name="sortDirectionIcon"
                  class="ml-1 inline-flex size-3.5"
                />
              </th>
              <th class="text-left">
                Name
                <UIcon
                  v-if="sort_by === 'name'"
                  :name="sortDirectionIcon"
                  class="ml-1 inline-flex size-3.5"
                />
              </th>
              <th class="w-28 whitespace-nowrap">
                Size
                <UIcon
                  v-if="sort_by === 'size'"
                  :name="sortDirectionIcon"
                  class="ml-1 inline-flex size-3.5"
                />
              </th>
              <th class="w-40 whitespace-nowrap">
                Date
                <UIcon
                  v-if="sort_by === 'date'"
                  :name="sortDirectionIcon"
                  class="ml-1 inline-flex size-3.5"
                />
              </th>
              <th v-if="controlEnabled" class="w-80 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="item in filteredItems" :key="item.path" class="hover:bg-muted/20">
              <td v-if="controlEnabled" class="px-3 py-3 text-center align-middle">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedElms"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item.path"
                  />
                </label>
              </td>

              <td class="px-3 py-3 text-center align-middle">
                <UTooltip :text="item.name">
                  <span class="inline-flex items-center justify-center text-toned">
                    <UIcon :name="itemTypeIcon(item)" class="size-6" />
                  </span>
                </UTooltip>
              </td>

              <td class="px-3 py-3 align-middle">
                <div class="flex min-w-0 items-center justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <UTooltip :text="item.name">
                      <a
                        :href="itemHref(item)"
                        class="block truncate font-medium text-highlighted hover:underline"
                        @click.prevent="handleClick(item)"
                      >
                        {{ item.name }}
                      </a>
                    </UTooltip>
                  </div>

                  <UButton
                    v-if="item.type === 'file'"
                    color="info"
                    variant="ghost"
                    size="xs"
                    icon="i-lucide-download"
                    class="shrink-0"
                    external
                    :href="downloadHref(item)"
                    :download="downloadName(item)"
                    square
                  />
                </div>
              </td>

              <td class="px-3 py-3 text-center align-middle text-toned whitespace-nowrap">
                {{ itemSizeLabel(item) }}
              </td>

              <td class="px-3 py-3 text-center align-middle text-toned whitespace-nowrap">
                <UTooltip :text="moment(item.mtime).format('YYYY-MM-DD H:mm:ss Z')">
                  <span>{{ moment(item.mtime).fromNow() }}</span>
                </UTooltip>
              </td>

              <td v-if="controlEnabled" class="w-80 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="warning"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="() => void handleAction('rename', item)"
                  >
                    Rename
                  </UButton>

                  <UButton
                    color="info"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-arrow-right-left"
                    @click="() => void handleAction('move', item)"
                  >
                    Move
                  </UButton>

                  <UButton
                    color="error"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void handleAction('delete', item)"
                  >
                    Delete
                  </UButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="hasItems" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <UCard
        v-for="item in filteredItems"
        :key="item.path"
        class="flex h-full flex-col border bg-default"
        :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
      >
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex items-start gap-2">
                <span class="pt-0.5 text-toned">
                  <UIcon :name="itemTypeIcon(item)" class="size-5" />
                </span>

                <div class="min-w-0 flex-1">
                  <UTooltip :text="item.name">
                    <a
                      :href="itemHref(item)"
                      class="block truncate text-sm font-semibold text-highlighted hover:underline"
                      @click.prevent="handleClick(item)"
                    >
                      {{ item.name }}
                    </a>
                  </UTooltip>
                </div>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-1">
              <UButton
                v-if="item.type === 'file'"
                color="info"
                variant="ghost"
                size="xs"
                icon="i-lucide-download"
                external
                :href="downloadHref(item)"
                :download="downloadName(item)"
                square
              />

              <label v-if="controlEnabled" class="inline-flex cursor-pointer items-center px-1">
                <input
                  v-model="selectedElms"
                  class="completed-checkbox size-4 rounded border-default"
                  type="checkbox"
                  :value="item.path"
                />
              </label>
            </div>
          </div>
        </template>

        <div class="flex flex-wrap gap-2 text-sm *:min-w-32 *:flex-1">
          <div
            class="min-w-0 rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-default"
          >
            <span class="block truncate">{{ itemTypeLabel(item) }}</span>
          </div>

          <div
            class="min-w-0 rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-toned"
          >
            <span class="block truncate">{{ itemSizeLabel(item) }}</span>
          </div>

          <div
            class="min-w-0 rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-toned"
          >
            <UTooltip :text="moment(item.mtime).format('YYYY-MM-DD H:mm:ss Z')">
              <span class="block truncate">{{ moment(item.mtime).fromNow() }}</span>
            </UTooltip>
          </div>
        </div>

        <div v-if="controlEnabled" class="mt-auto flex flex-wrap gap-2 pt-1 *:min-w-32 *:flex-1">
          <UButton
            color="warning"
            variant="outline"
            size="sm"
            icon="i-lucide-pencil"
            class="w-full justify-center"
            @click="() => void handleAction('rename', item)"
          >
            Rename
          </UButton>

          <UButton
            color="info"
            variant="outline"
            size="sm"
            icon="i-lucide-arrow-right-left"
            class="w-full justify-center"
            @click="() => void handleAction('move', item)"
          >
            Move
          </UButton>

          <UButton
            color="error"
            variant="outline"
            size="sm"
            icon="i-lucide-trash"
            class="w-full justify-center"
            @click="() => void handleAction('delete', item)"
          >
            Delete
          </UButton>
        </div>
      </UCard>
    </div>

    <div v-if="localSearch && !hasItems && !isLoading" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-filter"
        title="No results"
        :description="`No results found for '${localSearch}'.`"
      />

      <UButton color="neutral" variant="outline" size="sm" @click="clearFilter"
        >Clear filter</UButton
      >
    </div>

    <UAlert
      v-else-if="isLoading && !hasItems"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading content"
      description="Loading file browser contents..."
    />

    <UAlert
      v-else-if="!hasItems"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No Content"
      description="Directory is empty."
    />

    <UAlert
      v-if="!controlEnabled"
      color="info"
      variant="soft"
      icon="i-lucide-info"
      title="File controls disabled"
      description="You can enable rename, delete, move, and create directory controls by setting YTP_BROWSER_CONTROL_ENABLED=true and restarting the application."
    />

    <Pager
      v-if="pagination.total_pages > 1"
      :page="pagination.page"
      :last_page="pagination.total_pages"
      :isLoading="isLoading"
      @navigate="handlePageChange"
    />

    <UModal
      v-if="model_item"
      :open="Boolean(model_item)"
      :title="previewTitle"
      :dismissible="true"
      :ui="previewModalUi"
      @update:open="(open) => !open && closeModel()"
    >
      <template #body>
        <VideoPlayer
          v-if="model_item?.type === 'video'"
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="model_item"
          class="w-full"
          @closeModel="closeModel"
        />

        <GetInfo
          v-else-if="model_item?.type === 'text'"
          :link="model_item.filename"
          :useUrl="true"
          :externalModel="true"
          @closeModel="closeModel"
        />

        <ImageView
          v-else-if="model_item?.type === 'image'"
          :link="model_item.filename"
          @closeModel="closeModel"
        />
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import type { DropdownMenuItem } from '@nuxt/ui';
import type { FileItem } from '~/types/filebrowser';

const route = useRoute();
const toast = useNotification();
const config = useConfigStore();
const dialog = useDialog();
const browser = useBrowser();
const isMobile = useMediaQuery({ maxWidth: 1024 });

const display_style = useStorage<string>('browser_display_style', 'list');
const show_filter = ref(false);
const localSearch = ref('');
const searchInput = ref<HTMLInputElement | null>(null);

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
const hasItems = computed(() => filteredItems.value.length > 0);
const hasSelected = computed(() => selectedElms.value.length > 0);
const displayedItemPaths = computed(() => filteredItems.value.map((item) => item.path));
const sortDirectionIcon = computed(() =>
  sort_order.value === 'asc' ? 'i-lucide-arrow-down' : 'i-lucide-arrow-up',
);

const sortOptions = [
  { value: 'type', label: 'Type', icon: 'i-lucide-hash' },
  { value: 'name', label: 'Name', icon: 'i-lucide-arrow-down-a-z' },
  { value: 'size', label: 'Size', icon: 'i-lucide-scale' },
  { value: 'date', label: 'Date', icon: 'i-lucide-calendar' },
];

const breadcrumbItems = computed(() => makeBreadCrumb(browserPath.value));

const sortGroups = computed<DropdownMenuItem[][]>(() => [
  sortOptions.map((option) => ({
    label:
      sort_by.value === option.value
        ? `${option.label} (${sort_order.value === 'asc' ? 'ASC' : 'DESC'})`
        : option.label,
    icon: option.icon,
    color: sort_by.value === option.value ? 'primary' : 'neutral',
    onSelect: () => void handleChangeSort(option.value),
  })),
]);

const initialPath = (() => {
  const slug = route.params.slug;
  if (Array.isArray(slug) && slug.length > 0) {
    return '/' + slug.join('/');
  }
  return '/';
})();

const isUpdating = ref(false);

const model_item = ref<any | null>(null);

const previewTitle = computed(() => {
  if (!model_item.value) {
    return '';
  }

  switch (model_item.value.type) {
    case 'video':
      return 'Preview';
    case 'text':
      return 'File Contents';
    case 'image':
      return 'Image Preview';
    default:
      return 'Preview';
  }
});

const previewModalUi = computed(() => {
  if (model_item.value?.type === 'video') {
    return { content: 'sm:max-w-5xl', body: 'p-0' };
  }

  if (model_item.value?.type === 'image') {
    return { content: 'sm:max-w-5xl', body: 'p-4' };
  }

  return { content: 'sm:max-w-4xl', body: 'p-0' };
});

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
  const basePath = normalizedDir ? `/browser/${normalizedDir}` : '/browser';
  return queryString ? `${basePath}?${queryString}` : basePath;
};

const syncFromUrl = (): { page: number } => {
  const query = route.query;
  const page = parseInt(query.page as string, 10) || 1;

  browser.setSortBy('name');
  browser.setSortOrder('asc');
  browser.setSearchValue('');
  localSearch.value = '';
  show_filter.value = false;

  if (query.sort_by && ['name', 'size', 'date', 'type'].includes(query.sort_by as string)) {
    browser.setSortBy(query.sort_by as string);
  }

  if (query.sort_order && ['asc', 'desc'].includes(query.sort_order as string)) {
    browser.setSortOrder(query.sort_order as string);
  }

  if (query.search && typeof query.search === 'string') {
    browser.setSearchValue(query.search);
    localSearch.value = query.search;
    show_filter.value = true;
  }

  return { page };
};

watch(masterSelectAll, (value) => {
  selectedElms.value = value ? [...displayedItemPaths.value] : [];
});

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
  model_item.value = null;
};

const clearFilter = (): void => {
  localSearch.value = '';
  show_filter.value = false;
};

const isPlainLeftClick = (event: MouseEvent): boolean => {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
};

const handleBreadcrumbClick = (event: MouseEvent, path: string): void => {
  if (!isPlainLeftClick(event)) {
    return;
  }

  event.preventDefault();
  void reloadContent(path);
};

const itemHref = (item: FileItem): string => {
  return item.content_type === 'dir' ? uri(`/browser/${item.path}`) : downloadHref(item);
};

const downloadHref = (item: FileItem): string => {
  return makeDownload({}, { filename: item.path, folder: '' });
};

const downloadName = (item: FileItem): string => {
  return item.name.split('/').reverse()[0] || item.name;
};

const itemSizeLabel = (item: FileItem): string => {
  return item.type === 'file' ? formatBytes(item.size) : ucFirst(item.type);
};

const updateUrl = (dir: string, page?: number): void => {
  const normalizedDir = dir.replace(/^\/+/, '').replace(/\/+$/, '');
  const displayDir = normalizedDir ? normalizedDir : '/';
  const title = `File Browser: /${sTrim(displayDir, '/')}`;
  const stateUrl = buildStateUrl(dir, page);
  const fullUrl = window.location.origin + stateUrl;

  if (fullUrl !== window.location.href) {
    history.replaceState({ path: normalizedDir || '/', title }, title, stateUrl);
  }

  useHead({ title: decodeURIComponent(title) });
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
      name: 'Home',
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
    return 'Link';
  }

  if (item.content_type === 'dir') {
    return 'Folder';
  }

  if (['video', 'audio', 'text', 'subtitle', 'metadata', 'image'].includes(item.content_type)) {
    return ucFirst(item.content_type);
  }

  return item.type === 'file' ? 'File' : ucFirst(item.type);
};

const escapeHtml = (value: string): string => {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
};

const toggleFilter = async (): Promise<void> => {
  show_filter.value = !show_filter.value;

  if (!show_filter.value) {
    clearFilter();
    return;
  }

  await nextTick();
  searchInput.value?.focus();
};

const toggleDisplayStyle = (): void => {
  display_style.value = display_style.value === 'list' ? 'grid' : 'list';
};

const handleCreateDirectory = async (): Promise<void> => {
  if (!controlEnabled.value) {
    return;
  }

  const { status, value: newDir } = await dialog.promptDialog({
    title: 'Create New Directory',
    message: `Enter name for new directory in '${browserPath.value || '/'}':`,
    initial: '',
    confirmText: 'Create',
    cancelText: 'Cancel',
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
    const moveSideCars = item.type === 'file' ? ' (and its sidecars)' : '';
    const { status, value: newName } = await dialog.promptDialog({
      title: 'Rename Item',
      message: `Enter new name for '${item.name}'${moveSideCars}:`,
      initial: item.name,
      confirmText: 'Rename',
      cancelText: 'Cancel',
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
      ? `Delete '${item.name}' and all its contents?`
      : `Delete file '${item.name}'?`;

    const { status } = await dialog.confirmDialog({
      title: 'Delete Confirmation',
      message,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      confirmColor: 'error',
    });

    if (status !== true) {
      return;
    }

    await browser.deleteItem(item);
    return;
  }

  if (action === 'move') {
    const moveSideCars = item.type === 'file' ? ' (and its sidecars)' : '';
    const { status, value: newPath } = await dialog.promptDialog({
      title: 'Move Item',
      message: `Enter new path for '${item.name}'${moveSideCars}:`,
      initial: item.path.replace(/[^/]+$/, '') || '/',
      confirmText: 'Move',
      cancelText: 'Cancel',
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
    toast.error('No items selected.');
    return;
  }

  const rawHTML =
    '<ul>' +
    selectedElms.value
      .map((selectedPath) => {
        const item = items.value.find((entry) => entry.path === selectedPath);
        if (!item) {
          return '';
        }

        return `<li><strong>${escapeHtml(itemTypeLabel(item))}:</strong> ${escapeHtml(item.name)}</li>`;
      })
      .join('') +
    '</ul>';

  const { status } = await dialog.confirmDialog({
    title: 'Delete Confirmation',
    message: 'Delete the following items?',
    rawHTML,
    confirmText: 'Delete',
    cancelText: 'Cancel',
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
    toast.error('No items selected.');
    return;
  }

  const { status, value: newPath } = await dialog.promptDialog({
    title: 'Move Items',
    message: 'Enter new path for selected items:',
    initial: browserPath.value || '/',
    confirmText: 'Move',
    confirmColor: 'error',
    cancelText: 'Cancel',
  });

  if (status !== true || !newPath || newPath === browserPath.value) {
    selectedElms.value = [];
    return;
  }

  await browser.moveSelected(newPath);
};
</script>
