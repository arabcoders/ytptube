<template>
  <UModal
    :open="true"
    :title="`${t('tasks.inspectHandlerTitle')}: ${task.name}`"
    :dismissible="!busy"
    :ui="{
      content: 'w-full sm:max-w-5xl',
      body: 'max-h-[75vh] overflow-y-auto p-4 sm:p-5',
      footer: 'px-4 pb-4 sm:px-5 sm:pb-5',
    }"
    @update:open="(open) => !open && emit('close')"
  >
    <template #description>
      <span class="sr-only">{{ t('tasks.inspectHandlerDesc') }}</span>
    </template>

    <template #body>
      <div class="space-y-4">
        <div
          class="ytp-card sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 px-3 py-3"
        >
          <div class="flex flex-wrap items-center gap-2">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              :icon="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
              :disabled="busy || entries.length === 0"
              @click="toggleAll"
            >
              {{ allSelected ? t('common.unselect') : t('common.select') }}
            </UButton>
            <span class="text-sm text-toned">
              {{
                t('common.playlistSelectionCount', {
                  selected: selected.size,
                  total: entries.length,
                })
              }}
            </span>
          </div>
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-refresh-cw"
            :loading="loading"
            :disabled="opening"
            @click="inspect"
          >
            {{ t('common.refresh') }}
          </UButton>
        </div>

        <UAlert
          v-if="loading"
          color="info"
          variant="soft"
          icon="i-lucide-loader-circle"
          :ui="{ icon: 'animate-spin' }"
          :title="t('common.loading')"
        />

        <UAlert
          v-else-if="error"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          :title="t('common.error')"
          :description="error"
        />

        <template v-else-if="result">
          <PlaylistEntryList
            v-if="entries.length"
            :entries="entries"
            selectable
            :selected="selected"
            :disabled="opening"
            @toggle="toggleEntry"
          />
          <UEmpty
            v-else
            icon="i-lucide-list-video"
            :title="t('common.noItems')"
            class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
          />
        </template>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full flex-wrap items-center justify-between gap-2">
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-x"
          :disabled="busy"
          class="justify-center"
          @click="emit('close')"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          color="primary"
          icon="i-lucide-download"
          :loading="opening"
          :disabled="loading || selected.size === 0"
          @click="openDownloadForm"
        >
          {{ t('common.addToDownloadForm') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { PlaylistDisplayEntry } from '~/types/playlist';
import type { download_form_item } from '~/types/item';
import type { Task, TaskInspectResponse, TaskInspectSuccess } from '~/types/tasks';
import { parse_api_error, request } from '~/utils';
import { useFormHandoff } from '~/composables/useFormHandoff';

const props = defineProps<{ task: Task }>();
const emit = defineEmits<{ close: [] }>();
const { t } = useI18n();
const handoff = useFormHandoff<download_form_item>('download');
const loading = ref(false);
const opening = ref(false);
const error = ref('');
const result = ref<TaskInspectSuccess | null>(null);
const selected = ref<Set<string>>(new Set());
let generation = 0;
const busy = computed(() => loading.value || opening.value);

const entries = computed<PlaylistDisplayEntry[]>(() =>
  (result.value?.items || []).map((item, index) => {
    const data = item.metadata || {};
    const text = (key: string): string => (typeof data[key] === 'string' ? data[key] : '');
    const number = (key: string): number | null =>
      typeof data[key] === 'number' ? data[key] : null;

    return {
      key: `${index}:${item.url}`,
      url: item.url,
      title: item.title || item.url,
      description: item.description || text('description'),
      thumbnail: item.thumbnail || text('thumbnail'),
      duration: number('duration'),
      viewCount: number('view_count'),
      published: text('published') || null,
      broadcastDateLabel: text('broadcastDateLabel'),
      seriesTitle: text('seriesTitle'),
      broadcasterName: text('broadcasterName'),
      isArchived: item.is_archived === true || data.is_archived === true,
      archiveId: item.archive_id,
      extras: data,
    };
  }),
);

const inspect = async (): Promise<void> => {
  const token = ++generation;
  loading.value = true;
  error.value = '';
  result.value = null;
  selected.value = new Set();
  try {
    const response = await request('/api/tasks/inspect', {
      method: 'POST',
      body: JSON.stringify({
        url: props.task.url,
        preset: props.task.preset || undefined,
        resolve_ids: true,
      }),
    });
    const body = (await response.json()) as TaskInspectResponse;
    if (!response.ok) throw new Error(await parse_api_error(body));
    if (body.matched === false) throw new Error(body.message);
    if (token === generation) result.value = body;
  } catch (reason) {
    if (token === generation)
      error.value = reason instanceof Error ? reason.message : t('common.unknownError');
  } finally {
    if (token === generation) loading.value = false;
  }
};

const toggleEntry = (key: string, value: boolean | 'indeterminate'): void => {
  if (opening.value) return;
  const next = new Set(selected.value);
  if (value === true) next.add(key);
  else next.delete(key);
  selected.value = next;
};

const allSelected = computed(
  () => entries.value.length > 0 && entries.value.every((entry) => selected.value.has(entry.key)),
);

const toggleAll = (): void => {
  selected.value = allSelected.value ? new Set() : new Set(entries.value.map((entry) => entry.key));
};

const openDownloadForm = async (): Promise<void> => {
  if (!result.value || !props.task.id || selected.value.size === 0) return;
  opening.value = true;
  error.value = '';

  try {
    const picked = entries.value.filter((item) => selected.value.has(item.key));
    const data: download_form_item = {
      url: picked.map((entry) => entry.url).join('\n'),
      preset: props.task.preset,
      folder: props.task.folder,
      template: props.task.template,
      cli: props.task.cli,
      auto_start: props.task.auto_start,
      extras: {
        source_name: props.task.name,
        source_id: props.task.id,
        source_handler: result.value.handler,
        ignore_conditions: [...(props.task.ignore_conditions || [])],
      },
      picked_entries: picked.map((entry) => ({
        url: entry.url,
        extras: Object.keys(entry.extras).length ? { metadata: entry.extras } : {},
      })),
    };
    handoff.set(data);
    await navigateTo('/');
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : t('queue.failedToAdd');
  } finally {
    opening.value = false;
  }
};

onMounted(inspect);
onBeforeUnmount(() => generation++);
</script>
