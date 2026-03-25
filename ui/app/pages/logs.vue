<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex flex-wrap items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-file-text" class="size-5 text-toned" />
          <span>Logs</span>

          <UBadge :color="loading ? 'info' : 'success'" variant="soft" size="sm">
            {{ loading ? 'Loading history' : 'Live stream' }}
          </UBadge>

          <UBadge :color="autoScroll ? 'success' : 'neutral'" variant="soft" size="sm">
            {{ autoScroll ? 'Auto-follow' : 'Manual scroll' }}
          </UBadge>

          <UBadge color="neutral" variant="soft" size="sm">
            {{ filteredLogs.length }} shown
          </UBadge>

          <UBadge
            v-if="logs.length !== filteredLogs.length"
            color="neutral"
            variant="outline"
            size="sm"
          >
            {{ logs.length }} loaded
          </UBadge>

          <UBadge v-if="hasActiveFilter" color="warning" variant="soft" size="sm">
            {{ matchCount }} matches
          </UBadge>

          <UBadge v-if="reachedEnd && !hasActiveFilter" color="neutral" variant="soft" size="sm">
            Start of file loaded
          </UBadge>
        </div>

        <p class="text-sm text-toned">Scroll near the top to load older logs.</p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <UButton
          v-if="!autoScroll"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-arrow-down"
          @click="scrollToBottom(false)"
        >
          Jump to Live Tail
        </UButton>

        <div v-if="toggleFilter || query" class="relative w-full sm:w-72">
          <span
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-toned"
          >
            <UIcon name="i-lucide-filter" class="size-4" />
          </span>

          <input
            id="filter"
            v-model.lazy="query"
            type="search"
            placeholder="Filter displayed content"
            class="w-full rounded-md border border-default bg-elevated py-2 pr-3 pl-9 text-sm text-default outline-none transition focus:border-primary"
          />
        </div>

        <UButton
          color="neutral"
          :variant="toggleFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter = !toggleFilter"
        >
          Filter
        </UButton>

        <USwitch
          v-model="textWrap"
          color="primary"
          size="sm"
          :label="textWrap ? 'Wrap lines' : 'Horizontal scroll'"
          :ui="{ root: 'items-center gap-2', wrapper: 'ms-0 text-xs text-toned' }"
        />
      </div>
    </div>

    <UPageCard variant="naked" :ui="pageCardUi">
      <template #body>
        <div class="space-y-3">
          <div class="flex flex-wrap items-center justify-end gap-2 text-xs text-toned">
            <span v-if="searchTerm">
              Query: <code>{{ searchTerm }}</code>
            </span>

            <span v-if="filterContext > 0">
              Context: <code>{{ filterContext }}</code>
            </span>
          </div>

          <div ref="logContainer" class="logbox overflow-auto" @scroll.passive="handleScroll">
            <div
              class="min-w-full space-y-2 font-mono text-[12px] leading-6 text-default"
              role="log"
              aria-live="polite"
            >
              <div v-if="reachedEnd && !hasActiveFilter" class="flex justify-center">
                <div
                  class="rounded-full border border-default bg-muted/40 px-3 py-1 text-[11px] text-toned"
                >
                  No older lines remain in this file.
                </div>
              </div>

              <div v-if="filteredLogs.length > 0" class="space-y-1.5">
                <article
                  v-for="(entry, index) in filteredLogs"
                  :key="entry.log.id"
                  :class="logRowClass(entry, index)"
                >
                  <span class="log-timestamp" :title="logTimeTitle(entry.log.datetime)">
                    {{ logTimeLabel(entry.log.datetime) }}
                  </span>

                  <p class="log-line" :class="textWrap ? 'log-line--wrap' : 'log-line--nowrap'">
                    {{ entry.log.line }}
                  </p>
                </article>
              </div>

              <div
                v-else
                class="rounded-xl border border-default bg-muted/20 px-4 py-6 text-center"
              >
                <div class="space-y-2">
                  <p class="text-sm font-semibold text-highlighted">
                    {{
                      hasActiveFilter
                        ? 'No log lines match the current filter.'
                        : 'No log lines are available yet.'
                    }}
                  </p>

                  <p v-if="hasActiveFilter" class="text-xs text-toned">
                    Try a different term or clear <code>{{ query }}</code
                    >.
                  </p>
                </div>
              </div>

              <div ref="bottomMarker" />
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
import { disableOpacity, enableOpacity, parse_api_error, request, uri } from '~/utils';

type FilteredLogEntry = {
  log: log_line;
  isMatch: boolean;
  isContext: boolean;
};

type LogTone = 'default' | 'info' | 'warning' | 'error';

const FILTER_CONTEXT_REGEX = /context:(\d+)/;

let scrollTimeout: NodeJS.Timeout | null = null;

const toast = useNotification();
const config = useConfigStore();
const route = useRoute();

const logContainer = useTemplateRef<HTMLDivElement>('logContainer');
const bottomMarker = useTemplateRef<HTMLDivElement>('bottomMarker');
const textWrap = useStorage<boolean>('logs_wrap', true);
const sseController = ref<AbortController | null>(null);

