<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell">
      <template #actions>
        <UButton
          v-if="tasks.length > 0"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilterPanel"
        >
          <span>{{ t('common.filter') }}</span>
        </UButton>

        <UButton
          color="primary"
          variant="solid"
          size="sm"
          icon="i-lucide-plus"
          @click="openCreateForm"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          v-if="tasks.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => void loadContent(page)"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>

        <UInput
          v-if="showFilter && tasks.length > 0"
          id="filter"
          ref="filterInput"
          v-model="query"
          type="search"
          :placeholder="t('common.filterDisplayedContent')"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </template>
    </PageHeader>

    <div
      v-if="!isLoading && filteredTasks.length > 0"
      class="flex flex-wrap items-center justify-between gap-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="allSelected ? 'i-lucide-square-check-big' : 'i-lucide-square'"
          @click="toggleMasterSelection"
        >
          {{ allSelected ? t('common.unselect') : t('common.select') }}
        </UButton>

        <UBadge v-if="selectedElms.length > 0" color="error" variant="soft" size="sm">
          {{ selectedElms.length }}
        </UBadge>

        <UDropdownMenu :items="bulkActionGroups" :modal="false">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-list"
            trailing-icon="i-lucide-chevron-down"
          >
            {{ t('common.actions') }}
          </UButton>
        </UDropdownMenu>
      </div>

      <UPagination
        v-if="paging?.total_pages > 1"
        :page="paging.page"
        :total="paging.total"
        :items-per-page="paging.per_page"
        :disabled="isLoading"
        show-edges
        :sibling-count="0"
        @update:page="loadContent"
        size="sm"
      />
    </div>

    <div
      v-if="filteredTasks.length > 0"
      :aria-label="pageShell.pageLabel"
      :aria-busy="isLoading"
      class="ytp-card divide-y divide-default"
    >
      <article
        v-for="item in filteredTasks"
        :key="item.id"
        :aria-labelledby="`task-title-${item.id}`"
        class="min-w-0 w-full max-w-full"
      >
        <div class="grid gap-4 p-4 sm:p-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.5fr)_auto]">
          <div class="min-w-0">
            <div class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1 space-y-2">
                <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <h2 :id="`task-title-${item.id}`" class="min-w-0 text-base font-semibold">
                    <NuxtLink
                      :to="item.id ? `/tasks/${item.id}` : '/tasks'"
                      class="wrap-anywhere text-highlighted hover:text-primary hover:underline"
                      :aria-label="`${t('common.details')}: ${remove_tags(item.name)}`"
                    >
                      {{ remove_tags(item.name) }}
                    </NuxtLink>
                  </h2>
                  <UTooltip :text="item.url">
                    <a
                      :href="item.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex shrink-0 items-center text-toned hover:text-primary"
                      :aria-label="`${t('tasks.openSourceUrl')}: ${remove_tags(item.name)}`"
                    >
                      <UIcon name="i-lucide-external-link" class="size-3.5" aria-hidden="true" />
                    </a>
                  </UTooltip>
                  <span
                    v-if="item.id && isTaskInProgress(item.id)"
                    class="inline-flex items-center gap-1.5 text-xs text-toned"
                    role="status"
                  >
                    <UIcon
                      name="i-lucide-loader-circle"
                      class="size-3.5 shrink-0 animate-spin text-info"
                      aria-hidden="true"
                    />
                    {{ t('tasks.inProgress') }}
                  </span>
                </div>

                <div v-if="get_tags(item.name).length > 0" class="flex flex-wrap gap-1">
                  <UBadge
                    v-for="tag in get_tags(item.name)"
                    :key="`${item.id}-${tag}`"
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
                    class="text-start"
                    :aria-pressed="item.enabled !== false"
                    :aria-label="`${t('common.enabled')}: ${remove_tags(item.name)}`"
                    @click="() => void toggleFlag(item, 'enabled')"
                  >
                    <UIcon
                      name="i-lucide-power"
                      class="size-3.5"
                      :class="item.enabled !== false ? 'text-success' : 'text-error'"
                      aria-hidden="true"
                    />
                    {{ item.enabled !== false ? t('common.enabled') : t('common.disabled') }}
                  </UButton>
                  <UButton
                    type="button"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    :aria-pressed="item.auto_start"
                    @click="() => void toggleFlag(item, 'auto_start')"
                  >
                    <UIcon name="i-lucide-circle-play" class="size-3.5" aria-hidden="true" />
                    {{ item.auto_start ? t('tasks.autoStartYes') : t('tasks.autoStartNo') }}
                  </UButton>
                  <UButton
                    type="button"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    :aria-pressed="item.handler_enabled !== false"
                    @click="() => void toggleFlag(item, 'handler_enabled')"
                  >
                    <UIcon name="i-lucide-rss" class="size-3.5" aria-hidden="true" />
                    {{
                      item.handler_enabled !== false ? t('tasks.handlerOn') : t('tasks.handlerOff')
                    }}
                  </UButton>
                </div>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <UCheckbox
                  color="primary"
                  :model-value="item.id !== undefined && selectedElms.includes(item.id)"
                  :disabled="item.id === undefined"
                  :aria-label="`${t('common.select')}: ${remove_tags(item.name)}`"
                  @update:model-value="selectedElms = setSelected(selectedElms, item.id, $event)"
                />
              </div>
            </div>
          </div>

          <div class="min-w-0 space-y-4">
            <dl
              class="grid min-w-0 gap-x-8 gap-y-3 text-sm sm:grid-cols-2"
              :class="{ 'lg:grid-cols-3': item.timer }"
            >
              <div class="min-w-0 space-y-1">
                <dt class="flex items-center gap-1.5 text-xs text-muted">
                  <UIcon name="i-lucide-clock-3" class="size-3.5 shrink-0" aria-hidden="true" />
                  {{ item.timer ? t('tasks.nextRun') : t('tasks.schedule') }}
                </dt>
                <dd class="wrap-anywhere">
                  <span v-if="item.enabled === false" class="text-toned">{{
                    t('common.disabled')
                  }}</span>
                  <a
                    v-else-if="item.timer"
                    :href="`https://crontab.guru/#${item.timer.replace(/ /g, '_')}`"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-primary hover:underline underline-offset-2"
                    :title="item.timer"
                  >
                    {{ tryParse(item.timer) }}
                  </a>
                  <span v-else :class="willTaskBeProcessed(item) ? 'text-default' : 'text-error'">
                    {{
                      willTaskBeProcessed(item) ? t('tasks.handlerOnly') : t('tasks.notConfigured')
                    }}
                  </span>
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
                <dd class="wrap-anywhere">{{ item.preset ?? config.app.default_preset }}</dd>
              </div>
              <div v-if="item.timer" class="min-w-0 space-y-1">
                <dt class="flex items-center gap-1.5 text-xs text-muted">
                  <UIcon name="i-lucide-clock-3" class="size-3.5 shrink-0" aria-hidden="true" />
                  {{ t('tasks.timer') }}
                </dt>
                <dd class="min-w-0">
                  <a
                    :href="`https://crontab.guru/#${item.timer.replace(/ /g, '_')}`"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="wrap-anywhere font-mono text-primary hover:underline"
                    dir="ltr"
                    >{{ item.timer }}</a
                  >
                </dd>
              </div>
            </dl>

            <dl v-if="item.folder || item.template || item.cli" class="min-w-0 space-y-3 text-sm">
              <div v-if="item.folder" class="space-y-1">
                <dt class="flex items-center gap-1.5 text-xs text-muted">
                  <UIcon
                    name="i-lucide-folder-output"
                    class="size-3.5 shrink-0"
                    aria-hidden="true"
                  />
                  {{ t('common.downloadPath') }}
                </dt>
                <dd class="wrap-anywhere whitespace-pre-wrap font-mono text-xs" dir="ltr">
                  {{ calcPath(item.folder) }}
                </dd>
              </div>
              <div v-if="item.template" class="space-y-1">
                <dt class="flex items-center gap-1.5 text-xs text-muted">
                  <UIcon name="i-lucide-file-code-2" class="size-3.5 shrink-0" aria-hidden="true" />
                  {{ t('common.outputTemplate') }}
                </dt>
                <dd class="wrap-anywhere whitespace-pre-wrap font-mono text-xs" dir="ltr">
                  {{ item.template }}
                </dd>
              </div>
              <div v-if="item.cli" class="space-y-1">
                <dt class="flex items-center gap-1.5 text-xs text-muted">
                  <UIcon name="i-lucide-terminal" class="size-3.5 shrink-0" aria-hidden="true" />
                  {{ t('common.cliOptions') }}
                </dt>
                <dd class="wrap-anywhere whitespace-pre-wrap font-mono text-xs" dir="ltr">
                  {{ item.cli }}
                </dd>
              </div>
            </dl>
          </div>
          <div class="flex justify-end self-start">
            <div class="flex shrink-0 items-center gap-1.5">
              <UTooltip :text="t('common.edit')">
                <UButton
                  color="neutral"
                  variant="outline"
                  size="sm"
                  icon="i-lucide-pencil"
                  :aria-label="t('common.editTitle', { name: remove_tags(item.name) })"
                  @click="editItem(item)"
                >
                  <span>{{ t('common.edit') }}</span>
                </UButton>
              </UTooltip>

              <UDropdownMenu
                :items="itemActionGroups(item)"
                :modal="false"
                :content="{ align: 'end' }"
              >
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="sm"
                  icon="i-lucide-ellipsis"
                  square
                  :aria-label="`${t('common.actions')}: ${remove_tags(item.name)}`"
                />
              </UDropdownMenu>
            </div>
          </div>
        </div>
      </article>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :ui="{ icon: 'animate-spin' }"
    />

    <UEmpty
      v-else-if="query && filteredTasks.length < 1"
      size="sm"
      icon="i-lucide-search"
      :title="t('common.noResults')"
      :description="t('common.noResultsFor', { query })"
    />

    <UEmpty
      v-else-if="!query && tasks.length < 1"
      icon="i-lucide-calendar-clock"
      :title="t('common.noItems')"
      :description="t('common.empty')"
      size="sm"
    />

    <div v-if="filteredTasks.length > 0 && paging?.total_pages > 1" class="flex justify-end">
      <UPagination
        :page="paging.page"
        :total="paging.total"
        :items-per-page="paging.per_page"
        :disabled="isLoading"
        show-edges
        :sibling-count="0"
        @update:page="loadContent"
        size="sm"
      />
    </div>

    <details v-if="tasks.length > 0" class="text-sm">
      <summary class="w-fit cursor-pointer font-medium text-toned">
        {{ t('common.usageNotes') }}
      </summary>
      <ul class="mt-3 list-disc space-y-2 ps-5 text-sm text-toned">
        <li>
          <span class="text-error" v-html="t('tasks.noteArchive')" />
        </li>
        <li v-html="t('tasks.noteArchiveAll')" />
        <li v-html="t('tasks.noteCron')" />
        <li v-html="t('tasks.noteMetadata', { path: config.app.download_path })" />
        <li v-html="t('tasks.noteYoutubeRss')" />
      </ul>
    </details>

    <UModal
      v-if="toggleForm"
      :open="toggleForm"
      :title="
        taskRef ? t('common.editTitle', { name: task.name || t('tasks.task') }) : t('common.add')
      "
      :description="taskRef ? t('common.updateDescription') : t('common.createDescription')"
      :dismissible="!addInProgress"
      :ui="{ content: 'w-full sm:max-w-7xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <FormSubmitError :message="submission.message.value" @dismiss="submission.clear" />
        <LazyTaskForm
          :key="formKey"
          :addInProgress="addInProgress"
          :reference="taskRef"
          :task="task as Task"
          @dirty-change="(dirty) => (editorDirty = dirty)"
          @valid-change="(value) => (editorValid = value)"
          @submit="updateItem"
        />
      </template>

      <template #footer>
        <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <UButton
            type="button"
            color="neutral"
            variant="outline"
            icon="i-lucide-x"
            :disabled="addInProgress"
            class="justify-center"
            @click="() => void requestCloseEditor()"
          >
            {{ t('common.cancel') }}
          </UButton>

          <UButton
            type="submit"
            form="taskForm"
            color="primary"
            icon="i-lucide-save"
            :disabled="addInProgress || !editorValid"
            :loading="addInProgress"
            class="justify-center"
          >
            {{ t('common.save') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <UModal
      v-if="inspectTask"
      :open="Boolean(inspectTask)"
      :title="t('common.test')"
      :ui="{ content: 'w-full sm:max-w-4xl', body: 'p-4 sm:p-6' }"
      @update:open="(open) => !open && (inspectTask = null)"
    >
      <template #body>
        <LazyTaskInspect ref="taskInspect" :url="inspectTask.url" :preset="inspectTask.preset" />
      </template>

      <template #footer>
        <div class="flex w-full flex-wrap items-center justify-end gap-2">
          <template v-if="taskInspect?.hasResult">
            <UButton
              type="button"
              color="neutral"
              :variant="taskInspect.wrap ? 'soft' : 'outline'"
              size="sm"
              icon="i-lucide-wrap-text"
              :disabled="!taskInspect.hasVisibleResponse"
              @click="taskInspect.toggleWrap()"
            >
              <span class="hidden sm:inline">{{ t('common.wrap') }}</span>
            </UButton>

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-copy"
              :disabled="!taskInspect.hasVisibleResponse"
              @click="taskInspect.copyResponse()"
            >
              {{ t('common.copy') }}
            </UButton>

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-arrow-down"
              :disabled="!taskInspect.hasVisibleResponse"
              @click="taskInspect.scrollResponse('end')"
            >
              {{ t('common.goDown') }}
            </UButton>

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-arrow-up"
              :disabled="!taskInspect.hasVisibleResponse"
              @click="taskInspect.scrollResponse('start')"
            >
              {{ t('common.goUp') }}
            </UButton>
          </template>

          <div class="ml-auto flex items-center gap-2">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-rotate-ccw"
              :disabled="taskInspect?.loading"
              class="justify-center"
              @click="taskInspect?.onReset()"
            >
              {{ t('common.reset') }}
            </UButton>

            <UButton
              type="submit"
              form="taskInspectForm"
              color="primary"
              icon="i-lucide-search"
              :loading="taskInspect?.loading"
              :disabled="taskInspect?.loading"
              class="justify-center"
            >
              {{ t('common.test') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import { setSelected } from '~/utils/selection';
import type { DropdownMenuItem } from '@nuxt/ui';
import { CronExpressionParser } from 'cron-parser';
import { useConfirm } from '~/composables/useConfirm';
import { useTasks } from '~/composables/useTasks';
import type TaskInspect from '~/components/TaskInspect.vue';
import type { ExportedTask, Task, TaskScheduleDraft } from '~/types/tasks';
import type { WSEP } from '~/types/sockets';
import { sleep } from '~/utils';
import { formatRelativeTime } from '~/utils/relativeTime';
import { useSessionCache } from '~/utils/cache';
import type { item_request } from '~/types/item';
import { usePageShell } from '~/composables/usePageShell';
import { useFormHandoff } from '~/composables/useFormHandoff';
const { locale, t } = useI18n();

const box = useConfirm();
const toast = useNotification();
const config = useYtpConfig();
const socket = useAppSocket();
const stateStore = useQueueState();
const pageShell = usePageShell('tasks');
const route = useRoute();
const router = useRouter();
const { confirmDialog } = useDialog();
const sessionCache = useSessionCache();

const tasksComposable = useTasks();
const submission = useFormSubmit();
const {
  tasks,
  pagination: paging,
  isLoading,
  addInProgress,
  isTaskInProgress,
  setTaskInProgress,
  clearTaskInProgress,
} = tasksComposable;

const createEmptyTask = (): Partial<Task> => ({
  name: '',
  url: '',
  timer: '',
  preset: '',
  folder: '',
  template: '',
  cli: '',
  auto_start: true,
  handler_enabled: true,
  enabled: true,
});

const taskFormHandoff = useFormHandoff<TaskScheduleDraft>('task');

const task = ref<Partial<Task>>(createEmptyTask());
const taskRef = ref<number | null>(null);
const toggleForm = ref(false);
const taskInspect = ref<InstanceType<typeof TaskInspect> | null>(null);
const editorDirty = ref(false);
const editorValid = ref(false);
const selectedElms = ref<number[]>([]);
const massRun = ref(false);
const massDelete = ref(false);
const inspectTask = ref<Task | null>(null);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1);
const CACHE_KEY = 'tasks:handler_support';
const taskHandlerSupport = ref<Record<string, boolean>>(sessionCache.get(CACHE_KEY) || {});

const handleTaskEvent = (payload: WSEP['task_finished'] | WSEP['task_error']) => {
  const rawTaskId = payload.data?.task_id;
  const taskId = typeof rawTaskId === 'number' ? rawTaskId : Number(rawTaskId);
  if (Number.isSafeInteger(taskId) && taskId > 0) {
    clearTaskInProgress(taskId);
  }
};
const taskFinishedHandler = (payload: WSEP['task_finished']) => handleTaskEvent(payload);
const taskErrorHandler = (payload: WSEP['task_error']) => handleTaskEvent(payload);

const editorSessionId = ref(0);

const formKey = computed(() => `${taskRef.value ?? 'new'}:${editorSessionId.value}`);

const discardEditor = (): void => {
  editorDirty.value = false;
  editorValid.value = false;
  task.value = createEmptyTask();
  taskRef.value = null;
};

const { handleOpenChange: handleEditorOpenChange, requestClose: requestCloseEditor } =
  useDirtyCloseGuard(toggleForm, {
    dirty: editorDirty,
    preferenceKey: 'tasks',
    message: t('common.discardChanges'),
    onDiscard: async () => {
      discardEditor();
    },
  });

const filteredTasks = computed(() => {
  const normalizedQuery = query.value?.toLowerCase();
  if (!normalizedQuery) {
    return tasks.value;
  }

  return tasks.value.filter((item) => deepIncludes(item, normalizedQuery, new WeakSet()));
});

const selectableTaskIds = computed(() =>
  filteredTasks.value.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectableTaskIds.value.length > 0 &&
    selectableTaskIds.value.every((id) => selectedElms.value.includes(id)),
);

const hasSelected = computed(() => selectedElms.value.length > 0);

const bulkActionGroups = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: t('common.runSelected'),
      icon: 'i-lucide-square-play',
      color: 'primary',
      disabled: !hasSelected.value || massRun.value,
      onSelect: () => void runSelected(),
    },
    {
      label: t('common.removeSelected'),
      icon: 'i-lucide-trash',
      disabled: !hasSelected.value || massDelete.value,
      onSelect: () => void deleteSelected(),
    },
  ],
]);

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

