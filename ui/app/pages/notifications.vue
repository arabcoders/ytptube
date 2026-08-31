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
          v-if="notifications.length > 0"
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
          icon="i-lucide-plus"
          @click="openCreate"
        >
          <span>{{ t('common.add') }}</span>
        </UButton>

        <UButton
          v-if="notifications.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-send"
          :loading="sendingTest"
          :disabled="sendingTest"
          @click="() => void sendTest()"
        >
          <span>{{ t('common.test') }}</span>
        </UButton>

        <UButton
          v-if="notifications.length > 0"
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
          v-if="showFilter && notifications.length > 0"
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

    <div
      v-if="!isLoading && filteredTargets.length > 0"
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

    <div v-if="filteredTargets.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="item in filteredTargets" :key="item.id" class="min-w-0 w-full max-w-full">
        <div class="ytp-card flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden">
          <div class="p-4 pb-3 ytp-border-bottom-soft">
            <div dir="ltr" class="flex min-w-0 items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <div class="flex items-start gap-2">
                  <button
                    type="button"
                    class="min-w-0 flex-1 text-start text-sm font-semibold text-highlighted"
                    @click="toggleExpand(item.id, 'title')"
                  >
                    <span :class="['block', expandClass(item.id, 'title')]">
                      <bdi dir="ltr">
                        {{ item.request.method.toUpperCase() }}({{ ucFirst(item.request.type) }}) @
                        {{ item.name }}
                      </bdi>
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
                  @click="exportItem(item)"
                >
                  <span>{{ t('common.exportItem') }}</span>
                </UButton>

                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    v-model="selectedIds"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item.id"
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
                  :disabled="addInProgress"
                  @click="() => void toggleEnabled(item)"
                >
                  <UIcon
                    name="i-lucide-power"
                    class="size-3.5"
                    :class="item.enabled !== false ? 'text-success' : 'text-error'"
                  />
                  <span>{{
                    item.enabled !== false ? t('common.enabled') : t('common.disabled')
                  }}</span>
                </button>

                <span
                  class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                >
                  <UIcon name="i-lucide-bell-ring" class="size-3.5" />
                  <span>{{
                    item.on.length
                      ? t('notificationsPage.eventsCount', { count: item.on.length })
                      : t('notificationsPage.eventsAll')
                  }}</span>
                </span>

                <span
                  class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                >
                  <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
                  <span>{{
                    item.presets.length
                      ? t('notificationsPage.presetsCount', { count: item.presets.length })
                      : t('notificationsPage.presetsAll')
                  }}</span>
                </span>

                <span
                  v-if="headerKeys(item).length > 0"
                  class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1"
                >
                  <UIcon name="i-lucide-key" class="size-3.5" />
                  <span>{{
                    t('notificationsPage.headersCount', { count: headerKeys(item).length })
                  }}</span>
                </span>
              </div>

              <div class="feature-meta-grid">
                <button
                  type="button"
                  class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-start"
                  @click="toggleExpand(item.id, 'url')"
                >
                  <UIcon name="i-lucide-link" class="mt-0.5 size-4 shrink-0 text-toned" />
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-medium text-toned">
                      {{ t('common.targetUrl') }}
                    </div>
                    <a
                      :href="item.request.url"
                      target="_blank"
                      rel="noreferrer"
                      class="block text-highlighted hover:underline"
                      @click.stop
                    >
                      <span :class="['block', expandClass(item.id, 'url')]" dir="ltr">
                        {{ item.request.url }}
                      </span>
                    </a>
                  </div>
                </button>

                <button
                  v-if="headerKeys(item).length > 0"
                  type="button"
                  class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-start"
                  @click="toggleExpand(item.id, 'headers')"
                >
                  <UIcon name="i-lucide-key" class="mt-0.5 size-4 shrink-0 text-toned" />
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-medium text-toned">
                      {{ t('notificationsPage.headers') }}
                    </div>
                    <span :class="['block font-mono', expandClass(item.id, 'headers')]" dir="ltr">
                      {{ headerKeys(item).join(', ') }}
                    </span>
                  </div>
                </button>

                <button
                  type="button"
                  class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-start"
                  @click="toggleExpand(item.id, 'events')"
                >
                  <UIcon name="i-lucide-bell-ring" class="mt-0.5 size-4 shrink-0 text-toned" />
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-medium text-toned">
                      {{ t('notificationsPage.events') }}
                    </div>
                    <span :class="['block', expandClass(item.id, 'events')]" dir="ltr">{{
                      joinEvents(item.on)
                    }}</span>
                  </div>
                </button>

                <button
                  type="button"
                  class="flex min-w-0 w-full items-start gap-2 rounded-md border border-default bg-muted/20 px-3 py-2 text-start"
                  @click="toggleExpand(item.id, 'presets')"
                >
                  <UIcon
                    name="i-lucide-sliders-horizontal"
                    class="mt-0.5 size-4 shrink-0 text-toned"
                  />
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-medium text-toned">
                      {{ t('common.presets') }}
                    </div>
                    <span :class="['block', expandClass(item.id, 'presets')]">
                      {{ joinPresets(item.presets) }}
                    </span>
                  </div>
                </button>
              </div>
            </div>
          </div>

          <div class="ytp-border-top-soft px-4 py-4">
            <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-pencil"
                class="w-full justify-center"
                @click="editItem(item)"
              >
                {{ t('common.edit') }}
              </UButton>

              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                class="w-full justify-center"
                @click="() => void deleteItem(item)"
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

    <div v-else-if="query && filteredTargets.length < 1" class="space-y-3">
      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        :title="t('common.noResults')"
        :description="t('common.noResultsFor', { query })"
      />
    </div>

    <UEmpty
      v-else-if="!filteredTargets.length"
      icon="i-lucide-bell"
      :title="t('common.noItems')"
      :description="t('common.empty')"
      class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
    />

    <div v-if="filteredTargets.length > 0 && paging?.total_pages > 1" class="flex justify-end">
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
      v-if="!query && filteredTargets.length > 0"
      class="rounded-lg border border-info/30 bg-info/10 p-4 text-sm text-default"
    >
      <ul class="list-disc space-y-2 ps-5 text-sm text-default">
        <li v-html="t('notificationsPage.info1')" />
        <li v-html="t('notificationsPage.info2')" />
        <li v-html="t('notificationsPage.info3')" />
        <li v-html="t('notificationsPage.info4')" />
      </ul>
    </div>

    <UModal
      v-if="editorOpen"
      :open="editorOpen"
      :title="targetRef ? t('common.editTitle', { name: target.name }) : t('common.add')"
      :description="t('notificationsPage.description')"
      :dismissible="!addInProgress"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleEditorOpenChange"
    >
      <template #body>
        <FormSubmitError :message="submission.message.value" @dismiss="submission.clear" />
        <NotificationForm
          :key="modalKey"
          :addInProgress="addInProgress"
          :reference="targetRef"
          :item="target"
          :allowedEvents="allowedEvents"
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
            form="notificationForm"
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
  </main>
