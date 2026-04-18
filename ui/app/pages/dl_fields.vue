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

      <div class="flex flex-col gap-3 xl:items-end">
        <div class="flex flex-wrap gap-2 xl:justify-end">
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
            <span>New Field</span>
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
            @click="() => void reloadContent()"
          >
            <span>Reload</span>
          </UButton>
        </div>

        <div v-if="showFilter && items.length > 0" class="relative w-full xl:w-80">
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
      </div>
    </div>

    <Pager
      v-if="paging?.total_pages > 1"
      :page="paging.page"
      :last_page="paging.total_pages"
      :isLoading="isLoading"
      @navigate="navigatePage"
    />

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

      <div class="text-xs text-toned">{{ filteredItems.length }} displayed</div>
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
              <th class="w-full text-left">Field</th>
              <th class="w-48 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr
              v-for="field in filteredItems"
              :key="field.id"
              class="transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
            >
              <td class="px-3 py-3 text-center align-middle">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="field.id"
                  />
                </label>
              </td>

              <td class="px-3 py-3 align-middle">
                <div class="space-y-2">
                  <div class="font-semibold text-highlighted">{{ field.name }}</div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>Order: {{ field.order }}</span>
                    </span>

                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-shapes" class="size-3.5" />
                      <span>Type: {{ field.kind }}</span>
                    </span>

                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                    >
                      <UIcon name="i-lucide-terminal" class="size-3.5" />
                      <span>Option: {{ field.field }}</span>
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
                    @click="exportItem(field)"
                  >
                    Export
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="editItem(field)"
                  >
                    Edit
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void deleteItem(field)"
                  >
                    Delete
                  </UButton>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="filteredItems.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="field in filteredItems" :key="field.id" class="min-w-0 w-full max-w-full">
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
                    @click="toggleExpand(field.id, 'title')"
                  >
                    <span :class="['block', expandClass(field.id, 'title')]">{{ field.name }}</span>
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
                  @click="exportItem(field)"
                >
                  <span>Export Field</span>
                </UButton>

                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="field.id"
                  />
                </label>
              </div>
            </div>
          </template>

          <div class="space-y-2 text-sm text-default">
            <div class="flex flex-wrap gap-2 text-xs text-toned *:min-w-32 *:flex-1">
              <span
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                <span>Order: {{ field.order }}</span>
              </span>

              <span
                class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
              >
                <UIcon name="i-lucide-shapes" class="size-3.5" />
                <span>Type: {{ field.kind }}</span>
              </span>
            </div>

            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                type="button"
                :class="[
                  'flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left',
                  !field.description && 'sm:col-span-2',
                ]"
                @click="toggleExpand(field.id, 'field')"
              >
                <UIcon name="i-lucide-terminal" class="mt-0.5 size-4 shrink-0 text-toned" />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">Associated option</div>
                  <span :class="['block', expandClass(field.id, 'field')]">{{ field.field }}</span>
                </div>
              </button>

              <button
                v-if="field.description"
                type="button"
                class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
                @click="toggleExpand(field.id, 'description')"
              >
                <UIcon
                  name="i-lucide-message-square-text"
                  class="mt-0.5 size-4 shrink-0 text-toned"
                />
                <div class="min-w-0 flex-1">
                  <div class="text-xs font-medium text-toned">Description</div>
                  <span :class="['block', expandClass(field.id, 'description')]">
                    {{ field.description }}
                  </span>
                </div>
              </button>
            </div>
          </div>

          <template #footer>
            <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-pencil"
                class="w-full justify-center"
                @click="editItem(field)"
              >
                Edit
              </UButton>

              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                class="w-full justify-center"
                @click="() => void deleteItem(field)"
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

      <UButton color="neutral" variant="outline" size="sm" @click="query = ''">
        Clear filter
      </UButton>
    </div>

    <UAlert
      v-else-if="!filteredItems.length"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No items"
      description="There are no custom defined fields yet. Click the New Field button to add your first field."
    />

    <UModal
      v-if="editorOpen"
      :open="editorOpen"
      :title="modalTitle"
      :description="modalDescription"
      :dismissible="!dlFields.addInProgress.value"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <DLFieldForm
          :key="modalKey"
          :addInProgress="dlFields.addInProgress.value"
          :reference="itemRef"
          :item="item as DLField"
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
import { useDlFields } from '~/composables/useDlFields';
import type { DLField } from '~/types/dl_fields';
import type { APIResponse } from '~/types/responses';
import { copyText, encode } from '~/utils';
import { requirePageShell } from '~/utils/topLevelNavigation';

