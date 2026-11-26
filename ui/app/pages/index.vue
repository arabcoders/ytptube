<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell">
      <template #actions>
        <UButton
          v-if="hasQueueContent"
          color="neutral"
          :variant="toggleFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          :aria-expanded="toggleFilter"
          aria-controls="queue-filter"
          @click="toggleFilter = !toggleFilter"
        >
          {{ t('common.filter') }}
        </UButton>

        <UButton
          v-if="false === config.paused"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-pause"
          @click="() => pauseDownload()"
        >
          <span>{{ t('common.pause') }}</span>
        </UButton>

        <UButton
          v-else
          color="primary"
          variant="solid"
          size="sm"
          icon="i-lucide-play"
          @click="() => resumeDownload()"
        >
          <span>{{ t('common.resume') }}</span>
        </UButton>

        <UButton
          color="neutral"
          :variant="config.showForm ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-plus"
          @click="
            () => {
              config.showForm = !config.showForm;
            }
          "
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          v-if="socket.connectionStatus !== 'connected'"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isRefreshing"
          :disabled="isRefreshing"
          @click="() => refreshQueue()"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>

        <UInput
          v-if="toggleFilter && hasQueueContent"
          id="queue-filter"
          v-model.lazy="query"
          type="search"
          :placeholder="t('common.filterDisplayedContent')"
          :aria-label="t('common.filterDisplayedContent')"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </template>
    </PageHeader>

    <div v-if="config.showForm" ref="formSection" class="page-form-wrap scroll-mt-24">
      <LazyNewDownload
        :item="item_form"
        @clear_form="item_form = {}"
        @getInfo="
          (url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)
        "
      />
    </div>

    <UEmpty
      v-if="!hasQueueContent"
      icon="i-lucide-triangle-alert"
      :title="t('queue.empty')"
      class="py-10"
    />

    <section v-else id="queue" class="scroll-mt-24 space-y-4">
      <div class="w-full min-w-0 max-w-full space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
              :disabled="!hasItems"
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

          <div class="flex flex-wrap items-center gap-2">
            <UBadge color="neutral" variant="soft" size="sm">
              <span class="inline-flex items-center gap-1.5">
                <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                <span>{{ queueCountLabel }}</span>
              </span>
            </UBadge>

            <UButton
              v-if="stateStore.hasMore()"
              color="neutral"
              variant="outline"
              size="sm"
              :loading="isRefreshing"
              @click="() => loadMoreQueue()"
            >
              {{ t('common.showMore') }}
            </UButton>
          </div>
        </div>

        <div v-if="hasItems" :aria-busy="isRefreshing" class="ytp-card divide-y divide-default">
          <LateLoader
            v-for="item in displayedItems"
            :key="item._id"
            :unrender="true"
            :min-height="200"
            class="min-h-0 min-w-0 w-full max-w-full"
          >
            <article
              :aria-labelledby="`queue-title-${item._id}`"
              class="grid min-w-0 gap-4 p-4 sm:p-5 xl:grid-cols-[13.75rem_minmax(0,1fr)]"
            >
              <div class="min-w-0 space-y-3 xl:col-span-2">
                <div class="flex min-w-0 items-start justify-between gap-3">
                  <h2
                    :id="`queue-title-${item._id}`"
                    class="min-w-0 flex-1 text-base font-semibold text-highlighted"
                  >
                    <UTooltip :text="downloadTitleTooltip(item)" :content="{ align: 'start' }">
                      <a
                        :href="item.url"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="line-clamp-2 w-fit max-w-full wrap-anywhere hover:text-primary hover:underline"
                      >
                        <bdi>{{ downloadTitle(item) }}</bdi>
                      </a>
                    </UTooltip>
                  </h2>
                  <UCheckbox
                    :id="`checkbox-${item._id}`"
                    color="primary"
                    class="mt-1 shrink-0"
                    :model-value="selectedElms.includes(item._id)"
                    :aria-label="`${t('common.select')}: ${downloadTitle(item)}`"
                    @click.capture="rangeSelection.handleClick"
                    @keydown.capture="rangeSelection.handleKeydown"
                    @update:model-value="selectItem(item._id, $event)"
                  />
                </div>

                <div class="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 text-xs text-toned">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon
                      :name="setIcon(item)"
                      :class="[setIconColor(item), setIconAnimation(item), 'size-4 shrink-0']"
                      aria-hidden="true"
                    />
                    {{ setStatus(item) }}
                  </span>
                  <span
                    v-if="item.extras?.retry_attempt && item.extras.retry_attempt > 1"
                    class="inline-flex items-center gap-1.5 text-warning"
                  >
                    <UIcon name="i-lucide-rotate-cw" class="size-3.5 shrink-0" aria-hidden="true" />
                    {{ t('common.retryCount', { count: item.extras.retry_attempt }) }}
                  </span>
                </div>
              </div>

              <div
                v-if="showThumbnails"
                class="ytp-thumbnail aspect-video w-full max-w-full self-start sm:w-55"
              >
                <button
                  v-if="isEmbedable(item.url)"
                  type="button"
                  class="play-overlay focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary"
                  :aria-label="`${t('common.playVideo')}: ${downloadTitle(item)}`"
                  @click="playItem(item)"
                >
                  <span class="play-icon embed-icon" aria-hidden="true">
                    <UIcon name="i-lucide-play" class="size-6 text-white" />
                  </span>
                  <img
                    :src="getImage(config.app.download_path, item)"
                    alt=""
                    loading="lazy"
                    @error="onImgError"
                  />
                </button>
                <img
                  v-else
                  :src="getImage(config.app.download_path, item)"
                  alt=""
                  loading="lazy"
                  class="size-full object-cover"
                  @error="onImgError"
                />
              </div>

              <div class="min-w-0 space-y-4" :class="{ 'xl:col-span-2': !showThumbnails }">
                <div class="queue-progress">
                  <div
                    class="queue-progress__bar bg-success/35"
                    :style="{ width: progressWidth(item) }"
                  ></div>
                  <div class="queue-progress__label whitespace-normal">
                    <UIcon
                      v-if="progressIcon(item)"
                      :name="progressIcon(item)"
                      :class="[
                        'me-1 size-4 shrink-0',
                        ['i-lucide-settings-2', 'i-lucide-loader-circle'].includes(
                          progressIcon(item),
                        )
                          ? 'animate-spin'
                          : '',
                      ]"
                      aria-hidden="true"
                    />
                    <span class="min-w-0 wrap-anywhere">{{ progressText(item) }}</span>
                  </div>
                </div>

                <dl
                  class="grid min-w-0 grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-[8rem_12rem_minmax(0,1fr)]"
                >
                  <div class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon name="i-lucide-clock-3" class="size-3.5 shrink-0" aria-hidden="true" />
                      {{ t('common.created') }}
                    </dt>
                    <dd class="wrap-anywhere">
                      <UTooltip :text="formatLongDateTime(item.datetime, locale)">
                        <time :datetime="item.datetime" v-rtime="item.datetime" />
                      </UTooltip>
                    </dd>
                  </div>

                  <div class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-sliders-horizontal"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.presetLabel') }}
                    </dt>
                    <dd class="wrap-anywhere">
                      <bdi>{{ item.preset }}</bdi>
                    </dd>
                  </div>

                  <div v-if="getItemPath(item)" class="col-span-2 min-w-0 space-y-1 sm:col-span-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-folder-output"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.downloadPath') }}
                    </dt>
                    <dd class="flex min-w-0 items-start gap-2 text-xs">
                      <NuxtLink
                        v-if="getItemBrowserUrl(item)"
                        :to="getItemBrowserUrl(item)"
                        :title="getItemPath(item)"
                        class="min-w-0 flex-1 py-0.5 font-mono hover:text-primary hover:underline"
                      >
                        <bdi dir="ltr" :class="expandClass(item._id, 'path')">{{
                          getItemPath(item)
                        }}</bdi>
                      </NuxtLink>
                      <bdi
                        v-else
                        dir="ltr"
                        class="min-w-0 flex-1 py-0.5 font-mono"
                        :class="expandClass(item._id, 'path')"
                        >{{ getItemPath(item) }}</bdi
                      >
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="xs"
                        :icon="
                          isExpanded(item._id, 'path')
                            ? 'i-lucide-minimize-2'
                            : 'i-lucide-maximize-2'
                        "
                        :aria-label="`${t('queue.path')}: ${getItemPath(item)}`"
                        :aria-expanded="isExpanded(item._id, 'path')"
                        @click="toggleExpand(item._id, 'path')"
                      />
                    </dd>
                  </div>
                </dl>

                <dl
                  v-if="item.extras?.duration || item.downloaded_bytes || getItemTaskUrl(item)"
                  class="flex min-w-0 flex-wrap gap-x-6 gap-y-3 border-t border-default pt-3 text-sm"
                >
                  <div v-if="item.extras?.duration" class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon name="i-lucide-timer" class="size-3.5 shrink-0" aria-hidden="true" />
                      {{ t('queue.duration') }}
                    </dt>
                    <dd class="tabular-nums">{{ formatTime(item.extras.duration) }}</dd>
                  </div>
                  <div v-if="item.downloaded_bytes" class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-hard-drive"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.size') }}
                    </dt>
                    <dd class="tabular-nums">{{ formatBytes(item.downloaded_bytes, 2, t) }}</dd>
                  </div>
                  <div v-if="getItemTaskUrl(item)" class="min-w-0 max-w-full space-y-1 sm:max-w-xs">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-calendar-clock"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('tasks.task') }}
                    </dt>
                    <dd>
                      <NuxtLink
                        :to="getItemTaskUrl(item)"
                        class="wrap-anywhere text-primary hover:underline"
                      >
                        <bdi>{{ item.extras.source_name || `#${item.extras.source_id}` }}</bdi>
                      </NuxtLink>
                    </dd>
                  </div>
                </dl>

                <div class="flex flex-wrap items-center justify-between gap-3">
                  <UPopover
                    v-if="show_popover && item.description"
                    :content="{ side: 'bottom', align: 'start', sideOffset: 8 }"
                    :ui="{ content: 'max-w-[calc(100vw-2rem)]' }"
                  >
                    <UButton color="neutral" variant="outline" size="xs" icon="i-lucide-info">
                      {{ t('common.description') }}
                    </UButton>
                    <template #content>
                      <div class="w-md max-w-full space-y-3 p-4">
                        <p class="text-sm font-semibold text-highlighted">{{ item.title }}</p>
                        <p
                          class="max-h-64 overflow-y-auto whitespace-pre-wrap wrap-anywhere text-sm text-toned"
                        >
                          {{ item.description }}
                        </p>
                      </div>
                    </template>
                  </UPopover>

                  <div class="ms-auto flex flex-wrap items-center justify-end gap-1.5">
                    <UTooltip
                      v-if="!showThumbnails && isEmbedable(item.url)"
                      :text="t('common.playVideo')"
                    >
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="sm"
                        icon="i-lucide-play"
                        :aria-label="`${t('common.playVideo')}: ${downloadTitle(item)}`"
                        @click="playItem(item)"
                      />
                    </UTooltip>
                    <UButton
                      v-if="canStartItem(item)"
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-circle-play"
                      @click="() => startItem(item)"
                    >
                      {{ t('common.start') }}
                    </UButton>

                    <UButton
                      v-if="canPauseItem(item)"
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-pause"
                      @click="() => pauseItem(item)"
                    >
                      {{ t('common.pause') }}
                    </UButton>

                    <template v-if="wideActions">
                      <UButton
                        v-for="action in positionActions(item)"
                        :key="action.icon"
                        color="neutral"
                        variant="outline"
                        size="sm"
                        :icon="action.icon"
                        :label="action.label"
                        @click="action.onSelect"
                      />
                    </template>

                    <UTooltip :text="t('queue.manualStart')">
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="sm"
                        icon="i-lucide-rotate-cw"
                        :loading="requeueing.has(item._id)"
                        @click="() => void requeueItem(item)"
                      >
                        {{ t('common.requeue') }}
                      </UButton>
                    </UTooltip>

                    <UButton
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-circle-off"
                      @click="() => void confirmCancel(item)"
                    >
                      {{ item.is_live ? t('common.stopStream') : t('common.cancel') }}
                    </UButton>

                    <UDropdownMenu
                      :items="itemActionGroups(item)"
                      :modal="false"
                      :content="{ align: 'end' }"
                    >
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        icon="i-lucide-ellipsis"
                        :aria-label="`${t('common.actions')}: ${downloadTitle(item)}`"
                      />
                    </UDropdownMenu>
                  </div>
                </div>
              </div>
            </article>
          </LateLoader>
        </div>

        <div v-if="!hasItems" class="space-y-4">
          <UAlert
            v-if="query"
            color="warning"
            variant="soft"
            icon="i-lucide-search"
            :title="t('queue.filterTitle')"
          >
            <template #description>
              <div class="space-y-3 text-sm text-default">
                <p>
                  {{ t('queue.noResultsFor') }} <code>{{ query }}</code
                  >.
                </p>

                <p>
                  {{ t('queue.filterHelp') }}
                  {{ t('queue.filterKeyValue') }}
                </p>

                <div>
                  <p class="mb-1 font-medium">{{ t('queue.filterExamples') }}</p>
                  <ul class="list-disc space-y-1 ps-5">
                    <li><code>youtube.com</code> - {{ t('queue.filterExample1') }}</li>
                    <li><code>is_live:true</code> - {{ t('queue.filterExample2') }}</li>
                    <li><code>source_name:task_name</code> - {{ t('queue.filterExample3') }}</li>
                  </ul>
                </div>
              </div>
            </template>
          </UAlert>

          <UEmpty
            v-else
            icon="i-lucide-triangle-alert"
            :title="t('common.noItems')"
            :description="t('queue.emptyDesc')"
            class="py-10"
          />
        </div>

        <UModal
          v-if="embed_url"
          :open="Boolean(embed_url)"
          :dismissible="true"
          :title="t('common.embeddedPlayer')"
          :ui="{ content: 'sm:max-w-5xl', body: 'p-0' }"
          @update:open="(open) => !open && (embed_url = '')"
        >
          <template #body>
            <LazyEmbedPlayer :url="embed_url" @closeModel="embed_url = ''" />
          </template>
        </UModal>
      </div>
    </section>

    <LazyGetInfo
      v-if="info_view.url"
      :link="info_view.url"
      :preset="info_view.preset"
      :cli="info_view.cli"
      :useUrl="info_view.useUrl"
      @closeModel="close_info()"
    />
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import { useStorage } from '@vueuse/core';
import { useConfirm } from '~/composables/useConfirm';
import { useDialog } from '~/composables/useDialog';
import { downloadTitleTooltip, useDownloadTitle } from '~/composables/useDownloadTitle';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useMediaQuery } from '~/composables/useMediaQuery';
import type { download_form_item } from '~/types/item';
import type { StoreItem } from '~/types/store';
import {
  ag,
  deepIncludes,
  ensure_api_success,
  formatBytes,
  formatTime,
  getBrowserUrl,
  getImage,
  getPath,
  request,
  ucFirst,
} from '~/utils';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import { formatLongDateTime } from '~/utils/date';
import { usePageShell } from '~/composables/usePageShell';
import { useFormHandoff } from '~/composables/useFormHandoff';
import { isShareTarget, parseShareUrls, removeShareQuery } from '~/composables/useShareTarget';
import { useRangeSelection } from '~/composables/useRangeSelection';
import { taskSourceUrl } from '~/utils/taskDetails';
import { setSelected } from '~/utils/selection';
const { locale, t } = useI18n();

