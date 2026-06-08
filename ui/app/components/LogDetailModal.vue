<template>
  <UModal
    :open="open"
    title="Log details"
    :ui="{
      content: 'max-w-5xl',
      body: 'max-h-[75vh] overflow-y-auto',
    }"
    @update:open="emit('update:modelValue', $event)"
  >
    <template #body>
      <div v-if="log" class="space-y-5">
        <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
          <div class="flex min-w-0 flex-wrap items-center gap-2">
            <UBadge
              :color="LOG_LEVEL_COLOR[getLogLevel(log.level)]"
              variant="soft"
              size="sm"
              class="uppercase"
            >
              <UIcon :name="LOG_LEVEL_ICON[getLogLevel(log.level)]" class="mr-1 size-3.5" />
              {{ getLogLevel(log.level) }}
            </UBadge>
            <UBadge
              v-if="log.logger"
              color="neutral"
              variant="soft"
              size="sm"
              class="max-w-full min-w-0"
              :title="log.logger"
            >
              <UIcon name="i-lucide-tag" class="mr-1 size-3.5" />
              <span class="min-w-0 max-w-full truncate">{{ log.logger }}</span>
            </UBadge>
            <span class="text-xs text-toned">{{ logTimeTitle(log.datetime) }}</span>
          </div>

          <div class="flex shrink-0 flex-wrap justify-end gap-2">
            <UDropdownMenu :items="copyMenuItems" :content="{ align: 'end' }" :modal="false">
              <UButton
                color="neutral"
                variant="outline"
                size="xs"
                icon="i-lucide-copy"
                trailing-icon="i-lucide-chevron-down"
              >
                Copy
              </UButton>
            </UDropdownMenu>
          </div>

          <div class="min-w-0 space-y-2 sm:col-span-2">
            <p class="wrap-break-word w-full font-mono text-sm text-default">
              {{ log.message }}
            </p>

            <UAlert
              v-if="exceptionSummary(log)"
              color="error"
              variant="soft"
              icon="i-lucide-badge-alert"
              :title="exceptionSummary(log)"
              class="w-full"
            />
          </div>
        </div>

        <section v-if="log.exception" class="space-y-2">
          <button
            type="button"
            class="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-toned hover:text-default"
            @click="exceptionOpen = !exceptionOpen"
          >
            <UIcon
              name="i-lucide-chevron-right"
              :class="['size-4 transition-transform', exceptionOpen ? 'rotate-90' : '']"
            />
            <UIcon name="i-lucide-bug" class="size-4 text-error" />
            Exception
          </button>
          <pre
            v-if="exceptionOpen"
            class="max-h-72 overflow-auto rounded-sm border border-error/30 bg-error/5 p-3 text-xs whitespace-pre-wrap text-error"
            >{{ exceptionText(log) }}</pre
          >
        </section>

        <section v-if="detailRows(log).length > 0" class="space-y-2">
          <button
            type="button"
            class="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-toned hover:text-default"
            @click="sourceOpen = !sourceOpen"
          >
            <UIcon
              name="i-lucide-chevron-right"
              :class="['size-4 transition-transform', sourceOpen ? 'rotate-90' : '']"
            />
            <UIcon name="i-lucide-file-code" class="size-4 text-info" />
            Source
          </button>
          <dl v-if="sourceOpen" class="grid gap-2 sm:grid-cols-2">
            <div
              v-for="row in detailRows(log)"
              :key="row.label"
              class="rounded-sm border border-default bg-elevated/40 p-3"
            >
              <dt
                class="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-toned"
              >
                <UIcon :name="row.icon" class="size-3.5" />
                <span>{{ row.label }}</span>
              </dt>
              <dd class="mt-1 wrap-break-word font-mono text-xs text-default">{{ row.value }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="fieldRows(log).length > 0" class="space-y-2">
          <button
            type="button"
            class="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-toned hover:text-default"
            @click="fieldsOpen = !fieldsOpen"
          >
            <UIcon
              name="i-lucide-chevron-right"
              :class="['size-4 transition-transform', fieldsOpen ? 'rotate-90' : '']"
            />
            <UIcon name="i-lucide-tags" class="size-4 text-primary" />
            Fields
          </button>
          <div v-if="fieldsOpen" class="space-y-2">
            <div
              v-for="field in fieldRows(log)"
              :key="field.key"
              class="rounded-sm border border-default bg-elevated/40"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
                @click="toggleField(field.key)"
              >
                <span class="text-[11px] font-semibold uppercase tracking-wide text-toned">
                  {{ field.label }}
                </span>
                <div class="flex items-center gap-2">
                  <span v-if="field.preview" class="max-w-md truncate text-xs text-toned">
                    {{ field.preview }}
                  </span>
                  <UIcon
                    name="i-lucide-chevron-right"
                    :class="[
                      'size-4 shrink-0 text-toned transition-transform',
                      fieldOpen(field.key) ? 'rotate-90' : '',
                    ]"
                  />
                </div>
              </button>

              <div v-if="fieldOpen(field.key)" class="border-t border-default/70 px-3 py-3">
                <div class="mb-3 flex items-center justify-between gap-3">
                  <UInput
                    v-if="field.kind !== 'scalar'"
                    :model-value="fieldFilter(field.key)"
                    type="search"
                    icon="i-lucide-filter"
                    placeholder="Filter field lines"
                    size="sm"
                    class="w-full"
                    @update:model-value="setFieldFilter(field.key, $event)"
                  />
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-copy"
                    @click="copyFieldValue(field)"
                  >
                    Copy
                  </UButton>
                </div>

                <pre
                  v-if="field.kind === 'json'"
                  class="max-h-96 overflow-auto rounded-sm border border-default bg-elevated/50 p-3 text-xs whitespace-pre-wrap text-default"
                  >{{ displayedFieldValue(field) }}</pre
                >
                <pre
                  v-else-if="field.kind === 'text'"
                  class="max-h-96 overflow-auto rounded-sm border border-default bg-elevated/50 p-3 text-xs whitespace-pre-wrap text-default"
                  >{{ displayedFieldValue(field) }}</pre
                >
                <p v-else class="wrap-break-word font-mono text-xs text-default">
                  {{ field.value }}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section class="space-y-2">
          <button
            type="button"
            class="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-toned hover:text-default"
            @click="rawJsonOpen = !rawJsonOpen"
          >
            <UIcon
              name="i-lucide-chevron-right"
              :class="['size-4 transition-transform', rawJsonOpen ? 'rotate-90' : '']"
            />
            <UIcon name="i-lucide-braces" class="size-4 text-toned" />
            RAW DATA
          </button>
          <div v-if="rawJsonOpen" class="space-y-3">
            <div class="flex items-center justify-between gap-3">
              <UInput
                v-model="rawJsonFilter"
                type="search"
                icon="i-lucide-filter"
                placeholder="Filter lines"
                size="sm"
                class="w-full"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="outline"
                icon="i-lucide-copy"
                @click="log && copyText(logRaw(log))"
              >
                Copy
              </UButton>
            </div>
            <pre
              class="max-h-96 overflow-auto rounded-sm border border-default bg-elevated/50 p-3 text-xs whitespace-pre-wrap text-default"
              >{{ filteredRawJson }}</pre
            >
          </div>
        </section>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import type { log_line } from '~/types/logs';