const logs = ref<Array<log_line>>([]);
const offset = ref(0);
const loading = ref(false);
const autoScroll = ref(true);
const reachedEnd = ref(false);

const pageCardUi = {
  root: 'w-full bg-transparent',
  container: 'w-full p-4 sm:p-5',
  wrapper: 'w-full items-stretch',
  body: 'w-full',
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
    return logs.value.map((log) => ({ log, isMatch: false, isContext: false }));
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
      result.push({
        log: logs.value[index] as log_line,
        isMatch: matchedIndexes.has(index),
        isContext: !matchedIndexes.has(index),
      });
    });

  return result;
});

const matchCount = computed(() => filteredLogs.value.filter((entry) => entry.isMatch).length);

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

    nextTick(() => {
      if (autoScroll.value && bottomMarker.value) {
        bottomMarker.value.scrollIntoView({ behavior: 'auto' });
      }
    });
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

const scrollToBottom = (fast = false): void => {
  autoScroll.value = true;
  nextTick(() => {
    bottomMarker.value?.scrollIntoView({ behavior: fast ? 'auto' : 'smooth' });
  });
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

  nextTick(() => {
    if (autoScroll.value && bottomMarker.value) {
      bottomMarker.value.scrollIntoView({ behavior: 'smooth' });
    }
  });
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
  value ? moment(value).format('HH:mm:ss') : '--:--:--';

const logTimeTitle = (value?: string): string =>
  value ? moment(value).format('YYYY-MM-DD HH:mm:ss Z') : 'No timestamp';

const detectLogTone = (line: string): LogTone => {
  const normalized = line.toLowerCase();

  if (/error|failed|exception|traceback|fatal/.test(normalized)) {
    return 'error';
  }

  if (/warn|deprecated|retry/.test(normalized)) {
    return 'warning';
  }

  if (/info|started|connected|listening|ready/.test(normalized)) {
    return 'info';
  }

  return 'default';
};

const logRowClass = (entry: FilteredLogEntry, index: number): string[] => {
  const classes = ['log-row', `log-row--${detectLogTone(entry.log.line)}`];

  if (entry.isMatch) {
    classes.push('log-row--match');
    return classes;
  }

  if (entry.isContext) {
    classes.push('log-row--context');
    return classes;
  }

  if (index % 2 === 1) {
    classes.push('log-row--alt');
  }

  return classes;
};

onMounted(async () => {
  if (!config.app.file_logging) {
    await navigateTo('/');
    return;
  }

  disableOpacity();
  await fetchLogs();
  await startLogStream();
});

onBeforeUnmount(() => {
  sseController.value?.abort();
  enableOpacity();

  if (scrollTimeout) {
    clearTimeout(scrollTimeout);
    scrollTimeout = null;
  }
});

useHead({ title: 'Logs' });
</script>

<style scoped>
.logbox {
  min-width: 100%;
  min-height: 55vh;
  max-height: 60vh;
  background: transparent;
  padding: 0.75rem;
}

.log-row {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  padding: 0.625rem 0.75rem;
  background: var(--ui-bg);
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease;
}

.log-row--alt {
  background: var(--ui-bg-elevated);
}

.log-row--match {
  border-color: color-mix(in oklab, var(--ui-warning) 35%, transparent);
  background: color-mix(in oklab, var(--ui-warning) 12%, var(--ui-bg) 88%);
}

.log-row--context {
  border-color: color-mix(in oklab, var(--ui-border) 75%, transparent);
  background: color-mix(in oklab, var(--ui-bg-muted) 30%, var(--ui-bg) 70%);
}

.log-row:hover {
  border-color: var(--ui-border-accented);
  background: color-mix(in oklab, var(--ui-bg-elevated) 65%, var(--ui-bg-muted) 35%);
}

.log-timestamp {
  display: inline-flex;
  min-width: 4.75rem;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  border: 1px solid color-mix(in oklab, var(--ui-border) 80%, transparent);
  background: color-mix(in oklab, var(--ui-bg-muted) 50%, var(--ui-bg) 50%);
  padding: 0.2rem 0.55rem;
  font-size: 11px;
  font-weight: 600;
  color: var(--ui-text-toned);
}

.log-line {
  flex: 1;
  min-width: 0;
}

.log-line--wrap {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.log-line--nowrap {
  min-width: max-content;
  white-space: pre;
}

.log-row--default .log-line {
  color: var(--ui-text-highlighted);
}

.log-row--info .log-line {
  color: color-mix(in oklab, var(--ui-info) 55%, var(--ui-text-highlighted) 45%);
}

.log-row--warning .log-line {
  color: color-mix(in oklab, var(--ui-warning) 60%, var(--ui-text-highlighted) 40%);
}

.log-row--error .log-line {
  color: color-mix(in oklab, var(--ui-error) 70%, var(--ui-text-highlighted) 30%);
}
</style>