watch(
  filteredTasks,
  (items) => {
    const validIds = new Set(
      items.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
    );
    selectedElms.value = selectedElms.value.filter((id) => validIds.has(id));
  },
  { deep: true },
);

watch(taskHandlerSupport, (newValue) => sessionCache.set(CACHE_KEY, newValue), { deep: true });

watch(
  () => socket.isConnected,
  (connected) => {
    socket.off('item_status', statusHandler);
    socket.off('task_finished', taskFinishedHandler);
    socket.off('task_error', taskErrorHandler);
    if (connected) {
      socket.on('item_status', statusHandler);
      socket.on('task_finished', taskFinishedHandler);
      socket.on('task_error', taskErrorHandler);
    }
  },
  { immediate: true },
);

const syncPageQuery = async (pageNumber: number): Promise<void> => {
  const totalPages = tasksComposable.pagination.value.total_pages;
  const nextQuery = { ...route.query };

  if (totalPages > 1) {
    nextQuery.page = String(pageNumber);
  } else {
    delete nextQuery.page;
  }

  await router.replace({ query: nextQuery });
};

const toggleFilterPanel = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }

  await nextTick();
  filterInput.value?.inputRef?.value?.focus?.({ preventScroll: true });
};

const toggleMasterSelection = (): void => {
  if (allSelected.value) {
    selectedElms.value = [];
    return;
  }

  selectedElms.value = [...selectableTaskIds.value];
};