const config = useYtpConfig();
const stateStore = useQueueState();
const socket = useAppSocket();
const toast = useNotification();
const box = useConfirm();
const { confirmDialog } = useDialog();
const { downloadTitle } = useDownloadTitle();
const { toggleExpand, isExpanded, expandClass } = useExpandableMeta();
const downloadFormHandoff = useFormHandoff<download_form_item>('download');

const showThumbnails = useStorage<boolean>('show_thumbnail', true);
const show_popover = useStorage<boolean>('show_popover', true);
const wideActions = useMediaQuery({ query: '(min-width: 80rem)' });
const autoRefreshEnabled = useStorage<boolean>('queue_auto_refresh', true);
const autoRefreshDelay = useStorage<number>('queue_auto_refresh_delay', 10000);

const pageShell = usePageShell('downloads');
const formSection = ref<HTMLElement | null>(null);
const info_view = ref<{ url: string; preset: string; cli: string; useUrl: boolean }>({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
});
const item_form = ref<download_form_item | object>({});
const query = ref('');
const toggleFilter = ref(false);
const selectedElms = ref<string[]>([]);
const requeueing = reactive(new Set<string>());
const masterSelectAll = ref(false);
const embed_url = ref('');
const isRefreshing = ref(false);
const autoRefreshInterval = ref<ReturnType<typeof setInterval> | null>(null);
const hadSocketDisconnect = ref(false);
const route = useRoute();
const router = useRouter();
const shared = isShareTarget(route.query);
const sharedUrl = parseShareUrls(route.query).join('\n');

