<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <PageHeader v-bind="pageShell">
      <template v-if="canManage" #actions>
        <UButton
          v-if="items.length"
          color="neutral"
          :variant="showFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter"
        >
          <span>{{ t('common.filter') }}</span>
        </UButton>
        <UButton
          color="primary"
          variant="solid"
          size="sm"
          icon="i-lucide-plus"
          :disabled="busy || loading"
          @click="openEditor()"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>
        <UButton
          v-if="items.length || error"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="loading"
          :disabled="loading || busy"
          @click="() => load()"
        >
          <span>{{ t('common.refresh') }}</span>
        </UButton>
        <UInput
          v-if="showFilter && items.length"
          ref="filterInput"
          v-model="query"
          type="search"
          :placeholder="t('common.filterDisplayedContent')"
          :aria-label="t('common.filterDisplayedContent')"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </template>
    </PageHeader>

    <UAlert v-if="!canManage" color="warning" variant="soft" :title="t('errors.UNAUTHORIZED')" />
    <section v-else :aria-label="t('toolbox.title')" :aria-busy="loading" class="space-y-4">
      <div
        v-if="!loading && filtered.length > 0"
        class="flex flex-wrap items-center justify-between gap-3"
      >
        <div class="flex flex-wrap items-center gap-2">
          <UButton
            color="neutral"
            variant="outline"
            size="sm"
            :icon="allSelected ? 'i-lucide-square' : 'i-lucide-square-check-big'"
            :disabled="busy || loading"
            @click="selected = allSelected ? [] : filtered.map((item) => item.id)"
          >
            {{ allSelected ? t('common.unselect') : t('common.select') }}
          </UButton>
          <UBadge v-if="selected.length" color="error" variant="soft" size="sm">
            {{ selected.length }}
          </UBadge>
          <UDropdownMenu :items="bulkActions" :modal="false">
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-list"
              trailing-icon="i-lucide-chevron-down"
              :disabled="busy || loading"
            >
              {{ t('common.actions') }}
            </UButton>
          </UDropdownMenu>
        </div>

        <UPagination
          v-if="paging && paging.total_pages > 1"
          :page="paging.page"
          :total="paging.total"
          :items-per-page="paging.per_page"
          :disabled="busy || loading"
          show-edges
          :sibling-count="0"
          size="sm"
          @update:page="load"
        />
      </div>

      <div v-if="filtered.length > 0" class="ytp-card divide-y divide-default">
        <article v-for="item in filtered" :key="item.id" class="min-w-0 w-full max-w-full">
          <div class="grid gap-4 p-4 sm:p-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.5fr)_auto]">
            <div class="min-w-0">
              <div class="flex min-w-0 items-start justify-between gap-3">
                <div class="min-w-0 flex-1 space-y-2">
                  <h2 class="min-w-0">
                    <button
                      type="button"
                      class="min-w-0 flex-1 text-start text-base font-semibold text-highlighted"
                      :aria-expanded="isExpanded(item.id, 'title')"
                      @click="toggleExpand(item.id, 'title')"
                    >
                      <span :class="['block', expandClass(item.id, 'title')]">{{ item.name }}</span>
                    </button>
                  </h2>
                </div>
                <div class="flex shrink-0 items-center gap-2">
                  <UCheckbox
                    color="primary"
                    :model-value="selected.includes(item.id)"
                    :aria-label="`${t('common.select')}: ${item.name}`"
                    :disabled="busy || loading"
                    @update:model-value="selected = setSelected(selected, item.id, $event)"
                  />
                </div>
              </div>
            </div>

            <div class="min-w-0 space-y-4">
              <div class="space-y-2 text-sm text-default">
                <dl v-if="item.description" class="grid min-w-0 gap-x-6 gap-y-3 sm:grid-cols-2">
                  <div class="min-w-0 space-y-1 sm:col-span-2">
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
                        :aria-expanded="isExpanded(item.id, 'description')"
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
                    :disabled="busy || loading"
                    @click="openEditor(item)"
                  >
                    <span>{{ t('common.edit') }}</span>
                  </UButton>
                </UTooltip>
                <UDropdownMenu
                  :items="itemActions(item)"
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
                    :disabled="busy || loading"
                  />
                </UDropdownMenu>
              </div>
            </div>
          </div>
        </article>
      </div>

      <UAlert v-if="error" color="error" variant="soft" :title="error" />
      <UAlert
        v-if="loading"
        color="info"
        variant="soft"
        icon="i-lucide-loader-circle"
        :title="t('common.loading')"
        :ui="{ icon: 'animate-spin' }"
      />
      <UEmpty
        v-else-if="query && items.length && !filtered.length"
        size="sm"
        icon="i-lucide-search"
        :title="t('common.noResults')"
        :description="t('common.noResultsFor', { query })"
      />
      <UEmpty
        v-else-if="!error && !items.length"
        icon="i-lucide-wrench"
        :title="t('common.noItems')"
        :description="t('common.empty')"
        size="sm"
      />

      <div
        v-if="filtered.length > 0 && !query && paging && paging.total_pages > 1"
        class="flex justify-end"
      >
        <UPagination
          :page="paging.page"
          :total="paging.total"
          :items-per-page="paging.per_page"
          :disabled="busy || loading"
          show-edges
          :sibling-count="0"
          @update:page="load"
          size="sm"
        />
      </div>

      <UModal
        v-if="editorOpen"
        :open="editorOpen"
        :title="editorTitle"
        :description="editorDescription"
        :dismissible="!submitting && !editorLoading"
        :ui="{ content: 'w-full sm:max-w-6xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
        @update:open="closeEditor"
      >
        <template #body>
          <FormSubmitError :message="submission.message.value" @dismiss="submission.clear" />
          <UAlert
            v-if="editorLoading"
            color="info"
            variant="soft"
            icon="i-lucide-loader-circle"
            :title="t('common.loading')"
            :ui="{ icon: 'animate-spin' }"
          />
          <ToolboxDefinitionForm
            v-else-if="!editorItem || definition"
            :definition="definition"
            :submitting="submitting"
            :errors="fieldErrors"
            @dirty-change="dirty = $event"
            @valid-change="valid = $event"
            @submit="saveDefinition"
          />
        </template>

        <template #footer>
          <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-x"
              :disabled="submitting || editorLoading"
              class="justify-center"
              @click="closeEditor(false)"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              type="submit"
              form="toolboxDefinitionForm"
              color="primary"
              icon="i-lucide-save"
              :disabled="!valid || submitting"
              :loading="submitting"
              class="justify-center"
            >
              {{ t('common.save') }}
            </UButton>
          </div>
        </template>
      </UModal>
    </section>
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import { useAuth } from '~/composables/useAuth';
import { useDialog } from '~/composables/useDialog';
import { usePageShell } from '~/composables/usePageShell';
import { useToolboxDefinitions } from '~/composables/useToolboxDefinitions';
import type { Pagination } from '~/types/responses';
import type {
  ToolboxDefinition,
  ToolboxDefinitionPayload,
  ToolboxDefinitionSummary,
} from '~/types/toolbox';
import { copyText, formatPageTitle, to_api_error } from '~/utils';
import { setSelected } from '~/utils/selection';
import { exportToolboxDefinition } from '~/utils/toolboxDefinitions';

