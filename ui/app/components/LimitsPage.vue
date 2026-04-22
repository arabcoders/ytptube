<template>
  <div class="w-full min-w-0 max-w-full space-y-5 p-4 sm:p-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0 space-y-2">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-gauge" class="size-4 text-toned" />
          <span>Queue capacity overview</span>
        </div>

        <p class="max-w-3xl text-sm text-toned">
          Snapshot is based on the current queue state and configured backend limits.
          <template v-if="limits">
            {{ ' ' + queueLimitDescription }}
          </template>
        </p>
      </div>

      <UButton
        color="neutral"
        variant="outline"
        size="sm"
        icon="i-lucide-refresh-cw"
        :loading="limitsLoading"
        :disabled="limitsLoading"
        @click="void loadLimits(true)"
      >
        Refresh
      </UButton>
    </div>

    <div
      v-if="!limits && limitsLoading"
      class="flex min-h-72 items-center justify-center rounded-md border border-default bg-default/90"
    >
      <div class="flex flex-col items-center gap-3 text-center text-toned">
        <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin text-info" />

        <div class="space-y-1">
          <p class="text-sm font-medium text-default">Loading limits</p>
          <p class="text-xs">Fetching current queue capacity and runtime rules.</p>
        </div>
      </div>
    </div>

    <UAlert
      v-else-if="!limits && limitsError"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="Failed to load limits"
      :description="limitsError"
    />

    <div v-else-if="limits" class="space-y-5">
      <UAlert
        v-if="limitsError"
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        title="Showing last successful snapshot"
        :description="limitsError"
      />

      <UAlert
        v-if="limits.downloads.paused"
        color="warning"
        variant="soft"
        icon="i-lucide-pause"
        title="Download queue is paused"
      />

      <div class="rounded-md border border-default bg-default shadow-sm">
        <div class="grid gap-0 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <section
            class="space-y-4 border-b border-default px-4 py-4 sm:px-5 lg:border-r lg:border-b-0"
          >
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-download" class="size-4 text-toned" />
              <span>Download capacity</span>
            </div>

            <div class="space-y-3">
              <div
                v-for="row in capacityRows"
                :key="row.label"
                class="rounded-md border border-default bg-muted/20 px-3 py-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 space-y-1">
                    <p class="text-sm font-medium text-default">{{ row.label }}</p>
                    <p class="text-xs text-toned">{{ row.description }}</p>
                  </div>

                  <div class="shrink-0 text-right">
                    <p class="text-lg font-semibold text-default">{{ row.value }}</p>
                    <p v-if="row.meta" class="text-xs text-toned">{{ row.meta }}</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section class="space-y-4 px-4 py-4 sm:px-5">
            <div class="space-y-3">
              <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                <UIcon name="i-lucide-settings-2" class="size-4 text-toned" />
                <span>Extraction rules</span>
              </div>

              <div class="space-y-3">
                <div
                  v-for="row in extractionRows"
                  :key="row.label"
                  class="rounded-md border border-default bg-muted/20 px-3 py-3"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0 space-y-1">
                      <p class="text-sm font-medium text-default">{{ row.label }}</p>
                      <p class="text-xs text-toned">{{ row.description }}</p>
                    </div>

                    <div class="shrink-0 text-right">
                      <p class="text-lg font-semibold text-default">{{ row.value }}</p>
                      <p v-if="row.meta" class="text-xs text-toned">{{ row.meta }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="space-y-3 border-t border-default pt-4">
              <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
                <UIcon name="i-lucide-clock-3" class="size-4 text-toned" />
                <span>Premiere handling</span>
              </div>

              <div class="space-y-3">
                <div
                  v-for="row in premiereRows"
                  :key="row.label"
                  class="rounded-md border border-default bg-muted/20 px-3 py-3"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0 space-y-1">
                      <p class="text-sm font-medium text-default">{{ row.label }}</p>
                      <p class="text-xs text-toned">{{ row.description }}</p>
                    </div>

                    <div class="shrink-0 text-right">
                      <p class="text-lg font-semibold text-default">{{ row.value }}</p>
                      <p v-if="row.meta" class="text-xs text-toned">{{ row.meta }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <section class="space-y-3">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0 space-y-2">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-list" class="size-4 text-toned" />
              <span>Per extractor</span>
            </div>

            <p class="text-sm text-toned">
              Extractor-specific usage and overrides currently in effect.
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs text-toned">
            <span class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1">
              <UIcon name="i-lucide-gauge" class="size-3.5 shrink-0" />
              <span>{{ limits.downloads.per_extractor.default_limit }} default per extractor</span>
            </span>

            <span class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1">
              <UIcon name="i-lucide-list" class="size-3.5 shrink-0" />
              <span>{{ trackedExtractorCount }} tracked</span>
            </span>
          </div>
        </div>

        <UAlert
          v-if="trackedExtractorCount === 0"
          color="info"
          variant="soft"
          icon="i-lucide-info"
          title="No extractor-specific activity"
          description="Overrides and extractor usage appear here once downloads have active or queued work."
        />

        <div
          v-else
          class="w-full min-w-0 max-w-full overflow-hidden rounded-md border border-default bg-default"
        >
          <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
            <table class="min-w-180 w-full text-sm">
              <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
                <tr
                  class="text-left [&>th]:border-r [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-r-0"
                >
                  <th class="w-full min-w-56">Extractor</th>
                  <th class="w-36 whitespace-nowrap">Source</th>
                  <th class="w-24 whitespace-nowrap">Active</th>
                  <th class="w-24 whitespace-nowrap">Limit</th>
                  <th class="w-28 whitespace-nowrap">Available</th>
                  <th class="w-24 whitespace-nowrap">Queued</th>
                </tr>
              </thead>

              <tbody class="divide-y divide-default">
                <tr
                  v-for="item in extractorItems"
                  :key="item.name"
                  class="transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
                >
                  <td class="px-3 py-3 align-middle">
                    <div class="font-medium text-default">{{ item.name }}</div>
                  </td>

                  <td class="px-3 py-3 align-middle whitespace-nowrap text-toned">
                    <span
                      class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1"
                    >
                      <UIcon :name="extractorSourceIcon(item.source)" class="size-3.5 shrink-0" />
                      <span>{{ extractorSourceLabel(item.source) }}</span>
                    </span>
                  </td>

                  <td class="px-3 py-3 align-middle font-medium whitespace-nowrap text-default">
                    {{ item.active }}
                  </td>

                  <td class="px-3 py-3 align-middle font-medium whitespace-nowrap text-default">
                    {{ item.limit }}
                  </td>

                  <td class="px-3 py-3 align-middle whitespace-nowrap text-toned">
                    {{ item.available }}
                  </td>

                  <td class="px-3 py-3 align-middle whitespace-nowrap text-toned">
                    {{ item.queued }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import moment from 'moment';
import { parse_api_error, parse_api_response, request } from '~/utils';
import type { SystemLimitsExtractor, SystemLimitsResponse } from '~/types/limits';

type DetailRow = {
  label: string;
  description: string;
  value: string;
  meta?: string;
};

const limits = ref<SystemLimitsResponse | null>(null);
const limitsLoading = ref(false);
const limitsError = ref('');

const formatDuration = (seconds: number): string => {
  return moment.duration(seconds, 'seconds').humanize();
};

const extractorSourceLabel = (source: string): string => {
  return source === 'env_override' ? 'Override' : 'Default';
};

const extractorSourceIcon = (source: string): string => {
  return source === 'env_override' ? 'i-lucide-settings-2' : 'i-lucide-circle-check-big';
};

const queueLimitDescription = computed(() => {
  if (limits.value?.downloads.live_bypasses_limits === false) {
    return 'Regular worker slots apply to all downloads, including live downloads.';
  }

  return 'Regular worker slots apply only to non-live downloads.';
});

const capacityRows = computed<Array<DetailRow>>(() => {
  if (!limits.value) {
    return [];
  }

  const { downloads } = limits.value;
  const { global } = downloads;

  return [
    {
      label: 'Regular workers',
      description: 'Slots available for non-live downloads.',
      value: `${global.active}/${global.limit}`,
      meta: `${global.available} available`,
    },
    {
      label: 'Waiting queue',
      description: 'Downloads waiting for a regular worker slot.',
      value: `${global.queued}`,
      meta: global.queued === 1 ? 'item queued' : 'items queued',
    },
    {
      label: 'Live downloads',
      description: downloads.live_bypasses_limits
        ? 'Live downloads bypass the regular worker limit.'
        : 'Live downloads count toward the regular worker limit.',
      value: `${global.live_active}`,
      meta: global.live_active === 1 ? 'live item active' : 'live items active',
    },
  ];
});

const extractionRows = computed<Array<DetailRow>>(() => {
  if (!limits.value) {
    return [];
  }

  return [
    {
      label: 'Concurrent requests',
      description: 'Maximum info extraction jobs running at once.',
      value: `${limits.value.extraction.concurrency}`,
    },
    {
      label: 'Request timeout',
      description: 'Per extraction attempt before the backend gives up.',
      value: `${limits.value.extraction.timeout_seconds}s`,
    },
    {
      label: 'Cached info TTL',
      description: 'How long extracted info can be reused before refresh.',
      value: formatDuration(limits.value.extraction.info_cache_ttl_seconds),
      meta: `${limits.value.extraction.info_cache_ttl_seconds} seconds`,
    },
  ];
});

const premiereRows = computed<Array<DetailRow>>(() => {
  if (!limits.value) {
    return [];
  }

  return [
    {
      label: 'Initial premiere capture',
      description: 'Whether the first premiere capture is delayed until the buffer window passes.',
      value: limits.value.live.prevent_premiere ? 'Delayed' : 'Immediate',
    },
    {
      label: 'Premiere buffer',
      description: 'Extra time added after the scheduled start before download begins.',
      value: `${limits.value.live.premiere_buffer_minutes}m`,
      meta: `${limits.value.live.premiere_buffer_minutes} minute buffer`,
    },
  ];
});

const extractorItems = computed<Array<SystemLimitsExtractor>>(() => {
  return limits.value?.downloads.per_extractor.items ?? [];
});

const trackedExtractorCount = computed(() => extractorItems.value.length);

const loadLimits = async (force: boolean = false): Promise<void> => {
  if (limitsLoading.value) {
    return;
  }

  if (limits.value && !force) {
    return;
  }

  limitsError.value = '';

  try {
    limitsLoading.value = true;

    const response = await request('/api/system/limits');

    if (!response.ok) {
      try {
        limitsError.value = await parse_api_error(response.clone().json());
      } catch {
        limitsError.value = response.statusText || 'Failed to load limits.';
      }
      return;
    }

    limits.value = await parse_api_response<SystemLimitsResponse>(response.json());
  } catch (e) {
    limitsError.value = e instanceof Error ? e.message : 'Failed to load limits.';
  } finally {
    limitsLoading.value = false;
  }
};

onMounted(() => {
  void loadLimits(true);
});
</script>