const hasQueueContent = computed(() => stateStore.count() > 0 || query.value.trim().length > 0);

const displayedItems = computed<StoreItem[]>(() => {
  const normalizedQuery = query.value.trim().toLowerCase();
  const items = Object.values(stateStore.queue);

  if (!normalizedQuery) {
    return items;
  }

  return items.filter((item) => deepIncludes(item, normalizedQuery, new WeakSet()));
});

const queueCountLabel = computed(() => {
  if (stateStore.hasMore()) {
    return t('queue.queuedCount', { shown: stateStore.shown(), total: stateStore.count() });
  }

  return t('queue.queuedCountShort', { count: stateStore.count() });
});

const hasItems = computed(() => displayedItems.value.length > 0);
const hasSelected = computed(() => selectedElms.value.length > 0);
const displayedItemIds = computed(() => displayedItems.value.map((item) => item._id));
const rangeSelection = useRangeSelection(selectedElms, displayedItemIds);
const selectItem = (id: string, checked: boolean | 'indeterminate'): void => {
  selectedElms.value = setSelected(selectedElms.value, id, checked);
  rangeSelection.handleChange(id, new Event('change'));
};
const hasManualStart = computed(() =>
  Object.values(stateStore.queue).some((item) => !item.status && false === item.auto_start),
);
const hasPausable = computed(() =>
  Object.values(stateStore.queue).some((item) => !item.status && true === item.auto_start),
);

