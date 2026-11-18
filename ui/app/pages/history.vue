<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div
      class="ytp-lights-out"
      :class="lightsOut ? 'opacity-100' : 'opacity-0'"
      aria-hidden="true"
    />

    <PageHeader v-bind="pageShell">
      <template #actions>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="addNewDownload"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => reload({ order: 'DESC', perPage: config.app.default_pagination })"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>
      </template>
    </PageHeader>

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

          <UButton
            color="neutral"
            :variant="showFilter ? 'soft' : 'outline'"
            size="sm"
            icon="i-lucide-filter"
            :aria-expanded="showFilter"
            aria-controls="history-filter"
            @click="showFilter = !showFilter"
          >
            {{ t('common.filter') }}
          </UButton>
        </div>

        <UPagination
          v-if="paginationInfo.total_pages > 1"
          :page="paginationInfo.page"
          :total="paginationInfo.total"
          :items-per-page="paginationInfo.per_page"
          :disabled="paginationInfo.isLoading"
          show-edges
          :sibling-count="0"
          size="sm"
          @update:page="
            (page) => load(page, { order: 'DESC', perPage: config.app.default_pagination })
          "
        />
      </div>

      <UInput
        v-if="showFilter"
        id="history-filter"
        v-model.lazy="query"
        type="search"
        :placeholder="t('common.filterDisplayedContent')"
        :aria-label="t('common.filterDisplayedContent')"
        icon="i-lucide-filter"
        size="sm"
        class="w-full sm:w-80"
      />

      <UAlert
        v-if="paginationInfo.isLoading && !hasItems"
        color="info"
        variant="soft"
        icon="i-lucide-loader-circle"
        :title="t('history.loading')"
      />

      <div v-if="hasItems" :aria-busy="isLoading" class="ytp-card divide-y divide-default">
        <LateLoader
          v-for="item in displayedItems"
          :key="item._id"
          :unrender="true"
          :min-height="200"
          class="min-h-0 min-w-0 w-full max-w-full"
        >
          <article
            :aria-labelledby="`history-title-${item._id}`"
            class="grid min-w-0 gap-4 p-4 sm:p-5 xl:grid-cols-[13.75rem_minmax(0,1fr)]"
          >
            <div class="min-w-0 space-y-3 xl:col-span-2">
              <div class="flex min-w-0 items-start justify-between gap-3">
                <h2
                  :id="`history-title-${item._id}`"
                  class="min-w-0 flex-1 text-base font-semibold text-highlighted"
                >
                  <UTooltip :text="item.title" :content="{ align: 'start' }">
                    <a
                      :href="item.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="line-clamp-2 w-fit max-w-full wrap-anywhere hover:text-primary hover:underline"
                    >
                      <bdi>{{ item.title }}</bdi>
                    </a>
                  </UTooltip>
                </h2>

                <UCheckbox
                  :id="`checkbox-${item._id}`"
                  color="primary"
                  class="mt-1 shrink-0"
                  :model-value="selectedElms.includes(item._id)"
                  :aria-label="`${t('common.select')}: ${item.title}`"
                  @click.capture="rangeSelection.handleClick"
                  @keydown.capture="rangeSelection.handleKeydown"
                  @update:model-value="selectItem(item._id, $event)"
                />
              </div>

              <div class="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 text-xs text-toned">
                <span class="inline-flex items-center gap-1.5">
                  <UIcon
                    :name="setIcon(item)"
                    :class="[setIconColor(item), isQueuedAnimation(item), 'size-4 shrink-0']"
                    aria-hidden="true"
                  />
                  {{ setStatus(item) }}
                </span>

                <span
                  v-if="mediaProfileLabel(item)"
                  class="inline-flex min-w-0 items-start gap-1.5"
                >
                  <UIcon name="i-lucide-badge-info" class="size-3.5 shrink-0" aria-hidden="true" />
                  <span class="wrap-anywhere">{{ mediaProfileLabel(item) }}</span>
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
                v-if="item.filename || isEmbedable(item.url)"
                type="button"
                class="play-overlay focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary"
                :aria-label="`${t('common.playVideo')}: ${item.title}`"
                @click="playItem(item)"
              >
                <span
                  class="play-icon"
                  :class="{ 'embed-icon': !item.filename }"
                  aria-hidden="true"
                >
                  <UIcon name="i-lucide-play" class="size-6 text-white" />
                </span>
                <img
                  :src="getHistoryImage(item)"
                  alt=""
                  loading="lazy"
                  @error="onImgError($event, item)"
                />
              </button>
              <img
                v-else
                :src="getHistoryImage(item)"
                alt=""
                loading="lazy"
                class="size-full object-cover"
                @error="onImgError($event, item)"
              />
            </div>

            <div class="min-w-0 space-y-4" :class="{ 'xl:col-span-2': !showThumbnails }">
              <dl class="grid min-w-0 grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
                <div class="min-w-0 space-y-1">
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon name="i-lucide-clock-3" class="size-3.5 shrink-0" aria-hidden="true" />
                    {{ t('common.created') }}
                  </dt>
                  <dd>
                    <UTooltip :text="formatDateTime(item.datetime, locale)">
                      <time :datetime="item.datetime" v-rtime="item.datetime" />
                    </UTooltip>
                  </dd>
                </div>

                <div v-if="item.extras?.duration" class="min-w-0 space-y-1">
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon name="i-lucide-timer" class="size-3.5 shrink-0" aria-hidden="true" />
                    {{ t('queue.duration') }}
                  </dt>
                  <dd class="tabular-nums">{{ formatTime(item.extras.duration) }}</dd>
                </div>

                <div v-if="item.file_size" class="min-w-0 space-y-1">
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon
                      name="i-lucide-hard-drive"
                      class="size-3.5 shrink-0"
                      aria-hidden="true"
                    />
                    {{ t('common.size') }}
                  </dt>
                  <dd class="tabular-nums">{{ formatBytes(item.file_size, 2, t) }}</dd>
                </div>
              </dl>

              <dl class="flex min-w-0 flex-col gap-x-8 gap-y-3 text-sm sm:flex-row sm:items-start">
                <div class="min-w-0 space-y-1 sm:w-1/4 sm:shrink-0">
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
                <div v-if="getItemTaskUrl(item)" class="min-w-0 space-y-1 sm:max-w-1/4">
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
                <div v-if="getItemPath(item)" class="min-w-0 space-y-1 sm:flex-1">
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
                        isExpanded(item._id, 'path') ? 'i-lucide-minimize-2' : 'i-lucide-maximize-2'
                      "
                      :aria-label="`${t('queue.path')}: ${getItemPath(item)}`"
                      :aria-expanded="isExpanded(item._id, 'path')"
                      @click="toggleExpand(item._id, 'path')"
                    />
                  </dd>
                </div>
              </dl>

              <p
                v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)"
                class="flex items-center gap-1.5 text-sm text-info"
              >
                <UIcon name="i-lucide-calendar" class="size-3.5 shrink-0" aria-hidden="true" />
                <i18n-t keypath="history.retryAt" tag="span" scope="global">
                  <template #date>
                    <UTooltip
                      :text="formatDateTime(item.live_in || item.extras?.release_in, locale)"
                    >
                      <time
                        :datetime="item.live_in || item.extras?.release_in"
                        v-rtime="item.live_in || item.extras?.release_in"
                      />
                    </UTooltip>
                  </template>
                </i18n-t>
              </p>

              <div
                v-if="item.error || showMessage(item)"
                class="space-y-2 rounded-md border border-error/20 bg-error/5 px-3 py-2"
              >
                <button
                  v-if="item.error"
                  type="button"
                  class="block w-full text-start text-sm text-error"
                  :aria-expanded="isExpanded(item._id, 'error')"
                  @click="toggleExpand(item._id, 'error')"
                >
                  <span
                    :class="
                      isExpanded(item._id, 'error')
                        ? 'whitespace-pre-wrap wrap-anywhere'
                        : 'line-clamp-2 wrap-anywhere'
                    "
                    >{{ item.error }}</span
                  >
                </button>

                <button
                  v-if="showMessage(item)"
                  type="button"
                  class="block w-full text-start text-sm text-error"
                  :aria-expanded="isExpanded(item._id, 'msg')"
                  @click="toggleExpand(item._id, 'msg')"
                >
                  <span
                    :class="
                      isExpanded(item._id, 'msg')
                        ? 'whitespace-pre-wrap wrap-anywhere'
                        : 'line-clamp-2 wrap-anywhere'
                    "
                    >{{ item.msg }}</span
                  >
                </button>
              </div>

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
                    v-if="!showThumbnails && (item.filename || isEmbedable(item.url))"
                    :text="t('common.playVideo')"
                  >
                    <UButton
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-play"
                      :aria-label="`${t('common.playVideo')}: ${item.title}`"
                      @click="playItem(item)"
                    />
                  </UTooltip>
                  <UButton
                    v-if="showRetryAction(item)"
                    color="neutral"
                    variant="outline"
                    size="sm"
                    icon="i-lucide-rotate-cw"
                    @click="() => retryItem(item, false)"
                  >
                    {{ t('common.retry') }}
                  </UButton>
                  <UButton
                    v-if="item.filename && canShareUrl"
                    color="neutral"
                    variant="outline"
                    size="sm"
                    icon="i-lucide-share"
                    @click="() => shareUrl(item)"
                  >
                    {{ t('common.share') }}
                  </UButton>
                  <UButton
                    v-if="item.filename"
                    color="neutral"
                    variant="outline"
                    size="sm"
                    icon="i-lucide-download"
                    external
                    :href="makeDownload(config, item)"
                    :download="item.filename.split('/').pop()"
                  >
                    {{ t('common.download') }}
                  </UButton>
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="sm"
                    icon="i-lucide-trash"
                    @click="() => removeItem(item)"
                  >
                    {{ config.app.remove_files ? t('common.remove') : t('common.clear') }}
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
                      :aria-label="`${t('common.actions')}: ${item.title}`"
                    />
                  </UDropdownMenu>
                </div>
              </div>
            </div>
          </article>
        </LateLoader>
      </div>

      <div v-if="!hasItems && !paginationInfo.isLoading" class="space-y-4">
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
          :description="t('history.empty')"
          class="py-10"
        />
      </div>

      <div v-if="paginationInfo.total_pages > 1" class="flex justify-end pt-2">
        <UPagination
          :page="paginationInfo.page"
          :total="paginationInfo.total"
          :items-per-page="paginationInfo.per_page"
          :disabled="paginationInfo.isLoading"
          show-edges
          :sibling-count="0"
          @update:page="
            (page) => load(page, { order: 'DESC', perPage: config.app.default_pagination })
          "
        />
      </div>
    </div>

    <UModal
      v-if="video_item"
      :open="videoOpen"
      :dismissible="true"
      :title="video_item?.title || t('history.player')"
      :ui="{ content: lightsOut ? 'sm:max-w-5xl shadow-2xl' : 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="handleVideoOpenChange"
    >
      <template #body>
        <LazyVideoPlayer
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="video_item"
          class="w-full"
          @closeModel="() => void requestCloseVideo()"
          @error="async (error: string) => await box.alert(error)"
          @playback-state-change="(playing: boolean) => (playingNow = playing)"
        />
      </template>
    </UModal>

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

    <ToolboxCreateModal
      v-if="toolboxSource !== null"
      :file="toolboxSource"
      @close="toolboxSource = null"
      @created="showToolboxJob"
    />
    <ToolboxJobModal v-if="toolboxJob" :id="toolboxJob" @close="toolboxJob = null" />

    <LazyGetInfo
      v-if="info_view.url"
      :link="info_view.url"
      :preset="info_view.preset"
      :cli="info_view.cli"
      :useUrl="info_view.useUrl"
      @closeModel="close_info"
    />
  </main>
