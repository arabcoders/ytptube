<template>
  <section class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="flex items-center gap-2 text-sm font-semibold text-highlighted">
        <UIcon :name="icon" class="size-4 text-toned" />
        <span>{{ title }}</span>
      </h2>
      <div class="flex flex-wrap items-center justify-end gap-2">
        <UPagination
          v-if="!collapsed && pagination.total_pages > 1"
          :page="pagination.page"
          :total="pagination.total"
          :items-per-page="pagination.per_page"
          :disabled="loading"
          :sibling-count="0"
          show-edges
          @update:page="$emit('page', $event)"
        />
        <UBadge color="neutral" variant="soft" size="sm">{{ total }}</UBadge>
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          :icon="collapsed ? 'i-lucide-chevron-right' : 'i-lucide-chevron-down'"
          square
          :aria-label="title"
          :aria-expanded="!collapsed"
          :aria-controls="sectionId"
          @click="collapsed = !collapsed"
        />
      </div>
    </div>
    <Transition name="section-collapse">
      <div v-if="!collapsed" :id="sectionId" class="space-y-3 overflow-hidden">
        <UAlert
          v-if="error"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          :description="error"
        />
        <UAlert
          v-else-if="loading"
          color="info"
          variant="soft"
          icon="i-lucide-loader-circle"
          :ui="{ icon: 'animate-spin' }"
          :title="$t('common.loading')"
        />
        <UEmpty v-else-if="!items.length" icon="i-lucide-inbox" :title="empty" class="py-8" />
        <div v-else class="ytp-card divide-y divide-default">
          <article
            v-for="item in items"
            :key="item._id"
            class="grid min-w-0 gap-4 p-4 sm:p-5 xl:grid-cols-[13.75rem_minmax(0,1fr)]"
          >
            <div class="min-w-0 space-y-3 xl:col-span-2">
              <h3 class="min-w-0 text-base font-semibold text-highlighted">
                <UTooltip :text="item.title || item.url" :content="{ align: 'start' }">
                  <a
                    :href="item.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="line-clamp-2 w-fit max-w-full wrap-anywhere hover:text-primary hover:underline"
                  >
                    <bdi>{{ item.title || $t('simple.untitled') }}</bdi>
                  </a>
                </UTooltip>
              </h3>
              <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-toned">
                <span class="inline-flex items-center gap-1.5">
                  <UIcon
                    :name="statusIcon(item)"
                    :class="[
                      'size-4 shrink-0',
                      statusClass(item),
                      ['started', 'preparing', 'postprocessing'].includes(status(item))
                        ? 'animate-spin'
                        : '',
                    ]"
                    aria-hidden="true"
                  />
                  {{ statusLabel(item) }}
                </span>
                <span
                  v-if="item.extras?.retry_attempt && item.extras.retry_attempt > 1"
                  class="inline-flex items-center gap-1.5 text-warning"
                >
                  <UIcon name="i-lucide-rotate-cw" class="size-3.5 shrink-0" aria-hidden="true" />
                  {{ $t('common.retryCount', { count: item.extras.retry_attempt }) }}
                </span>
              </div>
            </div>

            <figure
              v-if="showThumbnails"
              class="aspect-video w-full max-w-full self-start overflow-hidden rounded-lg border border-default bg-muted/20 sm:w-55"
            >
              <img
                :src="thumbnail(item)"
                alt=""
                loading="lazy"
                class="size-full object-cover"
                @error="useFallbackImage"
              />
            </figure>

            <div class="min-w-0 space-y-4" :class="{ 'xl:col-span-2': !showThumbnails }">
              <div
                v-if="mode === 'queue' && activeStatuses.has(item.status)"
                class="queue-progress rounded-md border border-default bg-muted/20"
              >
                <div
                  class="queue-progress__bar bg-success/35"
                  :style="{ width: progressWidth(item) }"
                ></div>
                <div class="queue-progress__label">
                  <UIcon
                    v-if="progressIcon(item)"
                    :name="progressIcon(item)"
                    :class="[
                      'me-1 size-4',
                      progressIcon(item) === 'i-lucide-settings-2' ? 'animate-spin' : '',
                    ]"
                  />
                  <span>{{ progressLabel(item) }}</span>
                </div>
              </div>
              <dl class="grid min-w-0 grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
                <div v-if="item.datetime || item.timestamp" class="min-w-0 space-y-1">
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon name="i-lucide-clock-3" class="size-3.5 shrink-0" aria-hidden="true" />
                    {{ $t('common.created') }}
                  </dt>
                  <dd>
                    <UTooltip :text="formatDate(item)">
                      <time
                        :datetime="String(item.datetime || item.timestamp)"
                        v-rtime="item.datetime || item.timestamp"
                      />
                    </UTooltip>
                  </dd>
                </div>
                <div v-if="duration(item)" class="min-w-0 space-y-1">
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon name="i-lucide-timer" class="size-3.5 shrink-0" aria-hidden="true" />
                    {{ $t('queue.duration') }}
                  </dt>
                  <dd class="tabular-nums">{{ duration(item) }}</dd>
                </div>
                <div v-if="item.file_size" class="min-w-0 space-y-1">
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon
                      name="i-lucide-hard-drive"
                      class="size-3.5 shrink-0"
                      aria-hidden="true"
                    />
                    {{ $t('common.size') }}
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
                    {{ $t('common.presetLabel') }}
                  </dt>
                  <dd class="wrap-anywhere">{{ item.preset || config.app.default_preset }}</dd>
                </div>
                <div
                  v-if="getPath(config.app.download_path, item)"
                  class="min-w-0 space-y-1 sm:flex-1"
                >
                  <dt class="flex items-center gap-1.5 text-xs text-muted">
                    <UIcon
                      name="i-lucide-folder-output"
                      class="size-3.5 shrink-0"
                      aria-hidden="true"
                    />
                    {{ $t('common.downloadPath') }}
                  </dt>
                  <dd class="flex min-w-0 items-start gap-2 text-xs">
                    <NuxtLink
                      v-if="getBrowserUrl(config.app.download_path, item)"
                      :to="getBrowserUrl(config.app.download_path, item)"
                      class="min-w-0 flex-1 py-0.5 font-mono hover:text-primary hover:underline"
                    >
                      <bdi dir="ltr" :class="expandClass(item._id, 'path')">
                        {{ getPath(config.app.download_path, item) }}
                      </bdi>
                    </NuxtLink>
                    <bdi
                      v-else
                      dir="ltr"
                      class="min-w-0 flex-1 py-0.5 font-mono"
                      :class="expandClass(item._id, 'path')"
                    >
                      {{ getPath(config.app.download_path, item) }}
                    </bdi>
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="xs"
                      :icon="
                        isExpanded(item._id, 'path') ? 'i-lucide-minimize-2' : 'i-lucide-maximize-2'
                      "
                      :aria-label="$t('common.downloadPath')"
                      :aria-expanded="isExpanded(item._id, 'path')"
                      @click="toggleExpand(item._id, 'path')"
                    />
                  </dd>
                </div>
              </dl>
              <button
                v-if="item.error || item.msg"
                type="button"
                class="block w-full text-start text-sm text-error"
                @click="toggleExpand(item._id, 'message')"
              >
                <span :class="expandClass(item._id, 'message')">{{ item.error || item.msg }}</span>
              </button>
              <div class="flex flex-wrap items-center justify-between gap-3">
                <UPopover
                  v-if="showPopover && item.description"
                  :content="{ side: 'bottom', align: 'start', sideOffset: 8 }"
                  :ui="{ content: 'shell-surface max-w-[calc(100vw-2rem)] bg-transparent' }"
                >
                  <UButton color="neutral" variant="outline" size="xs" icon="i-lucide-info">
                    {{ $t('common.description') }}
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
                  <template v-if="mode === 'queue'">
                    <UButton
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-circle-off"
                      @click="runQueue('cancel', item)"
                    >
                      {{ item.is_live ? $t('common.stopStream') : $t('common.cancel') }}
                    </UButton>
                    <UButton
                      v-if="item.status === null && item.auto_start === false"
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-circle-play"
                      @click="runQueue('start', item)"
                    >
                      {{ $t('common.start') }}
                    </UButton>
                    <UButton
                      v-if="item.status === null && item.auto_start === true"
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-pause"
                      @click="runQueue('pause', item)"
                    >
                      {{ $t('common.pause') }}
                    </UButton>
                    <UDropdownMenu
                      v-if="queueActions(item).length"
                      :items="queueActions(item)"
                      :modal="false"
                      :content="{ align: 'end' }"
                    >
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="sm"
                        icon="i-lucide-ellipsis"
                        square
                        :aria-label="`${$t('common.actions')}: ${item.title}`"
                      />
                    </UDropdownMenu>
                  </template>

                  <template v-else>
                    <UButton
                      v-if="downloadLink(item)"
                      color="primary"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-download"
                      external
                      :href="downloadLink(item)"
                      :download="downloadName(item)"
                    >
                      {{ $t('common.download') }}
                    </UButton>
                    <UButton
                      v-if="!item.filename"
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-rotate-cw"
                      @click="requeue(item)"
                    >
                      {{ $t('simple.requeue') }}
                    </UButton>
                    <UButton
                      color="neutral"
                      variant="outline"
                      size="sm"
                      icon="i-lucide-trash"
                      @click="removeHistory(item)"
                    >
                      {{ $t('common.delete') }}
                    </UButton>
                  </template>
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import { useStorage } from '@vueuse/core';
import type { Pagination } from '~/types/responses';
import type { ItemStatus, StoreItem } from '~/types/store';
import type { item_request } from '~/types/item';
import { formatDateTime } from '~/utils/date';
import {
  ag,
  formatBytes,
  formatTime,
  getBrowserUrl,
  getHistoryImage,
  getImage,
  getPath,
  makeDownload,
  ucFirst,
} from '~/utils';
import { normalizeDownloadStatus } from '~/utils/taskDetails';

