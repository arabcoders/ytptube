<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-filter" class="size-5 text-toned" />
          <span>Conditions</span>
        </div>

        <p class="text-sm text-toned">
          Run yt-dlp custom match filter on returned info. and apply options.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="showFilter && items.length > 0" class="relative w-full sm:w-80">
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
          v-if="items.length > 0"
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
          @click="openCreate"
        >
          <span v-if="!isMobile">New Condition</span>
        </UButton>

        <UButton
          v-if="items.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          :icon="displayStyle === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          @click="toggleDisplayStyle"
        >
          <span v-if="!isMobile">{{ displayStyle === 'list' ? 'List' : 'Grid' }}</span>
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
          <span v-if="!isMobile">Reload</span>
        </UButton>
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
      v-if="displayStyle === 'list' && filteredItems.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-225 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-full text-left">Condition</th>
              <th class="w-[1%]">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="cond in filteredItems" :key="cond.id" class="hover:bg-muted/20">
              <td class="px-3 py-3 align-middle">
                <div class="space-y-2">
                  <div class="font-semibold text-highlighted">{{ cond.name }}</div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
                    <div class="inline-flex items-center gap-2">
                      <UTooltip
                        :text="`Click to ${cond.enabled !== false ? 'disable' : 'enable'} condition`"
                      >
                        <USwitch
                          :model-value="cond.enabled !== false"
                          :disabled="conditions.addInProgress.value"
                          @update:model-value="() => void toggleEnabled(cond)"
                        />
                      </UTooltip>
                      <span>{{ cond.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                    </div>

                    <span v-if="cond.priority > 0" class="inline-flex items-center gap-1">
                      <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                      <span>Priority: {{ cond.priority }}</span>
                    </span>
                  </div>

                  <div class="space-y-1 text-xs text-toned">
                    <div class="flex items-start gap-2">
                      <UIcon name="i-lucide-filter" class="mt-0.5 size-3.5 shrink-0" />
                      <code class="wrap-break-word">{{ cond.filter }}</code>
                    </div>

                    <div v-if="cond.cli" class="flex items-start gap-2">
                      <UIcon name="i-lucide-terminal" class="mt-0.5 size-3.5 shrink-0" />
                      <code class="wrap-break-word">{{ cond.cli }}</code>
                    </div>

                    <div
                      v-for="([key, value], index) in extrasEntries(cond.extras)"
                      :key="`${cond.id}-${key}-${index}`"
                      class="flex items-start gap-2"
                    >
                      <UIcon name="i-lucide-list" class="mt-0.5 size-3.5 shrink-0" />
                      <code class="wrap-break-word">{{ key }}: {{ value }}</code>
                    </div>
                  </div>
                </div>
              </td>

              <td class="w-[1%] px-3 py-3 align-middle whitespace-nowrap">
                <div class="flex items-center justify-end gap-2">
                  <UButton
                    color="info"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-file-up"
                    @click="exportItem(cond)"
                  >
                    <span v-if="!isMobile">Export</span>
                  </UButton>

                  <UButton
                    color="warning"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="editItem(cond)"
                  >
                    <span v-if="!isMobile">Edit</span>
                  </UButton>

                  <UButton
                    color="error"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void deleteItem(cond)"
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

    <div v-else-if="filteredItems.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <UCard
        v-for="cond in filteredItems"
        :key="cond.id"
        class="flex h-full flex-col border bg-default"
        :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
      >
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1 space-y-2">
              <button
                type="button"
                class="min-w-0 w-full text-left text-sm font-semibold text-highlighted"
                @click="toggleExpand(cond.id, 'name')"
              >
                <span :class="expandClass(cond.id, 'name')">{{ cond.name }}</span>
              </button>

              <div class="flex flex-wrap items-center gap-2 text-xs text-toned">
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
                  <span>Priority {{ cond.priority }}</span>
                </span>
              </div>
            </div>

            <UButton
              color="info"
              variant="ghost"
              size="xs"
              icon="i-lucide-file-up"
              square
              @click="exportItem(cond)"
            />
          </div>
        </template>

        <div class="space-y-2 text-sm text-default">
          <button
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(cond.id, 'filter')"
          >
            <UIcon name="i-lucide-filter" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(cond.id, 'filter')">{{ cond.filter }}</span>
          </button>

          <button
            v-if="cond.cli"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(cond.id, 'cli')"
          >
            <UIcon name="i-lucide-terminal" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(cond.id, 'cli')">{{ cond.cli }}</span>
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

          <button
            v-if="cond.description"
            type="button"
            class="flex w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-left"
            @click="toggleExpand(cond.id, 'description')"
          >
            <UIcon name="i-lucide-message-square-text" class="mt-0.5 size-4 shrink-0 text-toned" />
            <span :class="expandClass(cond.id, 'description')">{{ cond.description }}</span>
          </button>
        </div>

        <div class="mt-auto grid gap-2 pt-2 sm:grid-cols-2">
          <UButton
            color="warning"
            variant="outline"
            icon="i-lucide-pencil"
            class="w-full justify-center"
            @click="editItem(cond)"
          >
            Edit
          </UButton>

          <UButton
            color="error"
            variant="outline"
            icon="i-lucide-trash"
            class="w-full justify-center"
            @click="() => void deleteItem(cond)"
          >
            Delete
          </UButton>
        </div>
      </UCard>
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
      description="There are no custom defined conditions yet. Click the New Condition button to add your first condition."
    />

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
      :title="modalTitle"
      :description="modalDescription"
      :dismissible="!conditions.addInProgress.value"
      :ui="{ content: 'w-full sm:max-w-6xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && closeEditor()"
    >
      <template #body>
        <ConditionForm
          :key="modalKey"
          :addInProgress="conditions.addInProgress.value"
          :reference="itemRef"
          :item="item as Condition"
          @cancel="closeEditor()"
          @submit="updateItem"
        />
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { useConfirm } from '~/composables/useConfirm';
import { useConditions } from '~/composables/useConditions';
import type { Condition } from '~/types/conditions';
import type { APIResponse } from '~/types/responses';
import { cleanObject, copyText, encode } from '~/utils';

type ConditionItemWithUI = Condition & { raw?: boolean };

const box = useConfirm();
const isMobile = useMediaQuery({ maxWidth: 1024 });
const displayStyle = useStorage<'list' | 'grid'>('conditions_display_style', 'grid');
const conditions = useConditions();
const route = useRoute();
const router = useRouter();

const items = conditions.conditions as Ref<ConditionItemWithUI[]>;
const paging = conditions.pagination;
const isLoading = conditions.isLoading;
const page = ref<number>(route.query.page ? parseInt(route.query.page as string, 10) : 1);
const item = ref<Partial<Condition>>({});
const itemRef = ref<number | null | undefined>(null);
const editorOpen = ref(false);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);

const removeKeys = ['raw', 'toggle_description'];
const expandedItems = reactive<Record<number, Set<string>>>({});

const filteredItems = computed<ConditionItemWithUI[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  if (!normalizedQuery) {
    return items.value;
  }

  return items.value.filter((entry) => deepIncludes(entry, normalizedQuery, new WeakSet()));
});

const modalTitle = computed(() =>
  itemRef.value ? `Edit - ${item.value.name}` : 'Add new condition',
);
const modalDescription = computed(
  () => 'Run yt-dlp custom match filter on returned info. and apply options.',
);
const modalKey = computed(
  () => `${itemRef.value ?? 'new'}-${editorOpen.value ? 'open' : 'closed'}`,
);

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

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
  filterInput.value?.focus();
};

const loadContent = async (pageNumber = 1): Promise<void> => {
  page.value = pageNumber;
  await conditions.loadConditions(pageNumber);
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

const toggleExpand = (itemId: number | undefined, field: string): void => {
  if (!itemId) {
    return;
  }

  if (!expandedItems[itemId]) {
    expandedItems[itemId] = new Set();
  }

  if (expandedItems[itemId].has(field)) {
    expandedItems[itemId].delete(field);
  } else {
    expandedItems[itemId].add(field);
  }
};

const isExpanded = (itemId: number | undefined, field: string): boolean => {
  if (!itemId) {
    return false;
  }

  return expandedItems[itemId]?.has(field) ?? false;
};

const expandClass = (itemId: number | undefined, field: string): string => {
  return isExpanded(itemId, field) ? 'whitespace-pre-wrap break-words' : 'truncate';
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
