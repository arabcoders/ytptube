<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-workflow" class="size-5 text-toned" />
          <span>Task Definitions</span>
        </div>

        <p class="text-sm text-toned">
          Create definitions to turn any website into a downloadable feed of links.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="showFilter && definitions.length > 0" class="relative w-full sm:w-80">
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
          v-if="definitions.length > 0"
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
          icon="i-lucide-search"
          @click="inspect = true"
        >
          <span v-if="!isMobile">Inspect</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="openCreate"
        >
          <span v-if="!isMobile">New Definition</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          @click="toggleDisplayStyle"
        >
          <span v-if="!isMobile">{{ display_style === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UButton
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

    <UAlert
      v-if="lastError"
      color="error"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="Error"
      :description="lastError"
    />

    <div
      v-if="!isLoading && filteredDefinitions.length > 0"
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

        <UBadge v-if="selectedIds.length > 0" color="error" variant="soft" size="sm">
          {{ selectedIds.length }}
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

      <div class="text-xs text-toned">{{ filteredDefinitions.length }} displayed</div>
    </div>

    <div
      v-if="display_style === 'list' && filteredDefinitions.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-245 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-12">
                <button type="button" class="cursor-pointer" @click="toggleMasterSelection">
                  <UIcon
                    :name="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-left">Definition</th>
              <th class="w-28 whitespace-nowrap">Priority</th>
              <th class="w-36 whitespace-nowrap">Updated</th>
              <th class="w-44 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr
              v-for="definition in filteredDefinitions"
              :key="definition.id"
              class="hover:bg-muted/20"
            >
              <td class="px-3 py-3 text-center align-middle">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="definition.id"
                  />
                </label>
              </td>

              <td class="px-3 py-3 align-middle">
                <div class="space-y-1">
                  <div class="font-semibold text-highlighted">
                    {{ definition.name || '(Unnamed definition)' }}
                  </div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
                    <button
                      type="button"
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 transition hover:border-primary hover:text-default"
                      @click="() => void toggle(definition)"
                    >
                      <UIcon
                        name="i-lucide-power"
                        class="size-3.5"
                        :class="definition.enabled ? 'text-success' : 'text-error'"
                      />
                      <span>{{ definition.enabled ? 'Enabled' : 'Disabled' }}</span>
                    </button>

                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-link" class="size-3.5" />
                      <span>Patterns: {{ definition.match_url.length }} match/s</span>
                    </span>
                  </div>
                </div>
              </td>

              <td class="px-3 py-3 text-center align-middle">{{ definition.priority }}</td>

              <td class="px-3 py-3 text-center align-middle whitespace-nowrap">
                <UTooltip :text="moment(definition.updated_at).format('YYYY-M-DD H:mm Z')">
                  <span
                    class="inline-flex"
                    :date-datetime="moment(definition.updated_at).format('YYYY-M-DD H:mm Z')"
                    v-rtime="definition.updated_at"
                  />
                </UTooltip>
              </td>

              <td class="w-44 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-file-up"
                    @click="() => void exportDefinition(definition)"
                  >
                    <span v-if="!isMobile">Export</span>
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="() => void openEdit(definition)"
                  >
                    <span v-if="!isMobile">Edit</span>
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void remove(definition)"
                  >
                    <span v-if="!isMobile">Delete</span>
                  </UButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      v-else-if="filteredDefinitions.length > 0"
      class="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
    >
      <div
        v-for="definition in filteredDefinitions"
        :key="definition.id"
        class="min-w-0 w-full max-w-full"
      >
        <UCard
          class="flex h-full min-w-0 w-full max-w-full flex-col border bg-default"
          :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
        >
          <template #header>
            <div class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="flex items-start gap-2">
                  <button
                    type="button"
                    class="min-w-0 flex-1 text-left text-sm font-semibold text-highlighted"
                    @click="toggleExpand(definition.id, 'title')"
                  >
                    <span :class="['block', expandClass(definition.id, 'title')]">
                      {{ definition.name || '(Unnamed)' }}
                    </span>
                  </button>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-2">
                <UButton
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  icon="i-lucide-file-up"
                  square
                  @click="() => void exportDefinition(definition)"
                >
                  <span class="hidden sm:inline">Export Definition</span>
                </UButton>

                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="definition.id"
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
                @click="() => void toggle(definition)"
              >
                <UIcon
                  name="i-lucide-power"
                  class="size-3.5"
                  :class="definition.enabled ? 'text-success' : 'text-error'"
                />
                <span>{{ definition.enabled ? 'Enabled' : 'Disabled' }}</span>
              </button>

              <span
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                <span>Priority: {{ definition.priority }}</span>
              </span>
            </div>

            <button
              type="button"
              class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
              @click="toggleExpand(definition.id, 'patterns')"
            >
              <UIcon name="i-lucide-link" class="mt-0.5 size-4 shrink-0 text-toned" />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-toned">URL patterns</div>
                <span :class="['block', expandClass(definition.id, 'patterns')]">
                  {{ definition.match_url.join('\n') }}
                </span>
              </div>
            </button>
          </div>

          <div class="mt-auto flex flex-wrap gap-2 pt-2 *:min-w-32 *:flex-1">
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-pencil"
              class="w-full justify-center"
              @click="() => void openEdit(definition)"
            >
              Edit
            </UButton>

            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-trash"
              class="w-full justify-center"
              @click="() => void remove(definition)"
            >
              Delete
            </UButton>
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

    <div v-else-if="query && filteredDefinitions.length < 1" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        title="No Results"
        :description="`No results found for the query: ${query}. Please try a different search term.`"
      />

      <UButton color="neutral" variant="outline" size="sm" @click="query = ''"
        >Clear filter</UButton
      >
    </div>

    <UAlert
      v-else-if="!definitions.length"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No definitions"
      description="There are no task definitions. Click the New Definition button to create your first task definition."
    />

    <UModal
      v-if="isEditorOpen"
      :open="isEditorOpen"
      :title="editorTitle"
      :description="editorDescription"
      :dismissible="!editorLoading && !editorSubmitting"
      :ui="{ content: 'w-full sm:max-w-7xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <TaskDefinitionEditor
          :document="workingDefinition"
          :initial-show-import="showImportByDefault"
          :available-definitions="definitions"
          :loading="editorLoading"
          :submitting="editorSubmitting"
          @submit="submitDefinition"
          @cancel="() => void requestCloseEditor()"
          @dirty-change="(dirty) => (editorDirty = dirty)"
          @import-existing="importExistingDefinition"
        />
      </template>
    </UModal>

    <UModal
      v-if="inspect"
      :open="inspect"
      title="Inspect Task Handler"
      description="Enter the URL of the resource you want to inspect."
      :ui="{ content: 'w-full sm:max-w-4xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && (inspect = false)"
    >
      <template #body>
        <TaskInspect />
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import moment from 'moment';
import { computed, onMounted, ref, watch } from 'vue';
import { useStorage } from '@vueuse/core';

import { useExpandableMeta } from '~/composables/useExpandableMeta';
import useTaskDefinitionsComposable from '~/composables/useTaskDefinitions';
import { useDialog } from '~/composables/useDialog';
import { useMediaQuery } from '~/composables/useMediaQuery';
import { copyText, encode } from '~/utils';

import type {
  TaskDefinitionDetailed,
  TaskDefinitionDocument,
  TaskDefinitionSummary,
} from '~/types/task_definitions';

const DEFAULT_DEFINITION: TaskDefinitionDocument = {
  name: 'New Definition',
  priority: 0,
  enabled: true,
  match_url: ['https://example.com/*'],
  definition: {
    parse: {
      items: {
        type: 'css',
        selector: 'body',
        fields: {
          link: { type: 'css', expression: 'a', attribute: 'href' },
          title: { type: 'css', expression: 'a', attribute: 'text' },
        },
      },
    },
  },
};

const isMobile = useMediaQuery({ maxWidth: 1024 });
const { toggleExpand, expandClass } = useExpandableMeta();

const taskDefs = useTaskDefinitionsComposable();
const definitionsRef = taskDefs.definitions;
const isLoading = taskDefs.isLoading;
const lastError = taskDefs.lastError;
const loadDefinitions = taskDefs.loadDefinitions;
const getDefinition = taskDefs.getDefinition;
const createDefinition = taskDefs.createDefinition;
const updateDefinition = taskDefs.updateDefinition;
const deleteDefinition = taskDefs.deleteDefinition;
const toggleEnabled = taskDefs.toggleEnabled;

const definitions = computed<TaskDefinitionSummary[]>(() => [...definitionsRef.value]);

const { confirmDialog } = useDialog();

const isEditorOpen = ref(false);
const editorDirty = ref(false);
const editorMode = ref<'create' | 'edit'>('create');
const editorLoading = ref(false);
const editorSubmitting = ref(false);
const workingDefinition = ref<TaskDefinitionDocument | null>(null);
const workingId = ref<number | null>(null);
const inspect = ref(false);
const display_style = useStorage<'list' | 'grid'>('task-definitions:display', 'grid');

const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);
const hideImportByDefault = ref(false);
const selectedIds = ref<number[]>([]);
const massDelete = ref(false);

const filteredDefinitions = computed<TaskDefinitionSummary[]>(() => {
  const normalizedQuery = query.value.trim().toLowerCase();
  if (!normalizedQuery) {
    return definitions.value;
  }

  return definitions.value.filter((definition) => {
    const haystack = [
      definition.name,
      definition.priority,
      definition.enabled ? 'enabled' : 'disabled',
      ...definition.match_url,
    ]
      .join(' ')
      .toLowerCase();

    return haystack.includes(normalizedQuery);
  });
});

const selectableDefinitionIds = computed(() =>
  filteredDefinitions.value
    .map((item) => item.id)
    .filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectableDefinitionIds.value.length > 0 &&
    selectableDefinitionIds.value.every((id) => selectedIds.value.includes(id)),
);

const hasSelected = computed(() => selectedIds.value.length > 0);

const bulkActionGroups = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: 'Remove Selected',
      icon: 'i-lucide-trash',
      color: 'error',
      disabled: !hasSelected.value || massDelete.value,
      onSelect: () => void deleteSelected(),
    },
  ],
]);

