<template>
  <div ref="scrollEl" :class="maxHeight ? 'max-h-[55vh] overflow-y-auto' : ''">
    <div class="space-y-2">
      <LateLoader
        v-for="entry in entries"
        :key="entry.key"
        :root="scrollEl"
        :min-height="90"
        unrender
      >
        <component
          :is="selectable ? 'label' : 'div'"
          :class="[
            'flex items-center gap-3 border border-default p-2 transition-colors hover:bg-elevated/50',
            selectable && !disabled ? 'cursor-pointer' : '',
          ]"
        >
          <UCheckbox
            v-if="selectable"
            :model-value="selected?.has(entry.key)"
            :aria-label="entry.title"
            :disabled="disabled"
            @update:model-value="$emit('toggle', entry.key, $event)"
          />
          <img
            :src="entry.thumbnail || '/images/placeholder.png'"
            alt=""
            class="aspect-video w-24 shrink-0 rounded-md object-cover sm:w-32"
            loading="lazy"
            @error="useFallbackImage"
          />
          <div class="min-w-0 flex-1 space-y-1">
            <span v-if="selectable" class="block text-sm font-medium text-default">
              {{ entry.title }}
            </span>
            <a
              v-else
              :href="entry.url"
              target="_blank"
              rel="noreferrer"
              class="block text-sm font-medium text-highlighted hover:underline"
            >
              {{ entry.title }}
            </a>
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
              <UBadge v-if="entry.archiveId" color="neutral" variant="soft" size="xs">
                <code>{{ entry.archiveId }}</code>
              </UBadge>
              <UBadge v-if="entry.broadcastDateLabel" color="neutral" variant="soft" size="xs">
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
        </component>
      </LateLoader>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PlaylistDisplayEntry } from '~/types/playlist';
import { formatTime } from '~/utils';
import { formatDateOnly, formatDateTime, parseDate } from '~/utils/date';

withDefaults(
  defineProps<{
    entries: PlaylistDisplayEntry[];
    selectable?: boolean;
    selected?: ReadonlySet<string>;
    maxHeight?: boolean;
    disabled?: boolean;
  }>(),
  { selectable: false, selected: undefined, maxHeight: true, disabled: false },
);
defineEmits<{
  toggle: [key: string, value: boolean | 'indeterminate'];
}>();

const { locale, t } = useI18n();
const scrollEl = ref<HTMLElement | null>(null);

const formatPublished = (value: string, full: boolean = false): string => {
  const date = parseDate(value);
  if (!date) return value;
  return full
    ? formatDateTime(date, locale.value, { seconds: true })
    : formatDateOnly(date, locale.value);
};

const useFallbackImage = (event: Event): void => {
  const image = event.target as HTMLImageElement;
  if (!image.src.endsWith('/images/placeholder.png')) image.src = '/images/placeholder.png';
};
</script>
