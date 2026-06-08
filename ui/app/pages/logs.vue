<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div class="flex min-w-0 items-start gap-3">
        <span
          class="inline-flex size-11 shrink-0 items-center justify-center rounded-md border border-default bg-elevated/70 text-primary"
        >
          <UIcon
            name="i-lucide-file-text"
            :class="[
              'size-5 transition-colors',
              loading ? 'text-info' : 'animate-pulse text-success',
            ]"
            :title="loading ? 'Loading history' : 'Live stream active'"
            :aria-label="loading ? 'Loading history' : 'Live stream active'"
          />
        </span>

        <div class="min-w-0 space-y-2">
          <div
            class="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-toned"
          >
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex min-w-0 flex-wrap items-center justify-end gap-2 xl:justify-end">
        <UButton
          v-if="!autoScroll"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-arrow-down"
          @click="scrollToBottom(false)"
        >
          Bottom
        </UButton>

        <UButton
          color="neutral"
          :variant="toggleFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter = !toggleFilter"
        >
          Filter
        </UButton>

        <UButton
          color="neutral"
          :variant="textWrap ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-wrap-text"
          :aria-pressed="textWrap"
          :title="textWrap ? 'Text wrap enabled' : 'Text wrap disabled'"
          :class="['transition-all', textWrap ? '-translate-y-px ring ring-default shadow-xs' : '']"
          @click="textWrap = !textWrap"
        >
          Wrap
        </UButton>

        <USelectMenu
          v-model="selectedLevels"
          :items="levelFilterItems"
          value-key="value"
          label-key="label"
          color="neutral"
          multiple
          size="sm"
          icon="i-lucide-list-filter"
          class="w-44 shrink-0 sm:w-48"
          :ui="{ content: 'min-w-48', item: 'pl-6' }"
          :search-input="false"
        >
          {{ levelFilterLabel }}
        </USelectMenu>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-sliders-horizontal"
          class="shrink-0"
          :loading="runtimeLogLevelLoading"
          :disabled="!canApplyRuntimeLogLevel || runtimeLogLevelLoading"
          @click="applyRuntimeLogLevel"
        >
          Apply
        </UButton>

        <UInput
          v-if="toggleFilter || query"
          id="filter"
          v-model.lazy="query"
          type="search"
          placeholder="Filter displayed content"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </div>
    </div>

    <UPageCard variant="naked" :ui="pageCardUi">
      <template #body>
        <div class="overflow-hidden rounded-sm border border-default bg-default shadow-sm">
          <div
            ref="logContainer"
            class="w-full min-w-0 max-w-full min-h-[55vh] max-h-[60vh] overflow-x-auto overflow-y-auto bg-transparent font-mono text-sm text-default overscroll-x-contain"
            @scroll.passive="handleScroll"
          >
            <div
              v-if="reachedEnd && !hasActiveFilter"
              class="flex justify-center border-b border-default/40 px-4 py-3"
            >
              <div
                class="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-[11px] font-medium text-warning"
              >
                <UIcon name="i-lucide-triangle-alert" class="size-3.5 shrink-0" />
                No older lines remain in this file.
              </div>
            </div>

            <div
              v-if="canLoadFilteredHistory"
              class="flex justify-center border-b border-default/40 px-4 py-3"
            >
              <UButton
                color="neutral"
                variant="outline"
                size="xs"
                icon="i-lucide-history"
                :loading="loading"
                @click="fetchLogs(true)"
              >
                Load older lines into filter
              </UButton>
            </div>

            <template v-if="filteredLogs.length > 0">
              <article
                v-for="(entry, index) in filteredLogs"
                :key="entry.log.id"
                :class="logRowClass(entry, index)"
              >
                <div
                  :class="[
                    'flex min-w-0 flex-1 items-start gap-[0.65rem] px-3 py-[0.65rem] leading-[1.6]',
                    textWrap ? 'w-full' : 'w-max min-w-full',
                  ]"
                >
                  <p :class="logLineClass()">
                    <span
                      class="inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-1 align-middle"
                    >
                      <UTooltip :text="logTimeTitle(entry.log.datetime)">
                        <span class="inline text-[11px] font-semibold text-toned cursor-pointer">
                          {{ logTimeLabel(entry.log.datetime) }}
                        </span>
                      </UTooltip>
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="xs"
                        icon="i-lucide-panel-right-open"
                        aria-label="Open log details"
                        class="inline-flex align-[-0.2em] opacity-70 hover:opacity-100"
                        @click="openLogDetails(entry.log)"
                      />
                      <span
                        :class="logLevelBadgeClass(getLogLevel(entry.log.level))"
                        @click="openLogDetails(entry.log)"
                      >
                        <UIcon
                          :name="LOG_LEVEL_ICON[getLogLevel(entry.log.level)]"
                          class="size-3"
                        />
                        {{ getLogLevel(entry.log.level) }}
                      </span>
                      <span
                        v-if="
                          entry.log.logger && !['ytptube', 'http_api'].includes(entry.log.logger)
                        "
                        :title="entry.log.logger"
                        class="inline-block max-w-[46vw] truncate align-middle text-[11px] font-semibold text-toned sm:max-w-104"
                        >[{{ entry.log.logger }}]</span
                      >
                    </span>
                    <span class="ml-2">{{ entry.log.message }}</span>
                    <span v-if="exceptionSummary(entry.log)" class="ml-1 text-error/90">
                      : {{ exceptionSummary(entry.log) }}
                    </span>
                  </p>
                </div>
              </article>
            </template>

            <div
              v-else
              class="flex min-h-[55vh] flex-col items-center justify-center gap-3 px-6 py-8 text-center font-sans"
            >
              <UIcon
                :name="hasActiveFilter ? 'i-lucide-filter-x' : 'i-lucide-circle-off'"
                class="size-6 text-toned"
              />

              <div class="space-y-1">
                <p class="text-sm font-medium text-default">
                  {{ hasActiveFilter ? 'No logs match these filters' : 'No log lines available' }}
                </p>

                <p class="text-sm text-toned">
                  {{ hasActiveFilter ? 'No logs match these filters' : 'No log lines available' }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UPageCard>

    <LogDetailModal v-model="detailsOpen" :log="selectedLog" />
  </main>
</template>

<script setup lang="ts">
import { fetchEventSource } from '@microsoft/fetch-event-source';
import type { EventSourceMessage } from '@microsoft/fetch-event-source';
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import type { log_line } from '~/types/logs';
import { parse_api_error, request, uri } from '~/utils';
import { requirePageShell } from '~/utils/topLevelNavigation';

type FilteredLogEntry = {
  log: log_line;
  level: LogLevel;
  isMatch: boolean;
  isContext: boolean;
};

type LogLevel = 'debug' | 'info' | 'warning' | 'error';
type LevelFilterItem = {
  label: string;
  value: LogLevel;
};

const FILTER_CONTEXT_REGEX = /context:(\d+)/;
const LOG_LEVELS: LogLevel[] = ['debug', 'info', 'warning', 'error'];
const LOG_ROW_CLASS =
  'flex min-w-0 border-b border-default/40 bg-transparent transition-colors duration-150 last:border-b-0 hover:bg-elevated/70';
const LOG_LEVEL_ICON: Record<LogLevel, string> = {
  debug: 'i-lucide-terminal',
  info: 'i-lucide-info',
  warning: 'i-lucide-triangle-alert',
  error: 'i-lucide-circle-x',
};
const formatLogLevel = (level: LogLevel): string => level.charAt(0).toUpperCase() + level.slice(1);
const getStoredRuntimeLogLevel = (): LogLevel | null => {
  return config.app.runtime_log_level ? getLogLevel(config.app.runtime_log_level) : null;
};

let scrollTimeout: NodeJS.Timeout | null = null;

const toast = useNotification();
const config = useYtpConfig();
const route = useRoute();
const pageShell = requirePageShell('logs');

const logContainer = useTemplateRef<HTMLDivElement>('logContainer');
const textWrap = useStorage<boolean>('logs_wrap', true);
const selectedLevels = useStorage<LogLevel[]>('logs_level_filter', [...LOG_LEVELS]);
const sseController = ref<AbortController | null>(null);
const runtimeLogLevel = ref<LogLevel | null>(null);
const runtimeLogLevelLoading = ref(false);

const logs = ref<Array<log_line>>([]);
const selectedLog = ref<log_line | null>(null);
const offset = ref(0);
const loading = ref(false);
const autoScroll = ref(true);
const reachedEnd = ref(false);
const detailsOpen = ref(false);

const pageCardUi = {
  root: 'w-full min-w-0 max-w-full bg-transparent',
  container: 'w-full min-w-0 max-w-full p-4 sm:p-5',
  wrapper: 'w-full min-w-0 items-stretch',
  body: 'w-full min-w-0 max-w-full overflow-hidden',
};

const query = ref<string>(
  (() => {
    const filter = route.query.filter ?? '';
    if (!filter) {
      return '';
    }

    if (typeof filter === 'string') {
      return filter.trim();
    }

    if (Array.isArray(filter) && filter.length > 0) {
      return filter[0]?.trim() ?? '';
    }

    return '';
  })(),
);

const toggleFilter = ref(Boolean(query.value));

const normalizedQuery = computed(() => query.value.trim().toLowerCase());
const selectedLevelSet = computed(
  () => new Set(LOG_LEVELS.filter((level) => selectedLevels.value.includes(level))),
);
const hasLevelFilter = computed(() => selectedLevelSet.value.size !== LOG_LEVELS.length);
const filterContext = computed(() => {
  const match = normalizedQuery.value.match(FILTER_CONTEXT_REGEX);
  return match ? parseInt(match[1] ?? '0', 10) : 0;
});
const searchTerm = computed(() => normalizedQuery.value.replace(FILTER_CONTEXT_REGEX, '').trim());
const hasTextFilter = computed(() => Boolean(searchTerm.value));
const hasActiveFilter = computed(() => hasTextFilter.value || hasLevelFilter.value);
const canLoadFilteredHistory = computed(
  () => hasActiveFilter.value && !reachedEnd.value && logs.value.length > 0,
);
const levelCounts = computed<Record<LogLevel, number>>(() => {
  const counts: Record<LogLevel, number> = {
    debug: 0,
    info: 0,
    warning: 0,
    error: 0,
  };

  logs.value.forEach((log) => {
    const level = getLogLevel(log.level);
    counts[level] += 1;
  });

  return counts;
});

const levelFilterItems = computed<LevelFilterItem[]>(() => [
  ...LOG_LEVELS.map((level) => ({
    label: `${formatLogLevel(level)} (${levelCounts.value[level]})`,
    value: level,
  })),
]);

const runtimeLogLevelCandidate = computed<LogLevel | null>(() => {
  for (const level of LOG_LEVELS) {
    const thresholdLevels = LOG_LEVELS.slice(LOG_LEVELS.indexOf(level));
    if (thresholdLevels.length !== selectedLevelSet.value.size) {
      continue;
    }

    if (thresholdLevels.every((item) => selectedLevelSet.value.has(item))) {
      return level;
    }
  }

  return null;
});

const canApplyRuntimeLogLevel = computed(
  () =>
    runtimeLogLevelCandidate.value !== null &&
    runtimeLogLevel.value !== null &&
    runtimeLogLevelCandidate.value !== runtimeLogLevel.value,
);

const levelFilterLabel = computed(() => {
  if (selectedLevelSet.value.size === LOG_LEVELS.length) {
    return `All levels`;
  }

  if (selectedLevelSet.value.size === 0) {
    return 'No levels selected';
  }

  return LOG_LEVELS.filter((level) => selectedLevelSet.value.has(level)).join(', ');
});

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = '';
    scrollToBottom(true);
  }
});

