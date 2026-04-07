<template>
  <div
    class="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col gap-4 px-3 py-4 sm:px-4 sm:py-5"
  >
    <div
      class="transition-transform duration-300"
      :class="{
        'lg:-translate-x-72': settingsOpen,
      }"
    >
      <div class="mx-auto w-full transition-all duration-300" :class="formContainerClass">
        <UPageCard variant="outline" :ui="formCardUi">
          <template #body>
            <form autocomplete="off" class="space-y-4" @submit.prevent="addDownload">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 space-y-1">
                  <div class="flex items-center gap-2 text-base font-semibold text-highlighted">
                    <UIcon name="i-lucide-link" class="size-4 text-toned" />
                    <span>{{
                      isMobile ? 'What would you like to download?' : greetingMessage
                    }}</span>
                  </div>
                </div>

                <div class="flex shrink-0 items-center gap-1">
                  <UTooltip v-if="!socketStore.isConnected" text="Reload queue">
                    <UButton
                      color="info"
                      variant="ghost"
                      size="sm"
                      icon="i-lucide-refresh-cw"
                      :loading="isRefreshing"
                      :disabled="isRefreshing"
                      square
                      @click="() => void refreshQueue()"
                    />
                  </UTooltip>

                  <UTooltip text="Toggle color mode">
                    <UColorModeButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      aria-label="Toggle color mode"
                    />
                  </UTooltip>

                  <UTooltip text="WebUI Settings">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      icon="i-lucide-settings-2"
                      square
                      @click="$emit('show_settings')"
                    />
                  </UTooltip>
                </div>
              </div>

              <UAlert
                v-if="!socketStore.isConnected"
                color="warning"
                variant="soft"
                icon="i-lucide-plug-zap"
                title="Realtime connection unavailable"
                description="Downloads are disabled until the socket reconnects."
              />

              <div class="flex flex-col gap-2 sm:flex-row">
                <UTooltip :text="showExtras ? 'Hide extra options' : 'Show extra options'">
                  <UButton
                    type="button"
                    color="info"
                    variant="outline"
                    size="lg"
                    :icon="showExtras ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                    class="justify-center sm:w-12"
                    :disabled="addInProgress"
                    @click="showExtras = !showExtras"
                  />
                </UTooltip>

                <UInput
                  id="download-url"
                  v-model="formUrl"
                  type="url"
                  placeholder="https://..."
                  size="lg"
                  required
                  :disabled="isFormDisabled"
                  class="w-full"
                  :ui="urlInputUi"
                />

                <UButton
                  type="submit"
                  color="primary"
                  size="lg"
                  icon="i-lucide-plus"
                  :loading="addInProgress"
                  :disabled="isFormDisabled || !formUrl.trim()"
                  class="justify-center sm:min-w-28"
                >
                  Add
                </UButton>
              </div>

              <div v-if="showExtras" class="space-y-3 border-t border-default pt-4">
                <UFormField label="Preset" :ui="fieldUi" class="w-full">
                  <template #label>
                    <span class="inline-flex items-center gap-2 font-semibold">
                      <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
                      <span>Preset</span>
                    </span>
                  </template>

                  <USelect
                    id="preset"
                    v-model="formPreset"
                    :items="presetItems"
                    value-key="value"
                    label-key="label"
                    size="lg"
                    class="w-full"
                    :ui="selectUi"
                    :disabled="isFormDisabled"
                    placeholder="Select preset"
                  />
                </UFormField>

                <div
                  v-if="configStore.dl_fields.length > 0"
                  class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
                >
                  <DLInput
                    id="force_download"
                    v-model="dlFields['--no-download-archive']"
                    type="bool"
                    label="Force download"
                    icon="i-lucide-download"
                    :disabled="isFormDisabled"
                    description="Ignore archive and re-download."
                    compact
                  />

                  <DLInput
                    v-for="(fi, index) in sortedDLFields"
                    :id="fi?.id || `dlf-${index}`"
                    :key="fi.id || `dlf-${index}`"
                    v-model="dlFields[fi.field]"
                    :type="fi.kind"
                    :description="fi.description"
                    :label="fi.name"
                    :icon="fi.icon"
                    :field="fi.field"
                    :disabled="isFormDisabled"
                    compact
                  />
                </div>
              </div>
            </form>
          </template>
        </UPageCard>
      </div>
    </div>

    <Transition name="queue-fade">
      <section v-if="hasAnyItems" class="w-full space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-list-video" class="size-4 text-toned" />
              <span>Queue and history</span>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <UBadge color="info" variant="soft" size="sm">Queue {{ queueItems.length }}</UBadge>
            <UBadge color="neutral" variant="soft" size="sm"
              >History {{ historyEntries.length }}</UBadge
            >
          </div>
        </div>

        <TransitionGroup name="queue-card" tag="div" class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <UCard
            v-for="entry in displayItems"
            :key="entry.item._id"
            class="w-full min-w-0 max-w-full overflow-hidden border bg-default"
            :ui="queueCardUi"
          >
            <template #header>
              <div
                v-if="entry.source === 'queue' && shouldShowProgress(entry.item)"
                class="space-y-2"
              >
                <div class="flex flex-wrap items-center justify-between gap-2 text-xs text-toned">
                  <span class="font-medium text-highlighted">{{ updateProgress(entry.item) }}</span>
                  <span>{{ getProgressWidth(entry.item) }}</span>
                </div>

                <div class="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    class="h-full rounded-full bg-primary transition-[width] duration-300"
                    :style="{ width: getProgressWidth(entry.item) }"
                  />
                </div>
              </div>
            </template>

            <div class="flex min-w-0 flex-col gap-4 sm:flex-row">
              <button
                type="button"
                class="group relative block w-full shrink-0 overflow-hidden rounded-lg border border-default bg-muted/20 sm:w-52"
                :class="{ 'cursor-pointer': canOpenPlayer(entry.item) }"
                @click="openPlayer(entry.item)"
              >
                <img
                  :src="resolveThumbnail(entry)"
                  :alt="entry.item.title || 'Video thumbnail'"
                  loading="lazy"
                  class="aspect-video h-full w-full object-cover"
                  @error="onImgError"
                />

                <span
                  v-if="getDurationLabel(entry.item)"
                  class="absolute top-2 right-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-medium text-white"
                >
                  {{ getDurationLabel(entry.item) }}
                </span>

                <span
                  v-if="entry.item.filename || isEmbedable(entry.item.url)"
                  class="absolute inset-0 flex items-center justify-center bg-black/0 text-white transition group-hover:bg-black/45"
                >
                  <span
                    class="rounded-full border-2 border-white/90 bg-black/35 p-3"
                    :class="{
                      'text-error': isEmbedable(entry.item.url) && !entry.item.filename,
                    }"
                  >
                    <UIcon name="i-lucide-play" class="size-5" />
                  </span>
                </span>
              </button>

              <div class="min-w-0 flex-1 space-y-3">
                <div class="space-y-2">
                  <UTooltip :text="entry.item.title">
                    <a
                      :href="entry.item.url"
                      target="_blank"
                      rel="noreferrer"
                      class="block truncate text-sm font-semibold text-highlighted hover:underline"
                    >
                      {{ entry.item.title || 'Untitled' }}
                    </a>
                  </UTooltip>

                  <div class="flex flex-wrap items-center gap-2 text-xs">
                    <UBadge :color="getSourceColor(entry)" variant="soft" size="sm">
                      {{ getSourceLabel(entry) }}
                    </UBadge>

                    <UBadge :color="getStatusColor(entry.item)" variant="soft" size="sm">
                      {{ getStatusLabel(entry.item) }}
                    </UBadge>

                    <span
                      class="inline-flex items-center rounded-full border border-default px-2 py-0.5 text-toned"
                      :date-datetime="entry.item.datetime"
                      v-rtime="entry.item.datetime"
                    />
                  </div>
                </div>

                <p class="line-clamp-3 text-xs leading-5 text-toned wrap-break-word">
                  <template v-if="entry.item.error || showMessage(entry.item)">
                    <template v-if="entry.item.error">
                      <span class="text-error">{{ entry.item.error }}</span>
                    </template>
                    <template v-if="showMessage(entry.item)">
                      <span class="text-error">{{ entry.item.msg }}</span>
                    </template>
                  </template>
                  <template v-else>
                    {{ getDescription(entry.item) || 'No description available.' }}
                  </template>
                </p>

                <div class="mt-auto flex flex-wrap items-center justify-end gap-2 pt-1">
                  <template v-if="entry.source === 'queue'">
                    <UButton
                      v-if="canStart(entry.item)"
                      color="success"
                      variant="soft"
                      size="xs"
                      icon="i-lucide-play-circle"
                      @click="() => void startQueueItem(entry.item)"
                    >
                      Start
                    </UButton>

                    <UButton
                      v-if="canPause(entry.item)"
                      color="warning"
                      variant="soft"
                      size="xs"
                      icon="i-lucide-pause"
                      @click="() => void pauseQueueItem(entry.item)"
                    >
                      Pause
                    </UButton>

                    <UButton
                      color="error"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-x"
                      @click="() => void cancelDownload(entry.item)"
                    >
                      Cancel
                    </UButton>
                  </template>

                  <template v-else>
                    <UButton
                      v-if="getDownloadLink(entry.item)"
                      color="primary"
                      variant="soft"
                      size="xs"
                      icon="i-lucide-download"
                      external
                      :href="getDownloadLink(entry.item)"
                      :download="getDownloadName(entry.item)"
                    >
                      Download
                    </UButton>

                    <UButton
                      v-if="!entry.item.filename"
                      color="info"
                      variant="soft"
                      size="xs"
                      icon="i-lucide-rotate-cw"
                      @click="() => void requeueItem(entry.item)"
                    >
                      Requeue
                    </UButton>

                    <UButton
                      color="error"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-trash"
                      @click="() => void deleteHistoryItem(entry.item)"
                    >
                      Delete
                    </UButton>
                  </template>
                </div>
              </div>
            </div>
          </UCard>
        </TransitionGroup>

        <div
          v-if="paginationInfo.isLoaded && paginationInfo.page < paginationInfo.total_pages"
          ref="loadMoreTrigger"
          class="flex justify-center py-2"
        >
          <div v-if="paginationInfo.isLoading" class="flex items-center gap-2 text-sm text-toned">
            <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin text-info" />
            <span>Loading more items...</span>
          </div>
        </div>
      </section>
    </Transition>

    <UAlert
      v-if="!hasAnyItems"
      color="neutral"
      variant="soft"
      icon="i-lucide-inbox"
      title="No queue or history items"
      description="Add a URL to get started."
    />

    <UModal
      v-if="videoItem"
      :open="Boolean(videoItem)"
      title="Video"
      :dismissible="true"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && closePlayer()"
    >
      <template #body>
        <VideoPlayer
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="videoItem"
          class="w-full"
          @closeModel="closePlayer"
          @error="async (error: string) => await box.alert(error)"
        />
      </template>
    </UModal>

    <UModal
      v-if="embedUrl"
      :open="Boolean(embedUrl)"
      title="Embed"
      :dismissible="true"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && closePlayer()"
    >
      <template #body>
        <EmbedPlayer :url="embedUrl" @closeModel="closePlayer" />
      </template>
    </UModal>

    <ClientOnly>
      <Dialog />
    </ClientOnly>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, toRef, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useIntersectionObserver, useStorage } from '@vueuse/core';