</template>

<script setup lang="ts">
import { toRaw } from 'vue';
import ToolboxCreateModal from '~/components/ToolboxCreateModal.vue';
import ToolboxJobModal from '~/components/ToolboxJobModal.vue';
import { useStorage } from '@vueuse/core';
import { useConfirm } from '~/composables/useConfirm';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import { useDialog } from '~/composables/useDialog';
import { useAppSocket } from '~/composables/useAppSocket';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useHistoryState } from '~/composables/useHistoryState';
import { useHistoryNfo } from '~/composables/useHistoryNfo';
import { useWebShare } from '~/composables/useWebShare';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import {
  deepIncludes,
  formatBytes,
  formatTime,
  getBrowserUrl,
  getHistoryImage,
  getRemoteImage,
  getPath,
  isDownloadSkipped,
  makeDownload,
  request,
  uri,
  parse_api_error,
} from '~/utils';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import { mediaProfileLabel } from '~/utils/mediaProfile';
import { setSelected } from '~/utils/selection';
import { formatDateTime } from '~/utils/date';
import { usePageShell } from '~/composables/usePageShell';
import { useFormHandoff } from '~/composables/useFormHandoff';
import { useRangeSelection } from '~/composables/useRangeSelection';
import { taskSourceUrl } from '~/utils/taskDetails';
import type { ToolboxJob } from '~/types/toolbox';
const { locale, t } = useI18n();