watch(
  () => config.app.file_logging,
  async (value) => {
    if (value) {
      return;
    }

    await navigateTo('/');
  },
);

watch(detailsOpen, (open) => {
  if (!open) {
    selectedLog.value = null;
  }
});

const filteredLogs = computed<FilteredLogEntry[]>(() => {
  if (!hasActiveFilter.value) {
    return logs.value.map((log) => ({
      log,
      level: getLogLevel(log.level),
      isMatch: false,
      isContext: false,
    }));
  }

  const result: Array<FilteredLogEntry> = [];
  const visibleIndexes = new Set<number>();
  const matchedIndexes = new Set<number>();

  logs.value.forEach((log, index) => {
    if (!selectedLevelSet.value.has(getLogLevel(log.level))) {
      return;
    }

    if (!hasTextFilter.value) {
      visibleIndexes.add(index);
      return;
    }

    if (searchableLog(log).includes(searchTerm.value)) {
      matchedIndexes.add(index);

      for (
        let i = Math.max(0, index - filterContext.value);
        i <= Math.min(logs.value.length - 1, index + filterContext.value);
        i++
      ) {
        visibleIndexes.add(i);
      }
    }
  });

  Array.from(visibleIndexes)
    .sort((a, b) => a - b)
    .forEach((index) => {
      const log = logs.value[index] as log_line;
      if (!selectedLevelSet.value.has(getLogLevel(log.level))) {
        return;
      }

      result.push({
        log,
        level: getLogLevel(log.level),
        isMatch: matchedIndexes.has(index),
        isContext: !matchedIndexes.has(index),
      });
    });

  return result;
});

