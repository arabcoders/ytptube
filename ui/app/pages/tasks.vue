<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-list-todo" class="size-5 text-toned" />
          <span>Tasks</span>
        </div>

        <p class="text-sm text-toned">
          The task runner is simple queue system that allows you to poll channels or playlists for
          new content at specified intervals.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="showFilter && tasks.length > 0" class="relative w-full sm:w-80">
          <span
            class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-toned"
          >
            <UIcon name="i-lucide-filter" class="size-4" />
          </span>
          <input
            id="filter"
            ref="filterInput"
            v-model="query"
            type="search"
            placeholder="Filter displayed content"
            class="w-full rounded-md border border-default bg-elevated py-2 pr-3 pl-9 text-sm text-default outline-none transition focus:border-primary"
          />
        </div>

        <UButton
          v-if="tasks.length > 0"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilterPanel"
        >
          <span v-if="!isMobile">Filter</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="openCreateForm"
        >
          <span v-if="!isMobile">New Task</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="displayStyle === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          @click="toggleDisplayStyle"
        >
          <span v-if="!isMobile">{{ displayStyle === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UButton
          v-if="tasks.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => void reloadContent()"
        >
          <span v-if="!isMobile">Reload</span>
        </UButton>
      </div>
    </div>

    <div
      v-if="!isLoading && filteredTasks.length > 0"
      class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default bg-default px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
          @click="toggleMasterSelection"
        >
          {{ allSelected ? 'Unselect' : 'Select' }}
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
            Actions
          </UButton>
        </UDropdownMenu>
      </div>

      <div class="text-xs text-toned">{{ filteredTasks.length }} displayed</div>
    </div>

    <div
      v-if="displayStyle === 'list' && filteredTasks.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-290 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-[5%]">
                <button type="button" class="cursor-pointer" @click="toggleMasterSelection">
                  <UIcon
                    :name="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-left">Task</th>
              <th class="w-[18%]">Timer</th>
              <th class="w-[1%]">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="item in filteredTasks" :key="item.id" class="align-top hover:bg-muted/20">
              <td class="px-3 py-3 text-center align-top">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedElms"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item.id"
                  />
                </label>
              </td>

              <td class="px-3 py-3 align-top">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1 space-y-2">
                    <div class="flex items-start gap-2">
                      <NuxtLink
                        target="_blank"
                        :href="item.url"
                        class="min-w-0 truncate font-semibold text-highlighted hover:underline"
                      >
                        {{ remove_tags(item.name) }}
                      </NuxtLink>

                      <UIcon
                        v-if="item.id && isTaskInProgress(item.id)"
                        name="i-lucide-loader-circle"
                        class="mt-0.5 size-4 shrink-0 animate-spin text-info"
                      />
                    </div>

                    <div
                      v-if="get_tags(item.name).length > 0"
                      class="flex flex-wrap items-center gap-1"
                    >
                      <UBadge
                        v-for="tag in get_tags(item.name)"
                        :key="`${item.id}-${tag}`"
                        color="info"
                        variant="soft"
                        size="sm"
                      >
                        {{ tag }}
                      </UBadge>
                    </div>

                    <div class="flex flex-wrap items-center gap-2 text-xs text-toned">
                      <button
                        type="button"
                        class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 transition hover:border-primary hover:text-default"
                        @click="() => void toggleEnabled(item)"
                      >
                        <UIcon
                          name="i-lucide-power"
                          class="size-3.5"
                          :class="item.enabled !== false ? 'text-success' : 'text-error'"
                        />
                        <span>{{ item.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                      </button>

                      <span
                        class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                      >
                        <UIcon
                          :name="item.auto_start ? 'i-lucide-circle-pause' : 'i-lucide-circle-play'"
                          class="size-3.5"
                        />
                        <span>{{ item.auto_start ? 'Auto' : 'Manual' }}</span>
                      </span>

                      <button
                        type="button"
                        class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 transition hover:border-primary hover:text-default"
                        @click="() => void toggleHandlerEnabled(item)"
                      >
                        <UIcon
                          name="i-lucide-rss"
                          class="size-3.5"
                          :class="item.handler_enabled !== false ? 'text-success' : 'text-error'"
                        />
                        <span>{{ item.handler_enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                      </button>

                      <span
                        class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                      >
                        <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
                        <span class="capitalize">
                          {{ item.preset ?? config.app.default_preset }}
                        </span>
                      </span>
                    </div>

                    <div class="space-y-1 text-xs text-toned">
                      <div v-if="item.folder" class="flex items-start gap-2">
                        <UIcon name="i-lucide-folder-output" class="mt-0.5 size-3.5 shrink-0" />
                        <span class="break-all">{{ calcPath(item.folder) }}</span>
                      </div>

                      <div v-if="item.template" class="flex items-start gap-2">
                        <UIcon name="i-lucide-file-code-2" class="mt-0.5 size-3.5 shrink-0" />
                        <span class="break-all">{{ item.template }}</span>
                      </div>

                      <div v-if="item.cli" class="flex items-start gap-2">
                        <UIcon name="i-lucide-terminal" class="mt-0.5 size-3.5 shrink-0" />
                        <span class="break-all">{{ item.cli }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </td>

              <td class="px-3 py-3 align-top text-center">
                <div class="space-y-1">
                  <template v-if="item.timer">
                    <UTooltip :text="item.timer">
                      <a
                        class="font-medium text-highlighted hover:underline"
                        target="_blank"
                        :href="`https://crontab.guru/#${item.timer.replace(/ /g, '_')}`"
                      >
                        {{ item.timer }}
                      </a>
                    </UTooltip>
                    <p
                      class="text-xs"
                      :class="tryParse(item.timer) === 'Invalid' ? 'text-error' : 'text-toned'"
                    >
                      {{ tryParse(item.timer) }}
                    </p>
                  </template>

                  <p
                    v-else-if="!willTaskBeProcessed(item)"
                    class="text-xs font-medium text-error whitespace-nowrap"
                  >
                    <span class="inline-flex items-center gap-1 whitespace-nowrap">
                      <UIcon name="i-lucide-triangle-alert" class="size-3.5" />
                      <span>No timer or handler</span>
                    </span>
                  </p>

                  <p v-else class="text-xs font-medium text-toned whitespace-nowrap">
                    <span class="inline-flex items-center gap-1 whitespace-nowrap">
                      <UIcon name="i-lucide-rss" class="size-3.5" />
                      <span>Handler only</span>
                    </span>
                  </p>
                </div>
              </td>

              <td class="w-[1%] px-3 py-3 align-top whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="warning"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="editItem(item)"
                  >
                    <span v-if="!isMobile">Edit</span>
                  </UButton>

                  <UButton
                    color="error"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void deleteItem(item)"
                  >
                    <span v-if="!isMobile">Delete</span>
                  </UButton>

                  <UDropdownMenu :items="itemActionGroups(item)" :modal="false">
                    <UButton
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-settings-2"
                      trailing-icon="i-lucide-chevron-down"
                    >
                      <span v-if="!isMobile">Actions</span>
                    </UButton>
                  </UDropdownMenu>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      v-else-if="filteredTasks.length > 0"
      class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <div v-for="item in filteredTasks" :key="item.id" class="min-w-0 w-full max-w-full">
        <UCard
          class="flex h-full min-w-0 w-full max-w-full flex-col border bg-default"
          :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
        >
          <template #header>
            <div class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1 space-y-2">
                <div class="flex items-start gap-2">
                  <NuxtLink
                    target="_blank"
                    :href="item.url"
                    class="min-w-0 flex-1 truncate text-sm font-semibold text-highlighted hover:underline"
                  >
                    {{ remove_tags(item.name) }}
                  </NuxtLink>

                  <UIcon
                    v-if="item.id && isTaskInProgress(item.id)"
                    name="i-lucide-loader-circle"
                    class="mt-0.5 size-4 shrink-0 animate-spin text-info"
                  />
                </div>

                <div class="flex flex-wrap items-center gap-1">
                  <UBadge
                    v-for="tag in get_tags(item.name)"
                    :key="`${item.id}-${tag}`"
                    color="info"
                    variant="soft"
                    size="sm"
                  >
                    {{ tag }}
                  </UBadge>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-2">
                <UButton
                  color="info"
                  variant="ghost"
                  size="xs"
                  icon="i-lucide-file-up"
                  square
                  @click="() => void exportItem(item)"
                />

                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedElms"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item.id"
                  />
                </label>
              </div>
            </div>
          </template>

          <div class="space-y-2 text-sm text-default">
            <div class="flex flex-wrap gap-2 text-xs text-toned *:min-w-32 *:flex-1">
              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 transition hover:border-primary hover:text-default"
                @click="() => void toggleEnabled(item)"
              >
                <UIcon
                  name="i-lucide-power"
                  class="size-3.5"
                  :class="item.enabled !== false ? 'text-success' : 'text-error'"
                />
                <span>{{ item.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
              </button>

              <span
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon
                  :name="item.auto_start ? 'i-lucide-circle-pause' : 'i-lucide-circle-play'"
                  class="size-3.5"
                />
                <span>{{ item.auto_start ? 'Auto' : 'Manual' }}</span>
              </span>

              <button
                type="button"
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 transition hover:border-primary hover:text-default"
                @click="() => void toggleHandlerEnabled(item)"
              >
                <UIcon
                  name="i-lucide-rss"
                  class="size-3.5"
                  :class="item.handler_enabled !== false ? 'text-success' : 'text-error'"
                />
                <span>{{ item.handler_enabled !== false ? 'Handler on' : 'Handler off' }}</span>
              </button>

              <span
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
                <span class="capitalize">{{ item.preset ?? config.app.default_preset }}</span>
              </span>
            </div>

            <div class="rounded-md border border-default bg-muted/20 px-3 py-2">
              <div class="flex items-start gap-2 text-sm">
                <UIcon
                  :name="
                    item.timer
                      ? 'i-lucide-clock-3'
                      : willTaskBeProcessed(item)
                        ? 'i-lucide-rss'
                        : 'i-lucide-triangle-alert'
                  "
                  class="mt-0.5 size-4 shrink-0"
                  :class="!item.timer && !willTaskBeProcessed(item) ? 'text-error' : 'text-toned'"
                />

                <div class="min-w-0 flex-1">
                  <template v-if="item.timer">
                    <a
                      target="_blank"
                      :href="`https://crontab.guru/#${item.timer.replace(/ /g, '_')}`"
                      class="break-all text-highlighted hover:underline"
                    >
                      {{ item.timer }}
                    </a>
                    <p
                      class="mt-1 text-xs"
                      :class="tryParse(item.timer) === 'Invalid' ? 'text-error' : 'text-toned'"
                    >
                      {{ tryParse(item.timer) }}
                    </p>
                  </template>

                  <p v-else-if="willTaskBeProcessed(item)" class="text-toned whitespace-nowrap">
                    Handler only
                  </p>
                  <p v-else class="text-error whitespace-nowrap">No timer or handler</p>
                </div>
              </div>
            </div>

            <div v-if="item.folder" class="rounded-md border border-default bg-muted/20 px-3 py-2">
              <div class="flex items-start gap-2">
                <UIcon name="i-lucide-folder-output" class="mt-0.5 size-4 shrink-0 text-toned" />
                <span class="break-all text-toned">{{ calcPath(item.folder) }}</span>
              </div>
            </div>

            <div
              v-if="item.template"
              class="rounded-md border border-default bg-muted/20 px-3 py-2"
            >
              <div class="flex items-start gap-2">
                <UIcon name="i-lucide-file-code-2" class="mt-0.5 size-4 shrink-0 text-toned" />
                <span class="break-all text-toned">{{ item.template }}</span>
              </div>
            </div>

            <div v-if="item.cli" class="rounded-md border border-default bg-muted/20 px-3 py-2">
              <div class="flex items-start gap-2">
                <UIcon name="i-lucide-terminal" class="mt-0.5 size-4 shrink-0 text-toned" />
                <span class="break-all text-toned">{{ item.cli }}</span>
              </div>
            </div>
          </div>

          <div class="mt-auto flex flex-wrap gap-2 pt-2 *:min-w-32 *:flex-1">
            <UButton
              color="warning"
              variant="outline"
              icon="i-lucide-pencil"
              class="w-full justify-center"
              @click="editItem(item)"
            >
              Edit
            </UButton>

            <UButton
              color="error"
              variant="outline"
              icon="i-lucide-trash"
              class="w-full justify-center"
              @click="() => void deleteItem(item)"
            >
              Delete
            </UButton>

            <UDropdownMenu :items="itemActionGroups(item)" :modal="false">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-settings-2"
                trailing-icon="i-lucide-chevron-down"
                class="w-full justify-center"
              >
                Actions
              </UButton>
            </UDropdownMenu>
          </div>
        </UCard>
      </div>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading"
      description="Loading data. Please wait..."
    />

    <div v-else-if="query && filteredTasks.length < 1" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        title="No Results"
        :description="`No results found for the query: ${query}. Please try a different search term.`"
      />

      <UButton color="neutral" variant="outline" size="sm" @click="query = ''">
        Clear filter
      </UButton>
    </div>

    <UAlert
      v-if="!query && tasks.length < 1"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No tasks."
      description="There are no tasks defined yet. Click the New Task button to create your first automated download task."
    />

    <UAlert v-if="tasks.length > 0" color="info" variant="soft">
      <template #description>
        <ul class="list-disc space-y-2 pl-5 text-sm text-default">
          <li>
            <span class="text-error">
              All tasks operations require <code>--download-archive</code> to be set in the
              <b>preset</b> or in the <b>command options for yt-dlp</b> for the task to be
              dispatched. If you have selected one of the built in presets it already includes this
              option and no further action is required.
            </span>
          </li>
          <li>
            To avoid downloading all existing content from a channel/playlist, use
            <code>Actions &gt; Archive All</code> to mark existing items as already downloaded.
          </li>
          <li>
            <strong>Custom Handlers:</strong> Leave timer empty for custom handler definitions. The
            handler runs hourly and doesn't require timer.
          </li>
          <li>
            <strong>Generate metadata:</strong> will attempt first to save metadata based on the
            task <code>Download path</code> if not set, it will fallback to the
            <code>Output template</code> with the priority of <code>task</code>,
            <code>preset</code> and then finally to <code>YTP_OUTPUT_TEMPLATE</code>. The final path
            must resolve inside <code>{{ config.app.download_path }}</code
            >.
          </li>
        </ul>
      </template>
    </UAlert>

    <UModal
      v-if="toggleForm"
      :open="toggleForm"
      :title="editorTitle"
      :description="editorDescription"
      :dismissible="!addInProgress"
      :ui="{ content: 'w-full sm:max-w-7xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && closeEditor()"
    >
      <template #body>
        <TaskForm
          :key="formKey"
          :addInProgress="addInProgress"
          :reference="taskRef"
          :task="task as Task"
          @cancel="closeEditor"
          @submit="updateItem"
        />
      </template>
    </UModal>

    <UModal
      v-if="inspectTask"
      :open="Boolean(inspectTask)"
      title="Inspect Task Handler"
      description="Inspect how the current task URL maps to a handler."
      :ui="{ content: 'w-full sm:max-w-4xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && (inspectTask = null)"
    >
      <template #body>
        <TaskInspect :url="inspectTask.url" :preset="inspectTask.preset" />
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import { CronExpressionParser } from 'cron-parser';
import { useConfirm } from '~/composables/useConfirm';
import { useTasks } from '~/composables/useTasks';
import TaskInspect from '~/components/TaskInspect.vue';
import type { ExportedTask, Task } from '~/types/tasks';
import type { WSEP } from '~/types/sockets';
import { sleep } from '~/utils';
import { useSessionCache } from '~/utils/cache';
import type { item_request } from '~/types/item';

const box = useConfirm();
const toast = useNotification();
const config = useConfigStore();
const socket = useSocketStore();
const stateStore = useStateStore();
const { confirmDialog } = useDialog();
const sessionCache = useSessionCache();
const display_style = useStorage<'list' | 'grid' | 'cards'>('tasks_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 1024 });

const tasksComposable = useTasks();
const {
  tasks,
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

const task = ref<Partial<Task>>(createEmptyTask());
const taskRef = ref<number | null>(null);
const toggleForm = ref(false);
const selectedElms = ref<number[]>([]);
const massRun = ref(false);
const massDelete = ref(false);
const inspectTask = ref<Task | null>(null);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);
const CACHE_KEY = 'tasks:handler_support';
const taskHandlerSupport = ref<Record<string, boolean>>(sessionCache.get(CACHE_KEY) || {});

const displayStyle = computed<'list' | 'grid'>(() =>
  display_style.value === 'list' ? 'list' : 'grid',
);

const editorSessionId = ref(0);

const editorTitle = computed(() => {
  return taskRef.value ? `Edit - ${task.value.name}` : 'Add new task';
});

const editorDescription = computed(() => {
  return taskRef.value
    ? 'Update the settings of your automated download task'
    : 'Create an automated download task';
});

const formKey = computed(() => `${taskRef.value ?? 'new'}:${editorSessionId.value}`);

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

const bulkActionGroups = computed(() => [
  [
    {
      label: 'Run Selected',
      icon: 'i-lucide-square-play',
      color: 'primary',
      disabled: !hasSelected.value || massRun.value,
      onSelect: () => void runSelected(),
    },
    {
      label: 'Remove Selected',
      icon: 'i-lucide-trash',
      color: 'error',
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
    if (connected) {
      socket.on('item_status', statusHandler);
    }
  },
  { immediate: true },
);

const toggleFilterPanel = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }

  await nextTick();
  filterInput.value?.focus();
};

const toggleMasterSelection = (): void => {
  if (allSelected.value) {
    selectedElms.value = [];
    return;
  }

  selectedElms.value = [...selectableTaskIds.value];
};

const toggleDisplayStyle = (): void => {
  display_style.value = displayStyle.value === 'list' ? 'grid' : 'list';
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

const reloadContent = async (fromMounted: boolean = false) => {
  try {
    await tasksComposable.loadTasks();

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
  task.value = createEmptyTask();
  taskRef.value = null;

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
    toast.error('No tasks selected.');
    return;
  }

  const { status } = await confirmDialog({
    title: 'Delete Selected Tasks',
    rawHTML:
      `Delete <strong class="text-red-500">${selectedElms.value.length}</strong> task/s?<ul>` +
      selectedElms.value
        .map((id) => {
          const item = tasks.value.find((task) => task.id === id);
          return item ? `<li>${item.id}: ${item.name}</li>` : '';
        })
        .join('') +
      '</ul>',
    confirmText: 'Delete',
    confirmColor: 'error',
  });

  if (true !== status) {
    return;
  }

  const itemsToDelete = tasks.value.filter(
    (item) => item.id && selectedElms.value.includes(item.id),
  );
  if (itemsToDelete.length < 1) {
    toast.error('No tasks found to delete.');
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
  if (!item.id || true !== (await box.confirm(`Delete '${item.name}' task?`))) {
    return;
  }

  await tasksComposable.deleteTask(item.id);
};

const toggleEnabled = async (item: Task) => {
  if (!item.id) {
    toast.error('Task ID is missing');
    return;
  }

  const updated = await tasksComposable.patchTask(item.id, { enabled: !item.enabled });
  if (updated) {
    item.enabled = updated.enabled;
    if (updated.enabled) {
      await checkHandlerSupport(updated);
    }
  }
};

const toggleHandlerEnabled = async (item: Task) => {
  if (!item.id) {
    toast.error('Task ID is missing');
    return;
  }

  const updated = await tasksComposable.patchTask(item.id, {
    handler_enabled: !item.handler_enabled,
  });

  if (updated) {
    item.handler_enabled = updated.handler_enabled;
    if (updated.handler_enabled) {
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
  let createdOrUpdated: Task | Task[] | null = null;

  if (reference) {
    createdOrUpdated = await tasksComposable.updateTask(reference, task as Task);
  } else {
    createdOrUpdated = await tasksComposable.createTask(task);
  }

  if (!createdOrUpdated) {
    return;
  }

  const tasksList = Array.isArray(createdOrUpdated) ? createdOrUpdated : [createdOrUpdated];

  closeEditor();

  if (!reference && true === archive_all) {
    await nextTick();
    await sleep(1);
    toast.info(
      `Archiving existing items for '${tasksList.length}' tasks. This will take a while...`,
    );

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
    return moment(CronExpressionParser.parse(expression).next().toISOString()).fromNow();
  } catch {
    return 'Invalid';
  }
};

const runSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No tasks selected.');
    return;
  }

  const { status } = await confirmDialog({
    rawHTML:
      'Run the following tasks?<ul>' +
      selectedElms.value
        .map((id) => {
          const item = tasks.value.find((task) => task.id === id);
          return item ? `<li>${item.name}</li>` : '';
        })
        .join('') +
      '</ul>',
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
  toast.success('Dispatched selected tasks.');

  setTimeout(async () => {
    await nextTick();
    massRun.value = false;
  }, 500);
};

const runNow = async (item: Task, mass: boolean = false) => {
  if (!item.id) {
    return;
  }

  if (
    !mass &&
    true !== (await box.confirm(`Run '${item.name}' now? it will also run at the scheduled time.`))
  ) {
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
      source_handler: 'Web',
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

  setTimeout(async () => {
    await nextTick();
    if (item.id) {
      clearTaskInProgress(item.id);
    }
  }, 500);
};

async function statusHandler(payload: WSEP['item_status']) {
  const { status, msg } = payload.data || {};

  if ('error' === status) {
    toast.error(msg ?? 'Unknown error');
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
    toast.error('Task ID is missing');
    return;
  }

  try {
    if (true !== by_pass) {
      const { status } = await confirmDialog({
        message: `Mark all '${item.name}' items as downloaded in download archive?`,
      });

      if (true !== status) {
        return;
      }
    }

    setTaskInProgress(item.id);
    await tasksComposable.markTaskItems(item.id);
  } catch (error: any) {
    toast.error(`Failed to archive items. ${error.message || 'Unknown error.'}`);
  } finally {
    clearTaskInProgress(item.id);
  }
};

const unarchiveAll = async (item: Task) => {
  if (!item.id) {
    toast.error('Task ID is missing');
    return;
  }

  try {
    const { status } = await confirmDialog({
      message: `Remove all '${item.name}' items from download archive?`,
    });

    if (true !== status) {
      return;
    }

    setTaskInProgress(item.id);
    await tasksComposable.unmarkTaskItems(item.id);
  } catch (error: any) {
    toast.error(`Failed to remove items from archive. ${error.message || 'Unknown error.'}`);
  } finally {
    if (item.id) {
      clearTaskInProgress(item.id);
    }
  }
};

const generateMeta = async (item: Task) => {
  if (!item.id) {
    toast.error('Task ID is missing');
    return;
  }

  try {
    const { status } = await confirmDialog({
      rawHTML: `
      <p>
        Generate '${item.name}' metadata? you will be notified when it is done.
      </p>
      <p>
        <b>This action will generate:</b>
        <ul>
          <li><strong>tvshow.nfo</strong> - for media center compatibility</li>
          <li><strong>title [id].info.json</strong> - yt-dlp metadata file</li>
          <li>
          <strong>Thumbnails</strong>: poster.jpg, fanart.jpg, thumb.jpg, banner.jpg, icon.jpg, landscape.jpg
          <u>if they are available</u>.
          </li>
        </ul>
      </p>
      <p class="text-red-500">
          <span>Warning</span>: This will overwrite existing metadata files if they exist.
      </p>`,
    });

    if (true !== status) {
      return;
    }

    setTaskInProgress(item.id);
    await tasksComposable.generateTaskMetadata(item.id);
  } catch (error: any) {
    toast.error(`Failed to generate metadata. ${error.message || 'Unknown error.'}`);
  } finally {
    if (item.id) {
      clearTaskInProgress(item.id);
    }
  }
};

const itemActionGroups = (item: Task) => [
  [
    {
      label: 'Run now',
      icon: 'i-lucide-square-play',
      color: 'primary',
      onSelect: () => void runNow(item),
    },
    {
      label: 'Generate metadata',
      icon: 'i-lucide-film',
      onSelect: () => void generateMeta(item),
    },
  ],
  [
    {
      label: 'Inspect Handler',
      icon: 'i-lucide-search',
      onSelect: () => {
        inspectTask.value = item;
      },
    },
  ],
  [
    {
      label: 'Archive All',
      icon: 'i-lucide-box',
      onSelect: () => void archiveAll(item),
    },
    {
      label: 'Unarchive All',
      icon: 'i-lucide-box',
      onSelect: () => void unarchiveAll(item),
    },
  ],
  [
    {
      label: 'Export Task',
      icon: 'i-lucide-file-up',
      color: 'info',
      onSelect: () => void exportItem(item),
    },
  ],
];

onMounted(async () => {
  await reloadContent(true);
});

onBeforeUnmount(() => socket.off('item_status', statusHandler));
</script>