const { t } = useI18n();
const pageShell = usePageShell('toolbox');
const { status } = useAuth();
const canManage = computed(() => status.value?.disabled === false && status.value.authenticated);
const notification = useNotification();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass, isExpanded } = useExpandableMeta();
const { list, get, save, remove } = useToolboxDefinitions();
const items = ref<ToolboxDefinitionSummary[]>([]);
const paging = ref<Pagination | null>(null);
const error = ref('');
const loading = ref(false);
const busy = ref(false);
const selected = ref<number[]>([]);
const showFilter = ref(false);
const query = ref('');
const filterInput = useTemplateRef<{ inputRef?: HTMLInputElement }>('filterInput');
const toggleFilter = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }
  await nextTick();
  filterInput.value?.inputRef?.focus({ preventScroll: true });
};
const filtered = computed(() => {
  const search = query.value.trim().toLocaleLowerCase();
  if (!search) return items.value;
  return items.value.filter((item) =>
    [item.name, item.description].some((text) => text.toLocaleLowerCase().includes(search)),
  );
});
const allSelected = computed(
  () =>
    filtered.value.length > 0 && filtered.value.every((item) => selected.value.includes(item.id)),
);
watch(filtered, (items) => {
  const visible = new Set(items.map((item) => item.id));
  selected.value = selected.value.filter((id) => visible.has(id));
});

const submission = useFormSubmit();
const fieldErrors = computed(() => {
  const detail = submission.error.value?.payload?.detail;
  if (!Array.isArray(detail)) return {};
  return Object.fromEntries(
    detail.flatMap(({ loc, msg }) => (loc?.length === 1 && msg ? [[String(loc[0]), msg]] : [])),
  );
});
const editorOpen = ref(false);
const editorItem = ref<ToolboxDefinitionSummary>();
const definition = ref<ToolboxDefinition | null>(null);
const editorLoading = ref(false);
const submitting = ref(false);
const dirty = ref(false);
const valid = ref(false);
const editorTitle = computed(() =>
  editorItem.value ? t('common.editTitle', { name: editorItem.value.name }) : t('common.add'),
);
const editorDescription = computed(() => {
  if (editorLoading.value) return t('common.loadingData');
  return t(editorItem.value ? 'common.updateDescription' : 'common.createDescription');
});
const guard = useDirtyCloseGuard(editorOpen, { dirty, preferenceKey: 'toolbox-definitions' });
let disposed = false;
onScopeDispose(() => {
  disposed = true;
});