const props = defineProps<{
  title: string;
  empty: string;
  icon: string;
  mode: 'queue' | 'history';
  items: StoreItem[];
  pagination: Pagination;
  loading: boolean;
  error: string;
}>();
const emit = defineEmits<{ page: [page: number]; refresh: [] }>();
const { t, locale } = useI18n();
const config = useYtpConfig();
const queue = useQueueState();
const history = useHistoryState();
const { toggleExpand, expandClass, isExpanded } = useExpandableMeta();
const showThumbnails = useStorage<boolean>('show_thumbnail', true);
const showPopover = useStorage<boolean>('show_popover', true);
const collapsed = ref(false);
const sectionId = computed(() => `task-${props.mode}-section`);
const total = computed(() => props.pagination.total);
const activeStatuses = new Set<ItemStatus>([
  null,
  'started',
  'preparing',
  'downloading',
  'postprocessing',
]);
const status = (item: StoreItem) => normalizeDownloadStatus(item.status, item.download_skipped);
const statusLabel = (item: StoreItem) => {
  const value = status(item);
  const labels: Record<string, string> = {
    queued: t('common.queued'),
    completed: t('common.completed'),
    skipped: t('common.skipped'),
    failed: item.filename ? t('history.partialError') : t('common.error'),
    downloading: t('common.downloading'),
    preparing: t('queue.preparing'),
    postprocessing: t('queue.postProcessing'),
    started: t('common.starting'),
    cancelled: t('common.cancelled'),
  };
  return labels[value] || ucFirst(value.replace(/_/g, ' '));
};
const statusIcon = (item: StoreItem) =>
  ({
    completed: 'i-lucide-circle-check',
    skipped: 'i-lucide-circle-slash',
    failed: 'i-lucide-triangle-alert',
    downloading: 'i-lucide-download',
    preparing: 'i-lucide-loader-circle',
    postprocessing: 'i-lucide-settings-2',
    started: 'i-lucide-loader-circle',
    queued: 'i-lucide-hourglass',
    cancelled: 'i-lucide-circle-x',
  })[status(item)] || 'i-lucide-circle-question-mark';