const config = useYtpConfig();
const stateStore = useQueueState();
const socketStore = useAppSocket();
const toast = useNotification();
const box = useConfirm();
const { confirmDialog, promptDialog } = useDialog();
const { toggleExpand, isExpanded, expandClass } = useExpandableMeta();
const { canShare, shareUrl } = useWebShare();
const downloadFormHandoff = useFormHandoff<item_request>('download');
const toolboxSource = ref<string | null>(null);
const toolboxJob = ref<number | null>(null);
const showToolboxJob = (job: ToolboxJob): void => {
  toolboxSource.value = null;
  toolboxJob.value = job.id;
};
const {
  items: historyItems,
  pagination,
  isLoading,
  isLoaded,
  load,
  reload,
  remove,
  retry,
  rename,
  moveHandler,
} = useHistoryState();
const {
  isGenerating: isGeneratingNfo,
  generateNfo: generateNfoRequest,
  generateSelectedNfo,
} = useHistoryNfo();

const showThumbnails = useStorage<boolean>('show_thumbnail', true);
const show_popover = useStorage<boolean>('show_popover', true);

const pageShell = usePageShell('history');
const info_view = ref<{ url: string; preset: string; cli: string; useUrl: boolean }>({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
});
const query = ref('');
const showFilter = ref(false);
const selectedElms = ref<string[]>([]);
const masterSelectAll = ref(false);
const embed_url = ref('');
const video_item = ref<StoreItem | null>(null);
const playingNow = ref(false);
const lightsOut = computed(() => Boolean(video_item.value && playingNow.value));
const videoOpen = computed<boolean>({
  get: () => Boolean(video_item.value),
  set: (value: boolean) => {
    if (value) {
      return;
    }

    closeVideo();
  },
});
const paginationInfo = computed(() => ({
  ...pagination.value,
  isLoading: isLoading.value,
  isLoaded: isLoaded.value,
}));