const closeEditor = (value: boolean): void => {
  if (!value && !submitting.value && !editorLoading.value) void guard.requestClose();
};

watch(editorOpen, (open) => {
  if (open) return;
  submission.clear();
  definition.value = null;
  editorItem.value = undefined;
  dirty.value = false;
  valid.value = false;
});

const load = async (page = paging.value?.page ?? 1): Promise<void> => {
  if (loading.value || disposed) return;
  loading.value = true;
  error.value = '';
  try {
    const result = await list(page);
    if (disposed) return;
    items.value = result.items;
    paging.value = result.pagination;
  } catch (reason) {
    if (!disposed) error.value = to_api_error(reason).message;
  } finally {
    loading.value = false;
  }
};

const openEditor = async (item?: ToolboxDefinitionSummary): Promise<void> => {
  if (busy.value || editorOpen.value) return;
  editorItem.value = item;
  editorLoading.value = Boolean(item);
  editorOpen.value = true;
  if (!item) return;

  try {
    const data = await get(item.id);
    if (!disposed) definition.value = data;
  } catch (reason) {
    if (!disposed) submission.setError(reason);
  } finally {
    editorLoading.value = false;
  }
};

const saveDefinition = async (draft: ToolboxDefinitionPayload): Promise<void> => {
  if (submitting.value) return;
  submitting.value = true;
  const editingId = editorItem.value?.id;
  const editing = editingId !== undefined;
  try {
    const saved = await submission.run(() => save(draft, editingId));
    if (!saved) return;
    if (!disposed) {
      editorOpen.value = false;
      notification.success(
        t(editing ? 'common.crudUpdated' : 'common.crudCreated', {
          type: t('common.operation'),
          name: saved.name,
        }),
      );
    }
    await load(editing ? paging.value?.page : 1);
  } finally {
    submitting.value = false;
  }
};

const deleteItems = async (targets: ToolboxDefinitionSummary[], bulk = false): Promise<void> => {
  if (busy.value || !targets.length) return;
  busy.value = true;
  try {
    const result = await confirmDialog({
      title: t(bulk ? 'common.deleteSelected' : 'common.delete'),
      message: bulk
        ? `${t('common.deleteCountConfirm', { count: targets.length })}\n\n${targets
            .map(({ id, name }) => `${id}: ${name}`)
            .join('\n')}`
        : t('common.deleteNamedConfirm', { name: targets[0]?.name }),
      confirmText: t('common.delete'),
      confirmColor: 'error',
    });
    if (!result.status || disposed) return;

    let removed = 0;
    for (const { id } of targets) {
      if (disposed) break;
      try {
        await remove(id);
        removed++;
        selected.value = selected.value.filter((value) => value !== id);
      } catch (reason) {
        if (!disposed) notification.error(to_api_error(reason).message);
      }
    }

    if (removed) {
      if (!disposed) notification.success(t('common.crudDeleted', { type: t('common.operation') }));
      const page = paging.value;
      const last = page ? Math.max(1, Math.ceil((page.total - removed) / page.per_page)) : 1;
      await load(Math.min(page?.page ?? 1, last));
    }
  } finally {
    busy.value = false;
  }
};

const exportItem = async (item: ToolboxDefinitionSummary): Promise<void> => {
  if (busy.value) return;
  busy.value = true;
  try {
    const detailed = await get(item.id);
    if (disposed) return;
    const exported = exportToolboxDefinition(detailed);
    if (!exported) return;
    copyText(exported);
  } catch (reason) {
    if (!disposed) notification.error(to_api_error(reason).message);
  } finally {
    busy.value = false;
  }
};

const bulkActions = computed<DropdownMenuItem[][]>(() => [
  [
    {
      label: t('common.removeSelected'),
      icon: 'i-lucide-trash',
      disabled: !selected.value.length,
      onSelect: () =>
        void deleteItems(
          filtered.value.filter((item) => selected.value.includes(item.id)),
          true,
        ),
    },
  ],
]);

const itemActions = (item: ToolboxDefinitionSummary): DropdownMenuItem[][] => [
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
      onSelect: () => void deleteItems([item]),
    },
  ],
];

useHead(() => ({ title: formatPageTitle(t('toolbox.title')) }));
watch(
  canManage,
  (allowed) => {
    if (allowed) void load();
  },
  { immediate: true },
);
</script>
