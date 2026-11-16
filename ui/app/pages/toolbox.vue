<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell">
      <template #actions>
        <UButton
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="showFilter = !showFilter"
        >
          {{ t('common.filter') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading || bulkBusy"
          @click="refresh"
          >{{ t('common.refresh') }}</UButton
        >
        <UInput
          v-if="showFilter"
          v-model="query"
          type="search"
          :placeholder="t('common.filterDisplayedContent')"
          :aria-label="t('common.filterDisplayedContent')"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </template>
    </PageHeader>

    <div
      v-if="jobs.length > 0 || pagination.total_pages > 1"
      class="flex flex-wrap items-center justify-between gap-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="allSelected ? 'i-lucide-square-check-big' : 'i-lucide-square'"
          :disabled="!visibleIds.length || isLoading || bulkBusy"
          @click="toggleSelection"
        >
          {{ allSelected ? t('common.unselect') : t('common.select') }}
        </UButton>

        <UBadge v-if="selectedIds.length" color="error" variant="soft" size="sm">
          {{ selectedIds.length }}
        </UBadge>

        <UDropdownMenu :items="bulkActions" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-list"
            trailing-icon="i-lucide-chevron-down"
            :loading="bulkBusy"
            :disabled="isLoading || bulkBusy"
          >
            {{ t('common.actions') }}
          </UButton>
        </UDropdownMenu>
      </div>

      <div v-if="pagination.total_pages > 1" class="ms-auto max-w-full">
        <UPagination
          :page="pagination.page"
          :total="pagination.total"
          :items-per-page="pagination.per_page"
          :disabled="isLoading || bulkBusy"
          show-edges
          :sibling-count="0"
          size="sm"
          @update:page="loadPage"
        />
      </div>
    </div>

    <UAlert v-if="lastError" color="error" variant="soft" :title="lastError" />
    <UAlert
      v-if="isLoading && jobs.length === 0"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :ui="{ icon: 'animate-spin' }"
    />
    <UEmpty
      v-else-if="query && jobs.length > 0 && filteredJobs.length === 0"
      variant="naked"
      size="sm"
      icon="i-lucide-search"
      :title="t('common.noResults')"
      :description="t('common.noResultsFor', { query })"
    />
    <UEmpty
      v-else-if="!lastError && jobs.length === 0"
      :icon="pageShell.icon"
      :title="t('common.noItems')"
      :description="t('common.empty')"
      variant="naked"
      size="sm"
    />
    <div v-if="filteredJobs.length" class="ytp-card divide-y divide-default">
      <article
        v-for="job in filteredJobs"
        :key="job.id"
        :aria-labelledby="`toolbox-job-${job.id}`"
        class="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-3 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_22rem_auto]"
      >
        <div class="flex min-w-0 items-start gap-3">
          <UCheckbox
            :id="`checkbox-${job.id}`"
            color="primary"
            class="mt-0.5 shrink-0"
            :model-value="selectedIds.includes(job.id)"
            :aria-label="`${t('common.select')}: ${basename(job.file)}`"
            :disabled="isLoading || bulkBusy || inProgressIds.has(job.id)"
            @click.capture="rangeSelection.handleClick"
            @keydown.capture="rangeSelection.handleKeydown"
            @update:model-value="selectJob(job.id, $event)"
          />
          <div class="min-w-0 space-y-1">
            <h2 :id="`toolbox-job-${job.id}`" class="text-sm font-semibold text-highlighted">
              <NuxtLink
                :to="jobUrl(job.id)"
                class="wrap-anywhere hover:text-primary hover:underline"
                dir="auto"
              >
                {{ basename(job.file) }}
              </NuxtLink>
            </h2>
            <p class="wrap-anywhere whitespace-pre-wrap font-mono text-xs text-toned" dir="ltr">
              {{ job.file }}
            </p>
          </div>
        </div>

        <dl
          class="col-span-2 grid gap-3 text-sm sm:grid-cols-3 xl:col-span-1 xl:col-start-2 xl:row-start-1"
        >
          <div class="min-w-0 space-y-1">
            <dt class="text-xs text-muted">{{ t('common.operation') }}</dt>
            <dd class="wrap-anywhere">{{ toolLabel(job.tool) }}</dd>
          </div>
          <div class="min-w-0 space-y-1">
            <dt class="text-xs text-muted">{{ t('common.status') }}</dt>
            <dd>
              <UBadge :color="toolboxStatusColor(job.status)" variant="soft" size="sm">
                <UIcon
                  :name="statusIcons[job.status]"
                  class="size-3.5 shrink-0"
                  :class="job.status === 'running' ? 'animate-spin' : ''"
                  aria-hidden="true"
                />
                {{ toolboxStatusLabel(job.status, t) }}
              </UBadge>
            </dd>
          </div>
          <div class="min-w-0 space-y-1">
            <dt class="text-xs text-muted">{{ t('common.date') }}</dt>
            <dd>
              <UTooltip :text="formatDateTime(job.created_at, locale, { seconds: true })">
                <time
                  :datetime="job.created_at"
                  :data-datetime="job.created_at"
                  v-rtime="job.created_at"
                />
              </UTooltip>
            </dd>
          </div>
        </dl>

        <div class="col-start-2 row-start-1 flex justify-end xl:col-start-3">
          <UDropdownMenu :items="itemActions(job)" :modal="false" :content="{ align: 'end' }">
            <UButton
              color="neutral"
              variant="ghost"
              size="sm"
              icon="i-lucide-ellipsis"
              square
              :aria-label="`${t('common.actions')}: ${basename(job.file)}`"
              :loading="inProgressIds.has(job.id)"
              :disabled="bulkBusy || inProgressIds.has(job.id)"
            />
          </UDropdownMenu>
        </div>

        <div v-if="job.status === 'running'" class="col-span-2 xl:col-span-3">
          <div
            class="queue-progress rounded-md border border-default bg-muted/20"
            role="progressbar"
            :aria-label="t('queue.progress')"
            :aria-valuenow="job.progress ?? undefined"
            :aria-valuemin="0"
            :aria-valuemax="100"
          >
            <div
              class="queue-progress__bar bg-success/35"
              :class="job.progress === null ? 'w-1/3 animate-pulse' : ''"
              :style="job.progress !== null ? { width: `${job.progress}%` } : undefined"
            />
            <div class="queue-progress__label">
              <UIcon name="i-lucide-loader-circle" class="me-1 size-4 animate-spin" />
              <span>{{
                job.progress === null
                  ? toolboxStatusLabel(job.status, t)
                  : `${Math.round(job.progress)}%`
              }}</span>
            </div>
          </div>
        </div>
        <div
          v-if="job.error || showMessage(job)"
          class="col-span-2 space-y-2 border-t border-default pt-3 xl:col-span-3"
        >
          <button
            v-if="job.error"
            type="button"
            :class="messageClass(job.id, 'error')"
            :aria-expanded="isExpanded(job.id, 'error')"
            @click="toggleExpand(job.id, 'error')"
          >
            {{ job.error }}
          </button>
          <button
            v-if="showMessage(job)"
            type="button"
            :class="messageClass(job.id, 'message')"
            :aria-expanded="isExpanded(job.id, 'message')"
            @click="toggleExpand(job.id, 'message')"
          >
            {{ job.message }}
          </button>
        </div>
      </article>
    </div>
    <div v-if="pagination.total_pages > 1" class="flex justify-end">
      <UPagination
        :page="pagination.page"
        :total="pagination.total"
        :items-per-page="pagination.per_page"
        :disabled="isLoading || bulkBusy"
        show-edges
        :sibling-count="0"
        size="sm"
        @update:page="loadPage"
      />
    </div>
    <ToolboxJobModal v-if="jobId" :id="jobId" @close="closeJob" />
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import ToolboxJobModal from '~/components/ToolboxJobModal.vue';
import { useAppSocket } from '~/composables/useAppSocket';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { usePageShell } from '~/composables/usePageShell';
import { useRangeSelection } from '~/composables/useRangeSelection';
import { useToolbox } from '~/composables/useToolbox';
import type { WSEP } from '~/types/sockets';
import type { ToolboxJob, ToolboxStatus } from '~/types/toolbox';
import { basename, formatPageTitle } from '~/utils';
import { formatDateTime } from '~/utils/date';
import { setSelected } from '~/utils/selection';
import {
  isToolboxActive,
  toolboxShowMessage,
  toolboxStatusColor,
  toolboxStatusLabel,
} from '~/utils/toolbox';

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const dialog = useDialog();
const socket = useAppSocket();
const pageShell = usePageShell('toolbox');
const {
  tools,
  jobs,
  pagination,
  isLoading,
  inProgressIds,
  lastError,
  loadTools,
  loadJobs,
  cancelJob,
  deleteJob,
  upsert,
} = useToolbox();
const { toggleExpand, isExpanded } = useExpandableMeta();
const query = ref('');
const showFilter = ref(false);
const selectedIds = ref<number[]>([]);
const bulkBusy = ref(false);
const jobId = computed(() => {
  if (typeof route.query.job !== 'string') return null;
  const id = Number(route.query.job);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
});
let disposed = false;
const toolLabel = (id: string): string => tools.value.find((item) => item.id === id)?.name ?? id;
const statusIcons: Record<ToolboxStatus, string> = {
  queued: 'i-lucide-clock',
  running: 'i-lucide-loader-circle',
  succeeded: 'i-lucide-check',
  skipped: 'i-lucide-circle-slash',
  failed: 'i-lucide-circle-alert',
  cancelled: 'i-lucide-ban',
  interrupted: 'i-lucide-triangle-alert',
};
const filteredJobs = computed(() => {
  const search = query.value.trim().toLocaleLowerCase();
  if (!search) return jobs.value;
  return jobs.value.filter((job) =>
    [job.file, toolLabel(job.tool), toolboxStatusLabel(job.status, t)].some((value) =>
      value.toLocaleLowerCase().includes(search),
    ),
  );
});
const visibleIds = computed(() => filteredJobs.value.map((job) => job.id));
const rangeSelection = useRangeSelection(selectedIds, visibleIds);
const selectJob = (id: number, checked: boolean | 'indeterminate'): void => {
  selectedIds.value = setSelected(selectedIds.value, id, checked);
  rangeSelection.handleChange(id, new Event('change'));
};
const allSelected = computed(
  () =>
    visibleIds.value.length > 0 && visibleIds.value.every((id) => selectedIds.value.includes(id)),
);
const selectedJobs = computed(() =>
  filteredJobs.value.filter(
    (job) => selectedIds.value.includes(job.id) && !inProgressIds.value.has(job.id),
  ),
);
const activeJobs = computed(() => selectedJobs.value.filter(isToolboxActive));
const terminalJobs = computed(() => selectedJobs.value.filter((job) => !isToolboxActive(job)));
const bulkActions = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: t('common.cancel'),
      icon: 'i-lucide-square',
      disabled: !activeJobs.value.length || bulkBusy.value || isLoading.value,
      onSelect: () => void cancelSelected(),
    },
    {
      label: t('common.deleteSelected'),
      icon: 'i-lucide-trash',
      disabled: !terminalJobs.value.length || bulkBusy.value || isLoading.value,
      onSelect: () => void deleteSelected(),
    },
  ],
]);