</template>

<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui';
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useConfirm } from '~/composables/useConfirm';
import { useNotifications } from '~/composables/useNotifications';
import { copyText, encode, parse_api_error, request, ucFirst } from '~/utils';
import type { ImportedItem } from '~/types';
import type { notification } from '~/types/notification';
import { usePageShell } from '~/composables/usePageShell';
const { t } = useI18n();

const toast = useNotification();
const box = useConfirm();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();
const pageShell = usePageShell('notifications');

const notificationsStore = useNotifications();
const submission = useFormSubmit();
const notifications = notificationsStore.notifications;
const paging = notificationsStore.pagination;
const allowedEvents = notificationsStore.events;
const isLoading = notificationsStore.isLoading;
const addInProgress = notificationsStore.addInProgress;

const page = ref(1);
const targetRef = ref<number | undefined>(undefined);
const target = ref<notification>(defaultState());
const editorOpen = ref(false);
const editorDirty = ref(false);
const editorValid = ref(false);
const sendingTest = ref(false);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<{ inputRef?: { value?: HTMLInputElement | null } } | null>(null);
const selectedIds = ref<number[]>([]);
const massDelete = ref(false);

const modalKey = computed(
  () => `${targetRef.value ?? 'new'}-${editorOpen.value ? 'open' : 'closed'}`,
);

const discardEditor = (): void => {
  editorDirty.value = false;
  editorValid.value = false;
  target.value = defaultState();
  targetRef.value = undefined;
};

const { handleOpenChange: handleEditorOpenChange, requestClose: requestCloseEditor } =
  useDirtyCloseGuard(editorOpen, {
    dirty: editorDirty,
    preferenceKey: 'notifications',
    message: t('common.discardChanges'),
    onDiscard: async () => {
      discardEditor();
    },
  });

const filteredTargets = computed<notification[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  const items = notifications.value as notification[];

  if (!normalizedQuery) {
    return items;
  }

  return items.filter((item) => deepIncludes(item, normalizedQuery, new WeakSet()));
});

const selectableNotificationIds = computed(() =>
  filteredTargets.value.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
);