const handleHistoryItemMoved = moveHandler();

onMounted(async () => {
  socketStore.on('item_moved', handleHistoryItemMoved);
  await load(1, { order: 'DESC', perPage: config.app.default_pagination });
});

onBeforeUnmount(() => {
  socketStore.off('item_moved', handleHistoryItemMoved);
});

watch(showFilter, () => {
  if (!showFilter.value) {
    query.value = '';
  }
});

const canShareUrl = computed(() => canShare());

const close_info = (): void => {
  info_view.value.url = '';
  info_view.value.preset = '';
  info_view.value.cli = '';
  info_view.value.useUrl = false;
};

const closeVideo = (): void => {
  playingNow.value = false;
  video_item.value = null;
};

const { handleOpenChange: handleVideoOpenChange, requestClose: requestCloseVideo } =
  useDirtyCloseGuard(videoOpen, {
    dirty: playingNow,
    preferenceKey: 'player',
    title: t('common.closePlayer'),
    message: t('common.closePlayerDesc'),
    confirmText: t('common.closePlayer'),
    cancelText: t('common.keepPlaying'),
    onDiscard: async () => {
      closeVideo();
    },
  });

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

const addNewDownload = async (): Promise<void> => {
  config.showForm = true;
  await nextTick();
  await navigateTo('/');
};

const toNewDownload = async (item: item_request | Partial<StoreItem>): Promise<void> => {
  if (!item) {
    return;
  }

  downloadFormHandoff.set(item as item_request);
  await navigateTo('/');
};

const filterItem = (item: StoreItem): boolean => {
  const normalizedQuery = query.value.trim().toLowerCase();

  if (!normalizedQuery) {
    return true;
  }

  return deepIncludes(item, normalizedQuery, new WeakSet());
};