const statusClass = (item: StoreItem): string =>
  ({
    completed: 'text-success',
    skipped: 'text-warning',
    failed: 'text-error',
    downloading: 'text-info',
    preparing: 'text-info',
    postprocessing: 'text-info',
    started: 'text-info',
    cancelled: 'text-toned',
  })[status(item)] || 'text-toned';
const formatDate = (item: StoreItem) =>
  formatDateTime(item.datetime || item.timestamp, locale.value);
const thumbnail = (item: StoreItem) =>
  props.mode === 'history'
    ? getHistoryImage(item)
    : getImage(config.app.download_path || '/downloads', item);
const duration = (item: StoreItem): string => {
  const value = item.extras?.duration;
  return typeof value === 'number' && value > 0 ? formatTime(value) : '';
};
const progressWidth = (item: StoreItem): string => {
  if (!item.auto_start || (item.status === null && config.paused)) return '0%';
  if (['postprocessing', 'started', 'preparing'].includes(String(item.status))) return '100%';
  if (!item.percent || item.is_live) return '100%';
  return `${item.percent.toFixed(2)}%`;
};
const progressLabel = (item: StoreItem): string => {
  if (!item.auto_start) return t('queue.manualStart');
  if (item.status === null && config.paused) return t('queue.globalPause');
  if (item.status === 'started') return t('common.starting');
  if (item.status === 'postprocessing')
    return item.postprocessor
      ? t('queue.ppLabel', { pp: item.postprocessor })
      : t('queue.postProcessing');
  if (item.status === 'preparing')
    return ag(item, 'extras.external_downloader')
      ? t('queue.externalDownloader')
      : t('queue.preparing');
  if (item.status !== null && item.is_live && !item.speed) return t('queue.recordingLive');

  let value = '';
  if (item.status !== null)
    value += item.percent && !item.is_live ? `${item.percent.toFixed(2)}%` : t('common.live');
  value += item.speed ? ` - ${formatSpeed(item.speed)}` : t('queue.waiting');
  if (item.status !== null && item.eta) value += ` - ${formatEta(item.eta)}`;
  return value;
};
const progressIcon = (item: StoreItem): string => {
  if (item.status !== null && item.is_live && !item.speed) return 'i-lucide-loader-circle';
  return item.status === 'postprocessing' ? 'i-lucide-settings-2' : '';
};
const formatSpeed = (value: number): string => {
  if (!value) return `0 ${t('common.kib')}${t('common.perSec')}`;
  const units = ['bytes', 'kib', 'mib', 'gib', 'tib', 'pib', 'eib', 'zib', 'yib'] as const;
  const index = Math.floor(Math.log(value) / Math.log(1024));
  const speed = Number((value / 1024 ** index).toFixed(2));
  return `${speed} ${t(`common.${units[index]}`)}${t('common.perSec')}`;
};
const formatEta = (value: number): string => {
  if (!value) return t('common.live');
  if (value < 60) return `${Math.round(value)}${t('common.secAbbr')}`;
  if (value < 3600)
    return `${Math.floor(value / 60)}${t('common.minAbbr')} ${Math.round(value % 60)}${t('common.secAbbr')}`;
  const hours = Math.floor(value / 3600);
  const minutes = value % 3600;
  return `${hours}${t('common.hourAbbr')} ${Math.floor(minutes / 60)}${t('common.minAbbr')} ${Math.round(minutes % 60)}${t('common.secAbbr')}`;
};
const useFallbackImage = (event: Event): void => {
  const image = event.target as HTMLImageElement;
  if (!image.src.endsWith('/images/placeholder.png')) image.src = '/images/placeholder.png';
};
const runQueue = async (
  action: 'start' | 'force' | 'pause' | 'cancel',
  item: StoreItem,
): Promise<void> => {
  const actions = {
    start: queue.startItems,
    force: queue.forceStartItems,
    pause: queue.pauseItems,
    cancel: queue.cancelItems,
  };
  await actions[action]([item._id]);
  emit('refresh');
};
const downloadLink = (item: StoreItem): string =>
  item.filename ? makeDownload(config.app, item) : '';