const refreshQueue = async (): Promise<void> => {
  if (isRefreshing.value) {
    return;
  }

  isRefreshing.value = true;

  try {
    await stateStore.loadQueue();
  } catch (error) {
    console.error('Failed to refresh queue:', error);
  } finally {
    isRefreshing.value = false;
  }
};

const loadMoreQueue = async (): Promise<void> => {
  if (isRefreshing.value) {
    return;
  }

  isRefreshing.value = true;

  try {
    await stateStore.loadMore();
  } catch {
    toast.error(t('common.failedLoadMore'));
  } finally {
    isRefreshing.value = false;
  }
};

const startAutoRefresh = (): void => {
  if (autoRefreshInterval.value) {
    clearInterval(autoRefreshInterval.value);
  }

  if (!autoRefreshEnabled.value || socket.isConnected) {
    return;
  }

  autoRefreshInterval.value = setInterval(async () => {
    if (!socket.isConnected && autoRefreshEnabled.value) {
      await refreshQueue();
    }
  }, autoRefreshDelay.value);
};

const stopAutoRefresh = (): void => {
  if (!autoRefreshInterval.value) {
    return;
  }

  clearInterval(autoRefreshInterval.value);
  autoRefreshInterval.value = null;
};

onMounted(async () => {
  if (shared) {
    await router.replace({ query: removeShareQuery(route.query) });
  }

  if (sharedUrl) {
    await toNewDownload({ url: sharedUrl });
  }

  const pendingDownload = downloadFormHandoff.take();
  if (pendingDownload) {
    await toNewDownload(pendingDownload);
  }

  await refreshQueue();

  if (!socket.isConnected && autoRefreshEnabled.value) {
    startAutoRefresh();
  }
});