import { copyText } from '~/utils';

const props = defineProps<{
  modelValue?: boolean;
  log?: log_line | null;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const open = computed({
  get: () => props.modelValue ?? false,
  set: (val: boolean) => emit('update:modelValue', val),
});

type LogLevel = 'debug' | 'info' | 'warning' | 'error';
type LogLevelColor = 'neutral' | 'info' | 'warning' | 'error';
type DetailRow = {
  label: string;
  value: string;
  icon: string;
};
type LogFieldRow = {
  key: string;
  label: string;
  value: string;
  preview: string;
  kind: 'scalar' | 'text' | 'json';
};

const LOG_LEVEL_COLOR: Record<LogLevel, LogLevelColor> = {
  debug: 'neutral',
  info: 'info',
  warning: 'warning',
  error: 'error',
};
const LOG_LEVEL_ICON: Record<LogLevel, string> = {
  debug: 'i-lucide-terminal',
  info: 'i-lucide-info',
  warning: 'i-lucide-triangle-alert',
  error: 'i-lucide-circle-x',
};

const exceptionOpen = useStorage<boolean>('logs_exception_open', false);
const fieldsOpen = useStorage<boolean>('logs_fields_open', true);
const rawJsonOpen = useStorage<boolean>('logs_raw_json_open', false);
const rawJsonFilter = ref('');
const sourceOpen = useStorage<boolean>('logs_source_open', true);
const fieldOpenState = ref<Record<string, boolean>>({});
const fieldFilters = ref<Record<string, string>>({});

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

const logRaw = (log: log_line): string => JSON.stringify(log, null, 2);

const exceptionSummary = (log: log_line): string => {
  const type = log.exception?.type?.trim() ?? '';
  const message = log.exception?.message?.trim() ?? '';

  if (type && message) {
    return `${type}: ${message}`;
  }

  return type || message;
};

const exceptionText = (log: log_line): string =>
  log.exception ? JSON.stringify(log.exception, null, 2) : '';

const logTimeTitle = (value?: string): string =>
  value ? moment(value).format('YYYY-MM-DD HH:mm:ss Z') : 'No timestamp';

const copyMenuItems = computed(() => [
  [
    {
      label: 'Copy Message',
      icon: 'i-lucide-message-square-text',
      onSelect: () => {
        if (props.log) {
          copyText(props.log.message);
        }
      },
    },
    {
      label: 'Copy JSON',
      icon: 'i-lucide-braces',
      onSelect: () => {
        if (props.log) {
          copyText(logRaw(props.log));
        }
      },
    },
  ],
]);

const filteredRawJson = computed(() => {
  const raw = props.log ? logRaw(props.log) : '';
  const query = rawJsonFilter.value.toLowerCase();
  if (!query) return raw;
  return raw
    .split('\n')
    .filter((line) => line.toLowerCase().includes(query))
    .join('\n');
});

const formatDetailValue = (value: unknown): string => {
  if (value === undefined || value === null || value === '') {
    return '';
  }

  if (typeof value === 'string') {
    return value;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  return JSON.stringify(value);
};

const compactRows = (rows: Array<{ label: string; value: unknown; icon: string }>): DetailRow[] =>
  rows
    .map((row) => ({
      label: row.label,
      value: formatDetailValue(row.value),
      icon: row.icon,
    }))
    .filter((row) => Boolean(row.value));

const formatNameId = (name: unknown, id: unknown): string => {
  const nameValue = formatDetailValue(name);
  const idValue = formatDetailValue(id);
  if (nameValue && idValue) {
    return `${nameValue} / ${idValue}`;
  }

  return nameValue || idValue;
};

const detailRows = (log: log_line): DetailRow[] =>
  compactRows([
    { label: 'File', value: log.source?.file, icon: 'i-lucide-file' },
    { label: 'Line', value: log.source?.line, icon: 'i-lucide-hash' },
    { label: 'Function', value: log.source?.function, icon: 'i-lucide-code-2' },
    { label: 'Module', value: log.source?.module, icon: 'i-lucide-box' },
    { label: 'Path', value: log.source?.path, icon: 'i-lucide-folder-tree' },
    {
      label: 'Process / ID',
      value: formatNameId(log.process?.name, log.process?.id),
      icon: 'i-lucide-cpu',
    },
    {
      label: 'Thread / ID',
      value: formatNameId(log.thread?.name, log.thread?.id),
      icon: 'i-lucide-git-branch',
    },
  ]);

const fieldRows = (log: log_line): LogFieldRow[] => {
  if (!log.fields) return [];
  const rows: LogFieldRow[] = [];
  for (const [key, rawValue] of Object.entries(log.fields)) {
    if (rawValue === undefined || rawValue === null || rawValue === '') continue;
    const jsonValue =
      typeof rawValue === 'string'
        ? parseJsonContainerString(rawValue)
        : isJsonContainer(rawValue)
          ? rawValue
          : null;
    const value = jsonValue ? JSON.stringify(jsonValue, null, 2) : formatFieldValue(rawValue);
    const kind = jsonValue
      ? 'json'
      : typeof rawValue === 'string'
        ? rawValue.includes('\n')
          ? 'text'
          : 'scalar'
        : 'scalar';
    rows.push({
      key,
      label: normalizeFieldLabel(key),
      value,
      preview: formatFieldValue(rawValue).replaceAll('\n', ' '),
      kind,
    });
  }
  return rows;
};

const fieldOpen = (key: string) => fieldOpenState.value[key] ?? false;

const toggleField = (key: string) => {
  fieldOpenState.value = { ...fieldOpenState.value, [key]: !fieldOpen(key) };
};

const fieldFilter = (key: string) => fieldFilters.value[key] ?? '';

const setFieldFilter = (key: string, value: string | number) => {
  fieldFilters.value = { ...fieldFilters.value, [key]: String(value ?? '') };
};

const displayedFieldValue = (field: LogFieldRow): string => {
  const query = fieldFilter(field.key);
  if (!query) return field.value;
  const needle = query.toLowerCase();
  return field.value
    .split('\n')
    .filter((line) => line.toLowerCase().includes(needle))
    .join('\n');
};

const copyFieldValue = (field: LogFieldRow): void => {
  copyText(field.value);
};

const isJsonLike = (value: string): boolean => {
  const trimmed = value.trim();
  return (
    ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))) &&
    trimmed.length > 1
  );
};

const isJsonContainer = (value: unknown): value is Record<string, unknown> | unknown[] =>
  Array.isArray(value) || (!!value && typeof value === 'object');

const parseJsonContainerString = (value: string): Record<string, unknown> | unknown[] | null => {
  if (!isJsonLike(value)) return null;
  try {
    const parsed = JSON.parse(value) as unknown;
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
  return null;
};

const normalizeFieldLabel = (key: string) => key.replaceAll('_', ' ');

const formatFieldValue = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2);
};
</script>