import type { item_request } from '~/types/item';
import type { ItemStatus, StoreItem } from '~/types/store';
import { useNotification } from '~/composables/useNotification';
import { useConfigStore } from '~/stores/ConfigStore';
import { useSocketStore } from '~/stores/SocketStore';
import { useStateStore } from '~/stores/StateStore';
import EmbedPlayer from '~/components/EmbedPlayer.vue';
import { isEmbedable, getEmbedable } from '~/utils/embedable';
import {
  ag,
  encodePath,
  formatTime,
  makeDownload,
  request,
  stripPath,
  ucFirst,
  uri,
} from '~/utils';

defineEmits<{ (e: 'show_settings'): void }>();

withDefaults(
  defineProps<{
    settingsOpen?: boolean;
  }>(),
  {
    settingsOpen: false,
  },
);

const configStore = useConfigStore();
const stateStore = useStateStore();
const socketStore = useSocketStore();
const toast = useNotification();
const dlFields = useStorage<Record<string, any>>('dl_fields', {});
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const isMobile = useMediaQuery({ maxWidth: 1024 });
const box = useConfirm();

const app = toRef(configStore, 'app');
const paused = toRef(configStore, 'paused');
const presets = toRef(configStore, 'presets');
const { selectItems: presetItems } = usePresetOptions(presets);
const { queue, history } = storeToRefs(stateStore);

