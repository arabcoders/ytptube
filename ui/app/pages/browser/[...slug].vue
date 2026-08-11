<template>
  <div class="w-full min-w-0 max-w-full space-y-6">
    <div
      class="pointer-events-none fixed inset-0 z-20 bg-black/45 backdrop-blur-[1px] transition-all duration-500 ease-out"
      :class="lightsOut ? 'opacity-100' : 'opacity-0'"
      aria-hidden="true"
    />

    <div class="ytp-page-header">
      <div class="ytp-page-heading">
        <span class="ytp-page-icon">
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 flex-1 space-y-3">
          <nav :aria-label="t('common.breadcrumb')" class="min-w-0 ytp-page-kicker">
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>

            <template v-for="item in breadcrumbTrailItems" :key="item.path">
              <span>/</span>

              <button
                type="button"
                class="max-w-full truncate normal-case tracking-normal transition hover:text-highlighted"
                @click="() => void reloadContent(item.path)"
              >
                {{ item.name }}
              </button>
            </template>

            <UIcon
              v-if="isLoading"
              name="i-lucide-loader-circle"
              class="size-4 animate-spin text-info"
            />
          </nav>

          <div>
            <h1 class="truncate text-2xl font-semibold text-highlighted">
              {{ currentDirectoryName }}
            </h1>
          </div>
        </div>
      </div>

      <div class="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:justify-end">
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

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          class="hidden sm:inline-flex"
          @click="toggleDisplayStyle"
        >
          <span class="hidden sm:inline">{{
            display_style === 'list' ? t('common.list') : t('common.grid')
          }}</span>
        </UButton>

        <UDropdownMenu v-if="hasItems" :items="sortGroups" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-arrow-up-down"
            trailing-icon="i-lucide-chevron-down"
          >
            <span>{{ t('common.sort') }}</span>
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
      </div>
    </div>

    <div
      v-if="controlEnabled && hasItems"
      class="flex flex-wrap items-center justify-between gap-3 ytp-card px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
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
      v-if="contentStyle === 'list' && hasItems"
      class="w-full min-w-0 max-w-full overflow-hidden ytp-table-surface"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-360 w-full text-sm">
          <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
            <tr
              class="text-center [&>th]:border-e [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-e-0"
            >
              <th v-if="controlEnabled" class="w-16">
                <button
                  type="button"
                  class="cursor-pointer"
                  :aria-label="masterSelectAll ? t('common.unselectAll') : t('common.selectAll')"
                  @click="toggleMasterSelection"
                >
                  <UIcon
                    :name="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-start">
                {{ t('common.name') }}
                <UIcon
                  v-if="sort_by === 'name'"
                  :name="sortDirectionIcon"
                  class="ms-1 inline-flex size-3.5"
                />
              </th>
              <th class="w-28 whitespace-nowrap">
                {{ t('common.size') }}
                <UIcon
                  v-if="sort_by === 'size'"
                  :name="sortDirectionIcon"
                  class="ms-1 inline-flex size-3.5"
                />
              </th>
              <th class="w-40 whitespace-nowrap">
                {{ t('common.date') }}
                <UIcon
                  v-if="sort_by === 'date'"
                  :name="sortDirectionIcon"
                  class="ms-1 inline-flex size-3.5"
                />
              </th>
              <th v-if="controlEnabled" class="w-96 whitespace-nowrap">
                {{ t('common.actions') }}
              </th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr
              v-for="item in filteredItems"
              :key="item.path"
              class="transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
            >
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

              <td class="px-3 py-3 align-middle">
                <div class="flex min-w-0 items-center gap-3">
                  <UTooltip :text="itemTypeLabel(item)">
                    <span class="inline-flex shrink-0 items-center justify-center text-toned">
                      <UIcon :name="itemTypeIcon(item)" class="size-5" />
                    </span>
                  </UTooltip>

                  <div class="min-w-0 flex-1">
                    <UTooltip :text="item.name">
                      <a
                        :href="itemHref(item)"
                        class="block truncate font-medium text-highlighted hover:underline"
                        @click.prevent="handleClick(item)"
                      >
                        <bdi>{{ item.name }}</bdi>
                      </a>
                    </UTooltip>
                  </div>
                </div>
              </td>

              <td class="px-3 py-3 text-center align-middle text-toned whitespace-nowrap">
                {{ itemSizeLabel(item) }}
              </td>

              <td class="px-3 py-3 text-center align-middle text-toned whitespace-nowrap">
                <UTooltip :text="formatDateTime(item.mtime, locale, { seconds: true })">
                  <span>{{ relativeTime(item.mtime) }}</span>
                </UTooltip>
              </td>

              <td v-if="controlEnabled" class="w-96 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    v-if="item.type === 'file'"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-download"
                    class="shrink-0"
                    external
                    :href="downloadHref(item)"
                    :download="downloadName(item)"
                  >
                    {{ t('common.download') }}
                  </UButton>
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="() => void handleAction('rename', item)"
                  >
                    {{ t('common.rename') }}
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-arrow-right-left"
                    @click="() => void handleAction('move', item)"
                  >
                    {{ t('files.move') }}
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void handleAction('delete', item)"
                  >
                    {{ t('common.delete') }}
                  </UButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="hasItems" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="item in filteredItems"
        :key="item.path"
        class="ytp-card flex h-full flex-col overflow-hidden"
      >
        <div class="p-4 pb-3 ytp-border-bottom-soft">
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
                      <bdi>{{ item.name }}</bdi>
                    </a>
                  </UTooltip>
                </div>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-1">
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
        </div>

        <div class="flex flex-1 flex-col gap-4 p-4 pt-0">
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
              <UTooltip :text="formatDateTime(item.mtime, locale, { seconds: true })">
                <span class="block truncate">{{ relativeTime(item.mtime) }}</span>
              </UTooltip>
            </div>
          </div>
        </div>

        <div v-if="controlEnabled" class="ytp-border-top-soft px-4 py-4">
          <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
            <UButton
              v-if="item.type === 'file'"
              color="neutral"
              variant="outline"
              size="xs"
              icon="i-lucide-download"
              external
              :href="downloadHref(item)"
              :download="downloadName(item)"
              class="w-full justify-center"
            >
              {{ t('common.download') }}
            </UButton>

            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-pencil"
              class="w-full justify-center"
              @click="() => void handleAction('rename', item)"
            >
              {{ t('common.rename') }}
            </UButton>

            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-arrow-right-left"
              class="w-full justify-center"
              @click="() => void handleAction('move', item)"
            >
              {{ t('files.move') }}
            </UButton>

            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-trash"
              class="w-full justify-center"
              @click="() => void handleAction('delete', item)"
            >
              {{ t('common.delete') }}
            </UButton>
          </div>
        </div>
      </div>
    </div>

    <div v-if="localSearch && !hasItems && !isLoading" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
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
    />

    <UAlert
      v-else-if="!hasItems"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      :title="t('files.noContent')"
      :description="t('files.empty')"
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

    <LazyGetInfo
      v-if="model_item?.type === 'text'"
      :link="model_item.filename"
      :useUrl="true"
      @closeModel="closeModel"
    />
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import type { DropdownMenuItem } from '@nuxt/ui';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import type { FileItem } from '~/types/filebrowser';
import { formatPageTitle } from '~/utils';
import { formatRelativeTime, type RelativeTimeInput } from '~/utils/relativeTime';
import { formatDateTime } from '~/utils/date';
import { usePageShell } from '~/composables/usePageShell';
const { locale, t } = useI18n();

const route = useRoute();
const toast = useNotification();
const config = useYtpConfig();
const dialog = useDialog();
const browser = useBrowser();

const display_style = useStorage<string>('browser_display_style', 'list');
const isMobile = useMediaQuery({ maxWidth: 639 });
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
const contentStyle = computed<'list' | 'grid'>(() =>
  isMobile.value ? 'grid' : 'list' === display_style.value ? 'list' : 'grid',
);
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
  show_filter.value = false;
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

const toggleDisplayStyle = (): void => {
  display_style.value = display_style.value === 'list' ? 'grid' : 'list';
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
