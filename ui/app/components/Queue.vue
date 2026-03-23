<template>
  <div class="w-full min-w-0 max-w-full space-y-4">
    <div v-if="!socket.isConnected" class="flex justify-end">
      <UButton
        color="info"
        variant="outline"
        size="sm"
        icon="i-lucide-refresh-cw"
        :loading="isRefreshing"
        @click="refreshQueue"
      >
        Refresh
      </UButton>
    </div>

    <div v-if="hasItems" class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-check'"
          @click="toggleMasterSelection"
        >
          {{ masterSelectAll ? 'Unselect' : 'Select' }}
        </UButton>

        <UBadge v-if="selectedElms.length > 0" color="error" variant="soft" size="sm">
          {{ selectedElms.length }}
        </UBadge>

        <UDropdownMenu :items="bulkActionGroups">
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
    </div>

    <div
      v-if="'list' === display_style && hasItems"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-325 w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr class="text-center [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
              <th class="w-[5%]">
                <button type="button" class="cursor-pointer" @click="toggleMasterSelection">
                  <UIcon
                    :name="masterSelectAll ? 'i-lucide-square' : 'i-lucide-check'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="w-full text-left">Video Title</th>
              <th class="w-56">Progress</th>
              <th class="w-[15%]">Status</th>
              <th class="w-[15%]">Created</th>
              <th class="w-[1%]">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr v-for="item in displayedItems" :key="item._id" class="align-top hover:bg-muted/20">
              <td class="px-3 py-3 text-center align-top">
                <label class="inline-flex cursor-pointer items-center justify-center">
                  <input
                    :id="`checkbox-${item._id}`"
                    v-model="selectedElms"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item._id"
                  />
                </label>
              </td>

              <td class="px-3 py-3 align-top">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <UTooltip :text="`[${item.preset}] - ${item.title}`">
                      <div class="truncate font-medium text-highlighted">
                        <a target="_blank" :href="item.url" class="hover:underline">
                          {{ item.title }}
                        </a>
                      </div>
                    </UTooltip>
                  </div>

                  <div
                    v-if="item.downloaded_bytes || show_popover"
                    class="flex shrink-0 items-center gap-2"
                  >
                    <UBadge v-if="item.downloaded_bytes" color="neutral" variant="soft" size="sm">
                      {{ formatBytes(item.downloaded_bytes) }}
                    </UBadge>

                    <UPopover
                      v-if="show_popover"
                      :content="{ side: 'bottom', align: 'end', sideOffset: 8 }"
                    >
                      <UButton
                        color="neutral"
                        variant="ghost"
                        size="xs"
                        icon="i-lucide-info"
                        square
                      />

                      <template #content>
                        <UCard class="max-w-112.5" :ui="{ body: 'space-y-3 p-4' }">
                          <div class="space-y-2">
                            <div class="flex flex-wrap items-center gap-2">
                              <p class="text-sm font-semibold text-highlighted">{{ item.title }}</p>
                              <UBadge color="info" variant="soft" size="sm">{{
                                item.preset
                              }}</UBadge>
                            </div>

                            <p v-if="item.extras?.duration" class="text-xs text-toned">
                              <span class="font-semibold text-default">Duration:</span>
                              {{ formatTime(item.extras.duration) }}
                            </p>

                            <p v-if="getItemPath(item)" class="text-xs text-toned">
                              <span class="font-semibold text-default">Path:</span>
                              {{ getItemPath(item) }}
                            </p>
                          </div>

                          <img
                            v-if="showThumbnails && getListImage(item)"
                            :src="getListImage(item)"
                            class="max-h-56 w-full rounded-md object-cover"
                          />

                          <div
                            v-if="item.description"
                            class="max-h-40 overflow-y-auto rounded-md border border-default bg-muted/20 px-3 py-2 text-sm text-default"
                          >
                            {{ item.description }}
                          </div>
                        </UCard>
                      </template>
                    </UPopover>
                  </div>
                </div>
              </td>

              <td class="w-56 px-3 py-3 align-top">
                <div
                  class="queue-progress queue-progress--compact w-56 rounded-md border border-default bg-muted/20"
                >
                  <div
                    class="queue-progress__bar bg-success/35"
                    :style="{ width: progressWidth(item) }"
                  ></div>
                  <div class="queue-progress__label">
                    <template v-if="progressIcon(item)">
                      <UIcon
                        :name="progressIcon(item)"
                        :class="[
                          'mr-1 size-4',
                          progressIcon(item) === 'i-lucide-settings-2' ? 'animate-spin' : '',
                        ]"
                      />
                    </template>
                    <span>{{ progressText(item) }}</span>
                  </div>
                </div>
              </td>

              <td class="px-3 py-3 text-center align-top text-sm">
                <div class="inline-flex items-center gap-2 text-default whitespace-nowrap">
                  <span class="inline-flex items-center">
                    <UIcon
                      :name="setIcon(item)"
                      :class="[setIconColor(item), setIconAnimation(item), 'size-4 shrink-0']"
                    />
                  </span>
                  <span>{{ setStatus(item) }}</span>
                </div>
              </td>

              <td class="px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap">
                <UTooltip :text="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                  <span :data-datetime="item.datetime" v-rtime="item.datetime" />
                </UTooltip>
              </td>

              <td class="w-[1%] px-3 py-3 align-top whitespace-nowrap">
                <div class="flex items-center justify-end gap-1">
                  <UButton
                    color="warning"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-circle-off"
                    square
                    @click="() => void confirmCancel(item)"
                  />

                  <UButton
                    v-if="canStartItem(item)"
                    color="success"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-circle-play"
                    square
                    @click="() => void startItem(item)"
                  />

                  <UButton
                    v-if="canPauseItem(item)"
                    color="warning"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-pause"
                    square
                    @click="() => void pauseItem(item)"
                  />

                  <UDropdownMenu :items="itemActionGroups(item)">
                    <UButton
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-settings-2"
                      trailing-icon="i-lucide-chevron-down"
                    >
                      Actions
                    </UButton>
                  </UDropdownMenu>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="hasItems" class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      <LateLoader
        v-for="item in displayedItems"
        :key="item._id"
        :unrender="true"
        :min-height="showThumbnails ? 475 : 265"
        class="min-h-0 min-w-0 w-full max-w-full"
      >
        <UCard
          class="flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden border"
          :class="queueCardClass(item)"
          :ui="{ body: 'flex flex-1 flex-col gap-4 p-4', header: 'p-4 pb-3', root: 'bg-default' }"
        >
          <template #header>
            <div class="flex min-w-0 flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <UTooltip :text="item.title">
                  <div class="min-w-0 text-sm font-semibold text-highlighted">
                    <a target="_blank" :href="item.url" class="block truncate hover:underline">
                      {{ item.title }}
                    </a>
                  </div>
                </UTooltip>
              </div>

              <div class="flex max-w-full flex-wrap items-center justify-end gap-1 sm:shrink-0">
                <UBadge v-if="item.extras?.duration" color="info" variant="soft" size="sm">
                  {{ formatTime(item.extras.duration) }}
                </UBadge>

                <UPopover
                  v-if="show_popover"
                  :content="{ side: 'bottom', align: 'end', sideOffset: 8 }"
                >
                  <UButton color="neutral" variant="ghost" size="xs" icon="i-lucide-info" square />

                  <template #content>
                    <UCard class="max-w-112.5" :ui="{ body: 'space-y-3 p-4' }">
                      <div class="space-y-2">
                        <div class="flex flex-wrap items-center gap-2">
                          <p class="text-sm font-semibold text-highlighted">{{ item.title }}</p>
                          <UBadge color="info" variant="soft" size="sm">{{ item.preset }}</UBadge>
                        </div>

                        <p v-if="getItemPath(item)" class="text-xs text-toned">
                          <span class="font-semibold text-default">Path:</span>
                          {{ getItemPath(item) }}
                        </p>
                      </div>

                      <div
                        v-if="item.description"
                        class="max-h-40 overflow-y-auto rounded-md border border-default bg-muted/20 px-3 py-2 text-sm text-default"
                      >
                        {{ item.description }}
                      </div>
                    </UCard>
                  </template>
                </UPopover>

                <UButton
                  v-if="thumbnails"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  :icon="hideThumbnail ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up'"
                  square
                  @click="hideThumbnail = !hideThumbnail"
                />

                <label class="inline-flex cursor-pointer items-center justify-center px-1">
                  <input
                    :id="`checkbox-${item._id}`"
                    v-model="selectedElms"
                    class="completed-checkbox size-4 rounded border-default"
                    type="checkbox"
                    :value="item._id"
                  />
                </label>
              </div>
            </div>
          </template>

          <div
            v-if="showThumbnails"
            class="-mx-4 -mt-4 overflow-hidden border-b border-default bg-muted/20"
          >
            <figure :class="['relative w-full overflow-hidden', thumbnailRatioClass]">
              <span
                v-if="isEmbedable(item.url)"
                class="play-overlay"
                @click="embed_url = getEmbedable(item.url) as string"
              >
                <span class="play-icon embed-icon" aria-hidden="true">
                  <UIcon name="i-lucide-play" class="size-6 translate-x-px text-white" />
                </span>
                <img
                  v-if="getGridImage(item)"
                  :src="getGridImage(item)"
                  @load="pImg"
                  @error="onImgError"
                />
                <img v-else src="/images/placeholder.png" />
              </span>

              <template v-else>
                <img
                  v-if="getGridImage(item)"
                  :src="getGridImage(item)"
                  @load="pImg"
                  @error="onImgError"
                />
                <img v-else src="/images/placeholder.png" />
              </template>
            </figure>
          </div>

          <div class="queue-progress rounded-md border border-default bg-muted/20">
            <div
              class="queue-progress__bar bg-success/35"
              :style="{ width: progressWidth(item) }"
            ></div>
            <div class="queue-progress__label">
              <template v-if="progressIcon(item)">
                <UIcon
                  :name="progressIcon(item)"
                  :class="[
                    'mr-1 size-4',
                    progressIcon(item) === 'i-lucide-settings-2' ? 'animate-spin' : '',
                  ]"
                />
              </template>
              <span>{{ progressText(item) }}</span>
            </div>
          </div>

          <div class="grid gap-2 text-sm sm:auto-cols-fr sm:grid-flow-col">
            <div
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-default"
            >
              <span class="inline-flex items-center gap-2">
                <UIcon
                  :name="setIcon(item)"
                  :class="[setIconColor(item), setIconAnimation(item), 'size-4 shrink-0']"
                />
                <span>{{ setStatus(item) }}</span>
              </span>
            </div>

            <div
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-default"
            >
              <UTooltip :text="`Preset: ${item.preset}`">
                <span class="block min-w-0 truncate">{{ item.preset }}</span>
              </UTooltip>
            </div>

            <div
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-toned"
            >
              <UTooltip :text="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                <span :data-datetime="item.datetime" v-rtime="item.datetime" />
              </UTooltip>
            </div>

            <div
              v-if="item.downloaded_bytes"
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-center text-toned"
            >
              {{ formatBytes(item.downloaded_bytes) }}
            </div>
          </div>

          <div class="grid gap-2 sm:auto-cols-fr sm:grid-flow-col">
            <UButton
              color="warning"
              variant="outline"
              icon="i-lucide-circle-off"
              class="w-full justify-center"
              @click="() => void confirmCancel(item)"
            >
              Cancel
            </UButton>

            <UButton
              v-if="canStartItem(item)"
              color="success"
              variant="outline"
              icon="i-lucide-circle-play"
              class="w-full justify-center"
              @click="() => void startItem(item)"
            >
              Start
            </UButton>

            <UButton
              v-if="canPauseItem(item)"
              color="warning"
              variant="outline"
              icon="i-lucide-pause"
              class="w-full justify-center"
              @click="() => void pauseItem(item)"
            >
              Pause
            </UButton>

            <UDropdownMenu :items="itemActionGroups(item)" class="w-full">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-settings-2"
                trailing-icon="i-lucide-chevron-down"
                class="w-full justify-center"
              >
                Actions
              </UButton>
            </UDropdownMenu>
          </div>
        </UCard>
      </LateLoader>
    </div>

    <div v-if="!hasItems" class="space-y-4">
      <UAlert
        v-if="query"
        color="warning"
        variant="soft"
        icon="i-lucide-search"
        title="Filter results"
      >
        <template #description>
          <div class="space-y-3 text-sm text-default">
            <p>
              No results found for: <code>{{ query }}</code
              >.
            </p>

            <p>
              You can search using any value shown in the item's <code>Local Information</code>. You
              can also do a targeted search using <code><u>key</u>:value</code>.
            </p>

            <div>
              <p class="mb-1 font-medium">Examples:</p>
              <ul class="list-disc space-y-1 pl-5">
                <li><code>youtube.com</code> - items containing that text</li>
                <li><code>is_live:true</code> - only live downloads</li>
                <li><code>source_name:task_name</code> - items added by the specified task.</li>
              </ul>
            </div>

            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              @click="() => emitter('clear_search')"
            >
              Clear filter
            </UButton>
          </div>
        </template>
      </UAlert>

      <UEmpty
        v-else
        icon="i-lucide-triangle-alert"
        title="No items"
        description="Download queue is empty."
        class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
      />
    </div>

    <UModal
      v-if="embed_url"
      :open="Boolean(embed_url)"
      :dismissible="true"
      title="Embedded player"
      :ui="{ content: 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && (embed_url = '')"
    >
      <template #body>
        <EmbedPlayer :url="embed_url" @closeModel="embed_url = ''" />
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import type { StoreItem } from '~/types/store';
import { useConfirm } from '~/composables/useConfirm';
import { deepIncludes, getPath, getImage } from '~/utils';