const embedUrl = ref('');
const videoItem = ref<StoreItem | null>(null);
const loadMoreTrigger = ref<HTMLElement | null>(null);

const formUrl = ref('');
const formPreset = ref(app.value.default_preset || '');
const addInProgress = ref(false);
const showExtras = ref(false);
const isRefreshing = ref(false);

const DEFAULT_PAGE_SIZE = 12;
const downloadingStatuses: ReadonlySet<ItemStatus | null> = new Set([
  'downloading',
  'postprocessing',
  'preparing',
]);

type DisplayEntry = { item: StoreItem; source: 'queue' | 'history' };

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
};

const formCardUi = {
  root: 'w-full border bg-default',
  container: 'w-full p-4 sm:p-5',
  wrapper: 'w-full items-stretch',
  body: 'w-full',
};

const queueCardUi = {
  root: 'w-full',
  header: 'p-4 pb-0',
  body: 'p-4',
};

const urlInputUi = {
  root: 'w-full',
  base: 'bg-elevated/60 ring-default focus-visible:ring-primary',
};

const selectUi = {
  base: 'w-full',
};

const isFormDisabled = computed(() => !socketStore.isConnected || addInProgress.value);

const formContainerClass = computed(() => {
  if (queueItems.value.length === 0 && historyEntries.value.length === 0) {
    return 'max-w-2xl simple-form-center';
  }

  return 'max-w-full';
});