onBeforeUnmount(() => stopAutoRefresh());

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = '';
  }
});

watch(
  () => socket.isConnected,
  (connected) => {
    if (connected) {
      stopAutoRefresh();

      if (hadSocketDisconnect.value) {
        hadSocketDisconnect.value = false;
        void refreshQueue();
      }

      return;
    }

    hadSocketDisconnect.value = true;

    if (autoRefreshEnabled.value) {
      startAutoRefresh();
    }
  },
);

watch(autoRefreshEnabled, (enabled) => {
  if (enabled && !socket.isConnected) {
    startAutoRefresh();
    return;
  }

  stopAutoRefresh();
});

watch(autoRefreshDelay, () => {
  if (autoRefreshEnabled.value && !socket.isConnected) {
    startAutoRefresh();
  }
});

watch(
  displayedItemIds,
  (ids) => {
    const idSet = new Set(ids);
    selectedElms.value = selectedElms.value.filter((id) => idSet.has(id));

    if (masterSelectAll.value) {
      selectedElms.value = [...ids];
    }
  },
  { immediate: true },
);

watch(selectedElms, (value) => {
  const ids = displayedItemIds.value;
  masterSelectAll.value = ids.length > 0 && ids.every((id) => value.includes(id));
});

const toggleMasterSelection = (): void => {
  rangeSelection.reset();

  if (masterSelectAll.value) {
    selectedElms.value = [];
    masterSelectAll.value = false;
    return;
  }

  selectedElms.value = [...displayedItemIds.value];
  masterSelectAll.value = true;
};

const resumeDownload = async (): Promise<void> => {
  await request('/api/system/resume', { method: 'POST' });
};

const pauseDownload = async (): Promise<void> => {
  const { status } = await confirmDialog({
    title: t('app.pauseAll'),
    confirmText: t('common.pause'),
    cancelText: t('common.cancel'),
    confirmColor: 'warning',
    message: t('queue.pauseDownloadsDesc'),
  });

  if (!status) {
    return;
  }

  await request('/api/system/pause', { method: 'POST' });
};