const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string, cli: string): void;
  (e: 'getItemInfo', id: string): void;
  (e: 'clear_search'): void;
}>();

const props = defineProps<{
  thumbnails?: boolean;
  query?: string;
}>();

const config = useConfigStore();
const stateStore = useStateStore();
const socket = useSocketStore();
const box = useConfirm();
const toast = useNotification();

const hideThumbnail = useStorage<boolean>('hideThumbnailQueue', false);
const display_style = useStorage<'grid' | 'list'>('display_style', 'grid');
const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1');
const show_popover = useStorage<boolean>('show_popover', true);

const selectedElms = ref<string[]>([]);
const masterSelectAll = ref(false);
const embed_url = ref('');
const isRefreshing = ref(false);
const autoRefreshInterval = ref<NodeJS.Timeout | null>(null);
const autoRefreshEnabled = useStorage<boolean>('queue_auto_refresh', true);
const autoRefreshDelay = useStorage<number>('queue_auto_refresh_delay', 10000);

const showThumbnails = computed(() => Boolean(props.thumbnails) && !hideThumbnail.value);

const refreshQueue = async () => {
  isRefreshing.value = true;
  try {
    await stateStore.loadQueue();
  } catch {
    toast.error('Failed to refresh queue');
  } finally {
    isRefreshing.value = false;
  }
};