const getCacheKey = (item: Task): string => `${item.id}:${item.url}`;

const cleanStaleCache = (currentTasks: ReadonlyArray<Task>) => {
  const validKeys = new Set(currentTasks.map((item) => getCacheKey(item)));
  const nextCache: Record<string, boolean> = {};

  Object.keys(taskHandlerSupport.value).forEach((key) => {
    if (validKeys.has(key)) {
      nextCache[key] = Boolean(taskHandlerSupport.value[key]);
    }
  });

  taskHandlerSupport.value = nextCache;
};

const checkHandlerSupport = async (item: Task): Promise<boolean> => {
  const cacheKey = getCacheKey(item);

  if (undefined !== taskHandlerSupport.value[cacheKey]) {
    return taskHandlerSupport.value[cacheKey] as boolean;
  }

  try {
    const result = await tasksComposable.inspectTaskHandler({
      url: item.url,
      static_only: true,
    });
    const supported = true === result?.matched;
    taskHandlerSupport.value[cacheKey] = supported;
    return supported;
  } catch {
    taskHandlerSupport.value[cacheKey] = false;
    return false;
  }
};

const recheckHandlerSupport = async (updatedTasks: ReadonlyArray<Task>) => {
  for (const item of updatedTasks) {
    if (!item.timer && false !== item.handler_enabled) {
      await checkHandlerSupport(item);
    }
  }
};

