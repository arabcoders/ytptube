<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell" :page-label="taskTitle" description="" class="wrap-anywhere">
      <template #actions>
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
      </template>
    </PageHeader>

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
    <UEmpty v-else-if="!task" icon="i-lucide-search-x" :title="t('common.noItems')" class="py-10">
      <template #actions>
        <UButton to="/tasks" color="neutral" variant="outline">
          {{ pageShell.pageLabel }}
        </UButton>
      </template>
    </UEmpty>

    <template v-else>
      <section class="ytp-card divide-y divide-default">
        <div class="space-y-3 p-4 sm:p-5">
          <div v-if="tags.length" class="flex flex-wrap gap-1">
            <UBadge
              v-for="(tag, index) in tags"
              :key="index"
              color="neutral"
              variant="soft"
              size="xs"
            >
              {{ tag }}
            </UBadge>
          </div>
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-toned">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="xs"
              :aria-pressed="task.enabled !== false"
              :loading="saving === 'enabled'"
              :disabled="saving !== null"
              @click="() => void toggleFlag('enabled')"
            >
              <UIcon
                name="i-lucide-power"
                class="size-3.5 shrink-0"
                :class="task.enabled === false ? 'text-error' : 'text-success'"
                aria-hidden="true"
              />
              {{ task.enabled === false ? t('common.disabled') : t('common.enabled') }}
            </UButton>
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="xs"
              :aria-pressed="task.auto_start !== false"
              :loading="saving === 'auto_start'"
              :disabled="saving !== null"
              @click="() => void toggleFlag('auto_start')"
            >
              <UIcon
                name="i-lucide-circle-play"
                class="size-3.5 shrink-0"
                :class="task.auto_start === false ? 'text-warning' : 'text-success'"
                aria-hidden="true"
              />
              {{ task.auto_start === false ? t('tasks.autoStartNo') : t('tasks.autoStartYes') }}
            </UButton>
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="xs"
              :aria-pressed="task.handler_enabled !== false"
              :loading="saving === 'handler_enabled'"
              :disabled="saving !== null"
              @click="() => void toggleFlag('handler_enabled')"
            >
              <UIcon
                name="i-lucide-rss"
                class="size-3.5 shrink-0"
                :class="task.handler_enabled === false ? 'text-toned' : 'text-info'"
                aria-hidden="true"
              />
              {{ task.handler_enabled === false ? t('tasks.handlerOff') : t('tasks.handlerOn') }}
            </UButton>
            <a
              :href="task.url"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1.5 hover:text-primary hover:underline"
            >
              <UIcon name="i-lucide-external-link" class="size-3.5 shrink-0" aria-hidden="true" />
              {{ t('tasks.openSourceUrl') }}
            </a>
          </div>
        </div>
        <div class="space-y-5 p-4 sm:p-5">
          <dl class="grid min-w-0 gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
            <div class="min-w-0 space-y-1">
              <dt class="flex items-center gap-1.5 text-xs text-muted">
                <UIcon name="i-lucide-clock-3" class="size-3.5 shrink-0" aria-hidden="true" />
                {{ task.timer ? t('tasks.nextRun') : t('tasks.schedule') }}
              </dt>
              <dd class="wrap-anywhere">
                {{ task.enabled === false ? t('common.disabled') : nextRun }}
              </dd>
            </div>
            <div class="min-w-0 space-y-1">
              <dt class="flex items-center gap-1.5 text-xs text-muted">
                <UIcon
                  name="i-lucide-sliders-horizontal"
                  class="size-3.5 shrink-0"
                  aria-hidden="true"
                />
                {{ t('common.presetLabel') }}
              </dt>
              <dd class="wrap-anywhere">{{ task.preset || config.app.default_preset }}</dd>
            </div>
            <div v-if="task.timer" class="min-w-0 space-y-1">
              <dt class="flex items-center gap-1.5 text-xs text-muted">
                <UIcon
                  name="i-lucide-calendar-clock"
                  class="size-3.5 shrink-0"
                  aria-hidden="true"
                />
                {{ t('tasks.timer') }}
              </dt>
              <dd>
                <a
                  :href="`https://crontab.guru/#${task.timer.replace(/ /g, '_')}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="wrap-anywhere font-mono text-primary hover:underline"
                  dir="ltr"
                  >{{ task.timer }}</a
                >
              </dd>
            </div>
          </dl>
          <dl class="grid min-w-0 gap-x-8 gap-y-4 text-sm sm:grid-cols-2">
            <div
              v-for="item in metadata"
              :key="item.label"
              class="min-w-0 space-y-1"
              :class="{ 'sm:col-span-2': item.mono }"
            >
              <dt class="flex items-center gap-1.5 text-xs text-muted">
                <UIcon :name="item.icon" class="size-3.5 shrink-0" aria-hidden="true" />
                {{ item.label }}
              </dt>
              <dd
                class="wrap-anywhere whitespace-pre-wrap"
                :class="{ 'font-mono text-xs': item.mono }"
                :dir="item.mono ? 'ltr' : undefined"
              >
                <NuxtLink v-if="item.to" :to="item.to" class="hover:text-primary hover:underline">
                  {{ item.value }}
                </NuxtLink>
                <UTooltip
                  v-else-if="item.tooltip"
                  :text="item.tooltip"
                  :content="{ align: 'start' }"
                >
                  <span>{{ item.value }}</span>
                </UTooltip>
                <span v-else>{{ item.value }}</span>
              </dd>
            </div>
          </dl>
        </div>
      </section>
      <section class="space-y-3">
        <h2 class="text-sm font-semibold text-highlighted">{{ t('common.downloads') }}</h2>
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
      <details class="text-sm">
        <summary class="w-fit cursor-pointer font-medium text-toned">
          {{ t('common.usageNotes') }}
        </summary>
        <p class="mt-3 text-sm text-toned">{{ t('tasks.noteLiveActivity') }}</p>
      </details>
    </template>

    <LazyTaskSourceInspect v-if="task && inspectOpen" :task="task" @close="inspectOpen = false" />
  </main>