const startAutoRefresh = () => {
  if (autoRefreshInterval.value) {
    clearInterval(autoRefreshInterval.value);
  }

  if (!autoRefreshEnabled.value || socket.isConnected) {
    return;
  }

  autoRefreshInterval.value = setInterval(async () => {
    if (!socket.isConnected && autoRefreshEnabled.value) {
      await refreshQueue();
    }
  }, autoRefreshDelay.value);
};

const stopAutoRefresh = () => {
  if (autoRefreshInterval.value) {
    clearInterval(autoRefreshInterval.value);
    autoRefreshInterval.value = null;
  }
};

watch(
  () => socket.isConnected,
  (connected) => {
    if (connected) {
      stopAutoRefresh();
    } else if (autoRefreshEnabled.value) {
      startAutoRefresh();
    }
  },
);

watch(autoRefreshEnabled, (enabled) => {
  if (enabled && !socket.isConnected) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
});

watch(autoRefreshDelay, () => {
  if (autoRefreshEnabled.value && !socket.isConnected) {
    startAutoRefresh();
  }
});

onMounted(() => {
  if (!socket.isConnected && autoRefreshEnabled.value) {
    startAutoRefresh();
  }
});

onBeforeUnmount(() => stopAutoRefresh());

const displayedItems = computed<StoreItem[]>(() => {
  const q = props.query?.toLowerCase();
  if (!q) {
    return Object.values(stateStore.queue);
  }
  return Object.values(stateStore.queue).filter((i: StoreItem) =>
    deepIncludes(i, q, new WeakSet()),
  );
});