const willTaskBeProcessed = (item: Task): boolean => {
  if (false === item.enabled) {
    return false;
  }

  const hasTimer = Boolean(item.timer && item.timer.trim());
  const cacheKey = getCacheKey(item);
  const hasHandler = false !== item.handler_enabled && true === taskHandlerSupport.value[cacheKey];

  return hasTimer || hasHandler;
};

const loadContent = async (pageNumber = page.value, fromMounted: boolean = false) => {
  page.value = pageNumber;

  try {
    await tasksComposable.loadTasks(pageNumber);

    page.value = tasksComposable.pagination.value.page;
    await nextTick();
    await syncPageQuery(page.value);

    if (tasks.value.length > 0) {
      cleanStaleCache(tasks.value);
      await recheckHandlerSupport(tasks.value);
    }
  } catch (error) {
    if (!fromMounted) {
      console.error(error);
    }
  }
};

const resetForm = (closeForm: boolean = false) => {
  submission.clear();
  task.value = createEmptyTask();
  taskRef.value = null;
  editorDirty.value = false;
  editorValid.value = false;

  if (closeForm) {
    toggleForm.value = false;
  }
};

const closeEditor = (): void => {
  resetForm(true);
};

const openCreateForm = (): void => {
  resetForm(false);
  editorSessionId.value += 1;
  toggleForm.value = true;
};

const deleteSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noTasksSelected'));
    return;
  }

  const { status } = await confirmDialog({
    title: t('common.deleteSelected'),
    message:
      t('common.deleteCountConfirm', { count: selectedElms.value.length }) +
      '\n\n' +
      selectedElms.value
        .map((id) => {
          const item = tasks.value.find((task) => task.id === id);
          return item ? `${item.id}: ${item.name}` : '';
        })
        .filter(Boolean)
        .join('\n'),
    confirmText: t('common.delete'),
    confirmColor: 'error',
  });

  if (true !== status) {
    return;
  }

  const itemsToDelete = tasks.value.filter(
    (item) => item.id && selectedElms.value.includes(item.id),
  );
  if (itemsToDelete.length < 1) {
    toast.error(t('common.noTasksToDelete'));
    return;
  }

  massDelete.value = true;

  for (const item of itemsToDelete) {
    if (!item.id) {
      continue;
    }
    await tasksComposable.deleteTask(item.id);
  }

  selectedElms.value = [];

  setTimeout(async () => {
    await nextTick();
    massDelete.value = false;
  }, 500);
};

const deleteItem = async (item: Task) => {
  if (
    !item.id ||
    true !== (await box.confirm(t('common.deleteNamedConfirm', { name: item.name })))
  ) {
    return;
  }

  await tasksComposable.deleteTask(item.id);
};