const currentSummary = computed<TaskDefinitionSummary | undefined>(() => {
  if (editorMode.value !== 'edit' || !workingId.value) {
    return undefined;
  }

  return definitions.value.find((item) => item.id === workingId.value);
});

const editorTitle = computed(() => {
  return editorMode.value === 'create'
    ? 'Create Task Definition'
    : `Edit - ${currentSummary.value?.name || 'Task Definition'}`;
});

const editorDescription = computed(() => {
  if (editorLoading.value) {
    return 'Loading full definition before editing.';
  }

  return 'Use the GUI editor when it fits, or switch to advanced JSON for full control.';
});

const showImportByDefault = computed(
  () => editorMode.value === 'create' && !hideImportByDefault.value,
);

const discardEditor = (): void => {
  editorDirty.value = false;
  workingDefinition.value = null;
  workingId.value = null;
  editorLoading.value = false;
  editorSubmitting.value = false;
  hideImportByDefault.value = false;
};

const { handleOpenChange: handleEditorOpenChange, requestClose: requestCloseEditor } =
  useDirtyCloseGuard(isEditorOpen, {
    dirty: editorDirty,
    message: 'You have unsaved task definition changes. Do you want to discard them?',
    onDiscard: async () => {
      discardEditor();
    },
  });

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