const position = async (item: StoreItem, target: 'front' | 'back'): Promise<void> => {
  await queue.positionItems([item._id], target);
  emit('refresh');
};
const queueActions = (item: StoreItem): DropdownMenuItem[] => {
  if (item.status !== null) return [];
  const actions: DropdownMenuItem[] = [];
  if (queue.hasActive())
    actions.push({
      label: t('queue.forceStart'),
      icon: 'i-lucide-zap',
      onSelect: () => void runQueue('force', item),
    });
  if (queue.canPosition(item._id)) {
    if (!queue.isFirst(item._id))
      actions.push({
        label: t('queue.moveToFront'),
        icon: 'i-lucide-arrow-up-to-line',
        onSelect: () => void position(item, 'front'),
      });
    if (!queue.isLastPending(item._id))
      actions.push({
        label: t('queue.moveToBack'),
        icon: 'i-lucide-arrow-down-to-line',
        onSelect: () => void position(item, 'back'),
      });
  }
  return actions;
};
const downloadName = (item: StoreItem): string =>
  item.filename?.split('/').pop() || t('common.download');
const requeue = async (item: StoreItem): Promise<void> => {
  const data: item_request = {
    url: item.url,
    preset: item.preset || config.app.default_preset,
    folder: item.folder,
    template: item.template,
    cookies: item.cookies,
    cli: item.cli,
    auto_start: item.auto_start ?? true,
    extras: JSON.parse(JSON.stringify(item.extras || {})),
  };
  await history.remove({ ids: [item._id], removeFile: false });
  await queue.addDownload(data);
  emit('refresh');
};
const removeHistory = async (item: StoreItem): Promise<void> => {
  await history.remove({ ids: [item._id], removeFile: config.app.remove_files });
  emit('refresh');
};
</script>