const hasItems = computed(() => displayedItems.value.length > 0);
const hasSelected = computed(() => selectedElms.value.length > 0);
const displayedItemIds = computed(() => displayedItems.value.map((item) => item._id));

const hasManualStart = computed(() =>
  Object.values(stateStore.queue).some((item) => !item.status && false === item.auto_start),
);

const hasPausable = computed(() =>
  Object.values(stateStore.queue).some((item) => !item.status && true === item.auto_start),
);

const thumbnailRatioClass = computed(() =>
  thumbnail_ratio.value === 'is-16by9' ? 'aspect-video' : 'aspect-[3/1]',
);

const toggleMasterSelection = () => {
  if (masterSelectAll.value) {
    selectedElms.value = [];
    masterSelectAll.value = false;
    return;
  }

  selectedElms.value = [...displayedItemIds.value];
  masterSelectAll.value = true;
};

watch(
  displayedItemIds,
  (ids) => {
    const idSet = new Set(ids);
    selectedElms.value = selectedElms.value.filter((id) => idSet.has(id));

    if (masterSelectAll.value) {
      selectedElms.value = [...ids];
    }
  },
  { immediate: true },
);

watch(selectedElms, (value) => {
  const ids = displayedItemIds.value;
  masterSelectAll.value = ids.length > 0 && ids.every((id) => value.includes(id));
});