watch(
  filteredDefinitions,
  (items) => {
    const validIds = new Set(
      items.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
    );
    selectedIds.value = selectedIds.value.filter((id) => validIds.has(id));
  },
  { deep: true },
);

const cloneDocument = (document: TaskDefinitionDocument): TaskDefinitionDocument => {
  return JSON.parse(JSON.stringify(document)) as TaskDefinitionDocument;
};

const toggleFilterPanel = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }

  await nextTick();
  filterInput.value?.focus();
};

const reloadContent = async (): Promise<void> => {
  await loadDefinitions(1, 1000);
};

const toggleDisplayStyle = (): void => {
  display_style.value = display_style.value === 'list' ? 'grid' : 'list';
};

const toggleMasterSelection = (): void => {
  if (allSelected.value) {
    selectedIds.value = [];
    return;
  }

  selectedIds.value = [...selectableDefinitionIds.value];
};

const openCreate = (): void => {
  editorDirty.value = false;
  editorMode.value = 'create';
  workingId.value = null;
  workingDefinition.value = cloneDocument(DEFAULT_DEFINITION);
  editorLoading.value = false;
  editorSubmitting.value = false;
  hideImportByDefault.value = false;
  isEditorOpen.value = true;
};

const openEdit = async (summary: TaskDefinitionSummary): Promise<void> => {
  editorDirty.value = false;
  editorMode.value = 'edit';
  workingId.value = summary.id;
  workingDefinition.value = null;
  editorLoading.value = true;
  editorSubmitting.value = false;
  hideImportByDefault.value = true;
  isEditorOpen.value = true;

  const detailed: TaskDefinitionDetailed | null = await getDefinition(summary.id);
  if (!detailed) {
    closeEditor();
    return;
  }

  workingDefinition.value = {
    name: detailed.name,
    priority: detailed.priority,
    enabled: detailed.enabled,
    match_url: [...detailed.match_url],
    definition: JSON.parse(JSON.stringify(detailed.definition)),
  };
  editorLoading.value = false;
};

