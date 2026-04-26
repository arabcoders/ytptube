<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div class="flex min-w-0 items-center gap-3">
        <span
          class="inline-flex size-11 shrink-0 items-center justify-center rounded-md border border-default bg-elevated/70 text-primary"
        >
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div
            class="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-toned"
          >
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex min-w-0 flex-wrap items-center gap-2 xl:justify-end">
        <UButton
          v-if="items.length > 0"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilterPanel"
        >
          <span>Filter</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="openCreate"
        >
          <span>New Condition</span>
        </UButton>

        <UButton
          v-if="items.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          :icon="displayStyle === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          class="hidden sm:inline-flex"
          @click="toggleDisplayStyle"
        >
          <span class="hidden sm:inline">{{ displayStyle === 'list' ? 'List' : 'Grid' }}</span>
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
          <span>Reload</span>
        </UButton>

        <UInput
          v-if="showFilter && items.length > 0"
          id="filter"
          ref="filterInput"
          v-model="query"
          type="search"
          placeholder="Filter displayed content"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </div>
    </div>

    <div
      v-if="!isLoading && filteredItems.length > 0"
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
      v-if="contentStyle === 'list' && filteredItems.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-235 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr
              class="text-center [&>th]:border-r [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-r-0"
            >
              <th class="w-12">
                <button type="button" class="cursor-pointer" @click="toggleMasterSelection">
                  <UIcon
                    :name="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-left">Condition</th>
              <th class="w-48 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr
              v-for="cond in filteredItems"
              :key="cond.id"
              class="transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
            >
              <td class="px-3 py-3 text-center align-middle">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="cond.id"
                  />
                </label>
              </td>

              <td class="px-3 py-3 align-middle">
                <div class="space-y-2">
                  <div class="font-semibold text-highlighted">{{ cond.name }}</div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
                    <button
                      type="button"
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 transition hover:border-primary hover:text-default"
                      :disabled="conditions.addInProgress.value"
                      @click="() => void toggleEnabled(cond)"
                    >
                      <UIcon
                        name="i-lucide-power"
                        class="size-3.5"
                        :class="cond.enabled !== false ? 'text-success' : 'text-error'"
                      />
                      <span>{{ cond.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                    </button>

                    <span
                      v-if="cond.priority > 0"
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>Priority: {{ cond.priority }}</span>
                    </span>
                  </div>
                </div>
              </td>

              <td class="w-48 px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-file-up"
                    @click="exportItem(cond)"
                  >
                    <span class="hidden sm:inline">Export</span>
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="editItem(cond)"
                  >
                    <span class="hidden sm:inline">Edit</span>
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void deleteItem(cond)"
                  >
                    <span class="hidden sm:inline">Delete</span>
                  </UButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="filteredItems.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="cond in filteredItems" :key="cond.id" class="min-w-0 w-full max-w-full">
        <UCard
          class="flex h-full min-w-0 w-full max-w-full flex-col border bg-default"
          :ui="{
            header: 'p-4 pb-3',
            body: 'flex flex-1 flex-col gap-4 p-4 pt-0',
            footer: 'border-t border-default px-4 py-4',
          }"
        >
          <template #header>
            <div class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="flex items-start gap-2">
                  <button
                    type="button"
                    class="min-w-0 flex-1 text-left text-sm font-semibold text-highlighted"
                    @click="toggleExpand(cond.id, 'name')"
                  >
                    <span :class="['block', expandClass(cond.id, 'name')]">{{ cond.name }}</span>
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
                  @click="exportItem(cond)"
                >
                  <span>Export Condition</span>
                </UButton>

                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="cond.id"
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
                :disabled="conditions.addInProgress.value"
                @click="() => void toggleEnabled(cond)"
              >
                <UIcon
                  name="i-lucide-power"
                  class="size-3.5"
                  :class="cond.enabled !== false ? 'text-success' : 'text-error'"
                />
                <span>{{ cond.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
              </button>

              <span
                v-if="cond.priority > 0"
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                <span>Priority: {{ cond.priority }}</span>
              </span>
            </div>

            <div class="feature-meta-grid">
              <button
                type="button"
                class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
                @click="toggleExpand(cond.id, 'filter')"
              >
                <UIcon name="i-lucide-filter" class="mt-0.5 size-4 shrink-0 text-toned" />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">Filter</div>
                  <span :class="['block', expandClass(cond.id, 'filter')]">{{ cond.filter }}</span>
                </div>
              </button>

              <button
                v-if="cond.cli"
                type="button"
                class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
                @click="toggleExpand(cond.id, 'cli')"
              >
                <UIcon name="i-lucide-terminal" class="mt-0.5 size-4 shrink-0 text-toned" />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">CLI options</div>
                  <span :class="['block', expandClass(cond.id, 'cli')]">{{ cond.cli }}</span>
                </div>
              </button>
            </div>

            <button
              v-if="cond.description"
              type="button"
              class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
              @click="toggleExpand(cond.id, 'description')"
            >
              <UIcon name="i-lucide-align-left" class="mt-0.5 size-4 shrink-0 text-toned" />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium text-toned">Description</div>
                <span :class="['block', expandClass(cond.id, 'description')]">{{
                  cond.description
                }}</span>
              </div>
            </button>

            <div
              v-if="extrasEntries(cond.extras).length > 0"
              class="rounded-md border border-default bg-muted/20 px-3 py-2"
            >
              <div class="mb-2 flex items-center gap-2 text-toned">
                <UIcon name="i-lucide-list" class="size-4" />
                <span class="text-sm font-medium">Extras</span>
              </div>

              <div class="flex flex-wrap gap-2">
                <UBadge
                  v-for="([key, value], index) in extrasEntries(cond.extras)"
                  :key="`${cond.id}-${key}-${index}`"
                  color="info"
                  variant="soft"
                  size="sm"
                >
                  <span class="font-semibold">{{ key }}</span
                  >: {{ value }}
                </UBadge>
              </div>
            </div>
          </div>

          <template #footer>
            <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-pencil"
                class="w-full justify-center"
                @click="editItem(cond)"
              >
                Edit
              </UButton>

              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                class="w-full justify-center"
                @click="() => void deleteItem(cond)"
              >
                Delete
              </UButton>
            </div>
          </template>
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

    <div v-else-if="query && filteredItems.length < 1" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        title="No Results"
        :description="`No results found for the query: ${query}. Please try a different search term.`"
      />
    </div>

    <UAlert
      v-else-if="!filteredItems.length"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No items"
      description="There are no custom defined conditions yet. Click the New Condition button to add your first condition."
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

    <div
      v-if="filteredItems.length > 0 && !query"
      class="rounded-lg border border-info/30 bg-info/10 p-4 text-sm text-default"
    >
      <ul class="list-disc space-y-2 pl-5 text-sm text-default">
        <li>
          Filtering is based on yt-dlp's <code>--match-filter</code> logic. Any expression that
          works with yt-dlp will also work here, including the same boolean operators. We added
          extended support for the <code>OR</code> ( <code>||</code> ) operator, which yt-dlp does
          not natively support. This allows you to combine multiple conditions more flexibly.
        </li>
        <li>
          The primary use case for this feature is to apply custom cli arguments to specific
          returned info.
        </li>
        <li>
          For example, i follow specific channel that sometimes region lock some videos, by using
          the following filter i am able to bypass it
          <code>availability = 'needs_auth' &amp; channel_id = 'channel_id'</code>. and set proxy
          for that specific video, while leaving the rest of the videos to be downloaded normally.
        </li>
        <li>
          The data which the filter is applied on is the same data that yt-dlp returns, simply,
          click on the information button, and check the data to craft your filter. You will get
          instant feedback if the filter matches or not.
        </li>
      </ul>
    </div>

    <UModal
      v-if="editorOpen"
      :open="editorOpen"
      :title="itemRef ? `Edit - ${item.name || 'Condition'}` : 'Add new condition'"
      description="Run yt-dlp custom match filter on returned info. and apply options."
      :dismissible="!conditions.addInProgress.value"
      :ui="{ content: 'w-full sm:max-w-6xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <ConditionForm
          :key="modalKey"
          :addInProgress="conditions.addInProgress.value"
          :reference="itemRef"
          :item="item as Condition"
          @cancel="() => void requestCloseEditor()"
          @dirty-change="(dirty) => (editorDirty = dirty)"
          @submit="updateItem"
        />
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import { useStorage } from '@vueuse/core';
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useConfirm } from '~/composables/useConfirm';
import { useConditions } from '~/composables/useConditions';
import type { Condition } from '~/types/conditions';
import type { APIResponse } from '~/types/responses';
import { cleanObject, copyText, encode } from '~/utils';
import { requirePageShell } from '~/utils/topLevelNavigation';

type ConditionItemWithUI = Condition & { raw?: boolean };

const box = useConfirm();
const pageShell = requirePageShell('conditions');
const displayStyle = useStorage<'list' | 'grid'>('conditions_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 639 });
const { toggleExpand, expandClass } = useExpandableMeta();
const conditions = useConditions();
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
const contentStyle = computed<'list' | 'grid'>(() =>
  isMobile.value ? 'grid' : displayStyle.value,
);

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

const modalKey = computed(
  () => `${itemRef.value ?? 'new'}-${editorOpen.value ? 'open' : 'closed'}`,
);

const discardEditor = (): void => {
  editorDirty.value = false;
  item.value = {};
  itemRef.value = null;
};

const { handleOpenChange: handleEditorOpenChange, requestClose: requestCloseEditor } =
  useDirtyCloseGuard(editorOpen, {
    dirty: editorDirty,
    message: 'You have unsaved condition changes. Do you want to discard them?',
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
  item.value = {};
  itemRef.value = null;
  editorDirty.value = false;
};

const closeEditor = (): void => {
  editorOpen.value = false;
  resetEditor();
};

const openCreate = (): void => {
  resetEditor();
  editorOpen.value = true;
};

const toggleDisplayStyle = (): void => {
  displayStyle.value = displayStyle.value === 'list' ? 'grid' : 'list';
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
  if (true !== (await box.confirm(`Delete '${cond.name}'?`))) {
    return;
  }

  await conditions.deleteCondition(cond.id!);
};

const deleteSelected = async (): Promise<void> => {
  if (selectedIds.value.length < 1) {
    return;
  }

  const { status } = await confirmDialog({
    title: 'Delete Selected Conditions',
    message:
      `Delete ${selectedIds.value.length} condition/s?` +
      '\n\n' +
      selectedIds.value
        .map((id) => {
          const item = filteredItems.value.find((cond) => cond.id === id);
          return item ? `${item.id}: ${item.name}` : '';
        })
        .filter(Boolean)
        .join('\n'),
    confirmText: 'Delete',
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
  const callback = (response: APIResponse) => {
    if (response.success) {
      closeEditor();
    }
  };

  if (reference) {
    await conditions.patchCondition(reference, updatedItem, callback);
  } else {
    await conditions.createCondition(updatedItem, callback);
  }
};

const editItem = (value: Condition): void => {
  editorDirty.value = false;
  item.value = JSON.parse(JSON.stringify(value)) as Condition;
  itemRef.value = value.id;
  editorOpen.value = true;
};

const toggleEnabled = async (cond: Condition): Promise<void> => {
  await conditions.patchCondition(cond.id!, { enabled: !cond.enabled });
};

const exportItem = (cond: Condition): void => {
  copyText(
    encode({
      ...Object.fromEntries(
        Object.entries(cond).filter(
          ([key, value]) => !!value && !['id', ...removeKeys].includes(key),
        ),
      ),
      _type: 'condition',
      _version: '1.2',
    }),
  );
};

onMounted(async () => await loadContent(page.value));
</script>
