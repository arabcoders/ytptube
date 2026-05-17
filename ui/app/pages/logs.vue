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
                  <span
                    :class="[
                      'mt-[0.45rem] inline-flex size-2 shrink-0 rounded-full',
                      logLevelDotClass(entry.level),
                    ]"
                  />
                  <p :class="logLineClass(entry.level)">
                    <span
                      class="mr-2 inline text-[11px] font-semibold text-toned cursor-pointer"
                      :title="logTimeTitle(entry.log.datetime)"
                    >
                      {{ logTimeLabel(entry.log.datetime) }}
                    </span>
                    {{ entry.log.line }}
                  </p>
                </div>
              </article>
            </template>

            <div
              v-else
              class="flex min-h-[55vh] flex-col items-center justify-center gap-3 px-6 py-8 text-center font-sans"
            >
              <UIcon
                :name="query ? 'i-lucide-filter-x' : 'i-lucide-circle-off'"
                class="size-6 text-toned"
              />

              <div class="space-y-1">
                <p class="text-sm font-medium text-default">
                  {{ query ? 'No logs match this query' : 'No log lines available' }}
                </p>

                <p class="text-sm text-toned">
                  {{
                    query
                      ? `No log lines found for the query: ${query}. Please try a different search term.`
                      : 'No log lines are available yet.'
                  }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </template>
    </UPageCard>
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

const FILTER_CONTEXT_REGEX = /context:(\d+)/;
const LOG_LEVEL_PREFIX =
  /^\s*(?:\[(debug|info|warning|warn|error|critical|fatal)(?:[.\]])|(debug|info|warning|warn|error|critical|fatal)\b(?::|\s|-))/i;
const LOG_ROW_CLASS =
  'flex min-w-0 border-b border-default/40 bg-transparent transition-colors duration-150 last:border-b-0 hover:bg-elevated/70';
const LOG_LEVEL_DOT_CLASS: Record<LogLevel, string> = {
  debug: 'bg-muted',
  info: 'bg-info',
  warning: 'bg-warning',
  error: 'bg-error',
};
const LOG_LEVEL_TEXT_CLASS: Record<LogLevel, string> = {
  debug: 'text-toned',
  info: 'text-info',
  warning: 'text-warning',
  error: 'text-error',
};

let scrollTimeout: NodeJS.Timeout | null = null;

const toast = useNotification();
const config = useYtpConfig();
const route = useRoute();
const pageShell = requirePageShell('logs');

const logContainer = useTemplateRef<HTMLDivElement>('logContainer');
const textWrap = useStorage<boolean>('logs_wrap', true);
const sseController = ref<AbortController | null>(null);

const logs = ref<Array<log_line>>([]);
const offset = ref(0);
const loading = ref(false);
const autoScroll = ref(true);
const reachedEnd = ref(false);

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
const filterContext = computed(() => {
  const match = normalizedQuery.value.match(FILTER_CONTEXT_REGEX);
  return match ? parseInt(match[1] ?? '0', 10) : 0;
});
const searchTerm = computed(() => normalizedQuery.value.replace(FILTER_CONTEXT_REGEX, '').trim());
const hasActiveFilter = computed(() => Boolean(searchTerm.value));
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

const filteredLogs = computed<FilteredLogEntry[]>(() => {
  if (!hasActiveFilter.value) {
    return logs.value.map((log) => ({
      log,
      level: detectLogLevel(log.line),
      isMatch: false,
      isContext: false,
    }));
  }

  const result: Array<FilteredLogEntry> = [];
  const visibleIndexes = new Set<number>();
  const matchedIndexes = new Set<number>();

  logs.value.forEach((log, index) => {
    if (log.line.toLowerCase().includes(searchTerm.value)) {
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

      result.push({
        log,
        level: detectLogLevel(log.line),
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

const fetchLogs = async (): Promise<void> => {
  loading.value = true;

  if (reachedEnd.value || (hasActiveFilter.value && logs.value.length > 0)) {
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

const detectLogLevel = (line: string): LogLevel => {
  const match = line.match(LOG_LEVEL_PREFIX);
  const level = match?.[1] ?? match?.[2];

  return level ? getLogLevel(level) : 'debug';
};

const logLevelDotClass = (level: LogLevel): string => LOG_LEVEL_DOT_CLASS[level];

const logLineClass = (level: LogLevel): string[] => [
  'flex-1',
  textWrap.value
    ? 'min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]'
    : 'min-w-max whitespace-pre',
  LOG_LEVEL_TEXT_CLASS[level],
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

onMounted(async () => {
  if (!config.app.file_logging) {
    await navigateTo('/');
    return;
  }

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