const importExistingDefinition = async (id: number): Promise<void> => {
  const detailed = await getDefinition(id);
  if (!detailed) {
    return;
  }

  editorDirty.value = false;
  editorMode.value = 'create';
  workingId.value = null;
  workingDefinition.value = {
    name: detailed.name,
    priority: detailed.priority,
    enabled: detailed.enabled,
    match_url: [...detailed.match_url],
    definition: JSON.parse(JSON.stringify(detailed.definition)),
  };
  hideImportByDefault.value = true;
  editorLoading.value = false;
  isEditorOpen.value = true;
};

const closeEditor = (): void => {
  if (editorSubmitting.value) {
    return;
  }

  editorDirty.value = false;
  isEditorOpen.value = false;
  workingDefinition.value = null;
  workingId.value = null;
  editorLoading.value = false;
  editorSubmitting.value = false;
  hideImportByDefault.value = false;
};

const submitDefinition = async (definition: TaskDefinitionDocument): Promise<void> => {
  let shouldClose = false;
  editorSubmitting.value = true;

  try {
    if (editorMode.value === 'create') {
      const created = await createDefinition(definition);
      if (created) {
        shouldClose = true;
      }
    } else if (workingId.value) {
      const updated = await updateDefinition(workingId.value, definition);
      if (updated) {
        shouldClose = true;
      }
    }
  } finally {
    editorSubmitting.value = false;
  }

  if (shouldClose) {
    closeEditor();
  }
};

const remove = async (summary: TaskDefinitionSummary): Promise<void> => {
  const result = await confirmDialog({
    title: 'Delete Task Definition',
    message: `Are you sure you want to delete "${summary.name || summary.id}"?`,
    confirmColor: 'error',
  });

  if (!result.status) {
    return;
  }

  await deleteDefinition(summary.id);
};

const deleteSelected = async (): Promise<void> => {
  if (selectedIds.value.length < 1) {
    return;
  }

  const { status } = await confirmDialog({
    title: 'Delete Selected Task Definitions',
    rawHTML:
      `Delete <strong class="text-red-500">${selectedIds.value.length}</strong> task definition/s?<ul>` +
      selectedIds.value
        .map((id) => {
          const item = filteredDefinitions.value.find((definition) => definition.id === id);
          return item ? `<li>${item.id}: ${item.name || '(Unnamed definition)'}</li>` : '';
        })
        .join('') +
      '</ul>',
    confirmText: 'Delete',
    confirmColor: 'error',
  });

  if (true !== status) {
    return;
  }

  const itemsToDelete = filteredDefinitions.value.filter(
    (item) => item.id && selectedIds.value.includes(item.id),
  );
  if (itemsToDelete.length < 1) {
    return;
  }

  massDelete.value = true;

  for (const item of itemsToDelete) {
    await deleteDefinition(item.id);
  }

  selectedIds.value = [];
  massDelete.value = false;
};

const toggle = async (summary: TaskDefinitionSummary): Promise<void> => {
  await toggleEnabled(summary.id, !summary.enabled);
};

const exportDefinition = async (summary: TaskDefinitionSummary): Promise<void> => {
  const detailed = await getDefinition(summary.id);
  if (!detailed) {
    return;
  }

  copyText(
    encode({
      _type: 'task_definition',
      _version: '2.0',
      name: detailed.name,
      priority: detailed.priority,
      enabled: detailed.enabled,
      match_url: detailed.match_url,
      definition: detailed.definition,
    }),
  );
};

onMounted(async () => {
  if (!definitions.value.length) {
    await reloadContent();
  }
});
</script>