const scrollLogContainerToBottom = async (behavior: ScrollBehavior = 'auto'): Promise<void> => {
  await nextTick();

  if (!logContainer.value) {
    return;
  }

  logContainer.value.scrollTo({
    top: logContainer.value.scrollHeight,
    behavior,
  });
};

const fetchLogs = async (force = false): Promise<void> => {
  loading.value = true;

  if (reachedEnd.value || (!force && hasActiveFilter.value && logs.value.length > 0)) {
    loading.value = false;
    return;
  }

  try {
    const req = await request(`/api/logs?offset=${offset.value}`);
    if (!req.ok) {
      toast.error('Failed to fetch logs');
      return;
    }

    const response = await req.json();
    if (response.error) {
      toast.error(response.error);
      return;
    }

    const lines = response.logs ?? [];
    if (lines.length) {
      logs.value.unshift(...response.logs);
    }

    if (response?.next_offset) {
      offset.value = response.next_offset;
    }

    if (response?.end_is_reached) {
      reachedEnd.value = true;
    }

    if (autoScroll.value) {
      await scrollLogContainerToBottom();
    }
  } catch (error) {
    console.error('Failed to fetch logs:', error);
  } finally {
    loading.value = false;
  }
};

const handleScroll = (): void => {
  if (!logContainer.value || hasActiveFilter.value) {
    return;
  }

  const container = logContainer.value;
  const nearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50;
  const nearTop = container.scrollTop < 50;

  autoScroll.value = nearBottom;

  if (nearTop && !loading.value && !scrollTimeout) {
    scrollTimeout = setTimeout(async () => {
      const previousHeight = container.scrollHeight;
      await fetchLogs();
      nextTick(() => {
        const newHeight = container.scrollHeight;
        container.scrollTop += newHeight - previousHeight;
      });
      scrollTimeout = null;
    }, 300);
  }
};