const displayedItems = computed(() => historyItems.value.filter(filterItem));
const hasSelected = computed(() => selectedElms.value.length > 0);
const hasItems = computed(() => displayedItems.value.length > 0);
const displayedItemIds = computed(() => displayedItems.value.map((item) => item._id));
const rangeSelection = useRangeSelection(selectedElms, displayedItemIds);
const selectItem = (id: string, checked: boolean | 'indeterminate'): void => {
  selectedElms.value = setSelected(selectedElms.value, id, checked);
  rangeSelection.handleChange(id, new Event('change'));
};

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

const findHistoryItem = (itemId: string): StoreItem | null => {
  return historyItems.value.find((item) => item._id === itemId) ?? null;
};

const selectedDownloadableCount = computed(() =>
  selectedElms.value.reduce((count, itemId) => {
    const item = findHistoryItem(itemId);
    return item?.filename ? count + 1 : count;
  }, 0),
);
const retryIds = computed(() =>
  selectedElms.value.filter((id) => {
    const item = findHistoryItem(id);
    return item && item.status !== 'finished' && item.status !== 'skip';
  }),
);

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

const getItemPath = (item: StoreItem): string => getPath(config.app.download_path, item) || '';
const getItemBrowserUrl = (item: StoreItem): string =>
  getBrowserUrl(config.app.download_path, item);
const getItemTaskUrl = (item: StoreItem): string => taskSourceUrl(item.extras);
const playItem = (item: StoreItem): void => {
  if (item.filename) {
    video_item.value = item;
    return;
  }

  const embed = getEmbedable(item.url);
  if (embed) {
    embed_url.value = embed;
  }
};
const showRetryAction = (item: StoreItem): boolean =>
  !item.filename && item.status !== 'skip' && !isDownloadSkipped(item);

const hasIncomplete = computed(() =>
  historyItems.value.some((item) => item.status !== 'finished' && item.status !== 'skip'),
);
const hasCompleted = computed(() =>
  historyItems.value.some((item) => item.status === 'finished' || item.status === 'skip'),
);

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [
    [
      {
        label: t('common.download'),
        icon: 'i-lucide-download',
        disabled: !hasSelected.value || selectedDownloadableCount.value < 1,
        onSelect: () => void downloadSelected(),
      },
      {
        label: isGeneratingNfo.value ? t('common.generating') : t('common.generateNfo'),
        icon: 'i-lucide-file-code-2',
        disabled:
          !hasSelected.value || selectedDownloadableCount.value < 1 || isGeneratingNfo.value,
        onSelect: () => void generateNfoSelected(),
      },
      {
        label: t('common.retry'),
        icon: 'i-lucide-rotate-cw',
        disabled: retryIds.value.length < 1,
        onSelect: retrySelected,
      },
      {
        label: config.app.remove_files ? t('common.remove') : t('common.clear'),
        icon: 'i-lucide-trash',
        disabled: !hasSelected.value,
        onSelect: deleteSelectedItems,
      },
    ],
  ];

  const cleanupActions: Array<Record<string, unknown>> = [];

  if (hasCompleted.value) {
    cleanupActions.push({
      label: t('common.clearCompleted'),
      icon: 'i-lucide-circle-check-big',
      onSelect: clearCompleted,
    });
  }

  if (hasIncomplete.value) {
    cleanupActions.push(
      {
        label: t('common.clearIncomplete'),
        icon: 'i-lucide-circle-x',
        onSelect: clearIncomplete,
      },
      {
        label: t('common.retryIncomplete'),
        icon: 'i-lucide-rotate-cw',
        onSelect: retryIncomplete,
      },
    );
  }

  if (cleanupActions.length > 0) {
    groups.push(cleanupActions);
  }

  return groups;
});