const toggleFlag = async (item: Task, field: 'enabled' | 'auto_start' | 'handler_enabled') => {
  if (!item.id) {
    toast.error(t('common.taskIdMissing'));
    return;
  }

  const currentValue = item[field] !== false;
  let updated: Task | null = null;
  try {
    updated = await tasksComposable.patchTask(item.id, { [field]: !currentValue });
  } catch (error) {
    toast.error(error instanceof Error ? error.message : t('common.unknownError'));
    return;
  }

  if (updated) {
    item[field] = updated[field];

    if (field === 'enabled' && updated.enabled) {
      await checkHandlerSupport(updated);
    }

    if (field === 'handler_enabled' && updated.handler_enabled) {
      await checkHandlerSupport(updated);
    }
  }
};

const updateItem = async ({
  reference,
  task,
  archive_all,
}: {
  reference?: number | null | undefined;
  task: Task | Task[];
  archive_all?: boolean;
}) => {
  const createdOrUpdated = reference
    ? await submission.run(() => tasksComposable.updateTask(reference, task as Task))
    : await submission.run(() => tasksComposable.createTask(task));

  if (!createdOrUpdated) {
    return;
  }

  const tasksList = Array.isArray(createdOrUpdated) ? createdOrUpdated : [createdOrUpdated];

  closeEditor();

  if (!reference && true === archive_all) {
    await nextTick();
    await sleep(1);
    toast.info(t('tasks.archivingItems', { count: tasksList.length }));

    for (const item of tasksList) {
      if (item.id) {
        await archiveAll(item, true);
      }
    }
  }

  for (const item of tasksList) {
    if (!item.timer && false !== item.handler_enabled) {
      await checkHandlerSupport(item);
    }
  }
};