const close_info = (): void => {
  info_view.value.url = '';
  info_view.value.preset = '';
  info_view.value.cli = '';
  info_view.value.useUrl = false;
};

const view_info = (
  url: string,
  useUrl: boolean = false,
  preset: string = '',
  cli: string = '',
): void => {
  info_view.value.url = url;
  info_view.value.useUrl = useUrl;
  info_view.value.preset = preset;
  info_view.value.cli = cli;
};

const toNewDownload = async (item: download_form_item | Partial<StoreItem>): Promise<void> => {
  if (!item) {
    return;
  }

  if (config.showForm) {
    config.showForm = false;
    await nextTick();
  }

  item_form.value = item;

  await nextTick();
  config.showForm = true;
  await nextTick();
  formSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const getItemPath = (item: StoreItem): string => getPath(config.app.download_path, item) || '';
const getItemBrowserUrl = (item: StoreItem): string =>
  getBrowserUrl(config.app.download_path, item);
const getItemTaskUrl = (item: StoreItem): string => taskSourceUrl(item.extras);
const playItem = (item: StoreItem): void => {
  const embed = getEmbedable(item.url);
  if (embed) {
    embed_url.value = embed;
  }
};
const canStartItem = (item: StoreItem): boolean => !item.auto_start && !item.status;
const canPauseItem = (item: StoreItem): boolean => item.auto_start && !item.status;

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [[]];
  const selectedLiveOnly =
    selectedElms.value.length > 0 &&
    selectedElms.value.every((id) => {
      const item = stateStore.get(id);
      return Boolean(item?.is_live);
    });

  if (hasManualStart.value) {
    groups[0]?.push({
      label: t('common.start'),
      icon: 'i-lucide-circle-play',
      disabled: !hasSelected.value,
      onSelect: () => startItems(),
    });
  }

  if (stateStore.hasActive()) {
    groups[0]?.push({
      label: t('queue.forceStart'),
      icon: 'i-lucide-zap',
      disabled: !hasSelected.value,
      onSelect: () => forceStartItems(),
    });
  }

  groups[0]?.push({
    label: t('queue.moveToFront'),
    icon: 'i-lucide-arrow-up-to-line',
    disabled: !hasSelected.value,
    onSelect: () => positionItems('front'),
  });

  groups[0]?.push({
    label: t('queue.moveToBack'),
    icon: 'i-lucide-arrow-down-to-line',
    disabled: !hasSelected.value,
    onSelect: () => positionItems('back'),
  });

  if (hasPausable.value) {
    groups[0]?.push({
      label: t('common.pause'),
      icon: 'i-lucide-pause',
      disabled: !hasSelected.value,
      onSelect: () => pauseSelected(),
    });
  }

  groups[0]?.push({
    label: selectedLiveOnly ? t('common.stop') : t('common.cancel'),
    icon: 'i-lucide-circle-off',
    disabled: !hasSelected.value,
    onSelect: () => cancelSelected(),
  });

  return groups;
});

const positionActions = (item: StoreItem): DropdownMenuItem[] => {
  if (item.status || !stateStore.canPosition(item._id)) return [];

  const actions: DropdownMenuItem[] = [];
  if (!stateStore.isFirst(item._id)) {
    actions.push({
      label: t('queue.moveToFront'),
      icon: 'i-lucide-arrow-up-to-line',
      onSelect: () => void positionItem(item, 'front'),
    });
  }
  if (!stateStore.isLastPending(item._id)) {
    actions.push({
      label: t('queue.moveToBack'),
      icon: 'i-lucide-arrow-down-to-line',
      onSelect: () => void positionItem(item, 'back'),
    });
  }
  return actions;
};

const itemActionGroups = (item: StoreItem): DropdownMenuItem[][] => {
  const groups: DropdownMenuItem[][] = [];
  const queueActions: DropdownMenuItem[] = [];
  if (!item.status && stateStore.hasActive()) {
    queueActions.push({
      label: t('queue.forceStart'),
      icon: 'i-lucide-zap',
      onSelect: () => void forceStartItem(item),
    });
  }
  if (!wideActions.value) {
    queueActions.push(...positionActions(item));
  }
  if (queueActions.length) {
    groups.push(queueActions);
  }

  groups.push([
    {
      label: t('common.ytdlpInformation'),
      icon: 'i-lucide-info',
      onSelect: () => view_info(item.url, false, item.preset, item.cli),
    },
    {
      label: t('common.localInformation'),
      icon: 'i-lucide-info',
      onSelect: () => view_info(`/api/history/${item._id}`, true),
    },
  ]);

  return groups;
};