const itemActionGroups = (item: StoreItem): Array<Array<Record<string, unknown>>> => {
  const groups: Array<Array<Record<string, unknown>>> = [];
  const mediaActions: Array<Record<string, unknown>> = [];

  if (item.filename) {
    if (item.status === 'finished') {
      mediaActions.push({
        label: t('toolbox.title'),
        icon: 'i-lucide-wrench',
        onSelect: () => {
          toolboxSource.value = getItemPath(item);
        },
      });
    }

    mediaActions.push({
      label: t('common.playVideo'),
      icon: 'i-lucide-play',
      onSelect: () => playItem(item),
    });

    if ('error' === item.status) {
      mediaActions.push({
        label: t('common.retryDownload'),
        icon: 'i-lucide-rotate-cw',
        onSelect: () => void retryItem(item, true),
      });
    }

    mediaActions.push({
      label: t('common.generateNfo'),
      icon: 'i-lucide-file-code-2',
      onSelect: () => void generateNfo(item),
    });

    mediaActions.push({
      label: t('common.renameFile'),
      icon: 'i-lucide-pencil',
      onSelect: () => void renameFile(item),
    });
  } else if (isEmbedable(item.url)) {
    mediaActions.push({
      label: t('common.playVideo'),
      icon: 'i-lucide-play',
      onSelect: () => playItem(item),
    });
  }

  if (mediaActions.length > 0) {
    groups.push(mediaActions);
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
    {
      label: t('common.addToDownloadForm'),
      icon: 'i-lucide-copy',
      onSelect: () => void retryItem(item, true),
    },
  ]);

  if (item.is_archivable && !item.is_archived) {
    groups.push([
      {
        label: t('common.addToArchive'),
        icon: 'i-lucide-archive',
        onSelect: () => void addArchiveDialog(item),
      },
    ]);
  }

  if (item.is_archivable && item.is_archived) {
    groups.push([
      {
        label: t('common.removeFromArchive'),
        icon: 'i-lucide-archive-x',
        onSelect: () => void removeFromArchiveDialog(item),
      },
    ]);
  }

  return groups;
};

const showMessage = (item: StoreItem): boolean => {
  if (!item?.msg || item.msg === item?.error) {
    return false;
  }

  return (item.msg?.length || 0) > 0;
};

const deleteSelectedItems = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noItemsSelected'));
    return;
  }

  let message = t('history.confirmActionCount', {
    action: config.app.remove_files ? t('common.remove') : t('common.clear'),
    count: selectedElms.value.length,
  });

  if (true === config.app.remove_files) {
    message += t('history.removeFilesWarning');
  }

  if (false === (await box.confirm(message))) {
    return;
  }

  await remove({ ids: [...selectedElms.value], removeFile: config.app.remove_files });
  selectedElms.value = [];
  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const clearCompleted = async (): Promise<void> => {
  const message = t('history.clearCompletedConfirm');

  if (false === (await box.confirm(message))) {
    return;
  }

  selectedElms.value = [];

  await remove({ status: 'finished,skip', removeFile: false });

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const clearIncomplete = async (): Promise<void> => {
  if (false === (await box.confirm(t('history.clearIncompleteConfirm')))) {
    return;
  }

  selectedElms.value = [];
  await remove({ status: '!finished', removeFile: false });
  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const setIcon = (item: StoreItem): string => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'i-lucide-ban';
    }

    if (!item.filename) {
      return 'i-lucide-triangle-alert';
    }

    if (item.extras?.is_premiere) {
      return 'i-lucide-star';
    }

    return item.is_live ? 'i-lucide-globe' : 'i-lucide-circle-check-big';
  }

  if ('error' === item.status) {
    return 'i-lucide-circle-x';
  }

  if ('cancelled' === item.status) {
    return 'i-lucide-circle-off';
  }

  if ('not_live' === item.status) {
    return item.extras?.is_premiere ? 'i-lucide-star' : 'i-lucide-headphones';
  }

  if ('skip' === item.status) {
    return 'i-lucide-ban';
  }

  return 'i-lucide-circle';
};

const setIconColor = (item: StoreItem): string => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'text-info';
    }

    if (!item.filename) {
      return 'text-warning';
    }

    return 'text-success';
  }

  if ('not_live' === item.status) {
    return 'text-info';
  }

  if ('cancelled' === item.status || 'skip' === item.status) {
    return 'text-warning';
  }

  if ('error' === item.status && item.filename) {
    return 'text-warning';
  }

  return 'text-error';
};

const setStatus = (item: StoreItem): string => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return t('history.downloadSkipped');
    }

    if (item.extras?.is_premiere) {
      return t('history.premiered');
    }

    return item.is_live ? t('history.streamed') : t('common.completed');
  }

  if ('error' === item.status) {
    if (item.filename) {
      return t('history.partialError');
    }

    return t('common.error');
  }

  if ('cancelled' === item.status) {
    return t('common.cancelled');
  }

  if ('not_live' === item.status) {
    if (item.extras?.is_premiere) {
      return t('history.premiere');
    }

    return t('common.live');
  }

  if ('skip' === item.status) {
    return t('common.skipped');
  }

  return item.status || t('common.unknown');
};

