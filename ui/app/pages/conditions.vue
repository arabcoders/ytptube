<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell">
      <template #actions>
        <UButton
          v-if="items.length > 0"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilterPanel"
        >
          <span>{{ t('common.filter') }}</span>
        </UButton>

        <UButton color="primary" variant="solid" size="sm" icon="i-lucide-plus" @click="openCreate">
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          v-if="items.length > 0"
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
          v-if="showFilter && items.length > 0"
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

    <section :aria-label="t('common.allConditions')" :aria-busy="isLoading" class="space-y-4">
      <div
        v-if="!isLoading && filteredItems.length > 0"
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

      <div v-if="filteredItems.length > 0" class="ytp-card divide-y divide-default">
        <article v-for="cond in filteredItems" :key="cond.id" class="min-w-0 w-full max-w-full">
          <div class="grid gap-4 p-4 sm:p-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.5fr)_auto]">
            <div class="min-w-0">
              <div class="flex min-w-0 items-start justify-between gap-3">
                <div class="min-w-0 flex-1 space-y-2">
                  <h2 class="min-w-0">
                    <button
                      type="button"
                      class="min-w-0 flex-1 text-start text-base font-semibold text-highlighted"
                      @click="toggleExpand(cond.id, 'name')"
                    >
                      <span :class="['block', expandClass(cond.id, 'name')]">{{ cond.name }}</span>
                    </button>
                  </h2>

                  <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-toned">
                    <UButton
                      type="button"
                      color="neutral"
                      variant="outline"
                      size="xs"
                      class="text-start"
                      :disabled="conditions.addInProgress.value"
                      :aria-pressed="cond.enabled !== false"
                      @click="() => void toggleEnabled(cond)"
                    >
                      <UIcon
                        name="i-lucide-power"
                        class="size-3.5"
                        :class="cond.enabled !== false ? 'text-success' : 'text-error'"
                      />
                      <span>{{
                        cond.enabled !== false ? t('common.enabled') : t('common.disabled')
                      }}</span>
                    </UButton>

                    <span v-if="cond.priority > 0" class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>{{ t('presets.priority', { priority: cond.priority }) }}</span>
                    </span>
                  </div>
                </div>

                <div class="flex shrink-0 items-center gap-2">
                  <UCheckbox
                    color="primary"
                    :model-value="cond.id !== undefined && selectedIds.includes(cond.id)"
                    :disabled="cond.id === undefined"
                    :aria-label="`${t('common.select')}: ${cond.name}`"
                    @update:model-value="selectedIds = setSelected(selectedIds, cond.id, $event)"
                  />
                </div>
              </div>
            </div>

            <div class="min-w-0 space-y-4">
              <div class="space-y-2 text-sm text-default">
                <dl class="space-y-2">
                  <div class="min-w-0 space-y-1">
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon name="i-lucide-filter" class="size-3.5 shrink-0" aria-hidden="true" />
                      {{ t('common.filter') }}
                    </dt>
                    <dd class="min-w-0">
                      <button
                        type="button"
                        class="block w-full text-start text-default"
                        @click="toggleExpand(cond.id, 'filter')"
                      >
                        <span :class="['block', expandClass(cond.id, 'filter')]" dir="ltr">{{
                          cond.filter
                        }}</span>
                      </button>
                    </dd>
                  </div>

                  <div v-if="cond.cli" class="min-w-0 space-y-1">
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
                        @click="toggleExpand(cond.id, 'cli')"
                      >
                        <span :class="['block', expandClass(cond.id, 'cli')]" dir="ltr">{{
                          cond.cli
                        }}</span>
                      </button>
                    </dd>
                  </div>

                  <div v-if="cond.description" class="min-w-0 space-y-1">
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
                        @click="toggleExpand(cond.id, 'description')"
                      >
                        <span :class="['block', expandClass(cond.id, 'description')]">{{
                          cond.description
                        }}</span>
                      </button>
                    </dd>
                  </div>

                  <div
                    v-if="extrasEntries(cond.extras).length > 0"
                    class="min-w-0 space-y-1"
                    dir="ltr"
                  >
                    <dt class="flex items-center gap-1.5 text-xs text-muted">
                      <UIcon
                        name="i-lucide-list-plus"
                        class="size-3.5 shrink-0"
                        aria-hidden="true"
                      />
                      {{ t('conditions.extras') }}
                    </dt>
                    <dd class="flex flex-wrap gap-x-4 gap-y-1 text-default">
                      <span
                        v-for="([key, value], index) in extrasEntries(cond.extras)"
                        :key="`${cond.id}-${key}-${index}`"
                        class="min-w-0"
                      >
                        <span class="font-medium text-toned">{{ key }}</span
                        >: {{ key === 'set_cookies' ? t('presets.cookiesConfigured') : value }}
                      </span>
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
                    :aria-label="t('common.editTitle', { name: cond.name })"
                    @click="editItem(cond)"
                  >
                    <span class="hidden sm:inline">{{ t('common.edit') }}</span>
                  </UButton>
                </UTooltip>

                <UDropdownMenu
                  :items="itemActionGroups(cond)"
                  :modal="false"
                  :content="{ align: 'end' }"
                >
                  <UButton
                    color="neutral"
                    variant="ghost"
                    size="sm"
                    icon="i-lucide-ellipsis"
                    square
                    :aria-label="`${t('common.actions')}: ${cond.name}`"
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
        v-else-if="query && filteredItems.length < 1"
        variant="naked"
        size="sm"
        icon="i-lucide-search"
        :title="t('common.noResults')"
        :description="t('common.noResultsFor', { query })"
      />

      <UEmpty
        v-else-if="!filteredItems.length"
        icon="i-lucide-git-branch"
        :title="t('common.noItems')"
        :description="t('common.empty')"
        variant="naked"
        size="sm"
      />

      <div v-if="filteredItems.length > 0 && paging?.total_pages > 1" class="flex justify-end">
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

    <details v-if="filteredItems.length > 0 && !query" class="text-sm">
      <summary class="w-fit cursor-pointer font-medium text-toned">
        {{ t('common.usageNotes') }}
      </summary>
      <ul class="mt-3 list-disc space-y-2 ps-5 text-toned">
        <li v-html="t('conditions.info1')" />
        <li v-html="t('conditions.info2')" />
        <li v-html="t('conditions.info3')" />
        <li v-html="t('conditions.info4')" />
      </ul>
    </details>

    <UModal
      v-if="editorOpen"
      :open="editorOpen"
      :title="itemRef ? t('common.editTitle', { name: item.name || 'Condition' }) : t('common.add')"
      :description="t('conditions.description')"
      :dismissible="!conditions.addInProgress.value"
      :ui="{ content: 'w-full sm:max-w-6xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <FormSubmitError :message="submission.message.value" @dismiss="submission.clear" />
        <ConditionForm
          :key="modalKey"
          :addInProgress="conditions.addInProgress.value"
          :reference="itemRef"
          :item="item as Condition"
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
            :disabled="conditions.addInProgress.value"
            class="justify-center"
            @click="() => void requestCloseEditor()"
          >
            {{ t('common.cancel') }}
          </UButton>

          <UButton
            type="submit"
            form="conditionForm"
            color="primary"
            icon="i-lucide-save"
            :disabled="conditions.addInProgress.value || !editorValid"
            :loading="conditions.addInProgress.value"
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
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useConfirm } from '~/composables/useConfirm';
import { useConditions } from '~/composables/useConditions';
import type { Condition } from '~/types/conditions';
import { cleanObject, copyText, encode } from '~/utils';
import { usePageShell } from '~/composables/usePageShell';
const { t } = useI18n();