const getItemPath = (item: StoreItem): string => getPath(config.app.download_path, item) || '';

const getListImage = (item: StoreItem): string =>
  getImage(config.app.download_path, item, false) || '';

const getGridImage = (item: StoreItem): string => getImage(config.app.download_path, item) || '';

const queueCardClass = (item: StoreItem): string => {
  if ('postprocessing' === item.status) {
    return 'border-info';
  }

  if (['downloading', 'started'].includes(item.status || '')) {
    return 'border-success';
  }

  if (!item.auto_start || (null === item.status && true === config.paused)) {
    return 'border-warning';
  }

  return 'border-default';
};

const canStartItem = (item: StoreItem): boolean => !item.auto_start && !item.status;

const canPauseItem = (item: StoreItem): boolean => item.auto_start && !item.status;

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [[]];

  if (hasManualStart.value) {
    groups[0]?.push({
      label: 'Start',
      icon: 'i-lucide-circle-play',
      color: 'success',
      disabled: !hasSelected.value,
      onSelect: () => void startItems(),
    });
  }

  if (hasPausable.value) {
    groups[0]?.push({
      label: 'Pause',
      icon: 'i-lucide-pause',
      color: 'warning',
      disabled: !hasSelected.value,
      onSelect: () => void pauseSelected(),
    });
  }

  groups[0]?.push({
    label: 'Cancel',
    icon: 'i-lucide-circle-off',
    color: 'warning',
    disabled: !hasSelected.value,
    onSelect: () => void cancelSelected(),
  });

  return groups;
});

