<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="ytp-page-header">
      <div class="ytp-page-heading">
        <span class="ytp-page-icon"><UIcon :name="pageShell.icon" class="size-5" /></span>
        <div class="min-w-0 space-y-2">
          <div class="ytp-page-kicker">
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <NuxtLink to="/tasks" class="hover:text-highlighted">{{
              pageShell.pageLabel
            }}</NuxtLink>
          </div>
          <h1 class="truncate text-xl font-semibold text-highlighted">
            {{ task?.name || t('tasks.task') }}
          </h1>
        </div>
      </div>
      <div class="flex w-full flex-wrap items-center justify-end gap-2 xl:w-auto">
        <UButton to="/tasks" color="neutral" variant="outline" size="sm" icon="i-lucide-arrow-left">
          {{ pageShell.pageLabel }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          @click="loadTask"
        >
          {{ t('common.refresh') }}
        </UButton>
        <UButton
          v-if="task"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-search"
          @click="inspectOpen = true"
        >
          {{ t('common.inspect') }}
        </UButton>
      </div>
    </div>

    <UAlert
      v-if="errorMessage"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('common.error')"
      :description="errorMessage"
    >
      <template #actions>
        <UButton to="/tasks" color="neutral" variant="outline" size="sm">
          {{ pageShell.pageLabel }}
        </UButton>
      </template>
    </UAlert>
    <UAlert
      v-else-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :ui="{ icon: 'animate-spin' }"
      :title="t('common.loading')"
    />
    <UEmpty
      v-else-if="!task"
      icon="i-lucide-search-x"
      :title="t('common.noItems')"
      class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
    >
      <template #actions>
        <UButton to="/tasks" color="neutral" variant="outline">
          {{ pageShell.pageLabel }}
        </UButton>
      </template>
    </UEmpty>

    <template v-else>
      <section class="ytp-card flex flex-wrap items-center gap-2 p-3">
        <UBadge :color="task.enabled === false ? 'error' : 'success'" variant="soft">
          <UIcon name="i-lucide-power" class="size-3.5" />
          {{ task.enabled === false ? t('common.disabled') : t('common.enabled') }}
        </UBadge>
        <UBadge :color="task.handler_enabled === false ? 'neutral' : 'info'" variant="soft">
          <UIcon name="i-lucide-rss" class="size-3.5" />
          {{ task.handler_enabled === false ? t('tasks.handlerOff') : t('tasks.handlerOn') }}
        </UBadge>
        <UBadge :color="task.auto_start === false ? 'warning' : 'success'" variant="soft">
          <UIcon name="i-lucide-circle-play" class="size-3.5" />
          {{ task.auto_start === false ? t('queue.manualStart') : t('common.autoStart') }}
        </UBadge>
        <UBadge color="neutral" variant="soft">
          <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
          {{ task.preset || config.app.default_preset }}
        </UBadge>
        <UBadge color="neutral" variant="soft">
          <UIcon name="i-lucide-clock-3" class="size-3.5" />
          {{ task.timer || t('tasks.handlerOnly') }}
        </UBadge>
      </section>
      <section class="space-y-3">
        <h2 class="text-sm font-semibold text-highlighted">{{ t('common.details') }}</h2>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            v-for="item in metadata"
            :key="item.label"
            :label="item.label"
            :value="item.value"
            :icon="item.icon"
            :tooltip="item.tooltip"
            :href="item.href"
            :to="item.to"
            color="neutral"
            :value-wrap="item.valueWrap"
          />
        </div>
      </section>
      <section class="space-y-3">
        <h2 class="text-sm font-semibold text-highlighted">{{ t('common.downloads') }}</h2>
        <UAlert
          color="info"
          variant="soft"
          icon="i-lucide-info"
          :title="t('tasks.notesTitle')"
          :description="t('tasks.noteLiveActivity')"
        />
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <StatCard
            v-for="card in activityCards"
            :key="card.label"
            :label="card.label"
            :value="card.value"
            :icon="card.icon"
            :color="card.color"
          />
        </div>
        <TaskDownloadSection
          :title="t('common.queue')"
          :empty="t('queue.empty')"
          icon="i-lucide-list"
          mode="queue"
          v-bind="queueState"
          @page="loadQueue"
          @refresh="loadQueue()"
        />
        <TaskDownloadSection
          :title="t('common.history')"
          :empty="t('history.empty')"
          icon="i-lucide-history"
          mode="history"
          v-bind="historyState"
          @page="loadHistory"
          @refresh="loadHistory()"
        />
      </section>
    </template>

    <LazyTaskSourceInspect v-if="task && inspectOpen" :task="task" @close="inspectOpen = false" />
  </main>
</template>

<script setup lang="ts">
import type { Task } from '~/types/tasks';
import { formatDateTime } from '~/utils/date';
import { formatRelativeTime } from '~/utils/relativeTime';
import { eTrim, getBrowserUrl, parse_list_response, request, sTrim, shortPath } from '~/utils';
import type { Pagination } from '~/types/responses';
import type { StoreItem } from '~/types/store';
import { taskHistoryUrl } from '~/utils/taskDetails';

type DetailCard = {
  label: string;
  value: string;
  icon: string;
  tooltip?: string;
  href?: string;
  to?: string;
  valueWrap: boolean;
};

const { t, locale } = useI18n();
const config = useYtpConfig();
const pageShell = usePageShell('tasks');
const route = useRoute();
const { getTask } = useTasks();
const task = ref<Task | null>(null);
const isLoading = ref(false);
const errorMessage = ref('');
const emptyPagination = (): Pagination => ({
  page: 1,
  per_page: 10,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const queueState = reactive({
  items: [] as StoreItem[],
  pagination: emptyPagination(),
  loading: false,
  error: '',
});
const historyState = reactive({
  items: [] as StoreItem[],
  pagination: emptyPagination(),
  loading: false,
  error: '',
});
const activityGeneration = ref(0);
const inspectOpen = ref(false);
const loadList = async (
  target: typeof queueState,
  type: 'queue' | 'done',
  page: number,
  status?: string,
  generation = activityGeneration.value,
) => {
  target.loading = true;
  target.error = '';
  try {
    const response = await request(taskHistoryUrl(type, Number(route.params.id), page, 10, status));
    if (!response.ok) throw new Error(t('common.unknownError'));
    const data = await response.json();
    const parsed = await parse_list_response<StoreItem>(data);
    if (generation !== activityGeneration.value) return;
    target.items = parsed.items;
    target.pagination = parsed.pagination;
  } catch (error) {
    if (generation === activityGeneration.value)
      target.error = error instanceof Error ? error.message : t('common.unknownError');
  } finally {
    if (generation === activityGeneration.value) target.loading = false;
  }
};
const loadQueue = (page = 1) => loadList(queueState, 'queue', page);
const loadHistory = (page = 1) => loadList(historyState, 'done', page);
const activityCards = computed(() => [
  {
    label: t('common.queue'),
    value: queueState.pagination.total,
    icon: 'i-lucide-hourglass',
    color: 'info' as const,
  },
  {
    label: t('common.completed'),
    value: historyTotals.completed,
    icon: 'i-lucide-circle-check',
    color: 'success' as const,
  },
  {
    label: t('common.skipped'),
    value: historyTotals.skipped,
    icon: 'i-lucide-circle-slash',
    color: 'warning' as const,
  },
  {
    label: t('common.error'),
    value: historyTotals.failed,
    icon: 'i-lucide-triangle-alert',
    color: 'error' as const,
  },
  {
    label: t('common.cancelled'),
    value: historyTotals.cancelled,
    icon: 'i-lucide-circle-x',
    color: 'neutral' as const,
  },
  {
    label: t('simple.statusNotLive'),
    value: historyTotals.notLive,
    icon: 'i-lucide-clock-3',
    color: 'warning' as const,
  },
]);
const historyTotals = reactive({ completed: 0, skipped: 0, failed: 0, cancelled: 0, notLive: 0 });
const loadTotals = async (generation: number) => {
  for (const [key, status] of [
    ['completed', 'finished'],
    ['skipped', 'skip'],
    ['failed', 'error,partial'],
    ['cancelled', 'cancelled'],
    ['notLive', 'not_live'],
  ] as const) {
    const response = await request(taskHistoryUrl('done', Number(route.params.id), 1, 1, status));
    if (!response.ok) continue;
    const parsed = await parse_list_response<StoreItem>(await response.json());
    if (generation === activityGeneration.value) historyTotals[key] = parsed.pagination.total;
  }
};
const loadTask = async (): Promise<void> => {
  const id = Number(route.params.id);
  const generation = ++activityGeneration.value;
  task.value = null;
  inspectOpen.value = false;
  errorMessage.value = '';
  queueState.items = [];
  historyState.items = [];
  queueState.pagination = emptyPagination();
  historyState.pagination = emptyPagination();
  queueState.error = '';
  historyState.error = '';
  historyTotals.completed = 0;
  historyTotals.skipped = 0;
  historyTotals.failed = 0;
  historyTotals.cancelled = 0;
  historyTotals.notLive = 0;
  if (!Number.isSafeInteger(id) || id < 1) {
    errorMessage.value = t('common.taskIdMissing');
    return;
  }
  isLoading.value = true;
  try {
    const loaded = await getTask(id);
    if (generation !== activityGeneration.value) return;
    task.value = loaded;
    if (task.value) await Promise.all([loadQueue(), loadHistory(), loadTotals(generation)]);
  } catch (error) {
    if (generation === activityGeneration.value)
      errorMessage.value = error instanceof Error ? error.message : t('common.unknownError');
  } finally {
    if (generation === activityGeneration.value) isLoading.value = false;
  }
};
const metadata = computed<DetailCard[]>(() => {
  if (!task.value) return [];
  const path = shortPath(config.app.download_path || '/downloads');
  const downloadPath = task.value.folder
    ? `${eTrim(path, '/')}/${sTrim(task.value.folder, '/')}`
    : path;
  const browserUrl = getBrowserUrl(config.app.download_path, {
    download_dir: '',
    filename: null,
    folder: task.value.folder || '',
  });
  const items: DetailCard[] = [
    {
      label: t('common.url'),
      value: t('tasks.openSourceUrl'),
      icon: 'i-lucide-link',
      href: task.value.url,
      tooltip: task.value.url,
      valueWrap: false,
    },
    {
      label: t('common.downloadPath'),
      value: downloadPath,
      icon: 'i-lucide-folder-output',
      tooltip: downloadPath,
      to: browserUrl || undefined,
      valueWrap: false,
    },
  ];
  if (task.value.template)
    items.push({
      label: t('common.outputTemplate'),
      value: task.value.template,
      icon: 'i-lucide-file-code-2',
      valueWrap: true,
    });
  if (task.value.cli)
    items.push({
      label: t('common.cliOptions'),
      value: task.value.cli,
      icon: 'i-lucide-terminal',
      valueWrap: true,
    });
  if (task.value.created_at)
    items.push({
      label: t('common.created'),
      value: formatRelativeTime(task.value.created_at, locale.value),
      icon: 'i-lucide-calendar-plus',
      tooltip: formatDateTime(task.value.created_at, locale.value),
      valueWrap: false,
    });
  if (task.value.updated_at)
    items.push({
      label: t('taskDefinitions.updated'),
      value: formatRelativeTime(task.value.updated_at, locale.value),
      icon: 'i-lucide-calendar-clock',
      tooltip: formatDateTime(task.value.updated_at, locale.value),
      valueWrap: false,
    });
  return items;
});
watch(() => route.params.id, loadTask, { immediate: true });
</script>
