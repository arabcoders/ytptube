<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="ytp-page-header">
      <div class="ytp-page-heading">
        <span class="ytp-page-icon">
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

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
          v-if="definitions.length > 0"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilterPanel"
        >
          <span>{{ t('common.filter') }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-search"
          @click="
            () => {
              inspect = true;
            }
          "
        >
          <span>{{ t('common.inspect') }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="openCreate"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          class="hidden sm:inline-flex"
          @click="toggleDisplayStyle"
        >
          <span class="hidden sm:inline">{{
            display_style === 'list' ? t('common.list') : t('common.grid')
          }}</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="() => void loadDefinitions(1, 1000)"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>

        <UInput
          v-if="showFilter && definitions.length > 0"
          id="filter"
          ref="filterInput"
          v-model="query"
          type="search"
          :placeholder="t('common.filterDisplayedContent')"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </div>
    </div>

    <UAlert
      v-if="lastError"
      color="error"
      variant="soft"
      icon="i-lucide-circle-alert"
      :title="t('common.error')"
      :description="lastError"
    />

    <div
      v-if="!isLoading && filteredDefinitions.length > 0"
      class="flex flex-wrap items-center justify-between gap-3 ytp-card px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
          @click="toggleMasterSelection"
        >
          {{ allSelected ? t('common.unselect') : t('common.select') }}
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
            {{ t('common.actions') }}
          </UButton>
        </UDropdownMenu>
      </div>
    </div>

    <div
      v-if="contentStyle === 'list' && filteredDefinitions.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden ytp-table-surface"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-255 w-full text-sm">
          <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
            <tr
              class="text-center [&>th]:border-e [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-e-0"
            >
              <th class="w-12">
                <button type="button" class="cursor-pointer" @click="toggleMasterSelection">
                  <UIcon
                    :name="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-start">{{ t('taskDefinitions.definition') }}</th>
              <th class="w-28 whitespace-nowrap">{{ t('common.priority') }}</th>
              <th class="w-36 whitespace-nowrap">{{ t('taskDefinitions.updated') }}</th>
              <th class="w-48 whitespace-nowrap">{{ t('common.actions') }}</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr
              v-for="definition in filteredDefinitions"
              :key="definition.id"
              class="transition-colors hover:bg-elevated/70 [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
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
                    {{ definition.name || t('taskDefinitions.unnamed') }}
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
                      <span>{{
                        definition.enabled ? t('common.enabled') : t('common.disabled')
                      }}</span>
                    </button>

                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-link" class="size-3.5" />
                      <span>{{
                        t('taskDefinitions.patterns', { count: definition.match_url.length })
                      }}</span>
                    </span>
                  </div>
                </div>
              </td>

              <td class="px-3 py-3 text-center align-middle">
                {{ definition.priority }}
              </td>

              <td class="px-3 py-3 text-center align-middle whitespace-nowrap">
                <UTooltip :text="moment(definition.updated_at).format('YYYY-M-DD H:mm Z')">
                  <span
                    class="inline-flex"
                    :date-datetime="moment(definition.updated_at).format('YYYY-M-DD H:mm Z')"
                    v-rtime="definition.updated_at"
                  />
                </UTooltip>
              </td>

              <td class="w-48 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-file-up"
                    @click="() => void exportDefinition(definition)"
                  >
                    {{ t('common.exportItem') }}
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="() => void openEdit(definition)"
                  >
                    <span class="hidden sm:inline">{{ t('common.edit') }}</span>
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void remove(definition)"
                  >
                    <span class="hidden sm:inline">{{ t('common.delete') }}</span>
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
        <div class="ytp-card flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden">
          <div class="p-4 pb-3 ytp-border-bottom-soft">
            <div class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="flex items-start gap-2">
                  <button
                    type="button"
                    class="min-w-0 flex-1 text-start text-sm font-semibold text-highlighted"
                    @click="toggleExpand(definition.id, 'title')"
                  >
                    <span :class="['block', expandClass(definition.id, 'title')]">
                      {{ definition.name || t('taskDefinitions.unnamed') }}
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
                  <span>{{ t('common.exportItem') }}</span>
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
          </div>

          <div class="flex flex-1 flex-col gap-4 p-4 pt-0">
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
                  <span>{{ definition.enabled ? t('common.enabled') : t('common.disabled') }}</span>
                </button>

                <span
                  class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                >
                  <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                  <span>{{ t('common.priority') }}: {{ definition.priority }}</span>
                </span>
              </div>

              <button
                type="button"
                class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-start"
                @click="toggleExpand(definition.id, 'patterns')"
              >
                <UIcon name="i-lucide-link" class="mt-0.5 size-4 shrink-0 text-toned" />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">
                    {{ t('taskDefinitions.urlPatterns') }}
                  </div>
                  <span :class="['block', expandClass(definition.id, 'patterns')]" dir="ltr">
                    {{ definition.match_url.join('\n') }}
                  </span>
                </div>
              </button>
            </div>
          </div>

          <div class="ytp-border-top-soft px-4 py-4">
            <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-pencil"
                class="w-full justify-center"
                @click="() => void openEdit(definition)"
              >
                {{ t('common.edit') }}
              </UButton>

              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                class="w-full justify-center"
                @click="() => void remove(definition)"
              >
                {{ t('common.delete') }}
              </UButton>
            </div>
          </div>
        </div>
      </div>
    </div>

    <UAlert
      v-if="isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('common.loadingData')"
    />

    <div v-else-if="query && filteredDefinitions.length < 1" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        :title="t('common.noResults')"
        :description="t('common.noResultsFor', { query })"
      />
    </div>

    <UAlert
      v-else-if="!definitions.length"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      :title="t('common.noItems')"
      :description="t('common.empty')"
    />

    <UModal
      v-if="isEditorOpen"
      :open="isEditorOpen"
      :title="
        editorMode === 'create'
          ? t('common.add')
          : t('common.editTitle', {
              name: currentSummary?.name || t('taskDefinitions.definition'),
            })
      "
      :description="
        editorLoading ? t('taskDefinitions.editorLoadingDesc') : t('taskDefinitions.editorDesc')
      "
      :dismissible="!editorLoading && !editorSubmitting"
      :ui="{ content: 'w-full sm:max-w-7xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <TaskDefinitionEditor
          ref="definitionEditor"
          :document="workingDefinition"
          :initial-show-import="showImportByDefault"
          :available-definitions="definitions"
          :loading="editorLoading"
          :submitting="editorSubmitting"
          @submit="submitDefinition"
          @dirty-change="(dirty) => (editorDirty = dirty)"
          @valid-change="(value) => (editorValid = value)"
          @import-existing="importExistingDefinition"
        />
      </template>

      <template #footer>
        <div class="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="inline-flex self-start rounded-md border border-default bg-muted/20 p-1">
            <UButton
              type="button"
              size="sm"
              icon="i-lucide-sliders-horizontal"
              color="neutral"
              :variant="definitionEditor?.mode === 'gui' ? 'soft' : 'ghost'"
              :disabled="!definitionEditor?.guiSupported || definitionEditor?.isBusy"
              @click="definitionEditor?.switchMode('gui')"
            >
              {{ t('common.guiTab') }}
            </UButton>

            <UButton
              type="button"
              size="sm"
              icon="i-lucide-code"
              color="neutral"
              :variant="definitionEditor?.mode === 'advanced' ? 'soft' : 'ghost'"
              :disabled="definitionEditor?.isBusy"
              @click="definitionEditor?.switchMode('advanced')"
            >
              {{ t('common.advancedTab') }}
            </UButton>
          </div>

          <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <UButton
              v-if="definitionEditor?.advancedMode"
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-wand-sparkles"
              :disabled="definitionEditor.isBusy"
              class="justify-center"
              @click="definitionEditor.beautify"
            >
              {{ t('common.format') }}
            </UButton>

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-x"
              :disabled="editorLoading || editorSubmitting"
              class="justify-center"
              @click="() => void requestCloseEditor()"
            >
              {{ t('common.cancel') }}
            </UButton>

            <UButton
              type="button"
              color="primary"
              icon="i-lucide-save"
              :loading="editorSubmitting"
              :disabled="definitionEditor?.isBusy || !editorValid"
              class="justify-center"
              @click="definitionEditor?.submit()"
            >
              {{ t('common.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <UModal
      v-if="inspect"
      :open="inspect"
      :title="t('common.inspectHandler')"
      :ui="{ content: 'w-full sm:max-w-4xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && (inspect = false)"
    >
      <template #body>
        <TaskInspect ref="taskInspect" />
      </template>

      <template #footer>
        <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
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
            {{ t('common.inspect') }}
          </UButton>
        </div>
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
import { usePageShell } from '~/composables/usePageShell';
import TaskDefinitionEditor from '~/components/TaskDefinitionEditor.vue';
import TaskInspect from '~/components/TaskInspect.vue';
import type {
  TaskDefinitionDetailed,
  TaskDefinitionDocument,
  TaskDefinitionSummary,
} from '~/types/task_definitions';

const { t } = useI18n();

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

const pageShell = usePageShell('task-definitions');

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
const editorValid = ref(false);
const editorMode = ref<'create' | 'edit'>('create');
const editorLoading = ref(false);
const editorSubmitting = ref(false);
const workingDefinition = ref<TaskDefinitionDocument | null>(null);
const workingId = ref<number | null>(null);
const definitionEditor = ref<InstanceType<typeof TaskDefinitionEditor> | null>(null);
const taskInspect = ref<InstanceType<typeof TaskInspect> | null>(null);
const inspect = ref(false);
const display_style = useStorage<'list' | 'grid'>('task-definitions:display', 'grid');
const isMobile = useMediaQuery({ maxWidth: 639 });

const query = ref('');
const showFilter = ref(false);
const filterInput = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);
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
const contentStyle = computed<'list' | 'grid'>(() =>
  isMobile.value ? 'grid' : display_style.value,
);

const bulkActionGroups = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: t('common.removeSelected'),
      icon: 'i-lucide-trash',
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

const showImportByDefault = computed(
  () => editorMode.value === 'create' && !hideImportByDefault.value,
);

const discardEditor = (): void => {
  editorDirty.value = false;
  editorValid.value = false;
  workingDefinition.value = null;
  workingId.value = null;
  editorLoading.value = false;
  editorSubmitting.value = false;
  hideImportByDefault.value = false;
};

const { handleOpenChange: handleEditorOpenChange, requestClose: requestCloseEditor } =
  useDirtyCloseGuard(isEditorOpen, {
    dirty: editorDirty,
    message: t('common.discardChanges'),
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
  filterInput.value?.inputRef?.value?.focus?.({ preventScroll: true });
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
  editorValid.value = false;
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
  editorValid.value = false;
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
  editorValid.value = false;
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
  editorValid.value = false;
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
    title: t('common.delete'),
    message: t('common.deleteNamedConfirm', { name: summary.name || String(summary.id) }),
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
    title: t('common.deleteSelected'),
    message:
      t('common.deleteCountConfirm', { count: selectedIds.value.length }) +
      '\n\n' +
      selectedIds.value
        .map((id) => {
          const item = filteredDefinitions.value.find((definition) => definition.id === id);
          return item ? `${item.id}: ${item.name || t('taskDefinitions.unnamed')}` : '';
        })
        .filter(Boolean)
        .join('\n'),
    confirmText: t('common.delete'),
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
    await loadDefinitions(1, 1000);
  }
});
</script>