const setIcon = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'i-lucide-clock-3';
  }

  if ('downloading' === item.status && item.is_live) {
    return 'i-lucide-globe';
  }

  if ('downloading' === item.status) {
    return 'i-lucide-download';
  }

  if ('postprocessing' === item.status) {
    return 'i-lucide-settings-2';
  }

  if (null === item.status && true === config.paused) {
    return 'i-lucide-circle-pause';
  }

  if (!item.status) {
    return 'i-lucide-circle-question-mark';
  }

  return 'i-lucide-loader-circle';
};

const setIconAnimation = (item: StoreItem): string => {
  const icon = setIcon(item);

  return ['i-lucide-globe', 'i-lucide-settings-2', 'i-lucide-loader-circle'].includes(icon)
    ? 'animate-spin'
    : '';
};

const setStatus = (item: StoreItem): string => {
  if (!item.auto_start) {
    return t('queue.pending');
  }

  if (null === item.status && true === config.paused) {
    return t('common.paused');
  }

  if ('downloading' === item.status && item.is_live) {
    return t('common.streaming');
  }

  if ('started' === item.status) {
    return t('common.starting');
  }

  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader') ? t('queue.externalDL') : t('queue.preparing');
  }

  if (!item.status) {
    return t('common.unknownError');
  }

  return ucFirst(item.status);
};

const setIconColor = (item: StoreItem): string => {
  if (['downloading', 'started'].includes(item.status || '')) {
    return 'text-success';
  }

  if ('postprocessing' === item.status) {
    return 'text-info';
  }

  if (!item.auto_start || (null === item.status && true === config.paused)) {
    return 'text-warning';
  }

  return 'text-default';
};

const ETAPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return t('common.live');
  }

  if (value < 60) {
    return `${Math.round(value)}${t('common.secAbbr')}`;
  }

  if (value < 3600) {
    return `${Math.floor(value / 60)}${t('common.minAbbr')} ${Math.round(value % 60)}${t('common.secAbbr')}`;
  }

  const hours = Math.floor(value / 3600);
  const minutes = value % 3600;
  return `${hours}${t('common.hourAbbr')} ${Math.floor(minutes / 60)}${t('common.minAbbr')} ${Math.round(minutes % 60)}${t('common.secAbbr')}`;
};

const speedPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return `0 ${t('common.kib')}${t('common.perSec')}`;
  }

  const k = 1024;
  const dm = 2;
  const sizes = ['bytes', 'kib', 'mib', 'gib', 'tib', 'pib', 'eib', 'zib', 'yib'] as const;
  const i = Math.floor(Math.log(value) / Math.log(k));
  return `${parseFloat((value / Math.pow(k, i)).toFixed(dm))} ${t(`common.${sizes[i]}`)}${t('common.perSec')}`;
};

const percentPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return '00.00';
  }

  return parseFloat(String(value)).toFixed(2);
};

const progressWidth = (item: StoreItem): string => {
  if (!item.auto_start || (null === item.status && true === config.paused)) {
    return '0%';
  }

  if (
    'postprocessing' === item.status ||
    'started' === item.status ||
    'preparing' === item.status
  ) {
    return '100%';
  }

  if (!item.percent || item.is_live) {
    return '100%';
  }

  return `${percentPipe(item.percent)}%`;
};

const progressIcon = (item: StoreItem): string => {
  if (null != item.status && item.is_live && !item.speed) {
    return 'i-lucide-loader-circle';
  }

  if ('postprocessing' === item.status) {
    return 'i-lucide-settings-2';
  }

  return '';
};

const progressText = (item: StoreItem): string => {
  if (!item.auto_start) {
    return t('queue.manualStart');
  }

  if (null === item.status && true === config.paused) {
    return t('queue.globalPause');
  }

  if ('started' === item.status) {
    return t('common.starting');
  }

  if ('postprocessing' === item.status) {
    if (item.postprocessor) {
      return t('queue.ppLabel', { pp: item.postprocessor });
    }

    return t('queue.postProcessing');
  }

  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader')
      ? t('queue.externalDownloader')
      : t('queue.preparing');
  }

  if (null != item.status && item.is_live && !item.speed) {
    return t('queue.recordingLive');
  }

  let value = '';

  if (null != item.status) {
    value += item.percent && !item.is_live ? `${percentPipe(item.percent)}%` : t('common.live');
  }

  value += item.speed ? ` - ${speedPipe(item.speed)}` : t('queue.waiting');

  if (null != item.status && item.eta) {
    value += ` - ${ETAPipe(item.eta)}`;
  }

  return value;
};