const paginationInfo = computed(() => stateStore.getPagination());

const queueItems = computed<StoreItem[]>(() =>
  Object.values(queue.value ?? {})
    .slice()
    .sort((a, b) => (b.timestamp ?? 0) - (a.timestamp ?? 0)),
);

const historyEntries = computed<StoreItem[]>(() => {
  const items = Object.values(history.value ?? {});
  return items
    .slice()
    .sort((a, b) => new Date(b.datetime).getTime() - new Date(a.datetime).getTime());
});

const displayItems = computed<DisplayEntry[]>(() => [
  ...queueItems.value
    .filter((item) => isDownloading(item.status))
    .map((item) => ({ item, source: 'queue' as const })),
  ...queueItems.value
    .filter((item) => !isDownloading(item.status))
    .map((item) => ({ item, source: 'queue' as const })),
  ...historyEntries.value.map((item) => ({ item, source: 'history' as const })),
]);

const hasAnyItems = computed(() => queueItems.value.length > 0 || historyEntries.value.length > 0);

const greetingMessage = computed(() => {
  const hour = new Date().getHours();

  if (hour >= 5 && hour < 12) {
    return 'Good morning, what would you like to download?';
  }

  if (hour >= 12 && hour < 17) {
    return 'Good afternoon, what would you like to download?';
  }

  if (hour >= 17 && hour < 21) {
    return 'Good evening, what would you like to download?';
  }

  return 'Hello, what would you like to download?';
});

const sortedDLFields = computed(() =>
  [...configStore.dl_fields].sort((a, b) => (a.order || 0) - (b.order || 0)),
);

const isDownloading = (status: ItemStatus | null): boolean => downloadingStatuses.has(status);

const refreshQueue = async (): Promise<void> => {
  if (isRefreshing.value) {
    return;
  }

  isRefreshing.value = true;

  try {
    await stateStore.loadQueue();
  } catch (error) {
    console.error('Failed to refresh queue:', error);
    toast.error('Failed to refresh queue');
  } finally {
    isRefreshing.value = false;
  }
};

