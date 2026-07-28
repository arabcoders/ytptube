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

        <div v-if="isLoading" class="flex min-h-80 items-center justify-center">
          <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin text-toned" />
        </div>

        <UAlert
          v-else-if="errorMessage"
          color="error"
          variant="soft"
          icon="i-lucide-circle-alert"
          :title="errorMessage"
        />

        <UEmpty
          v-else-if="filteredEntries.length === 0"
          icon="i-lucide-list-video"
          :title="entries.length === 0 ? t('common.noPlaylistEntries') : t('common.noResults')"
          class="py-12"
        />

        <div v-else class="max-h-[55vh] overflow-y-auto">
          <div class="space-y-2">
            <label
              v-for="entry in filteredEntries"
              :key="entry.key"
              class="flex cursor-pointer items-center gap-3 rounded-lg border border-default p-2 transition-colors hover:bg-elevated/50"
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
                </div>
              </div>
            </label>
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
import { formatTime, parse_api_error, request } from '~/utils';

type RawEntry = {
  url?: unknown;
  webpage_url?: unknown;
  title?: unknown;
  thumbnail?: unknown;
  thumbnails?: unknown;
  duration?: unknown;
  view_count?: unknown;
};

type PlaylistEntry = {
  key: string;
  url: string;
  title: string;
  thumbnail: string;
  duration: number | null;
  viewCount: number | null;
};

const props = defineProps<{
  link: string;
  preset?: string;
  cli?: string;
}>();

const emitter = defineEmits<{
  (event: 'closeModel'): void;
  (event: 'dirty-change', dirty: boolean): void;
  (event: 'picked', urls: string[]): void;
}>();

const { t } = useI18n();
const toast = useNotification();
const query = ref('');
const entries = ref<PlaylistEntry[]>([]);
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

const normalizeEntries = (value: unknown): PlaylistEntry[] => {
  if (
    !value ||
    typeof value !== 'object' ||
    !Array.isArray((value as { entries?: unknown }).entries)
  ) {
    return [];
  }

  return (value as { entries: RawEntry[] }).entries.flatMap((entry, index) => {
    if (!entry || typeof entry !== 'object') {
      return [];
    }

    const url = typeof entry.webpage_url === 'string' ? entry.webpage_url : entry.url;
    if (typeof url !== 'string' || !url) {
      return [];
    }

    const rawTitle = typeof entry.title === 'string' ? entry.title : '';
    const indexTitle = Number.isInteger(index) ? `(${index + 1})` : '';
    const title = rawTitle || indexTitle || url;

    return [
      {
        key: `${index}:${url}`,
        url,
        title,
        thumbnail: normalizeThumbnail(entry),
        duration: typeof entry.duration === 'number' ? entry.duration : null,
        viewCount: typeof entry.view_count === 'number' ? entry.view_count : null,
      },
    ];
  });
};

const loadEntries = async (): Promise<void> => {
  query.value = '';
  entries.value = [];
  selected.value = new Set();
  errorMessage.value = '';
  playlistTitle.value = '';
  isLoading.value = true;

  try {
    const params = new URLSearchParams({ url: props.link });
    params.set('entries', 'true');
    if (props.preset) params.set('preset', props.preset);
    if (props.cli) params.set('args', props.cli);

    const response = await request(`/api/yt-dlp/url/info?${params.toString()}`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(await parse_api_error(body));
    }

    playlistTitle.value = typeof body.title === 'string' ? body.title : '';
    entries.value = normalizeEntries(body);
    if (entries.value.length === 0) {
      errorMessage.value = t('common.noPlaylistEntries');
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : t('common.failedFetch');
    errorMessage.value = message;
    toast.error(t('common.errorPrefix', { msg: message }));
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
    entries.value.filter((entry) => selectedKeys.has(entry.key)).map((entry) => entry.url),
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
