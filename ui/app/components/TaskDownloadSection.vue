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
        <UEmpty
          v-else-if="!items.length"
          icon="i-lucide-inbox"
          :title="empty"
          class="rounded-lg border border-dashed border-default bg-muted/10 py-8"
        />
        <div v-else class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <article
            v-for="item in items"
            :key="item._id"
            class="ytp-card w-full min-w-0 max-w-full overflow-hidden"
          >
            <div
              v-if="mode === 'queue' && activeStatuses.has(item.status)"
              class="p-4 pb-0 ytp-border-bottom-soft"
            >
              <div class="queue-progress rounded-md border border-default bg-muted/20">
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
            </div>

            <div class="p-4">
              <div class="flex min-w-0 flex-col gap-4 sm:flex-row">
                <figure
                  class="relative w-full shrink-0 overflow-hidden rounded-lg border border-default bg-muted/20 sm:w-52"
                >
                  <img
                    :src="thumbnail(item)"
                    :alt="item.title || $t('simple.videoThumbnail')"
                    loading="lazy"
                    class="aspect-video h-full w-full object-cover"
                    @error="useFallbackImage"
                  />
                  <span
                    v-if="duration(item)"
                    class="absolute top-2 right-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-medium text-white"
                  >
                    {{ duration(item) }}
                  </span>
                </figure>

                <div class="min-w-0 flex-1 space-y-3">
                  <div class="space-y-2">
                    <UTooltip :text="item.title || item.url">
                      <a
                        :href="item.url"
                        target="_blank"
                        rel="noreferrer"
                        class="block truncate text-sm font-semibold text-highlighted hover:underline"
                      >
                        {{ item.title || $t('simple.untitled') }}
                      </a>
                    </UTooltip>

                    <div class="flex flex-wrap items-center gap-2 text-xs">
                      <UBadge :color="statusColor(item)" variant="soft" size="sm" class="gap-1">
                        <UIcon
                          :name="statusIcon(item)"
                          :class="[
                            'size-3.5',
                            ['downloading', 'preparing', 'postprocessing'].includes(status(item))
                              ? 'animate-spin'
                              : '',
                          ]"
                        />
                        <span>{{ statusLabel(item) }}</span>
                      </UBadge>

                      <UBadge
                        v-if="item.extras?.retry_attempt && item.extras.retry_attempt > 1"
                        color="warning"
                        variant="soft"
                        size="sm"
                        icon="i-lucide-rotate-cw"
                      >
                        {{ $t('common.retryCount', { count: item.extras.retry_attempt }) }}
                      </UBadge>

                      <UTooltip v-if="item.datetime || item.timestamp" :text="formatDate(item)">
                        <time
                          class="inline-flex items-center rounded-full border border-default px-2 py-0.5 text-toned"
                          :datetime="String(item.datetime || item.timestamp)"
                          v-rtime="item.datetime || item.timestamp"
                        />
                      </UTooltip>
                    </div>
                  </div>

                  <p class="line-clamp-3 text-xs leading-5 text-toned wrap-break-word">
                    <span v-if="item.error || item.msg" class="text-error">
                      {{ item.error || item.msg }}
                    </span>
                    <template v-else>{{ item.description || $t('simple.noDescription') }}</template>
                  </p>

                  <div class="mt-auto flex flex-wrap items-center justify-end gap-2 pt-1">
                    <template v-if="mode === 'queue'">
                      <UButton
                        v-if="item.status === null && item.auto_start === false"
                        color="neutral"
                        variant="soft"
                        size="xs"
                        icon="i-lucide-play-circle"
                        @click="runQueue('start', item)"
                      >
                        {{ $t('common.start') }}
                      </UButton>
                      <UButton
                        v-if="item.status === null && queue.hasActive()"
                        color="neutral"
                        variant="soft"
                        size="xs"
                        icon="i-lucide-zap"
                        @click="runQueue('force', item)"
                      >
                        {{ $t('queue.forceStart') }}
                      </UButton>
                      <UButton
                        v-if="
                          item.status === null &&
                          queue.canPosition(item._id) &&
                          !queue.isFirst(item._id)
                        "
                        color="neutral"
                        variant="soft"
                        size="xs"
                        icon="i-lucide-arrow-up-to-line"
                        @click="position(item, 'front')"
                      >
                        {{ $t('queue.moveToFront') }}
                      </UButton>
                      <UButton
                        v-if="
                          item.status === null &&
                          queue.canPosition(item._id) &&
                          !queue.isLastPending(item._id)
                        "
                        color="neutral"
                        variant="soft"
                        size="xs"
                        icon="i-lucide-arrow-down-to-line"
                        @click="position(item, 'back')"
                      >
                        {{ $t('queue.moveToBack') }}
                      </UButton>
                      <UButton
                        v-if="item.status === null && item.auto_start === true"
                        color="neutral"
                        variant="soft"
                        size="xs"
                        icon="i-lucide-pause"
                        @click="runQueue('pause', item)"
                      >
                        {{ $t('common.pause') }}
                      </UButton>
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-x"
                        @click="runQueue('cancel', item)"
                      >
                        {{ item.is_live ? $t('common.stop') : $t('common.cancel') }}
                      </UButton>
                    </template>

                    <template v-else>
                      <UButton
                        v-if="downloadLink(item)"
                        color="primary"
                        variant="soft"
                        size="xs"
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
                        variant="soft"
                        size="xs"
                        icon="i-lucide-rotate-cw"
                        @click="requeue(item)"
                      >
                        {{ $t('simple.requeue') }}
                      </UButton>
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-trash"
                        @click="removeHistory(item)"
                      >
                        {{ $t('common.delete') }}
                      </UButton>
                    </template>
                  </div>
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
import type { Pagination } from '~/types/responses';
import type { ItemStatus, StoreItem } from '~/types/store';
import type { item_request } from '~/types/item';
import { formatDateTime } from '~/utils/date';
import { ag, formatTime, getHistoryImage, getImage, makeDownload, ucFirst } from '~/utils';
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
const statusColor = (item: StoreItem) =>
  (({
    completed: 'success',
    skipped: 'warning',
    failed: 'error',
    downloading: 'info',
    preparing: 'info',
    postprocessing: 'info',
    started: 'info',
    cancelled: 'neutral',
  })[status(item)] || 'neutral') as 'success' | 'warning' | 'error' | 'info' | 'neutral';
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