const addDownload = async (): Promise<void> => {
  const url = formUrl.value.trim();
  if (!url) {
    toast.error('Please enter a valid URL.');
    return;
  }

  let cli = '';
  const dlFieldsExtra = ['--no-download-archive'];

  const is_valid = (dl_field: string): boolean => {
    if (dlFieldsExtra.includes(dl_field)) {
      return true;
    }

    if (configStore.dl_fields && configStore.dl_fields.length > 0) {
      return configStore.dl_fields.some((f) => dl_field === f.field);
    }

    return false;
  };

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = [];

    for (const [key, value] of Object.entries(dlFields.value)) {
      if (is_valid(key) === false) {
        continue;
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue;
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (cli && keyRegex.test(cli)) {
        continue;
      }

      joined.push(value === true ? `${key}` : `${key} ${value}`);
    }

    if (joined.length > 0) {
      cli = joined.join(' ');
    }
  }

  const payload: item_request[] = [
    {
      url,
      preset: formPreset.value || app.value.default_preset,
      cli: cli || '',
      auto_start: true,
    },
  ];

  try {
    addInProgress.value = true;

    const response = await request('/api/history', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      toast.error(data?.error ?? 'Failed to add download.');
      return;
    }

    const failures = Array.isArray(data)
      ? data.filter((item: Record<string, any>) => item?.status === false)
      : [];

    if (failures.length > 0) {
      failures.forEach((item: Record<string, any>) =>
        toast.error(item?.msg ?? 'Failed to add download.'),
      );
      return;
    }

    formUrl.value = '';
    formPreset.value = app.value.default_preset || '';
    dlFields.value = {};
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to add download.';
    toast.error(message);
  } finally {
    addInProgress.value = false;
  }
};

const resolveThumbnail = (entry: DisplayEntry): string => {
  if (!show_thumbnail.value) {
    return '/images/placeholder.png';
  }

  const { item, source } = entry;
  const sidecarImage = item.sidecar?.image?.[0]?.file;

  if (source === 'history' && sidecarImage) {
    const relativePath = stripPath(app.value.download_path ?? '', sidecarImage);
    return uri(`/api/download/${encodeURIComponent(relativePath)}`);
  }

  const remoteThumb = ag<string | null>(item, 'extras.thumbnail', null);
  if (remoteThumb) {
    return uri(`/api/thumbnail?id=${item._id}&url=${encodePath(remoteThumb)}`);
  }

  return '/images/placeholder.png';
};

const canOpenPlayer = (item: StoreItem): boolean => Boolean(item.filename || isEmbedable(item.url));

const openPlayer = (item: StoreItem): void => {
  if (item.filename) {
    videoItem.value = item;
    return;
  }

  if (!isEmbedable(item.url)) {
    return;
  }

  const embed = getEmbedable(item.url);
  if (embed) {
    embedUrl.value = embed;
  }
};

const closePlayer = (): void => {
  embedUrl.value = '';
  videoItem.value = null;
};

const getSourceLabel = (entry: DisplayEntry): string => {
  if (entry.source === 'history') {
    return 'History';
  }

  if (isDownloading(entry.item.status)) {
    return 'Active';
  }

  return 'Queued';
};

const getSourceColor = (entry: DisplayEntry): 'neutral' | 'info' | 'warning' => {
  if (entry.source === 'history') {
    return 'neutral';
  }

  if (isDownloading(entry.item.status)) {
    return 'info';
  }

  return 'warning';
};

const getDescription = (item: StoreItem): string => {
  const direct = (item.description ?? '').toString().trim();
  if (direct) {
    return direct;
  }

  const extrasDescription = ag<string | null>(item, 'extras.description', null)?.toString().trim();
  if (extrasDescription) {
    return extrasDescription;
  }

  const errorDescription = item.error?.trim();
  if (errorDescription) {
    return errorDescription;
  }

  const message = ag<string | null>(item, 'msg', null)?.toString().trim();
  if (message) {
    return message;
  }

  return '';
};