</template>

<script setup lang="ts">
import { CronExpressionParser } from 'cron-parser';
import type { Task } from '~/types/tasks';
import { formatDateTime } from '~/utils/date';
import { formatRelativeTime } from '~/utils/relativeTime';
import { eTrim, getBrowserUrl, parse_list_response, request, sTrim, shortPath } from '~/utils';
import type { Pagination } from '~/types/responses';
import type { StoreItem } from '~/types/store';
import { taskHistoryUrl } from '~/utils/taskDetails';

type DetailField = {
  label: string;
  value: string;
  icon: string;
  tooltip?: string;
  to?: string;
  mono?: boolean;
};
type TaskFlag = 'enabled' | 'auto_start' | 'handler_enabled';

const { t, locale } = useI18n();
const config = useYtpConfig();
const pageShell = usePageShell('tasks');
const route = useRoute();
const { getTask, patchTask } = useTasks();
const toast = useNotification();
const task = ref<Task | null>(null);
const saving = ref<TaskFlag | null>(null);
const toggleFlag = async (field: TaskFlag): Promise<void> => {
  const item = task.value;
  if (!item?.id || saving.value !== null) return;

  saving.value = field;
  try {
    const updated = await patchTask(item.id, { [field]: item[field] === false });
    if (updated && task.value === item) task.value = updated;
  } catch (error) {
    if (task.value === item)
      toast.error(error instanceof Error ? error.message : t('common.unknownError'));
  } finally {
    saving.value = null;
  }
};
const taskTitle = computed(
  () => task.value?.name.replace(/\[(.*?)\]/g, '').trim() || t('tasks.task'),
);
const tags = computed(
  () => task.value?.name.match(/\[(.*?)\]/g)?.map((tag) => tag.replace(/[[\]]/g, '').trim()) || [],
);
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
const nextRun = computed(() => {
  if (!task.value?.timer) return t('tasks.handlerOnly');
  try {
    return formatRelativeTime(
      CronExpressionParser.parse(task.value.timer).next().toISOString(),
      locale.value,
    );
  } catch {
    return t('common.invalid');
  }
});
const metadata = computed<DetailField[]>(() => {
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
  const items: DetailField[] = [
    {
      label: t('common.downloadPath'),
      value: downloadPath,
      icon: 'i-lucide-folder-output',
      to: browserUrl || undefined,
      mono: true,
    },
  ];
  if (task.value.template)
    items.push({
      label: t('common.outputTemplate'),
      value: task.value.template,
      icon: 'i-lucide-file-code-2',
      mono: true,
    });
  if (task.value.cli)
    items.push({
      label: t('common.cliOptions'),
      value: task.value.cli,
      icon: 'i-lucide-terminal',
      mono: true,
    });
  if (task.value.created_at)
    items.push({
      label: t('common.created'),
      value: formatRelativeTime(task.value.created_at, locale.value),
      icon: 'i-lucide-calendar-plus',
      tooltip: formatDateTime(task.value.created_at, locale.value),
    });
  if (task.value.updated_at)
    items.push({
      label: t('taskDefinitions.updated'),
      value: formatRelativeTime(task.value.updated_at, locale.value),
      icon: 'i-lucide-calendar-clock',
      tooltip: formatDateTime(task.value.updated_at, locale.value),
    });
  return items;
});
watch(() => route.params.id, loadTask, { immediate: true });
</script>