const confirmCancel = async (item: StoreItem): Promise<boolean> => {
  if (
    true !==
    (await box.confirm(
      t('common.confirmActionNamed', {
        action: item.is_live ? t('common.stop') : t('common.cancel'),
        name: downloadTitle(item),
      }),
    ))
  ) {
    return false;
  }

  cancelItems(item._id);
  return true;
};

const requeueItem = async (item: StoreItem): Promise<void> => {
  const id = item._id;
  if (requeueing.has(id)) {
    return;
  }

  requeueing.add(id);
  try {
    if (
      item.status &&
      !(await box.confirm(
        t('common.confirmActionNamed', { action: t('common.stop'), name: downloadTitle(item) }),
        { confirmText: t('common.requeue') },
      ))
    ) {
      return;
    }

    const response = await request(`/api/history/${encodeURIComponent(id)}/requeue`, {
      method: 'POST',
    });
    await ensure_api_success(response);

    if (response.status === 202) {
      return;
    }

    toast.success(t('queue.pausedCount', { count: 1 }));
    if (!socket.isConnected) {
      await refreshQueue();
    }
  } catch (error) {
    toast.error(error instanceof Error ? error.message : t('common.unknownError'));
  } finally {
    requeueing.delete(id);
  }
};

const cancelSelected = async (): Promise<boolean> => {
  const selectedLiveOnly =
    selectedElms.value.length > 0 &&
    selectedElms.value.every((id) => {
      const item = stateStore.get(id);
      return Boolean(item?.is_live);
    });

  if (
    true !==
    (await box.confirm(
      t('common.confirmActionSelected', {
        action: selectedLiveOnly ? t('common.stop') : t('common.cancel'),
        count: selectedElms.value.length,
      }),
    ))
  ) {
    return false;
  }

  cancelItems(selectedElms.value);
  selectedElms.value = [];
  masterSelectAll.value = false;
  return true;
};

const cancelItems = (item: string | string[]): void => {
  const items = Array.isArray(item) ? [...item] : [item];

  if (items.length < 1) {
    return;
  }

  stateStore.cancelItems(items);
};

const startItem = async (item: StoreItem): Promise<void> => await stateStore.startItems([item._id]);
const forceStartItem = async (item: StoreItem): Promise<void> =>
  await stateStore.forceStartItems([item._id]);
const positionItem = async (item: StoreItem, position: 'front' | 'back'): Promise<void> =>
  await stateStore.positionItems([item._id], position);
const pauseItem = async (item: StoreItem): Promise<void> => await stateStore.pauseItems([item._id]);

const startItems = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get(id);
    return Boolean(item && !item.auto_start && !item.status);
  });

  selectedElms.value = [];

  if (eligible.length < 1) {
    toast.error(t('common.noEligibleStart'));
    return;
  }

  if (true !== (await box.confirm(t('queue.startSelectedConfirm', { count: eligible.length })))) {
    return;
  }

  await stateStore.startItems(eligible);
};

const forceStartItems = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get(id);
    return Boolean(item && !item.status);
  });

  selectedElms.value = [];
  if (eligible.length < 1) {
    toast.error(t('common.noEligibleStart'));
    return;
  }

  if (
    true !== (await box.confirm(t('queue.forceStartSelectedConfirm', { count: eligible.length })))
  ) {
    return;
  }

  await stateStore.forceStartItems(eligible);
};

const positionItems = async (position: 'front' | 'back'): Promise<void> => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get(id);
    return Boolean(item && !item.status);
  });

  selectedElms.value = [];
  if (eligible.length < 1) {
    toast.error(t('common.noEligibleStart'));
    return;
  }

  await stateStore.positionItems(eligible, position);
};

const pauseSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get(id);
    return Boolean(item && item.auto_start && !item.status);
  });

  selectedElms.value = [];

  if (eligible.length < 1) {
    toast.error(t('common.noEligiblePause'));
    return;
  }

  if (true !== (await box.confirm(t('queue.pauseSelectedConfirm', { count: eligible.length })))) {
    return;
  }

  await stateStore.pauseItems(eligible);
};

const onImgError = (event: Event): void => {
  const target = event.target as HTMLImageElement;

  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  target.src = '/images/placeholder.png';
};
</script>

<style scoped>
.page-form-wrap {
  max-width: 100%;
}
</style>