const itemActionGroups = (item: StoreItem) => {
  const groups: Array<Array<Record<string, unknown>>> = [];
  const primaryActions: Array<Record<string, unknown>> = [];

  if (isEmbedable(item.url)) {
    primaryActions.push({
      label: 'Play video',
      icon: 'i-lucide-play',
      color: 'error',
      onSelect: () => {
        embed_url.value = getEmbedable(item.url) as string;
      },
    });
  }

  primaryActions.push({
    label: 'Cancel Download',
    icon: 'i-lucide-circle-off',
    color: 'warning',
    onSelect: () => void confirmCancel(item),
  });

  if (canStartItem(item)) {
    primaryActions.push({
      label: 'Start Download',
      icon: 'i-lucide-circle-play',
      color: 'success',
      onSelect: () => void startItem(item),
    });
  }

  if (canPauseItem(item)) {
    primaryActions.push({
      label: 'Pause Download',
      icon: 'i-lucide-pause',
      color: 'warning',
      onSelect: () => void pauseItem(item),
    });
  }

  groups.push(primaryActions);

  groups.push([
    {
      label: 'yt-dlp Information',
      icon: 'i-lucide-info',
      onSelect: () => emitter('getInfo', item.url, item.preset, item.cli),
    },
    {
      label: 'Local Information',
      icon: 'i-lucide-info',
      onSelect: () => emitter('getItemInfo', item._id),
    },
  ]);

  return groups;
};

const setIcon = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'i-lucide-clock-3';
  }
  if ('downloading' === item.status && item.is_live) {
    return 'i-lucide-globe';
  }
  if ('downloading' === item.status) {
    return 'i-lucide-download';
  }
  if ('postprocessing' === item.status) {
    return 'i-lucide-settings-2';
  }
  if (null === item.status && true === config.paused) {
    return 'i-lucide-circle-pause';
  }
  if (!item.status) {
    return 'i-lucide-circle-question-mark';
  }
  return 'i-lucide-loader-circle';
};

const setIconAnimation = (item: StoreItem): string => {
  const icon = setIcon(item);

  return ['i-lucide-globe', 'i-lucide-settings-2', 'i-lucide-loader-circle'].includes(icon)
    ? 'animate-spin'
    : '';
};

const setStatus = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'Pending';
  }
  if (null === item.status && true === config.paused) {
    return 'Paused';
  }
  if ('downloading' === item.status && item.is_live) {
    return 'Streaming';
  }
  if ('started' === item.status) {
    return 'Starting';
  }
  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader') ? 'External-DL' : 'Preparing..';
  }
  if (!item.status) {
    return 'Unknown...';
  }
  return ucFirst(item.status);
};

const setIconColor = (item: StoreItem): string => {
  if (['downloading', 'started'].includes(item.status || '')) {
    return 'text-success';
  }
  if ('postprocessing' === item.status) {
    return 'text-info';
  }
  if (!item.auto_start || (null === item.status && true === config.paused)) {
    return 'text-warning';
  }
  return 'text-default';
};

const ETAPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return 'Live';
  }
  if (value < 60) {
    return `${Math.round(value)}s`;
  }
  if (value < 3600) {
    return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
  }
  const hours = Math.floor(value / 3600);
  const minutes = value % 3600;
  return `${hours}h ${Math.floor(minutes / 60)}m ${Math.round(minutes % 60)}s`;
};

const speedPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return '0KB/s';
  }
  const k = 1024;
  const dm = 2;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s', 'EB/s', 'ZB/s', 'YB/s'];
  const i = Math.floor(Math.log(value) / Math.log(k));
  return `${parseFloat((value / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
};

const percentPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return '00.00';
  }
  return parseFloat(String(value)).toFixed(2);
};

const progressWidth = (item: StoreItem): string => {
  if (!item.auto_start || (null === item.status && true === config.paused)) {
    return '0%';
  }

  if (
    'postprocessing' === item.status ||
    'started' === item.status ||
    'preparing' === item.status
  ) {
    return '100%';
  }

  if (!item.percent || item.is_live) {
    return '100%';
  }

  return `${percentPipe(item.percent)}%`;
};

const progressIcon = (item: StoreItem): string => {
  if ('postprocessing' === item.status) {
    return 'i-lucide-settings-2';
  }

  return '';
};

const progressText = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'Manual start';
  }
  if (null === item.status && true === config.paused) {
    return 'Global Pause';
  }
  if ('started' === item.status) {
    return 'Starting';
  }
  if ('postprocessing' === item.status) {
    if (item.postprocessor) {
      return `PP: ${item.postprocessor}`;
    }
    return 'Post-processors are running.';
  }
  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader') ? 'External downloader.' : 'Preparing';
  }

  let value = '';
  if (null != item.status) {
    value += item.percent && !item.is_live ? `${percentPipe(item.percent)}%` : 'Live';
  }
  value += item.speed ? ` - ${speedPipe(item.speed)}` : ' - Waiting..';
  if (null != item.status && item.eta) {
    value += ` - ${ETAPipe(item.eta)}`;
  }
  return value;
};

const confirmCancel = async (item: StoreItem) => {
  if (true !== (await box.confirm(`Cancel '${item.title}'?`))) {
    return false;
  }
  cancelItems(item._id);
  return true;
};

const cancelSelected = async () => {
  if (true !== (await box.confirm(`Cancel '${selectedElms.value.length}' selected items?`))) {
    return false;
  }
  cancelItems(selectedElms.value);
  selectedElms.value = [];
  masterSelectAll.value = false;
  return true;
};

const cancelItems = (item: string | string[]) => {
  const items = Array.isArray(item) ? [...item] : [item];
  if (items.length < 1) {
    return;
  }
  stateStore.cancelItems(items);
};

const startItem = async (item: StoreItem) => await stateStore.startItems([item._id]);
const pauseItem = async (item: StoreItem) => await stateStore.pauseItems([item._id]);

const startItems = async () => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get('queue', id) as StoreItem;
    return Boolean(item && !item.auto_start && !item.status);
  });

  selectedElms.value = [];
  if (eligible.length < 1) {
    toast.error('No eligible items to start.');
    return;
  }
  if (true !== (await box.confirm(`Start '${eligible.length}' selected items?`))) {
    return false;
  }
  await stateStore.startItems(eligible);
};

const pauseSelected = async () => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get('queue', id) as StoreItem;
    return Boolean(item && item.auto_start && !item.status);
  });

  selectedElms.value = [];
  if (eligible.length < 1) {
    toast.error('No eligible items to pause.');
    return;
  }
  if (true !== (await box.confirm(`Pause '${eligible.length}' selected items?`))) {
    return false;
  }
  await stateStore.pauseItems(eligible);
};

const pImg = (e: Event) => {
  const target = e.target as HTMLImageElement;
  if (target.naturalHeight > target.naturalWidth) {
    target.classList.add('image-portrait');
  }
};

const onImgError = (e: Event) => {
  const target = e.target as HTMLImageElement;
  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }
  target.src = '/images/placeholder.png';
};

watch(embed_url, (v) => {
  if (!bg_enable.value) {
    return;
  }
  document.querySelector('body')?.setAttribute('style', `opacity: ${v ? 1 : bg_opacity.value}`);
});
</script>

<style scoped>
.queue-progress {
  position: relative;
  min-height: 2.25rem;
  overflow: hidden;
}

.queue-progress__bar {
  position: absolute;
  inset: 0 auto 0 0;
}

.queue-progress__label {
  position: relative;
  z-index: 1;
  display: flex;
  min-height: 2.25rem;
  min-width: 0;
  align-items: center;
  justify-content: center;
  flex-wrap: nowrap;
  padding: 0.5rem 0.75rem;
  text-align: center;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--ui-text-highlighted);
  white-space: nowrap;
}

.queue-progress--compact {
  min-height: 1.875rem;
}

.queue-progress--compact .queue-progress__label {
  min-height: 1.875rem;
  padding: 0.375rem 0.75rem;
}
</style>