const retryIncomplete = async (): Promise<void> => {
  if (false === (await box.confirm(t('history.retryIncompleteConfirm')))) {
    return;
  }

  selectedElms.value = [];
  await retry({ status: '!finished,!skip' });
  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const retrySelected = async (): Promise<void> => {
  const ids = [...retryIds.value];
  if (ids.length < 1) {
    toast.error(t('common.noItemsSelected'));
    return;
  }

  const message = t('history.confirmActionCount', {
    action: t('common.retry'),
    count: ids.length,
  });
  if (false === (await box.confirm(message))) {
    return;
  }

  selectedElms.value = [];
  await retry({ ids });
  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const addArchiveDialog = async (item: StoreItem): Promise<void> => {
  const { status, value } = await confirmDialog({
    title: t('history.archiveTitle'),
    message: t('history.archiveConfirm', { title: item.title || item.id || item.url || '??' }),
    confirmText: t('history.archiveLabel'),
    confirmColor: 'warning',
    options: [{ key: 'remove_history', label: t('history.removeFromHistory') }],
  });

  if (!status) {
    return;
  }

  await archiveItem(item, value ?? undefined);
};

const archiveItem = async (item: StoreItem, opts = {}): Promise<void> => {
  try {
    const response = await request(`/api/history/${item._id}/archive`, { method: 'POST' });
    const data = await response.json();

    if (!response.ok) {
      toast.error(await parse_api_error(data));
      return;
    }

    toast.success(
      data.message ?? t('history.archived', { title: item.title || item.id || item.url || '??' }),
    );
  } catch (error: any) {
    console.error(error);
    return;
  }

  if ((opts as { remove_history?: boolean })?.remove_history) {
    await remove({ ids: [item._id], removeFile: false });
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const removeItem = async (item: StoreItem): Promise<void> => {
  const action = config.app.remove_files ? t('common.remove') : t('common.clear');
  const title = item.title || item.id || item.url || '??';
  const message =
    item.status === 'finished' && config.app.remove_files
      ? t('history.itemActionConfirmWithFiles', { action, title })
      : t('history.itemActionConfirm', { action, title });

  if (false === (await box.confirm(message))) {
    return;
  }

  await remove({ ids: [item._id], removeFile: config.app.remove_files });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((entry) => entry !== item._id);
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const retryItem = async (
  item: StoreItem,
  re_add: boolean = false,
  remove_file: boolean = false,
): Promise<void> => {
  if (!re_add) {
    await retry({ ids: [item._id] });
    await reload({ order: 'DESC', perPage: config.app.default_pagination });
    return;
  }

  const item_req: item_request = {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    cookies: item.cookies,
    template: item.template,
    cli: item?.cli,
    extras: toRaw(item?.extras || {}) ?? {},
    auto_start: item.auto_start,
  };

  await remove({ ids: [item._id], removeFile: remove_file });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((entry) => entry !== item._id);
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });

  if (true === re_add) {
    toast.info(t('common.itemAddedToForm'));
    await toNewDownload(item_req);
    return;
  }

  await stateStore.addDownload(item_req);
};

const onImgError = (event: Event, item: StoreItem): void => {
  const target = event.target as HTMLImageElement;
  const fallback = item ? getRemoteImage(item, false) || '' : '';
  const currentSrc = target.getAttribute('src') || '';

  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  if (fallback && currentSrc !== uri(fallback)) {
    target.src = uri(fallback);
    return;
  }

  target.src = '/images/placeholder.png';
};

const downloadSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noItemsSelected'));
    return;
  }

  const files_list: string[] = [];

  for (const itemId of selectedElms.value) {
    const item = findHistoryItem(itemId);

    if (!item?.filename) {
      continue;
    }

    files_list.push(item.folder ? item.folder + '/' + item.filename : item.filename);
  }

  selectedElms.value = [];

  try {
    const response = await request('/api/file/download', {
      method: 'POST',
      body: JSON.stringify(files_list),
    });
    const json = await response.json();

    if (!response.ok) {
      toast.error(json.error || t('common.failedStartDownload'));
      return;
    }

    const token = json.token;
    const body = document.querySelector('body');
    const link = document.createElement('a');
    link.href = uri(`/api/file/download/${token}`);
    link.setAttribute('target', '_blank');
    body?.appendChild(link);
    link.click();
    body?.removeChild(link);
  } catch (error: any) {
    console.error(error);
    toast.error(t('common.errorPrefix', { msg: error.message }));
  }
};

const removeFromArchiveDialog = async (item: StoreItem): Promise<void> => {
  const options = [
    { key: 'remove_history', label: t('history.removeFromHistory') },
    { key: 're_add', label: t('common.readdToForm') },
  ];

  if (config.app.remove_files) {
    options.push({ key: 'dont_remove_file', label: t('history.dontRemoveFiles') });
  }

  const { status, value } = await confirmDialog({
    title: t('history.removeFromArchiveTitle'),
    message: t('history.removedFromArchive', { title: item.title || item.id || item.url || '??' }),
    confirmText: t('common.remove'),
    confirmColor: 'error',
    options,
  });

  if (!status) {
    return;
  }

  await removeFromArchive(item, value ?? undefined);
};

const removeFromArchive = async (
  item: StoreItem,
  opts?: { re_add?: boolean; remove_history?: boolean; dont_remove_file?: boolean },
): Promise<void> => {
  try {
    const response = await request(`/api/history/${item._id}/archive`, { method: 'DELETE' });
    const data = await response.json();

    if (!response.ok) {
      toast.error(await parse_api_error(data));
      return;
    }

    toast.success(
      data.message ||
        t('history.removedFromArchive', { title: item.title || item.id || item.url || '??' }),
    );
  } catch (error: any) {
    console.error(error);
    toast.error(t('common.errorPrefix', { msg: error.message }));
    return;
  }

  let file_delete = config.app.remove_files;

  if (opts?.dont_remove_file) {
    file_delete = false;
  }

  if (opts?.re_add) {
    await retryItem(item, true, file_delete);
    return;
  }

  if (opts?.remove_history) {
    await remove({ ids: [item._id], removeFile: file_delete });
  }

  await reload({ order: 'DESC', perPage: config.app.default_pagination });
};

const isQueuedAnimation = (item: StoreItem): string => {
  if (!item?.status || 'not_live' !== item.status) {
    return '';
  }

  return item.live_in || item.extras?.live_in || item.extras?.release_in ? 'animate-spin' : '';
};

const generateNfoSelected = async (): Promise<void> => {
  if (isGeneratingNfo.value) {
    return;
  }

  const items = selectedElms.value
    .map((itemId) => findHistoryItem(itemId))
    .filter((item): item is StoreItem => Boolean(item?.filename));

  if (items.length < 1) {
    return;
  }

  const { status } = await confirmDialog({
    title: t('common.pleaseConfirm'),
    message: t('common.confirmActionSelected', {
      action: t('common.generateNfo'),
      count: items.length,
    }),
    confirmText: t('common.generateNfo'),
    confirmIcon: 'i-lucide-file-code-2',
  });

  if (!status) {
    return;
  }

  toast.info(t('common.generating'), { timeout: 2000 });
  const { failed } = await generateSelectedNfo(items);
  toast[failed ? 'error' : 'success'](
    t(failed ? 'common.failedGenerateNfo' : 'common.nfoGenerated'),
  );
};

const generateNfo = async (item: StoreItem): Promise<void> => {
  try {
    toast.info(t('common.generating'), { timeout: 2000 });
    const data = await generateNfoRequest(item);
    toast.success(data.message || t('common.nfoGenerated'));
  } catch (error: any) {
    if ('NfoResponseError' === error.name) {
      toast.error(error.message || t('common.failedGenerateNfo'));
      return;
    }

    toast.error(t('common.errorPrefix', { msg: error.message }));
  }
};

const renameFile = async (item: StoreItem): Promise<void> => {
  if (!item.filename) {
    return;
  }

  const currentName = item.filename.split('/').pop() || item.filename;
  const { status, value: newName } = await promptDialog({
    title: t('history.renameFileTitle'),
    message: t('files.renameItemDesc', { name: currentName }),
    initial: currentName,
    confirmText: t('common.rename'),
    cancelText: t('common.cancel'),
  });

  if (!status) {
    return;
  }

  const trimmedName = (newName || '').trim();
  if (!trimmedName || trimmedName === currentName) {
    return;
  }

  const success = await rename(item, trimmedName);
  if (success) {
    toast.success(t('common.renamed', { name: currentName }));
  }
};
</script>