const scrollToBottom = async (fast = false): Promise<void> => {
  autoScroll.value = true;
  await scrollLogContainerToBottom(fast ? 'auto' : 'smooth');
};

const loadRuntimeLogLevel = async (): Promise<void> => {
  try {
    const response = await request('/api/logs/level');
    if (!response.ok) {
      runtimeLogLevel.value = getStoredRuntimeLogLevel();
      return;
    }

    const data = await response.json();
    if (typeof data.conf === 'string' && data.conf) {
      config.app.log_level = getLogLevel(data.conf);
    }

    if (!config.app.log_level && getStoredRuntimeLogLevel() === null) {
      runtimeLogLevel.value = null;
      return;
    }

    if (typeof data.active === 'string' && data.active) {
      const level = getLogLevel(data.active);
      runtimeLogLevel.value = level;
      config.app.runtime_log_level = level;
      return;
    }

    runtimeLogLevel.value = getStoredRuntimeLogLevel();
  } catch (error) {
    runtimeLogLevel.value = getStoredRuntimeLogLevel();
    console.error('Failed to load runtime log level:', error);
  }
};

const applyRuntimeLogLevel = async (): Promise<void> => {
  const normalized = runtimeLogLevelCandidate.value;
  if (!normalized || runtimeLogLevel.value === null || normalized === runtimeLogLevel.value) {
    return;
  }

  const previous = runtimeLogLevel.value;

  try {
    runtimeLogLevelLoading.value = true;
    const response = await request(`/api/logs/level/${normalized}`, {
      method: 'POST',
    });

    if (!response.ok) {
      const data = await response.json();
      const message = await parse_api_error(data);
      runtimeLogLevel.value = previous;
      toast.error(`Failed to change log level. ${message}`);
      return;
    }

    runtimeLogLevel.value = normalized;
    config.app.runtime_log_level = normalized;
    toast.success('log level updated until next restart.');
  } catch (error: any) {
    runtimeLogLevel.value = previous;
    const message = error?.message || 'Unknown error';
    toast.error(`Failed to change log level. ${message}`);
  } finally {
    runtimeLogLevelLoading.value = false;
  }
};