const box = useConfirm();
const { toggleExpand, expandClass } = useExpandableMeta();
const pageShell = requirePageShell('custom-fields');
const displayStyle = useStorage<'list' | 'grid'>('dl_fields_display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 639 });
const dlFields = useDlFields();
const route = useRoute();
const router = useRouter();
const { confirmDialog } = useDialog();

const items = dlFields.dlFields as Ref<DLField[]>;
const paging = dlFields.pagination;
const isLoading = dlFields.isLoading;
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1);
const item = ref<Partial<DLField>>({});
const itemRef = ref<number | null | undefined>(null);
const editorOpen = ref(false);
const editorDirty = ref(false);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);
const selectedIds = ref<number[]>([]);
const massDelete = ref(false);

const filteredItems = computed<DLField[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  if (!normalizedQuery) {
    return items.value;
  }

  return items.value.filter((entry) => deepIncludes(entry, normalizedQuery, new WeakSet()));
});

const selectableFieldIds = computed(() =>
  filteredItems.value.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectableFieldIds.value.length > 0 &&
    selectableFieldIds.value.every((id) => selectedIds.value.includes(id)),
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

const modalTitle = computed(() => (itemRef.value ? `Edit - ${item.value.name}` : 'Add new field'));
const modalDescription = computed(
  () => 'Custom fields allow you to add new fields to the download form.',
);
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
    message: 'You have unsaved custom field changes. Do you want to discard them?',
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
  const totalPages = dlFields.pagination.value.total_pages;
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
  filterInput.value?.focus();
};

const loadContent = async (pageNumber = 1): Promise<void> => {
  page.value = pageNumber;
  await dlFields.loadDlFields(pageNumber);
  await nextTick();
  await syncPageQuery(pageNumber);
};

const reloadContent = async (): Promise<void> => {
  await loadContent(page.value);
};

const navigatePage = async (newPage: number): Promise<void> => {
  await loadContent(newPage);
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

  selectedIds.value = [...selectableFieldIds.value];
};

const deleteItem = async (field: DLField): Promise<void> => {
  if (true !== (await box.confirm(`Delete '${field.name}'?`))) {
    return;
  }

  await dlFields.deleteDlField(field.id!);
};

const deleteSelected = async (): Promise<void> => {
  if (selectedIds.value.length < 1) {
    return;
  }

  const { status } = await confirmDialog({
    title: 'Delete Selected Fields',
    message:
      `Delete ${selectedIds.value.length} field/s?` +
      '\n\n' +
      selectedIds.value
        .map((id) => {
          const item = filteredItems.value.find((field) => field.id === id);
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
    await dlFields.deleteDlField(item.id);
  }

  selectedIds.value = [];
  massDelete.value = false;
};

const updateItem = async ({
  reference,
  item: updatedItem,
}: {
  reference: number | null | undefined;
  item: DLField;
}): Promise<void> => {
  const callback = (response: APIResponse) => {
    if (response.success) {
      closeEditor();
    }
  };

  if (reference) {
    await dlFields.patchDlField(reference, updatedItem, callback);
  } else {
    await dlFields.createDlField(updatedItem, callback);
  }
};

const editItem = (field: DLField): void => {
  editorDirty.value = false;
  item.value = JSON.parse(JSON.stringify(field)) as DLField;
  itemRef.value = field.id;
  editorOpen.value = true;
};

const exportItem = (field: DLField): void => {
  copyText(
    encode({
      ...Object.fromEntries(
        Object.entries(field).filter(([key, value]) => !!value && 'id' !== key),
      ),
      _type: 'dl_field',
      _version: '1.0',
    }),
  );
};

onMounted(async () => await loadContent(page.value));
</script>