const editItem = (item: Task) => {
  submission.clear();
  editorDirty.value = false;
  editorValid.value = false;
  task.value = { ...item };
  taskRef.value = item.id ?? null;
  editorSessionId.value += 1;
  toggleForm.value = true;
};

const calcPath = (path: string) => {
  const location = shortPath(config.app.download_path || '/downloads');

  if (path) {
    return eTrim(location, '/') + '/' + sTrim(path, '/');
  }

  return location;
};

const tryParse = (expression: string) => {
  try {
    return formatRelativeTime(
      CronExpressionParser.parse(expression).next().toISOString(),
      locale.value,
    );
  } catch {
    return t('common.invalid');
  }
};

const runSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error(t('common.noTasksSelected'));
    return;
  }

  const { status } = await confirmDialog({
    message:
      t('tasks.runTasksConfirm') +
      '\n\n' +
      selectedElms.value
        .map((id) => {
          const item = tasks.value.find((task) => task.id === id);
          return item ? item.name : '';
        })
        .filter(Boolean)
        .join('\n'),
  });

  if (true !== status) {
    return;
  }

  massRun.value = true;

  for (const id of selectedElms.value) {
    const item = tasks.value.find((task) => task.id === id);
    if (!item) {
      continue;
    }

    await runNow(item, true);
  }

  selectedElms.value = [];
  toast.success(t('common.dispatchedTasks'));

  massRun.value = false;
};

const runNow = async (item: Task, mass: boolean = false) => {
  if (!item.id) {
    return;
  }

  if (!mass && true !== (await box.confirm(t('tasks.runNowConfirm', { name: item.name })))) {
    return;
  }

  if (!mass) {
    setTaskInProgress(item.id);
  }

  const data: item_request = {
    url: item.url,
    preset: item.preset,
    extras: {
      source_name: item.name,
      source_id: item.id,
      source_handler: 'web',
      ...(item.ignore_conditions?.length ? { ignore_conditions: [...item.ignore_conditions] } : {}),
    },
  };

  if (item.folder) {
    data.folder = item.folder;
  }

  if (item.template) {
    data.template = item.template;
  }

  if (item.cli) {
    data.cli = item.cli;
  }

  if (undefined !== item.auto_start) {
    data.auto_start = item.auto_start;
  }

  await stateStore.addDownload(data);

  if (mass) {
    return;
  }

  if (!socket.isConnected) {
    clearTaskInProgress(item.id);
  }
};

async function statusHandler(payload: WSEP['item_status']) {
  const { status, msg } = payload.data || {};

  if ('error' === status) {
    toast.error(msg ?? t('common.unknownError'));
  }
}

const exportItem = async (item: Task) => {
  const info = JSON.parse(JSON.stringify(item));

  const data = {
    name: info.name,
    url: info.url,
    preset: info.preset,
    timer: info.timer,
    folder: info.folder,
    auto_start: info?.auto_start ?? true,
    handler_enabled: info?.handler_enabled ?? true,
    enabled: info?.enabled ?? true,
    ignore_conditions: info?.ignore_conditions ?? [],
  } as ExportedTask;

  if (info.template) {
    data.template = info.template;
  }

  if (info.cli) {
    data.cli = info.cli;
  }

  data._type = 'task';
  data._version = '2.0';

  return copyText(encode(data));
};