const handleStreamMessage = (event: EventSourceMessage): void => {
  if (event.event !== 'log_lines' || !event.data) {
    return;
  }

  let payload: log_line | null = null;
  try {
    payload = JSON.parse(event.data) as log_line;
  } catch {
    payload = null;
  }

  if (!payload) {
    return;
  }

  logs.value.push(payload);

  if (autoScroll.value) {
    void scrollLogContainerToBottom('smooth');
  }
};

const startLogStream = async (): Promise<void> => {
  sseController.value?.abort();
  const controller = new AbortController();
  sseController.value = controller;

  try {
    await fetchEventSource(uri('/api/logs/stream'), {
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
      },
      credentials: 'same-origin',
      signal: controller.signal,
      onopen: async (response) => {
        if (response.ok) {
          return;
        }

        let message = response.statusText || 'Failed to start log stream.';
        try {
          message = await parse_api_error(response.clone().json());
        } catch {
          try {
            const text = await response.text();
            if (text) {
              message = text;
            }
          } catch {
            message = response.statusText || 'Failed to start log stream.';
          }
        }

        throw new Error(message);
      },
      onmessage: handleStreamMessage,
      onerror: (error) => {
        if (controller.signal.aborted) {
          return;
        }

        console.error('Log stream error:', error);
      },
    });
  } catch (error) {
    if (!controller.signal.aborted) {
      console.error('Log stream error:', error);
    }
  } finally {
    if (controller === sseController.value) {
      sseController.value = null;
    }
  }
};

const logTimeLabel = (value?: string): string =>
  value ? moment(value).format('HH:mm:ss') : '00:00:00';

const logTimeTitle = (value?: string): string =>
  value ? moment(value).format('YYYY-MM-DD HH:mm:ss Z') : 'No timestamp';

const exceptionSummary = (log: log_line): string => {
  const type = log.exception?.type?.trim() ?? '';
  const message = log.exception?.message?.trim() ?? '';

  if (type && message) {
    return `${type}: ${message}`;
  }

  return type || message;
};

const searchableLog = (log: log_line): string =>
  [
    log.message,
    log.level,
    log.logger,
    exceptionSummary(log),
    log.exception ? JSON.stringify(log.exception) : '',
    log.source ? JSON.stringify(log.source) : '',
    log.process ? JSON.stringify(log.process) : '',
    log.thread ? JSON.stringify(log.thread) : '',
    log.fields ? JSON.stringify(log.fields) : '',
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

const getLogLevel = (level: string): LogLevel => {
  switch (level.toLowerCase()) {
    case 'info':
      return 'info';
    case 'warning':
    case 'warn':
      return 'warning';
    case 'error':
    case 'critical':
    case 'fatal':
      return 'error';
    default:
      return 'debug';
  }
};

const logLevelBadgeClass = (level: LogLevel): string[] => [
  'inline-flex items-center gap-1.5 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide cursor-pointer',
  level === 'debug' ? 'bg-muted/40 text-muted' : '',
  level === 'info' ? 'bg-info/10 text-info' : '',
  level === 'warning' ? 'bg-warning/10 text-warning' : '',
  level === 'error' ? 'bg-error/10 text-error' : '',
];

const logLineClass = (): string[] => [
  'flex-1',
  textWrap.value
    ? 'min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]'
    : 'min-w-max whitespace-pre',
  'text-default',
];

const logRowClass = (entry: FilteredLogEntry, index: number): string[] => {
  const classes = [LOG_ROW_CLASS];

  if (entry.isMatch) {
    classes.push('bg-warning/10');
    return classes;
  }

  if (entry.isContext) {
    classes.push('bg-muted/30');
    return classes;
  }

  if (index % 2 === 1) {
    classes.push('bg-elevated/40');
  }

  return classes;
};

const openLogDetails = (log: log_line): void => {
  selectedLog.value = log;
  detailsOpen.value = true;
};

onMounted(async () => {
  if (!config.app.file_logging) {
    await navigateTo('/');
    return;
  }

  runtimeLogLevel.value = getStoredRuntimeLogLevel();
  await loadRuntimeLogLevel();
  await fetchLogs();
  await startLogStream();
});

onBeforeUnmount(() => {
  sseController.value?.abort();

  if (scrollTimeout) {
    clearTimeout(scrollTimeout);
    scrollTimeout = null;
  }
});
</script>