const allSelected = computed(
  () =>
    selectableNotificationIds.value.length > 0 &&
    selectableNotificationIds.value.every((id) => selectedIds.value.includes(id)),
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

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

watch(
  filteredTargets,
  (items) => {
    const validIds = new Set(
      items.map((item) => item.id).filter((id): id is number => typeof id === 'number'),
    );
    selectedIds.value = selectedIds.value.filter((id) => validIds.has(id));
  },
  { deep: true },
);

function defaultState(): notification {
  return {
    name: '',
    on: [],
    presets: [],
    enabled: true,
    request: { method: 'POST', url: '', type: 'json', headers: [], data_key: 'data' },
  };
}

const toggleFilterPanel = async (): Promise<void> => {
  showFilter.value = !showFilter.value;
  if (!showFilter.value) {
    query.value = '';
    return;
  }

  await nextTick();
  filterInput.value?.inputRef?.value?.focus?.({ preventScroll: true });
};

const loadContent = async (pageNumber = page.value): Promise<void> => {
  page.value = pageNumber;
  await notificationsStore.loadNotifications(pageNumber);
};

const resetEditor = (): void => {
  submission.clear();
  target.value = defaultState();
  targetRef.value = undefined;
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

  selectedIds.value = [...selectableNotificationIds.value];
};

const editItem = (item: notification): void => {
  submission.clear();
  editorDirty.value = false;
  target.value = JSON.parse(JSON.stringify(item)) as notification;
  targetRef.value = item.id ?? undefined;
  editorOpen.value = true;
};

const deleteItem = async (item: notification): Promise<void> => {
  if (true !== (await box.confirm(t('common.deleteNamedConfirm', { name: item.name })))) {
    return;
  }

  if (!item.id) {
    toast.error(t('common.targetNotFound'));
    return;
  }

  await notificationsStore.deleteNotification(item.id);
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
          const item = filteredTargets.value.find((target) => target.id === id);
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

  const itemsToDelete = filteredTargets.value.filter(
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
    await notificationsStore.deleteNotification(item.id);
  }

  selectedIds.value = [];
  massDelete.value = false;
};

const toggleEnabled = async (item: notification): Promise<void> => {
  if (!item.id) {
    toast.error(t('common.targetNotFound'));
    return;
  }

  try {
    await notificationsStore.patchNotification(item.id, { enabled: !item.enabled });
  } catch (error) {
    toast.error(error instanceof Error ? error.message : t('common.unknownError'));
  }
};

const updateItem = async ({
  reference,
  item,
}: {
  reference: number | undefined;
  item: notification;
}): Promise<void> => {
  const result = reference
    ? await submission.run(() => notificationsStore.updateNotification(reference, item))
    : await submission.run(() => notificationsStore.createNotification(item));

  if (result) {
    closeEditor();
  }
};

const joinEvents = (events: string[]): string =>
  !events || events.length < 1 ? t('common.all') : events.map((event) => ucFirst(event)).join(', ');

const joinPresets = (presets: string[]): string =>
  !presets || presets.length < 1 ? t('common.all') : presets.join(', ');

const headerKeys = (item: notification): string[] =>
  item.request?.headers?.map((header) => header.key).filter(Boolean) ?? [];

const sendTest = async (): Promise<void> => {
  if (true !== (await box.confirm(t('common.sendTestNotification')))) {
    return;
  }

  try {
    sendingTest.value = true;
    const response = await request('/api/notifications/test', { method: 'POST' });

    if (!response.ok) {
      const data = await response.json();
      const message = await parse_api_error(data);
      toast.error(
        t('common.failedWithReason', {
          message: t('common.failedTestNotification'),
          reason: message,
        }),
      );
      return;
    }

    toast.success(t('common.testNotificationSent'));
  } catch (error: any) {
    const message = error?.message || t('common.unknownError');
    toast.error(
      t('common.failedWithReason', {
        message: t('common.failedTestNotification'),
        reason: message,
      }),
    );
  } finally {
    sendingTest.value = false;
  }
};

const exportItem = async (item: notification): Promise<void> => {
  const data: notification & ImportedItem = {
    ...JSON.parse(JSON.stringify(item)),
    _type: 'notification',
    _version: '1.0',
  };

  const keys = ['id', 'raw'];
  keys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(data, key)) {
      const { [key]: _, ...rest } = data as Record<string, unknown>;
      Object.assign(data, rest);
    }
  });

  if (data.request?.headers?.length) {
    data.request.headers = data.request.headers.filter(
      (header) => 'authorization' !== header.key.toLowerCase(),
    );
  }

  copyText(encode(data));
};

onMounted(async () => await loadContent(page.value));
</script>