const getDurationLabel = (item: StoreItem): string | null => {
  const duration = ag<number | null>(item, 'extras.duration', null);
  if (duration == null || Number.isNaN(duration) || duration <= 0) {
    return null;
  }

  return formatTime(duration);
};

const statusOverrides: Record<string, string> = {
  downloading: 'Downloading',
  postprocessing: 'Post-processing',
  preparing: 'Preparing',
  finished: 'Completed',
  error: 'Error',
  cancelled: 'Cancelled',
  not_live: 'Not live yet',
  skip: 'Skipped',
};

const getStatusLabel = (item: StoreItem): string => {
  if (item.status === null) {
    return 'Queued';
  }

  if (item.status === 'error' && item.filename) {
    return 'Partial Error';
  }

  return statusOverrides[item.status] ?? ucFirst(item.status.replace(/_/g, ' '));
};

const getStatusColor = (item: StoreItem): 'neutral' | 'info' | 'success' | 'error' | 'warning' => {
  if (item.status === null) {
    return 'neutral';
  }

  if (item.status === 'error' && item.filename) {
    return 'warning';
  }

  const map: Record<string, 'neutral' | 'info' | 'success' | 'error' | 'warning'> = {
    downloading: 'info',
    postprocessing: 'info',
    preparing: 'info',
    finished: 'success',
    error: 'error',
    cancelled: 'neutral',
    not_live: 'warning',
    skip: 'neutral',
  };

  return map[item.status] ?? 'info';
};

const shouldShowProgress = (item: StoreItem): boolean =>
  isDownloading(item.status) || item.status === null;

const percentPipe = (value: number | null): string => {
  if (value === null || Number.isNaN(value)) {
    return '00.00';
  }

  return parseFloat(String(value)).toFixed(2);
};

const ETAPipe = (value: number | null): string => {
  if (value === null || value === 0) {
    return 'Live';
  }

  if (value < 60) {
    return `${Math.round(value)}s`;
  }

  if (value < 3600) {
    return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
  }

  const hours = Math.floor(value / 3600);
  const minutes = value % 3600;
  return `${hours}h ${Math.floor(minutes / 60)}m ${Math.round(minutes % 60)}s`;
};

