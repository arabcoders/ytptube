<template>
  <main class="w-full min-w-0 max-w-full space-y-4">
    <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-lg font-semibold text-highlighted">
          <UIcon name="i-lucide-bell" class="size-5 text-toned" />
          <span>Notifications</span>
        </div>

        <p class="text-sm text-toned">
          Send notifications to your webhooks based on specified events or presets.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <div v-if="showFilter && notifications.length > 0" class="relative w-full sm:w-80">
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
          v-if="notifications.length > 0"
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
          <span v-if="!isMobile">New Notification</span>
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
          <span v-if="!isMobile">Send Test</span>
        </UButton>

        <UButton
          v-if="notifications.length > 0"
          color="neutral"
          variant="outline"
          size="sm"
          :icon="displayStyle === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          @click="toggleDisplayStyle"
        >
          <span v-if="!isMobile">{{ displayStyle === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UButton
          v-if="notifications.length > 0"
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
      v-if="displayStyle === 'list' && filteredTargets.length > 0"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-225 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-full text-left">Targets</th>
              <th class="w-[1%]">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="item in filteredTargets" :key="item.id" class="hover:bg-muted/20">
              <td class="px-3 py-3 align-middle">
                <div class="space-y-2">
                  <div class="min-w-0 text-sm font-semibold text-highlighted">
                    {{ item.request.method.toUpperCase() }}({{ ucFirst(item.request.type) }}) @
                    <a
                      :href="item.request.url"
                      target="_blank"
                      rel="noreferrer"
                      class="break-all text-primary hover:underline"
                    >
                      {{ item.name }}
                    </a>
                  </div>

                  <div class="flex flex-wrap items-center gap-3 text-xs text-toned">
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
                      <span>{{ item.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                    </button>

                    <span class="inline-flex items-center gap-1">
                      <UIcon name="i-lucide-bell-ring" class="size-3.5" />
                      <span>On: {{ joinEvents(item.on) }}</span>
                    </span>

                    <span class="inline-flex items-center gap-1">
                      <UIcon name="i-lucide-sliders-horizontal" class="size-3.5" />
                      <span>Presets: {{ joinPresets(item.presets) }}</span>
                    </span>

                    <span v-if="headerKeys(item).length > 0" class="inline-flex items-center gap-1">
                      <UIcon name="i-lucide-key" class="size-3.5" />
                      <span>Headers: {{ headerKeys(item).join(', ') }}</span>
                    </span>
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
                    @click="exportItem(item)"
                  >
                    <span v-if="!isMobile">Export</span>
                  </UButton>

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
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="filteredTargets.length > 0" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <UCard
        v-for="item in filteredTargets"
        :key="item.id"
        class="flex h-full flex-col border bg-default"
        :ui="{ header: 'p-4 pb-3', body: 'flex flex-1 flex-col gap-4 p-4 pt-0' }"
      >
        <template #header>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1 space-y-2">
              <span class="text-sm font-semibold text-highlighted">
                {{ item.request.method.toUpperCase() }}({{ ucFirst(item.request.type) }})
              </span>
              @
              <a
                :href="item.request.url"
                target="_blank"
                rel="noreferrer"
                class="text-sm text-primary hover:underline"
              >
                {{ item.name }}
              </a>

              <div class="flex flex-wrap items-center gap-2 text-xs text-toned">
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
                  <span>{{ item.enabled !== false ? 'Enabled' : 'Disabled' }}</span>
                </button>
              </div>
            </div>

            <UButton
              color="info"
              variant="ghost"
              size="xs"
              icon="i-lucide-file-up"
              square
              @click="exportItem(item)"
            />
          </div>
        </template>

        <div class="space-y-2 text-sm text-default">
          <div class="rounded-md border border-default bg-muted/20 px-3 py-2">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-bell-ring" class="mt-0.5 size-4 shrink-0 text-toned" />
              <span class="wrap-break-word">On: {{ joinEvents(item.on) }}</span>
            </div>
          </div>

          <div class="rounded-md border border-default bg-muted/20 px-3 py-2">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-sliders-horizontal" class="mt-0.5 size-4 shrink-0 text-toned" />
              <span class="wrap-break-word">Presets: {{ joinPresets(item.presets) }}</span>
            </div>
          </div>

          <div
            v-if="headerKeys(item).length > 0"
            class="rounded-md border border-default bg-muted/20 px-3 py-2"
          >
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-key" class="mt-0.5 size-4 shrink-0 text-toned" />
              <span class="wrap-break-word">Headers: {{ headerKeys(item).join(', ') }}</span>
            </div>
          </div>
        </div>

        <div class="mt-auto grid gap-2 pt-2 sm:grid-cols-2">
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

    <div v-else-if="query && filteredTargets.length < 1" class="space-y-3">
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
      v-else-if="!filteredTargets.length"
      color="warning"
      variant="soft"
      icon="i-lucide-circle-alert"
      title="No targets"
      description="No notification targets found. Click on the New Notification button to add your first notification target."
    />

    <div
      v-if="!query && filteredTargets.length > 0"
      class="rounded-lg border border-info/30 bg-info/10 p-4 text-sm text-default"
    >
      <ul class="list-disc space-y-2 pl-5 text-sm text-default">
        <li>
          When you export notification target, We remove <code>Authorization</code> header key by
          default, However this might not be enough to remove credentials from the exported data.
          it's your responsibility to ensure that the exported data does not contain any sensitive
          information for sharing.
        </li>
        <li>
          When you set the request type as <code>Form</code>, the event data will be JSON encoded
          and sent as <code>...&amp;data_key=json_string</code>, only the <code>data</code> field
          will be JSON encoded. The other keys <code>id</code>, <code>event</code> and
          <code>created_at</code> will be sent as they are.
        </li>
        <li>
          We also send two special headers <code>X-Event-ID</code> and <code>X-Event</code> with the
          request.
        </li>
        <li>
          If you have selected specific presets or events, this will take priority, For example, if
          you limited the target to <code>default</code> preset and selected
          <code>ALL</code> events, only events that reference the <code>default</code> preset will
          be sent to that target. Like wise, if you have limited both events and presets, then ONLY
          events that satisfy both conditions will be sent to that target. Only the
          <code>test</code> events can bypass these conditions.
        </li>
      </ul>
    </div>

    <UModal
      v-if="editorOpen"
      :open="editorOpen"
      :title="modalTitle"
      :description="modalDescription"
      :dismissible="!addInProgress"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && closeEditor()"
    >
      <template #body>
        <NotificationForm
          :key="modalKey"
          :addInProgress="addInProgress"
          :reference="targetRef"
          :item="target"
          :allowedEvents="allowedEvents"
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
import { useNotifications } from '~/composables/useNotifications';
import { copyText, encode, parse_api_error, request, ucFirst } from '~/utils';
import type { ImportedItem } from '~/types';
import type { notification } from '~/types/notification';

const toast = useNotification();
const box = useConfirm();
const isMobile = useMediaQuery({ maxWidth: 1024 });
const displayStyleState = useStorage<'list' | 'grid' | 'cards'>(
  'notification_display_style',
  'cards',
);

const notificationsStore = useNotifications();
const notifications = notificationsStore.notifications;
const paging = notificationsStore.pagination;
const allowedEvents = notificationsStore.events;
const isLoading = notificationsStore.isLoading;
const addInProgress = notificationsStore.addInProgress;
const lastError = notificationsStore.lastError;

const page = ref(1);
const targetRef = ref<number | undefined>(undefined);
const target = ref<notification>(defaultState());
const editorOpen = ref(false);
const sendingTest = ref(false);
const query = ref('');
const showFilter = ref(false);
const filterInput = ref<HTMLInputElement | null>(null);

const displayStyle = computed<'list' | 'grid'>(() =>
  displayStyleState.value === 'list' ? 'list' : 'grid',
);

const modalTitle = computed(() =>
  targetRef.value ? `Edit - ${target.value.name}` : 'Add new notification target',
);
const modalDescription = computed(
  () => 'Send notifications to your webhooks based on specified events or presets.',
);
const modalKey = computed(
  () => `${targetRef.value ?? 'new'}-${editorOpen.value ? 'open' : 'closed'}`,
);

const filteredTargets = computed<notification[]>(() => {
  const normalizedQuery = query.value?.toLowerCase();
  const items = notifications.value as notification[];

  if (!normalizedQuery) {
    return items;
  }

  return items.filter((item) => deepIncludes(item, normalizedQuery, new WeakSet()));
});

watch(showFilter, (value) => {
  if (!value) {
    query.value = '';
  }
});

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
  filterInput.value?.focus();
};

const loadContent = async (pageNumber = page.value): Promise<void> => {
  page.value = pageNumber;
  await notificationsStore.loadNotifications(pageNumber);
};

const reloadContent = async (): Promise<void> => {
  await loadContent(page.value);
};

const navigatePage = async (newPage: number): Promise<void> => {
  await loadContent(newPage);
};

const resetEditor = (): void => {
  target.value = defaultState();
  targetRef.value = undefined;
};

const closeEditor = (): void => {
  editorOpen.value = false;
  resetEditor();
};

const openCreate = (): void => {
  resetEditor();
  editorOpen.value = true;
};

const editItem = (item: notification): void => {
  target.value = JSON.parse(JSON.stringify(item)) as notification;
  targetRef.value = item.id ?? undefined;
  editorOpen.value = true;
};

const deleteItem = async (item: notification): Promise<void> => {
  if (true !== (await box.confirm(`Delete '${item.name}'?`))) {
    return;
  }

  if (!item.id) {
    toast.error('Notification target not found.');
    return;
  }

  await notificationsStore.deleteNotification(item.id);
};

const toggleEnabled = async (item: notification): Promise<void> => {
  if (!item.id) {
    toast.error('Notification target not found.');
    return;
  }

  await notificationsStore.patchNotification(item.id, { enabled: !item.enabled });
};

const updateItem = async ({
  reference,
  item,
}: {
  reference: number | undefined;
  item: notification;
}): Promise<void> => {
  if (reference) {
    await notificationsStore.updateNotification(reference, item);
  } else {
    await notificationsStore.createNotification(item);
  }

  if (!lastError.value) {
    closeEditor();
  }
};

const toggleDisplayStyle = (): void => {
  displayStyleState.value = displayStyle.value === 'list' ? 'grid' : 'list';
};

const joinEvents = (events: string[]): string =>
  !events || events.length < 1 ? 'ALL' : events.map((event) => ucFirst(event)).join(', ');

const joinPresets = (presets: string[]): string =>
  !presets || presets.length < 1 ? 'ALL' : presets.map((preset) => ucFirst(preset)).join(', ');

const headerKeys = (item: notification): string[] =>
  item.request?.headers?.map((header) => header.key).filter(Boolean) ?? [];

const sendTest = async (): Promise<void> => {
  if (true !== (await box.confirm('Send test notification?'))) {
    return;
  }

  try {
    sendingTest.value = true;
    const response = await request('/api/notifications/test', { method: 'POST' });

    if (!response.ok) {
      const data = await response.json();
      const message = await parse_api_error(data);
      toast.error(`Failed to send test notification. ${message}`);
      return;
    }

    toast.success('Test notification sent.');
  } catch (error: any) {
    const message = error?.message || 'Unknown error';
    toast.error(`Failed to send test notification. ${message}`);
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
