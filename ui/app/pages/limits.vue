<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="ytp-page-header">
      <div class="ytp-page-heading items-start">
        <span class="ytp-page-icon">
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div class="ytp-page-kicker">
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:justify-end">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="limitsLoading"
          :disabled="limitsLoading"
          @click="void loadLimits(true)"
        >
          {{ t('common.refresh') }}
        </UButton>
      </div>
    </div>

    <UAlert
      v-if="!limits && limitsLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('common.loadingData')"
    />

    <UAlert
      v-else-if="!limits && limitsError"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('common.failedFetch')"
      :description="limitsError"
    />

    <div v-else-if="limits" class="space-y-7">
      <UAlert
        v-if="limitsError"
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        :title="t('common.showingLastSnapshot')"
        :description="limitsError"
      />

      <UAlert
        v-if="limits.downloads.paused"
        color="warning"
        variant="soft"
        icon="i-lucide-pause"
        :title="t('common.downloadQueuePaused')"
      />

      <section class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-download" class="size-4 text-toned" />
          <span>{{ t('common.downloadCapacity') }}</span>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            v-for="card in capacityCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :tooltip="card.tooltip"
            :icon="card.icon"
            :color="card.color"
            value-wrap
          />
        </div>
      </section>

      <div class="grid gap-7 xl:grid-cols-[minmax(0,3fr)_minmax(20rem,2fr)]">
        <section class="space-y-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
            <UIcon name="i-lucide-settings-2" class="size-4 text-toned" />
            <span>{{ t('common.extractionRules') }}</span>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <StatCard
              v-for="card in extractionCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :tooltip="card.tooltip"
              :icon="card.icon"
              :color="card.color"
              value-wrap
            />
          </div>
        </section>

        <section class="space-y-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
            <UIcon name="i-lucide-clock-3" class="size-4 text-toned" />
            <span>{{ t('common.premiereHandling') }}</span>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <StatCard
              v-for="card in premiereCards"
              :key="card.label"
              :label="card.label"
              :value="card.value"
              :tooltip="card.tooltip"
              :icon="card.icon"
              :color="card.color"
              value-wrap
            />
          </div>
        </section>
      </div>

      <section class="space-y-3">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div class="min-w-0 space-y-2">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-gauge" class="size-4 text-toned" />
              <span>{{ t('common.perExtractor') }}</span>
            </div>

            <p class="text-sm text-toned" v-if="trackedExtractorCount">
              {{ t('common.extractorUsageDesc') }}
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs text-toned">
            <span class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1">
              <UIcon name="i-lucide-gauge" class="size-3.5 shrink-0" />
              <span class="inline-flex items-baseline gap-1">
                <span class="font-semibold">{{
                  limits.downloads.per_extractor.default_limit
                }}</span>
                <span>{{ t('common.slotsPerExtractor') }}</span>
              </span>
            </span>

            <span class="inline-flex items-center gap-1 rounded-sm border border-default px-2 py-1">
              <UIcon name="i-lucide-list" class="size-3.5 shrink-0" />
              <span class="inline-flex items-baseline gap-1">
                <span class="font-semibold">{{ trackedExtractorCount }}</span>
                <span>{{ t('common.tracked') }}</span>
              </span>
            </span>
          </div>
        </div>

        <UAlert
          v-if="trackedExtractorCount === 0"
          color="info"
          variant="soft"
          icon="i-lucide-info"
          :title="t('common.noActivity')"
          :description="t('common.noActivityDesc')"
        />

        <div v-else class="w-full min-w-0 max-w-full overflow-hidden ytp-table-surface">
          <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
            <table class="min-w-160 w-full text-sm">
              <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
                <tr
                  class="text-start [&>th]:border-e [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-2.5 [&>th]:font-semibold [&>th:last-child]:border-e-0"
                >
                  <th class="w-full min-w-48">{{ t('common.extractor') }}</th>
                  <th class="w-40 whitespace-nowrap">{{ t('common.source') }}</th>
                  <th class="w-20 whitespace-nowrap">{{ t('common.active') }}</th>
                  <th class="w-20 whitespace-nowrap">{{ t('common.limit') }}</th>
                  <th class="w-24 whitespace-nowrap">{{ t('common.available') }}</th>
                  <th class="w-20 whitespace-nowrap">{{ t('common.queued') }}</th>
                </tr>
              </thead>

              <tbody class="divide-y divide-default">
                <tr
                  v-for="item in extractorItems"
                  :key="item.name"
                  class="transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td]:px-3 [&>td]:py-2.5 [&>td:last-child]:border-e-0"
                >
                  <td class="font-medium text-highlighted">{{ item.name }}</td>
                  <td class="whitespace-nowrap">
                    <span class="inline-flex items-center gap-1 text-xs text-toned">
                      <UIcon :name="extractorSourceIcon(item.source)" class="size-3.5 shrink-0" />
                      <span>{{ extractorSourceLabel(item.source) }}</span>
                    </span>
                  </td>
                  <td class="font-semibold whitespace-nowrap text-default">{{ item.active }}</td>
                  <td class="font-semibold whitespace-nowrap text-default">{{ item.limit }}</td>
                  <td
                    :class="[
                      'font-semibold whitespace-nowrap',
                      item.available > 0 ? 'text-success' : 'text-warning',
                    ]"
                  >
                    {{ item.available }}
                  </td>
                  <td
                    :class="[
                      'font-semibold whitespace-nowrap',
                      item.queued > 0 ? 'text-warning' : 'text-default',
                    ]"
                  >
                    {{ item.queued }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import StatCard from '~/components/StatCard.vue';
import { parse_api_error, parse_api_response, request } from '~/utils';
import { humanizeDuration } from '~/utils/date';
import type { SystemLimitsExtractor, SystemLimitsResponse } from '~/types/limits';

const { locale, t } = useI18n();
const pageShell = usePageShell('limits');

type MetricColor = 'success' | 'error' | 'warning' | 'info' | 'neutral';

type MetricCard = {
  label: string;
  value: string;
  tooltip?: string;
  icon: string;
  color: MetricColor;
};

const limits = ref<SystemLimitsResponse | null>(null);
const limitsLoading = ref(false);
const limitsError = ref('');

const formatDuration = (seconds: number): string => {
  return humanizeDuration(seconds, locale.value);
};

const extractorSourceLabel = (source: string): string => {
  return source === 'env_override' ? t('common.overrideSource') : t('common.defaultSource');
};

const extractorSourceIcon = (source: string): string => {
  return source === 'env_override' ? 'i-lucide-settings-2' : 'i-lucide-circle-check-big';
};

const capacityCards = computed<Array<MetricCard>>(() => {
  if (!limits.value) {
    return [];
  }

  const { downloads } = limits.value;
  const { global } = downloads;

  return [
    {
      label: t('common.regularWorkers'),
      value: `${global.active} / ${global.limit}`,
      tooltip: t('common.slotsAvailable'),
      icon: 'i-lucide-users',
      color:
        global.limit > 0 && global.active >= global.limit
          ? 'error'
          : global.limit > 0 && global.active / global.limit >= 0.8
            ? 'warning'
            : 'neutral',
    },
    {
      label: t('common.available'),
      value: `${global.available}`,
      tooltip: t('common.slotsAvailable'),
      icon: 'i-lucide-circle-check-big',
      color: global.available > 0 ? 'success' : 'warning',
    },
    {
      label: t('common.waitingQueue'),
      value: `${global.queued}`,
      tooltip: t('common.waitingQueueDesc'),
      icon: 'i-lucide-list-ordered',
      color: global.queued > 0 ? 'warning' : 'neutral',
    },
    {
      label: t('common.liveDownloads'),
      value: `${global.live_active}`,
      tooltip: t('common.liveDownloadsDesc'),
      icon: 'i-lucide-radio',
      color: global.live_active > 0 ? 'info' : 'neutral',
    },
  ];
});

const extractionCards = computed<Array<MetricCard>>(() => {
  if (!limits.value) {
    return [];
  }

  return [
    {
      label: t('common.concurrentRequests'),
      value: `${limits.value.extraction.concurrency}`,
      tooltip: t('common.concurrentRequestsDesc'),
      icon: 'i-lucide-waypoints',
      color: 'info',
    },
    {
      label: t('common.requestTimeout'),
      value: formatDuration(limits.value.extraction.timeout_seconds),
      tooltip: t('common.requestTimeoutDesc'),
      icon: 'i-lucide-timer',
      color: 'neutral',
    },
    {
      label: t('common.cachedInfoTtl'),
      value: formatDuration(limits.value.extraction.info_cache_ttl_seconds),
      tooltip: t('common.cachedInfoTtlDesc'),
      icon: 'i-lucide-database-zap',
      color: 'neutral',
    },
  ];
});

const premiereCards = computed<Array<MetricCard>>(() => {
  if (!limits.value) {
    return [];
  }

  return [
    {
      label: t('common.initialPremiereCapture'),
      value: limits.value.live.prevent_premiere ? t('common.afterBuffer') : t('common.immediate'),
      icon: limits.value.live.prevent_premiere ? 'i-lucide-clock-3' : 'i-lucide-play',
      color: limits.value.live.prevent_premiere ? 'warning' : 'success',
    },
    {
      label: t('common.premiereBuffer'),
      value: formatDuration(limits.value.live.premiere_buffer_minutes * 60),
      tooltip: t('common.premiereBufferDesc'),
      icon: 'i-lucide-hourglass',
      color: 'neutral',
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
        limitsError.value = response.statusText || t('common.failedFetch');
      }
      return;
    }

    limits.value = await parse_api_response<SystemLimitsResponse>(response.json());
  } catch (e) {
    limitsError.value = e instanceof Error ? e.message : t('common.failedFetch');
  } finally {
    limitsLoading.value = false;
  }
};

onMounted(() => {
  void loadLimits(true);
});
</script>