const speedPipe = (value: number | null): string => {
  if (value === null || value === 0) {
    return '0KB/s';
  }

  const k = 1024;
  const dm = 2;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s', 'EB/s', 'ZB/s', 'YB/s'];
  const i = Math.floor(Math.log(value) / Math.log(k));
  return `${parseFloat((value / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
};

const updateProgress = (item: StoreItem): string => {
  let text = '';

  if (!item.auto_start) {
    return 'Manual start';
  }

  if (item.status === null && paused.value === true) {
    return 'Global Pause';
  }

  if (item.status === 'postprocessing') {
    return 'Post-processors are running.';
  }

  if (item.status === 'preparing') {
    return ag(item, 'extras.external_downloader') ? 'External downloader.' : 'Preparing';
  }

  if (item.status !== null) {
    text += item.percent && !item.is_live ? `${percentPipe(item.percent)}%` : 'Live';
  }

  text += item.speed ? ` - ${speedPipe(item.speed)}` : ' - Waiting..';

  if (item.status !== null && item.eta) {
    text += ` - ${ETAPipe(item.eta)}`;
  }

  return text;
};

const getProgressWidth = (item: StoreItem): string => {
  const percent = parseFloat(percentPipe(item.percent ?? 0));
  const clamped = Number.isNaN(percent) ? 0 : Math.min(100, Math.max(0, percent));
  return `${clamped}%`;
};

const canStart = (item: StoreItem): boolean => !item.status && item.auto_start === false;
const canPause = (item: StoreItem): boolean => !item.status && item.auto_start === true;

const startQueueItem = async (item: StoreItem): Promise<void> => {
  await stateStore.startItems([item._id]);
};

const pauseQueueItem = async (item: StoreItem): Promise<void> => {
  await stateStore.pauseItems([item._id]);
};

const cancelDownload = async (item: StoreItem): Promise<void> => {
  await stateStore.cancelItems([item._id]);
};

const getDownloadLink = (item: StoreItem): string => {
  if (!item.filename) {
    return '';
  }

  return makeDownload(app.value, item);
};

const getDownloadName = (item: StoreItem): string => {
  if (!item.filename) {
    return 'download';
  }

  const segments = item.filename.split('/');
  return segments[segments.length - 1] || 'download';
};

const requeueItem = async (item: StoreItem): Promise<void> => {
  if (!item.url) {
    toast.error('Unable to requeue item; missing URL.');
    return;
  }

  const payload: item_request = {
    url: item.url,
    preset: item.preset || app.value.default_preset,
    folder: item.folder,
    template: item.template,
    cookies: item.cookies,
    cli: item.cli,
    auto_start: item.auto_start ?? true,
  };

  if (item.extras && Object.keys(item.extras).length > 0) {
    payload.extras = JSON.parse(JSON.stringify(item.extras));
  }

  await stateStore.removeItems('history', [item._id], false);
  await stateStore.addDownload(payload);
};

const deleteHistoryItem = async (item: StoreItem): Promise<void> => {
  await stateStore.removeItems('history', [item._id], app.value.remove_files);
  toast.info('Removed from history queue.');
};

const showMessage = (item: StoreItem): boolean => {
  if (!item?.msg || item.msg === item?.error) {
    return false;
  }

  return (item.msg?.length || 0) > 0;
};

const loadMoreHistory = async (): Promise<void> => {
  if (
    paginationInfo.value.isLoading ||
    paginationInfo.value.page >= paginationInfo.value.total_pages
  ) {
    return;
  }

  try {
    await stateStore.loadPaginated(
      'history',
      paginationInfo.value.page + 1,
      DEFAULT_PAGE_SIZE,
      'DESC',
      true,
    );
  } catch (error) {
    console.error('Failed to load more history:', error);
    toast.error('Failed to load more history');
  }
};

const onImgError = (event: Event): void => {
  const target = event.target as HTMLImageElement;
  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  target.src = '/images/placeholder.png';
};

useIntersectionObserver(
  loadMoreTrigger,
  ([entry]) => {
    if (
      entry?.isIntersecting &&
      !paginationInfo.value.isLoading &&
      paginationInfo.value.page < paginationInfo.value.total_pages
    ) {
      void loadMoreHistory();
    }
  },
  { threshold: 0.5 },
);

onMounted(async () => {
  const route = useRoute();

  if (route.query?.simple !== undefined) {
    const simpleMode = useStorage<boolean>('simple_mode', configStore.app.simple_mode || false);
    simpleMode.value = ['true', '1', 'yes', 'on'].includes(route.query.simple as string);
    await nextTick();

    const url = new URL(window.location.href);
    url.searchParams.delete('simple');
    window.history.replaceState({}, '', url.toString());
  }

  if (!paginationInfo.value.isLoaded) {
    try {
      await stateStore.loadPaginated('history', 1, DEFAULT_PAGE_SIZE, 'DESC');
    } catch (error) {
      console.error('Failed to load history on mount:', error);
    }
  }

  if (window?.location && window.location.pathname !== '/') {
    window.history.replaceState({}, '', '/');
  }
});

watch(
  () => socketStore.isConnected,
  async (connected) => {
    if (connected && !paginationInfo.value.isLoaded) {
      try {
        await stateStore.loadPaginated('history', 1, DEFAULT_PAGE_SIZE, 'DESC');
      } catch (error) {
        console.error('Failed to load history after socket connection:', error);
      }
    }
  },
);

watch(
  () => app.value.default_preset,
  (value) => {
    if (!formPreset.value) {
      formPreset.value = value || '';
    }
  },
);
</script>

<style scoped>
.simple-form-center {
  transform: translateY(24vh);
}

.queue-fade-enter-active,
.queue-fade-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.32s ease;
}

.queue-fade-enter-from,
.queue-fade-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

.queue-card-enter-active,
.queue-card-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.28s ease;
}

.queue-card-enter-from,
.queue-card-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.queue-card-leave-active {
  position: absolute;
}

@media (max-width: 768px) {
  .simple-form-center {
    transform: translateY(16vh);
  }
}
</style>