const get_tags = (name: string): string[] => {
  const regex = /\[(.*?)\]/g;
  const matches = name.match(regex);
  return !matches ? [] : matches.map((tag) => tag.replace(/[[\]]/g, '').trim());
};

const remove_tags = (name: string): string => name.replace(/\[(.*?)\]/g, '').trim();

const archiveAll = async (item: Task, by_pass: boolean = false) => {
  if (!item.id) {
    toast.error(t('common.taskIdMissing'));
    return;
  }

  try {
    if (true !== by_pass) {
      const { status } = await confirmDialog({
        message: t('tasks.archiveAllConfirm', { name: item.name }),
      });

      if (true !== status) {
        return;
      }
    }

    setTaskInProgress(item.id);
    await tasksComposable.markTaskItems(item.id);
  } catch (error: any) {
    toast.error(
      t('common.failedWithReason', {
        message: t('common.failedArchive'),
        reason: error.message || t('common.unknownError'),
      }),
    );
  } finally {
    clearTaskInProgress(item.id);
  }
};

const unarchiveAll = async (item: Task) => {
  if (!item.id) {
    toast.error(t('common.taskIdMissing'));
    return;
  }

  try {
    const { status } = await confirmDialog({
      message: t('tasks.unarchiveAllConfirm', { name: item.name }),
    });

    if (true !== status) {
      return;
    }

    setTaskInProgress(item.id);
    await tasksComposable.unmarkTaskItems(item.id);
  } catch (error: any) {
    toast.error(
      t('common.failedWithReason', {
        message: t('common.failedRemoveArchive'),
        reason: error.message || t('common.unknownError'),
      }),
    );
  } finally {
    if (item.id) {
      clearTaskInProgress(item.id);
    }
  }
};

const generateMeta = async (item: Task) => {
  if (!item.id) {
    toast.error(t('common.taskIdMissing'));
    return;
  }

  try {
    const { status } = await confirmDialog({
      message:
        t('tasks.generateMetadataConfirm', { name: item.name }) +
        '\n\n' +
        t('tasks.generateMetadataConfirmDesc'),
    });

    if (true !== status) {
      return;
    }

    setTaskInProgress(item.id);
    await tasksComposable.generateTaskMetadata(item.id);
  } catch (error: any) {
    toast.error(
      t('common.failedWithReason', {
        message: t('common.failedGenerateMetadata'),
        reason: error.message || t('common.unknownError'),
      }),
    );
  } finally {
    if (item.id) {
      clearTaskInProgress(item.id);
    }
  }
};

const itemActionGroups = (item: Task): DropdownMenuItem[][] => [
  [
    {
      label: t('common.runNow'),
      icon: 'i-lucide-square-play',
      onSelect: () => void runNow(item),
    },
    {
      label: t('common.generateMetadata'),
      icon: 'i-lucide-film',
      onSelect: () => void generateMeta(item),
    },
  ],
  [
    {
      label: t('common.test'),
      icon: 'i-lucide-search',
      onSelect: () => {
        inspectTask.value = item;
      },
    },
  ],
  [
    {
      label: t('common.archiveAll'),
      icon: 'i-lucide-box',
      onSelect: () => void archiveAll(item),
    },
    {
      label: t('common.unarchiveAll'),
      icon: 'i-lucide-box',
      onSelect: () => void unarchiveAll(item),
    },
  ],
  [
    {
      label: t('common.exportItem'),
      icon: 'i-lucide-file-up',
      onSelect: () => void exportItem(item),
    },
  ],
  [
    {
      label: t('common.delete'),
      icon: 'i-lucide-trash',
      color: 'error',
      onSelect: () => void deleteItem(item),
    },
  ],
];

onMounted(async () => {
  const draft = taskFormHandoff.take();
  if (draft) {
    task.value = { ...createEmptyTask(), ...draft };
    editorSessionId.value += 1;
    toggleForm.value = true;
  }

  await loadContent(page.value, true);
});

onBeforeUnmount(() => {
  socket.off('item_status', statusHandler);
  socket.off('task_finished', taskFinishedHandler);
  socket.off('task_error', taskErrorHandler);
});
</script>
