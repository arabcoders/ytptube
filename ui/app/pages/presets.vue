<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell">
      <template #actions>
        <UButton
          v-if="presets.length > 0"
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
          @click="editor.openCreate()"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          v-if="presets.length > 0"
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
          v-if="showFilter && presets.length > 0"
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

    <section :aria-label="t('common.presets')" :aria-busy="isLoading" class="space-y-4">
      <div
        v-if="!isLoading && filteredPresets.length > 0"
        class="flex flex-wrap items-center justify-between gap-3"
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

      <div v-if="filteredPresets.length > 0" class="ytp-card divide-y divide-default">
        <article v-for="item in filteredPresets" :key="item.id" class="min-w-0 w-full max-w-full">
          <div class="grid gap-4 p-4 sm:p-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.5fr)_auto]">
            <div class="min-w-0">
              <div class="flex min-w-0 items-start justify-between gap-3">
                <div class="min-w-0 flex-1 space-y-2">
                  <h2 class="min-w-0">
                    <button
                      type="button"
                      class="min-w-0 flex-1 text-start text-base font-semibold text-highlighted"
                      @click="toggleExpand(item.id, 'title')"
                    >
                      <span :class="['block', expandClass(item.id, 'title')]">{{ item.name }}</span>
                    </button>
                  </h2>

                  <div class="flex flex-wrap items-start gap-x-4 gap-y-2 text-xs text-toned">
                    <span class="inline-flex items-center gap-1.5">
                      <UIcon
                        name="i-lucide-cookie"
                        class="size-3.5"
                        :class="item.cookies ? 'text-success' : ''"
                      />
                      <span>{{
                        item.cookies ? t('presets.cookiesConfigured') : t('presets.cookiesNotSet')
                      }}</span>
                    </span>

                    <span v-if="item.priority > 0" class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>{{ t('presets.priority', { priority: item.priority }) }}</span>
                    </span>
                  </div>
                </div>

                <div class="flex shrink-0 items-center gap-2">
                  <UCheckbox
                    color="primary"
                    :model-value="item.id !== undefined && selectedIds.includes(item.id)"
                    :disabled="item.id === undefined"
                    :aria-label="`${t('common.select')}: ${item.name}`"
                    @update:model-value="selectedIds = setSelected(selectedIds, item.id, $event)"
                  />
                </div>
              </div>
            </div>

            <div class="min-w-0 space-y-4">
              <div class="space-y-2 text-sm text-default">
                <dl
                  v-if="item.folder || item.template || item.cli || item.description"
                  class="grid min-w-0 gap-x-6 gap-y-3 sm:grid-cols-2"
                >
                  <div v-if="item.folder" class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-folder-output"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.downloadPath') }}
                    </dt>
                    <dd class="min-w-0">
                      <button
                        type="button"
                        class="block w-full text-start text-default"
                        @click="toggleExpand(item.id, 'folder')"
                      >
                        <span :class="['block', expandClass(item.id, 'folder')]" dir="ltr">{{
                          calcPath(item.folder)
                        }}</span>
                      </button>
                    </dd>
                  </div>

                  <div v-if="item.template" class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-file-code-2"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.outputTemplate') }}
                    </dt>
                    <dd class="min-w-0">
                      <button
                        type="button"
                        class="block w-full text-start text-default"
                        @click="toggleExpand(item.id, 'template')"
                      >
                        <span :class="['block', expandClass(item.id, 'template')]" dir="ltr">{{
                          item.template
                        }}</span>
                      </button>
                    </dd>
                  </div>

                  <div v-if="item.cli" class="min-w-0 space-y-1 sm:col-span-2">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-terminal"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.cliOptions') }}
                    </dt>
                    <dd class="min-w-0">
                      <button
                        type="button"
                        class="block w-full text-start text-default"
                        @click="toggleExpand(item.id, 'cli')"
                      >
                        <span :class="['block', expandClass(item.id, 'cli')]" dir="ltr">{{
                          item.cli
                        }}</span>
                      </button>
                    </dd>
                  </div>

                  <div v-if="item.description" class="min-w-0 space-y-1 sm:col-span-2">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-message-square-text"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('common.description') }}
                    </dt>
                    <dd class="min-w-0">
                      <button
                        type="button"
                        class="block w-full text-start text-default"
                        @click="toggleExpand(item.id, 'description')"
                      >
                        <span :class="['block', expandClass(item.id, 'description')]">{{
                          item.description
                        }}</span>
                      </button>
                    </dd>
                  </div>
                </dl>
              </div>
            </div>

            <div class="flex justify-end self-start">
              <div class="flex shrink-0 items-center gap-1.5">
                <UTooltip :text="t('common.edit')">
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="sm"
                    icon="i-lucide-pencil"
                    :aria-label="t('common.editTitle', { name: item.name })"
                    @click="editor.openEdit(item)"
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
                    :aria-label="`${t('common.actions')}: ${item.name}`"
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
        v-else-if="query && filteredPresets.length < 1"
        size="sm"
        icon="i-lucide-search"
        :title="t('common.noResults')"
        :description="t('common.noResultsFor', { query })"
      />

      <UEmpty
        v-else-if="!filteredPresets.length"
        icon="i-lucide-sliders-horizontal"
        :title="t('common.noItems')"
        :description="t('common.empty')"
        size="sm"
      />

      <div
        v-if="filteredPresets.length > 0 && !query && paging?.total_pages > 1"
        class="flex justify-end"
      >
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
    </section>

    <details v-if="!query && presets.length > 0" class="text-sm">
      <summary class="w-fit cursor-pointer font-medium text-toned">
        {{ t('common.usageNotes') }}
      </summary>
      <ul class="mt-3 list-disc space-y-2 ps-5 text-toned">
        <li>{{ t('presets.info1') }}</li>
      </ul>
    </details>

    <UModal
      v-if="editor.isOpen.value"
      :open="editor.isOpen.value"
      :title="editor.modalTitle.value"
      :description="editor.modalDescription.value"
      :dismissible="!editor.addInProgress.value"
      :ui="{ content: 'w-full sm:max-w-6xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => void editor.handleOpenChange(open)"
    >
      <template #body>
        <FormSubmitError :message="editor.submitError.value" @dismiss="editor.clearSubmitError" />
        <PresetForm
          :key="editor.modalKey.value"
          :addInProgress="editor.addInProgress.value"
          :reference="editor.reference.value"
          :preset="editor.preset.value"
          @dirty-change="(dirty) => (editor.dirty.value = dirty)"
          @valid-change="(value) => (editorValid = value)"
          @submit="editor.submit"
        />
      </template>

      <template #footer>
        <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <UButton
            type="button"
            color="neutral"
            variant="outline"
            icon="i-lucide-x"
            :disabled="editor.addInProgress.value"
            class="justify-center"
            @click="() => void editor.requestClose()"
          >
            {{ t('common.cancel') }}
          </UButton>

          <UButton
            type="submit"
            form="presetForm"
            color="primary"
            icon="i-lucide-save"
            :disabled="editor.addInProgress.value || !editorValid"
            :loading="editor.addInProgress.value"
            class="justify-center"
          >
            {{ t('common.save') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import PageHeader from '~/components/PageHeader.vue';
import { setSelected } from '~/utils/selection';
import type { DropdownMenuItem } from '@nuxt/ui';
import type { Preset } from '~/types/presets';
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useConfirm } from '~/composables/useConfirm';
import { usePageShell } from '~/composables/usePageShell';
const { t } = useI18n();

type PresetWithUI = Preset & { raw?: boolean; toggle_description?: boolean };

const presetsStore = usePresets();
const config = useYtpConfig();
const box = useConfirm();
const editor = usePresetEditor();
const editorValid = ref(false);
const pageShell = usePageShell('presets');
const route = useRoute();
const router = useRouter();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();

const query = ref('');
const showFilter = ref(false);
const filterInput = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);
const selectedIds = ref<number[]>([]);
const massDelete = ref(false);
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1);