const itemActions = (job: ToolboxJob): DropdownMenuItem[][] => [
  [
    isToolboxActive(job)
      ? {
          label: t('common.cancel'),
          icon: 'i-lucide-square',
          onSelect: () => void cancel(job),
        }
      : {
          label: t('common.delete'),
          icon: 'i-lucide-trash',
          color: 'error',
          onSelect: () => void remove(job),
        },
  ],
];

watch(showFilter, (visible) => {
  if (!visible) query.value = '';
});
watch(
  visibleIds,
  (ids) => {
    const visible = new Set(ids);
    selectedIds.value = selectedIds.value.filter((id) => visible.has(id));
  },
  { flush: 'sync' },
);

const toggleSelection = (): void => {
  selectedIds.value = allSelected.value ? [] : [...visibleIds.value];
  rangeSelection.reset();
};
const loadPage = async (page: number): Promise<void> => {
  selectedIds.value = [];
  rangeSelection.reset();
  await loadJobs(page);
};
const refresh = async (): Promise<void> => {
  await Promise.all([loadTools(), loadJobs()]);
};
const onJob = (event: WSEP['toolbox_job']): void => upsert(event.data);
const reloadJobs = async (): Promise<void> => {
  await loadJobs(
    jobs.value.length === 0 ? Math.max(1, pagination.value.page - 1) : pagination.value.page,
  );
};
const showMessage = (job: ToolboxJob): boolean => toolboxShowMessage(job, t);
const messageClass = (id: number, field: 'error' | 'message'): string[] => [
  'block w-full cursor-pointer text-start text-sm [overflow-wrap:anywhere]',
  field === 'error' ? 'text-error' : 'text-toned',
  isExpanded(id, field) ? 'whitespace-pre-wrap break-words' : 'line-clamp-2 break-words',
];
const jobUrl = (id: number) => ({
  path: route.path,
  query: { ...route.query, job: id },
  hash: route.hash,
});
const closeJob = async (): Promise<void> => {
  if (disposed || !('job' in route.query)) return;
  await router.replace({
    path: route.path,
    query: { ...route.query, job: undefined },
    hash: route.hash,
  });
};
const remove = async (job: ToolboxJob): Promise<void> => {
  if (disposed || bulkBusy.value || inProgressIds.value.has(job.id)) return;
  const result = await dialog.confirmDialog({
    title: t('common.delete'),
    message: t('common.deleteNamedConfirm', { name: basename(job.file) }),
    confirmText: t('common.delete'),
  });
  if (!result.status || disposed) return;
  const deleted = await deleteJob(job);
  if (disposed) return;
  if (deleted && jobId.value === job.id) await closeJob();
  await reloadJobs();
};
const cancel = async (job: ToolboxJob): Promise<void> => {
  if (disposed || bulkBusy.value || inProgressIds.value.has(job.id)) return;
  await cancelJob(job);
  if (!disposed) await loadJobs();
};
const cancelSelected = async (): Promise<void> => {
  if (disposed || bulkBusy.value || !activeJobs.value.length) return;
  bulkBusy.value = true;
  try {
    for (const job of [...activeJobs.value]) {
      if (disposed) return;
      if (await cancelJob(job)) selectedIds.value = selectedIds.value.filter((id) => id !== job.id);
    }
    if (!disposed) await loadJobs();
  } finally {
    bulkBusy.value = false;
  }
};
const deleteSelected = async (): Promise<void> => {
  if (disposed || bulkBusy.value || !terminalJobs.value.length) return;
  const ids = new Set(terminalJobs.value.map((job) => job.id));
  bulkBusy.value = true;
  try {
    const result = await dialog.confirmDialog({
      title: t('common.deleteSelected'),
      message: t('common.deleteCountConfirm', { count: ids.size }),
      confirmText: t('common.delete'),
      confirmColor: 'error',
    });
    if (!result.status || disposed) return;
    const deleted = new Set<number>();
    for (const job of terminalJobs.value.filter((job) => ids.has(job.id))) {
      if (disposed) return;
      if (await deleteJob(job)) deleted.add(job.id);
    }
    if (disposed) return;
    selectedIds.value = selectedIds.value.filter((id) => !deleted.has(id));
    if (jobId.value !== null && deleted.has(jobId.value)) await closeJob();
    if (!disposed) await reloadJobs();
  } finally {
    bulkBusy.value = false;
  }
};
useHead(() => ({ title: formatPageTitle(t('toolbox.title')) }));
onMounted(() => {
  socket.on('toolbox_job', onJob);
  socket.on('connect', refresh);
  void refresh();
});
onScopeDispose(() => {
  disposed = true;
  socket.off('toolbox_job', onJob);
  socket.off('connect', refresh);
});
</script>
