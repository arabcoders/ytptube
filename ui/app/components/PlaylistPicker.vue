<template>
  <UModal
    v-model:open="modalOpen"
    :title="resolvedTitle"
    :dismissible="!isLoading"
    :ui="{
      content: 'w-full sm:max-w-5xl',
      body: 'p-4 sm:p-5',
      footer: 'px-4 pb-4 sm:px-5 sm:pb-5',
    }"
  >
    <template #description>
      <span class="sr-only">{{ t('common.playlistPickerDesc') }}</span>
    </template>

    <template #body>
      <div class="space-y-4">
        <div class="flex flex-wrap items-center justify-between gap-3 ytp-card px-3 py-3">
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              :icon="allFilteredSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
              :disabled="isLoading || filteredEntries.length === 0"
              @click="toggleFilteredSelection"
            >
              {{ allFilteredSelected ? t('common.unselect') : t('common.select') }}
            </UButton>
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-x"
              :disabled="isLoading || selected.size === 0"
              @click="clearSelection"
            >
              {{ t('common.clearSelection') }}
            </UButton>
            <span class="text-sm text-toned">{{
              t('common.playlistSelectionCount', { selected: selected.size, total: entries.length })
            }}</span>
          </div>

          <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            <UButton
              color="neutral"
              :variant="showFilter ? 'soft' : 'outline'"
              size="sm"
              icon="i-lucide-filter"
              :disabled="isLoading || entries.length === 0"
              @click="toggleFilter"
            >
              {{ t('common.filter') }}
            </UButton>
            <UInput
              v-if="showFilter"
              v-model="query"
              type="search"
              icon="i-lucide-filter"
              size="sm"
              :placeholder="t('common.filterDisplayedContent')"
              :disabled="isLoading || entries.length === 0"
              class="order-last w-full sm:order-first sm:w-64"
              autofocus
            />
          </div>
        </div>

        <UAlert
          v-if="!isLoading && entries.length > 0"
          color="info"
          variant="soft"
          icon="i-lucide-info"
          :description="t('common.playlistMetadataNotice')"
        />

        <div v-if="isLoading" class="flex min-h-80 items-center justify-center">
          <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin text-toned" />
        </div>

        <FormSubmitError
          v-else-if="errorMessage"
          :message="errorMessage"
          @dismiss="errorMessage = ''"
        />

        <UEmpty
          v-else-if="filteredEntries.length === 0"
          icon="i-lucide-list-video"
          :title="entries.length === 0 ? t('common.noPlaylistEntries') : t('common.noResults')"
          class="py-12"
        />

        <div v-else ref="entryScrollEl" class="max-h-[55vh] overflow-y-auto">
          <div class="space-y-2">
            <LateLoader
              v-for="entry in filteredEntries"
              :key="entry.key"
              :root="entryScrollEl"
              :min-height="90"
              unrender
            >
              <label
                class="flex cursor-pointer items-center gap-3 border border-default p-2 transition-colors hover:bg-elevated/50"
              >
                <UCheckbox
                  :model-value="selected.has(entry.key)"
                  :aria-label="entry.title"
                  @update:model-value="toggleEntry(entry.key, $event)"
                />
                <img
                  :src="entry.thumbnail || '/images/placeholder.png'"
                  :alt="''"
                  class="aspect-video w-24 shrink-0 rounded-md object-cover sm:w-32"
                  loading="lazy"
                  @error="useFallbackImage"
                />
                <div class="min-w-0 flex-1 space-y-1">
                  <span class="block text-sm font-medium text-default">{{ entry.title }}</span>
                  <p
                    v-if="entry.description"
                    class="line-clamp-2 text-xs text-toned"
                    :title="entry.description"
                  >
                    {{ entry.description }}
                  </p>
                  <div class="flex flex-wrap items-center gap-2">
                    <UBadge v-if="entry.duration" color="info" variant="soft" size="xs">
                      {{ formatTime(entry.duration) }}
                    </UBadge>
                    <UBadge v-if="entry.viewCount" color="neutral" variant="soft" size="xs">
                      <span class="inline-flex items-center gap-1">
                        <UIcon name="i-lucide-eye" class="size-3" />
                        {{ entry.viewCount.toLocaleString() }}
                      </span>
                    </UBadge>
                    <UBadge v-if="entry.seriesTitle" color="neutral" variant="soft" size="xs">
                      {{ entry.seriesTitle }}
                    </UBadge>
                    <UBadge v-if="entry.broadcasterName" color="neutral" variant="soft" size="xs">
                      {{ entry.broadcasterName }}
                    </UBadge>
                    <UBadge
                      v-if="entry.isArchived"
                      color="success"
                      variant="soft"
                      size="xs"
                      icon="i-lucide-check"
                    >
                      {{ t('common.alreadyDownloaded') }}
                    </UBadge>
                    <UBadge
                      v-if="entry.broadcastDateLabel"
                      color="neutral"
                      variant="soft"
                      size="xs"
                    >
                      {{ entry.broadcastDateLabel }}
                    </UBadge>
                    <UTooltip v-if="entry.published" :text="formatPublished(entry.published, true)">
                      <UBadge color="neutral" variant="soft" size="xs">
                        <span class="inline-flex items-center gap-1">
                          <UIcon name="i-lucide-calendar" class="size-3" />
                          {{ formatPublished(entry.published) }}
                        </span>
                      </UBadge>
                    </UTooltip>
                  </div>
                </div>
              </label>
            </LateLoader>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          icon="i-lucide-x"
          class="justify-center"
          @click="closePicker"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          type="button"
          color="primary"
          icon="i-lucide-check"
          :disabled="selected.size === 0 || isLoading"
          class="justify-center"
          @click="pickEntries"
        >
          {{ t('common.pickSelected') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import moment from 'moment';
import { formatTime, parse_api_error, request } from '~/utils';
import { playlistExtras } from '~/utils/playlist';

type RawEntry = {
  url?: unknown;
  webpage_url?: unknown;
  title?: unknown;
  description?: unknown;
  thumbnail?: unknown;
  thumbnails?: unknown;
  duration?: unknown;
  view_count?: unknown;
  published?: unknown;
  broadcastDateLabel?: unknown;
  seriesTitle?: unknown;
  broadcasterName?: unknown;
  metadata?: unknown;
  [key: string]: unknown;
};

type PlaylistEntry = {
  key: string;
  url: string;
  title: string;
  description: string;
  thumbnail: string;
  duration: number | null;
  viewCount: number | null;
  published: string | null;
  broadcastDateLabel: string;
  seriesTitle: string;
  broadcasterName: string;
  isArchived: boolean;
  extras: Record<string, unknown>;
};

const props = defineProps<{
  link: string;
  preset?: string;
  cli?: string;
}>();

const emitter = defineEmits<{
  (event: 'closeModel'): void;
  (event: 'dirty-change', dirty: boolean): void;
  (event: 'picked', entries: Array<{ url: string; extras: Record<string, unknown> }>): void;
}>();

const { t } = useI18n();
const query = ref('');
const entries = ref<PlaylistEntry[]>([]);
const entryScrollEl = ref<HTMLElement | null>(null);
const selected = ref<Set<string>>(new Set());
const isLoading = ref(false);
const errorMessage = ref('');
const playlistTitle = ref('');
const showFilter = ref(false);

const resolvedTitle = computed(() => playlistTitle.value || t('common.pickPlaylistVideos'));

const modalOpen = computed({
  get: () => true,
  set: (value: boolean) => {
    if (!value) {
      emitter('closeModel');
    }
  },
});

const filteredEntries = computed(() => {
  const value = query.value.trim().toLocaleLowerCase();
  if (!value) {
    return entries.value;
  }

  return entries.value.filter(
    (entry) =>
      entry.title.toLocaleLowerCase().includes(value) ||
      entry.description.toLocaleLowerCase().includes(value) ||
      entry.seriesTitle.toLocaleLowerCase().includes(value) ||
      entry.broadcasterName.toLocaleLowerCase().includes(value) ||
      entry.broadcastDateLabel.toLocaleLowerCase().includes(value) ||
      entry.url.toLocaleLowerCase().includes(value),
  );
});

const normalizeThumbnail = (entry: RawEntry): string => {
  if (typeof entry.thumbnail === 'string' && entry.thumbnail) {
    return entry.thumbnail;
  }

  if (!Array.isArray(entry.thumbnails)) {
    return '';
  }

  const thumbnail = [...entry.thumbnails].reverse().find((item) => {
    return (
      typeof item === 'object' &&
      item !== null &&
      typeof (item as { url?: unknown }).url === 'string'
    );
  }) as { url: string } | undefined;

  return thumbnail?.url || '';
};

const normalizeEntry = (
  entry: RawEntry,
  index: number,
  keyPrefix: string,
  playlist: RawEntry | null = null,
  total: number = 0,
): PlaylistEntry | null => {
  if (!entry || typeof entry !== 'object') {
    return null;
  }

  const metadata =
    entry.metadata && typeof entry.metadata === 'object' ? (entry.metadata as RawEntry) : undefined;
  const url = typeof entry.webpage_url === 'string' ? entry.webpage_url : entry.url;
  if (typeof url !== 'string' || !url) {
    return null;
  }

  const rawTitle = typeof entry.title === 'string' ? entry.title : '';
  const description =
    typeof entry.description === 'string'
      ? entry.description
      : metadata && typeof metadata.description === 'string'
        ? metadata.description
        : '';
  const indexTitle = Number.isInteger(index) ? `(${index + 1})` : '';
  const title = rawTitle || indexTitle || url;
  const thumbnail = normalizeThumbnail(entry) || (metadata ? normalizeThumbnail(metadata) : '');
  const duration =
    typeof entry.duration === 'number'
      ? entry.duration
      : metadata && typeof metadata.duration === 'number'
        ? metadata.duration
        : null;
  const viewCount =
    typeof entry.view_count === 'number'
      ? entry.view_count
      : metadata && typeof metadata.view_count === 'number'
        ? metadata.view_count
        : null;
  const published =
    typeof entry.published === 'string'
      ? entry.published
      : metadata && typeof metadata.published === 'string'
        ? metadata.published
        : null;
  const broadcastDateLabel =
    typeof entry.broadcastDateLabel === 'string'
      ? entry.broadcastDateLabel
      : metadata && typeof metadata.broadcastDateLabel === 'string'
        ? metadata.broadcastDateLabel
        : '';
  const seriesTitle =
    typeof entry.seriesTitle === 'string'
      ? entry.seriesTitle
      : metadata && typeof metadata.seriesTitle === 'string'
        ? metadata.seriesTitle
        : '';
  const broadcasterName =
    typeof entry.broadcasterName === 'string'
      ? entry.broadcasterName
      : metadata && typeof metadata.broadcasterName === 'string'
        ? metadata.broadcasterName
        : '';
  const extras = playlistExtras(entry, playlist, index, total);
  const isArchived = entry.is_archived === true || metadata?.is_archived === true;

  return {
    key: `${keyPrefix}:${index}:${url}`,
    url,
    title,
    description,
    thumbnail,
    duration,
    viewCount,
    published,
    broadcastDateLabel,
    seriesTitle,
    broadcasterName,
    isArchived,
    extras,
  };
};

const formatPublished = (value: string, full: boolean = false): string => {
  const date = moment(value);
  if (!date.isValid()) {
    return value;
  }

  return date.format(full ? 'YYYY-MM-DD HH:mm:ss Z' : 'YYYY-MM-DD');
};

const normalizeEntries = (value: unknown): PlaylistEntry[] => {
  if (
    !value ||
    typeof value !== 'object' ||
    !Array.isArray((value as { entries?: unknown }).entries)
  ) {
    return [];
  }

  const playlist = value as RawEntry & { entries: RawEntry[] };
  return playlist.entries.flatMap((entry, index) => {
    const normalized = normalizeEntry(entry, index, 'ytdlp', playlist, playlist.entries.length);
    return normalized ? [normalized] : [];
  });
};

const normalizeTaskEntries = (value: unknown): PlaylistEntry[] => {
  if (!value || typeof value !== 'object' || !Array.isArray((value as { items?: unknown }).items)) {
    return [];
  }

  return (value as { items: RawEntry[] }).items.flatMap((entry, index) => {
    const normalized = normalizeEntry(entry, index, 'task');
    return normalized ? [normalized] : [];
  });
};

const normalizeSingleEntry = (value: unknown): PlaylistEntry[] => {
  if (!value || typeof value !== 'object' || 'video' !== (value as { _type?: unknown })._type) {
    return [];
  }

  const normalized = normalizeEntry(value as RawEntry, 0, 'single');
  return normalized ? [normalized] : [];
};

const usesDirectRssInspect = (link: string): boolean => {
  try {
    const url = new URL(link);
    const hash = url.hash.startsWith('#') ? url.hash.slice(1) : url.hash;
    return (
      url.searchParams.get('handler')?.toLowerCase() === 'rss' ||
      new URLSearchParams(hash).get('handler')?.toLowerCase() === 'rss'
    );
  } catch {
    return /(?:[?#&])handler=rss(?:[&#]|$)/i.test(link);
  }
};

const removeHandlerMarker = (link: string): string => {
  try {
    const url = new URL(link);
    url.searchParams.delete('handler');

    if (url.hash.startsWith('#')) {
      const hash = new URLSearchParams(url.hash.slice(1));
      hash.delete('handler');
      url.hash = hash.toString();
    }

    return url.toString();
  } catch {
    return link.replace(/([?#&])handler=rss(?:[&#]|$)/i, '$1').replace(/[?#&]$/, '');
  }
};

const loadEntries = async (): Promise<void> => {
  query.value = '';
  entries.value = [];
  selected.value = new Set();
  errorMessage.value = '';
  playlistTitle.value = '';
  isLoading.value = true;

  try {
    let body: unknown = null;
    const extractionErrors: string[] = [];
    let normalizedEntries: PlaylistEntry[] = [];

    const inspect = async (url: string = props.link): Promise<void> => {
      try {
        const inspectResponse = await request('/api/tasks/inspect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url,
            preset: props.preset,
          }),
        });

        const inspectBody = await inspectResponse.json();
        if (inspectResponse.ok) {
          normalizedEntries = normalizeTaskEntries(inspectBody);
        } else {
          extractionErrors.push(await parse_api_error(inspectBody));
        }
      } catch (error: unknown) {
        extractionErrors.push(error instanceof Error ? error.message : t('common.failedFetch'));
      }
    };

    if (usesDirectRssInspect(props.link)) {
      await inspect(removeHandlerMarker(props.link));
    } else {
      const params = new URLSearchParams({ url: props.link });
      params.set('entries', 'true');
      if (props.preset) params.set('preset', props.preset);
      if (props.cli) params.set('args', props.cli);

      try {
        const response = await request(`/api/yt-dlp/url/info?${params.toString()}`);
        body = await response.json();

        if (response.ok) {
          const info = body as { title?: unknown };
          playlistTitle.value = typeof info.title === 'string' ? info.title : '';
          normalizedEntries = normalizeEntries(body);
        } else {
          extractionErrors.push(await parse_api_error(body));
        }
      } catch (error: unknown) {
        extractionErrors.push(error instanceof Error ? error.message : t('common.failedFetch'));
      }

      if (normalizedEntries.length === 0) {
        await inspect();
      }
    }

    if (normalizedEntries.length === 0) {
      normalizedEntries = normalizeSingleEntry(body);
    }

    if (normalizedEntries.length === 0) {
      const errors = [...new Set(extractionErrors.filter(Boolean))];
      throw new Error(errors.join('\n\n') || t('common.noPlaylistEntries'));
    }

    entries.value = normalizedEntries;
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : t('common.failedFetch');
    errorMessage.value = message;
  } finally {
    isLoading.value = false;
  }
};

const toggleEntry = (key: string, value: boolean | 'indeterminate'): void => {
  const next = new Set(selected.value);
  if (value === true) next.add(key);
  else next.delete(key);
  selected.value = next;
  emitter('dirty-change', selected.value.size > 0);
};

const clearSelection = (): void => {
  selected.value = new Set();
  emitter('dirty-change', false);
};

const allFilteredSelected = computed(
  () =>
    filteredEntries.value.length > 0 &&
    filteredEntries.value.every((entry) => selected.value.has(entry.key)),
);

const toggleFilteredSelection = (): void => {
  const next = new Set(selected.value);
  if (allFilteredSelected.value) {
    filteredEntries.value.forEach((entry) => next.delete(entry.key));
  } else {
    filteredEntries.value.forEach((entry) => next.add(entry.key));
  }
  selected.value = next;
  emitter('dirty-change', selected.value.size > 0);
};

const toggleFilter = (): void => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
  }
};

const pickEntries = (): void => {
  const selectedKeys = selected.value;
  emitter(
    'picked',
    entries.value
      .filter((entry) => selectedKeys.has(entry.key))
      .map(({ url, extras }) => ({ url, extras })),
  );
  emitter('dirty-change', false);
  emitter('closeModel');
};

const closePicker = (): void => {
  emitter('closeModel');
};

const useFallbackImage = (event: Event): void => {
  const image = event.target as HTMLImageElement;
  if (!image.src.endsWith('/images/placeholder.png')) {
    image.src = '/images/placeholder.png';
  }
};

onMounted(() => void loadEntries());
</script>