const presets = computed(() => presetsStore.presets.value as PresetWithUI[]);
const paging = presetsStore.pagination;
const isLoading = presetsStore.isLoading;

const filteredPresets = computed<PresetWithUI[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  if (!normalizedQuery) {
    return presets.value;
  }

  return presets.value.filter((item) => deepIncludes(item, normalizedQuery, new WeakSet()));
});

const selectablePresetIds = computed(() =>
  filteredPresets.value.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectablePresetIds.value.length > 0 &&
    selectablePresetIds.value.every((id) => selectedIds.value.includes(id)),
);

const hasSelected = computed(() => selectedIds.value.length > 0);

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

const itemActionGroups = (item: Preset): DropdownMenuItem[][] => [
  [
    {
      label: t('common.exportItem'),
      icon: 'i-lucide-file-up',
      onSelect: () => exportItem(item),
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

const syncPageQuery = async (pageNumber: number): Promise<void> => {
  const totalPages = paging.value.total_pages;
  const nextQuery = { ...route.query };

  if (totalPages > 1) {
    nextQuery.page = String(pageNumber);
  } else {
    delete nextQuery.page;
  }

  await router.replace({ query: nextQuery });
};

watch(editor.isOpen, (value) => {
  if (!value) {
    editorValid.value = false;
  }
});

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

watch(
  filteredPresets,
  (items) => {
    const validIds = new Set(
      items.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
    );
    selectedIds.value = selectedIds.value.filter((id) => validIds.has(id));
  },
  { deep: true },
);

const toggleFilterPanel = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }

  await nextTick();
  filterInput.value?.inputRef?.value?.focus?.({ preventScroll: true });
};

const loadContent = async (pageNumber = 1): Promise<void> => {
  page.value = pageNumber;
  await presetsStore.loadPresets(pageNumber, undefined, { excludeDefaults: true });
  await nextTick();
  await syncPageQuery(pageNumber);
};

const toggleMasterSelection = (): void => {
  if (allSelected.value) {
    selectedIds.value = [];
    return;
  }

  selectedIds.value = [...selectablePresetIds.value];
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
          const item = filteredPresets.value.find((preset) => preset.id === id);
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

  const itemsToDelete = filteredPresets.value.filter(
    (item) => item.id && selectedIds.value.includes(item.id),
  );
  if (itemsToDelete.length < 1) {
    return;
  }

  massDelete.value = true;

  try {
    for (const item of itemsToDelete) {
      if (!item.id) {
        continue;
      }

      await presetsStore.deletePreset(item.id);
    }
  } finally {
    selectedIds.value = [];
    massDelete.value = false;
  }

  await loadContent(page.value);
};

const deleteItem = async (item: Preset): Promise<void> => {
  if (true !== (await box.confirm(t('common.deleteNamedConfirm', { name: item.name })))) {
    return;
  }

  if (item.id) {
    await presetsStore.deletePreset(item.id);
  }
};

const exportItem = (item: Preset): void => {
  const excludedKeys = ['id', 'default', 'raw', 'cookies', 'toggle_description'];
  const userData = Object.fromEntries(
    Object.entries(JSON.parse(JSON.stringify(item))).filter(
      ([key, value]) => !excludedKeys.includes(key) && value,
    ),
  );

  userData['_type'] = 'preset';
  userData['_version'] = '2.6';

  copyText(encode(userData));
};

const calcPath = (path?: string): string => {
  const location = config.app.download_path || '/downloads';
  return path ? location + '/' + sTrim(path, '/') : location;
};

onMounted(async () => await loadContent(page.value));
</script>
