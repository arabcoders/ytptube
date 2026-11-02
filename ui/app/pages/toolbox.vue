<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="ytp-page-header">
      <div class="ytp-page-heading">
        <span class="ytp-page-icon"><UIcon :name="pageShell.icon" class="size-5" /></span>
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
      </div>
    </div>

    <div
      v-if="jobs.length > 0 || pagination.total_pages > 1"
      class="flex flex-wrap items-center justify-between gap-3 ytp-card px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
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
    />
    <UAlert
      v-else-if="query && jobs.length > 0 && filteredJobs.length === 0"
      color="warning"
      variant="soft"
      icon="i-lucide-search"
      :title="t('common.noResults')"
      :description="t('common.noResultsFor', { query })"
    />
    <UEmpty
      v-else-if="!lastError && jobs.length === 0"
      :icon="pageShell.icon"
      :title="t('common.noItems')"
      :description="t('common.empty')"
      class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
    />
    <div v-if="filteredJobs.length" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="job in filteredJobs"
        :key="job.id"
        class="ytp-card flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden"
      >
        <div class="p-4 pb-3 ytp-border-bottom-soft">
          <div class="flex min-w-0 items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <UTooltip :text="job.file">
                <div class="min-w-0 text-sm font-semibold text-highlighted">
                  <NuxtLink :to="jobUrl(job.id)" class="block truncate hover:underline" dir="auto">
                    {{ basename(job.file) }}
                  </NuxtLink>
                </div>
              </UTooltip>
            </div>

            <label class="inline-flex cursor-pointer items-center justify-center px-1">
              <input
                :id="`checkbox-${job.id}`"
                v-model="selectedIds"
                class="completed-checkbox size-4 rounded border-default"
                type="checkbox"
                :value="job.id"
                :aria-label="`${t('common.select')}: ${basename(job.file)}`"
                :disabled="isLoading || bulkBusy || inProgressIds.has(job.id)"
                @click="rangeSelection.handleClick"
                @keydown="rangeSelection.handleKeydown"
                @change="rangeSelection.handleChange(job.id, $event)"
              />
            </label>
          </div>
        </div>
        <div class="flex flex-1 flex-col gap-4 p-4">
          <div
            v-if="job.status === 'running'"
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

          <div class="flex flex-wrap gap-2 text-sm *:min-w-32 *:flex-1">
            <button
              type="button"
              class="min-w-0 rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
              :aria-label="t('common.status')"
              @click="toggleExpand(job.id, 'status')"
            >
              <span class="inline-flex w-full items-center justify-center gap-2">
                <UIcon
                  :name="statusIcons[job.status]"
                  :class="[statusColors[toolboxStatusColor(job.status)], 'size-4 shrink-0']"
                />
                <span :class="['min-w-0 text-center', expandClass(job.id, 'status')]">
                  {{ toolboxStatusLabel(job.status, t) }}
                </span>
              </span>
            </button>

            <button
              type="button"
              class="min-w-0 rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
              :aria-label="t('common.operation')"
              @click="toggleExpand(job.id, 'operation')"
            >
              <span class="inline-flex w-full items-center justify-center gap-2">
                <UIcon name="i-lucide-wrench" class="size-4 shrink-0 text-toned" />
                <span :class="['min-w-0 text-center', expandClass(job.id, 'operation')]">
                  {{ toolLabel(job.tool) }}
                </span>
              </span>
            </button>

            <button
              type="button"
              class="min-w-0 rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
              :aria-label="t('common.date')"
              @click="toggleExpand(job.id, 'date')"
            >
              <UTooltip :text="formatDateTime(job.created_at, locale, { seconds: true })">
                <span class="inline-flex w-full items-center justify-center gap-2">
                  <UIcon name="i-lucide-clock-3" class="size-4 shrink-0 text-toned" />
                  <span
                    :class="['min-w-0 text-center', expandClass(job.id, 'date')]"
                    :data-datetime="job.created_at"
                    v-rtime="job.created_at"
                  />
                </span>
              </UTooltip>
            </button>
          </div>

          <div v-if="job.error || showMessage(job)" class="space-y-2 border-t border-default pt-3">
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
        </div>
        <div class="ytp-border-top-soft px-4 py-4">
          <div class="flex flex-wrap justify-end gap-2">
            <UButton
              v-if="isToolboxActive(job)"
              color="neutral"
              variant="outline"
              icon="i-lucide-square"
              class="justify-center"
              :loading="inProgressIds.has(job.id)"
              :disabled="bulkBusy || inProgressIds.has(job.id)"
              @click="cancel(job)"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              v-else
              color="neutral"
              variant="outline"
              icon="i-lucide-trash"
              class="justify-center"
              :loading="inProgressIds.has(job.id)"
              :disabled="bulkBusy || inProgressIds.has(job.id)"
              @click="remove(job)"
            >
              {{ t('common.delete') }}
            </UButton>
          </div>
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
const { toggleExpand, isExpanded, expandClass } = useExpandableMeta();
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
const statusColors = {
  success: 'text-success',
  error: 'text-error',
  warning: 'text-warning',
  info: 'text-info',
  neutral: 'text-toned',
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