type ConditionItemWithUI = Condition & { raw?: boolean };

const box = useConfirm();
const toast = useNotification();
const pageShell = usePageShell('conditions');
const { toggleExpand, expandClass } = useExpandableMeta();
const conditions = useConditions();
const submission = useFormSubmit();
const route = useRoute();
const router = useRouter();
const { confirmDialog } = useDialog();

const items = conditions.conditions as Ref<ConditionItemWithUI[]>;
const paging = conditions.pagination;
const isLoading = conditions.isLoading;
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1);
const item = ref<Partial<Condition>>({});
const itemRef = ref<number | null | undefined>(null);
const editorOpen = ref(false);
const editorDirty = ref(false);
const editorValid = ref(false);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);
const selectedIds = ref<number[]>([]);
const massDelete = ref(false);

const removeKeys = ['raw', 'toggle_description'];

const filteredItems = computed<ConditionItemWithUI[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  if (!normalizedQuery) {
    return items.value;
  }

  return items.value.filter((entry) => deepIncludes(entry, normalizedQuery, new WeakSet()));
});

const selectableConditionIds = computed(() =>
  filteredItems.value.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectableConditionIds.value.length > 0 &&
    selectableConditionIds.value.every((id) => selectedIds.value.includes(id)),
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

const itemActionGroups = (cond: Condition): DropdownMenuItem[][] => [
  [
    {
      label: t('common.exportItem'),
      icon: 'i-lucide-file-up',
      onSelect: () => exportItem(cond),
    },
  ],
  [
    {
      label: t('common.delete'),
      icon: 'i-lucide-trash',
      color: 'error',
      onSelect: () => void deleteItem(cond),
    },
  ],
];

const modalKey = computed(
  () => `${itemRef.value ?? 'new'}-${editorOpen.value ? 'open' : 'closed'}`,
);

const discardEditor = (): void => {
  editorDirty.value = false;
  editorValid.value = false;
  item.value = {};
  itemRef.value = null;
};

const { handleOpenChange: handleEditorOpenChange, requestClose: requestCloseEditor } =
  useDirtyCloseGuard(editorOpen, {
    dirty: editorDirty,
    preferenceKey: 'conditions',
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
  filteredItems,
  (items) => {
    const validIds = new Set(
      items.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
    );
    selectedIds.value = selectedIds.value.filter((id) => validIds.has(id));
  },
  { deep: true },
);

const syncPageQuery = async (pageNumber: number): Promise<void> => {
  const totalPages = conditions.pagination.value.total_pages;
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

const loadContent = async (pageNumber = 1): Promise<void> => {
  page.value = pageNumber;
  await conditions.loadConditions(pageNumber);
  await nextTick();
  await syncPageQuery(pageNumber);
};

const resetEditor = (): void => {
  submission.clear();
  item.value = {};
  itemRef.value = null;
  editorDirty.value = false;
  editorValid.value = false;
};

const closeEditor = (): void => {
  editorOpen.value = false;
  resetEditor();
};

const openCreate = (): void => {
  resetEditor();
  editorOpen.value = true;
};

const toggleMasterSelection = (): void => {
  if (allSelected.value) {
    selectedIds.value = [];
    return;
  }

  selectedIds.value = [...selectableConditionIds.value];
};

const extrasEntries = (extras?: Record<string, unknown>): Array<[string, unknown]> => {
  if (!extras) {
    return [];
  }

  return Object.entries(extras).filter(([, value]) => value !== undefined && value !== '');
};

const deleteItem = async (cond: Condition): Promise<void> => {
  if (true !== (await box.confirm(t('common.deleteNamedConfirm', { name: cond.name })))) {
    return;
  }

  await conditions.deleteCondition(cond.id!);
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
          const item = filteredItems.value.find((cond) => cond.id === id);
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

  const itemsToDelete = filteredItems.value.filter(
    (item) => item.id && selectedIds.value.includes(item.id),
  );
  if (itemsToDelete.length < 1) {
    return;
  }

  massDelete.value = true;

  for (const item of itemsToDelete) {
    if (!item.id) {
      continue;
    }
    await conditions.deleteCondition(item.id);
  }

  selectedIds.value = [];
  massDelete.value = false;
};

const updateItem = async ({
  reference,
  item: updatedItem,
}: {
  reference: number | null | undefined;
  item: Condition;
}): Promise<void> => {
  updatedItem = cleanObject(updatedItem, removeKeys) as Condition;
  const result = reference
    ? await submission.run(() => conditions.patchCondition(reference, updatedItem))
    : await submission.run(() => conditions.createCondition(updatedItem));

  if (result) {
    closeEditor();
  }
};

const editItem = (value: Condition): void => {
  submission.clear();
  editorDirty.value = false;
  item.value = JSON.parse(JSON.stringify(value)) as Condition;
  itemRef.value = value.id;
  editorOpen.value = true;
};

const toggleEnabled = async (cond: Condition): Promise<void> => {
  try {
    await conditions.patchCondition(cond.id!, { enabled: !cond.enabled });
  } catch (error) {
    toast.error(error instanceof Error ? error.message : t('common.unknownError'));
  }
};

const exportItem = (cond: Condition): void => {
  const extras = Object.fromEntries(
    Object.entries(cond.extras || {}).filter(([key]) => key !== 'set_cookies'),
  );
  const exported = Object.fromEntries(
    Object.entries(cond).filter(
      ([key, value]) => !!value && key !== 'extras' && !['id', ...removeKeys].includes(key),
    ),
  );

  if (Object.keys(extras).length > 0) {
    exported.extras = extras;
  }

  copyText(
    encode({
      ...exported,
      _type: 'condition',
      _version: '1.2',
    }),
  );
};

onMounted(async () => await loadContent(page.value));
</script>
