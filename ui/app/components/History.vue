<template>
  <div class="w-full min-w-0 max-w-full space-y-4">
    <div
      v-if="hasItems"
      class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-default bg-default px-3 py-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
          @click="toggleMasterSelection"
        >
          {{ masterSelectAll ? 'Unselect' : 'Select' }}
        </UButton>

        <UBadge v-if="selectedElms.length > 0" color="error" variant="soft" size="sm">
          {{ selectedElms.length }}
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

      <div class="flex flex-wrap items-center gap-2">
        <UBadge color="neutral" variant="soft" size="sm">
          <span class="inline-flex items-center gap-1.5">
            <UIcon name="i-lucide-history" class="size-3.5" />
            <span>Total: {{ stateStore.count('history') }}</span>
          </span>
        </UBadge>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="direction === 'desc' ? 'i-lucide-arrow-down-a-z' : 'i-lucide-arrow-up-a-z'"
          @click="toggleDirection"
        >
          <span>Sort</span>
        </UButton>
      </div>
    </div>

    <UAlert
      v-if="paginationInfo.isLoading && !hasItems"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading history..."
    />

    <div
      v-if="'list' === contentStyle && hasItems"
      class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
    >
      <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
        <table class="min-w-210 table-fixed w-full text-sm">
          <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
            <tr
              class="text-center [&>th]:border-r [&>th]:border-default/60 [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold [&>th:last-child]:border-r-0"
            >
              <th class="w-12">
                <button
                  type="button"
                  class="cursor-pointer"
                  :aria-label="masterSelectAll ? 'Unselect all items' : 'Select all items'"
                  @click="toggleMasterSelection"
                >
                  <UIcon
                    :name="masterSelectAll ? 'i-lucide-square' : 'i-lucide-square-check-big'"
                    class="size-4"
                  />
                </button>
              </th>
              <th class="text-left">Title</th>
              <th class="w-32 whitespace-nowrap">Status</th>
              <th class="w-36 whitespace-nowrap">Created</th>
              <th class="w-36 whitespace-nowrap">Size/Starts</th>
              <th class="w-80 whitespace-nowrap">Actions</th>
            </tr>
          </thead>

          <tbody class="divide-y divide-default">
            <tr
              v-for="item in displayedItems"
              :key="item._id"
              class="align-top transition-colors hover:bg-elevated/70 [&>td]:border-r [&>td]:border-default/60 [&>td:last-child]:border-r-0"
            >
              <td class="border-r border-default/60 px-3 py-3 text-center align-top">
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

              <td class="w-0 border-r border-default/60 px-3 py-3 align-top">
                <div class="flex min-w-0 items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <UTooltip
                      :text="
                        show_popover
                          ? `${item.preset}: ${item.title}`
                          : `[${item.preset}] - ${item.title}`
                      "
                    >
                      <div class="truncate font-medium text-highlighted">
                        <a target="_blank" :href="item.url" class="hover:underline">
                          {{ item.title }}
                        </a>
                      </div>
                    </UTooltip>
                  </div>

                  <div
                    v-if="item.extras?.duration || show_popover"
                    class="flex shrink-0 items-center gap-2"
                  >
                    <UBadge v-if="item.extras?.duration" color="info" variant="soft" size="sm">
                      {{ formatTime(item.extras.duration) }}
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

                <p
                  v-if="item.error"
                  :class="messageClass(item._id, 'error', 'list', 'mt-2')"
                  @click="toggleMessage(item._id, 'error', 'list')"
                >
                  {{ item.error }}
                </p>

                <p
                  v-if="showMessage(item)"
                  :class="messageClass(item._id, 'msg', 'list', 'mt-1')"
                  @click="toggleMessage(item._id, 'msg', 'list')"
                >
                  {{ item.msg }}
                </p>
              </td>

              <td class="border-r border-default/60 px-3 py-3 text-center align-top text-sm">
                <div class="inline-flex items-center gap-2 text-default">
                  <span class="inline-flex items-center">
                    <UIcon
                      :name="setIcon(item)"
                      :class="[setIconColor(item), isQueuedAnimation(item), 'size-4 shrink-0']"
                    />
                  </span>
                  <span>{{ setStatus(item) }}</span>
                </div>
              </td>

              <td
                class="border-r border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
              >
                <UTooltip :text="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                  <span :date-datetime="item.datetime" v-rtime="item.datetime" />
                </UTooltip>
              </td>

              <td
                class="border-r border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
              >
                <template
                  v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)"
                >
                  <UTooltip
                    :text="`Retry at: ${moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')}`"
                  >
                    <span
                      :date-datetime="item.live_in || item.extras?.release_in"
                      v-rtime="item.live_in || item.extras?.release_in"
                    />
                  </UTooltip>
                </template>

                <template v-else>
                  {{ item.file_size ? formatBytes(item.file_size) : 'N/A' }}
                </template>
              </td>

              <td class="w-80 px-3 py-3 align-top whitespace-nowrap">
                <div class="flex items-center justify-end gap-1">
                  <UButton
                    v-if="showRetryAction(item)"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-rotate-cw"
                    @click="() => void retryItem(item, true)"
                  >
                    Retry
                  </UButton>

                  <UButton
                    v-if="item.filename"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-download"
                    external
                    :href="makeDownload(config, item)"
                    :download="item.filename?.split('/').reverse()[0]"
                  >
                    Download
                  </UButton>

                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    @click="() => void removeItem(item)"
                  >
                    Remove
                  </UButton>

                  <UDropdownMenu v-if="item.url" :items="itemActionGroups(item)" :modal="false">
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
        :min-height="showThumbnails ? 410 : 210"
        class="min-h-0 min-w-0 w-full max-w-full"
      >
        <UCard
          class="flex h-full min-w-0 w-full max-w-full flex-col overflow-hidden border"
          :ui="{
            body: 'flex flex-1 flex-col gap-4 p-4',
            footer: 'border-t border-default px-4 py-4',
            header: 'p-4 pb-3',
            root: 'bg-default',
          }"
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
                  v-if="show_popover && getItemPath(item)"
                  :content="{ side: 'bottom', align: 'end', sideOffset: 8 }"
                >
                  <UButton color="neutral" variant="ghost" size="xs" icon="i-lucide-info" square />

                  <template #content>
                    <UCard class="max-w-137.5" :ui="{ body: 'space-y-3 p-4' }">
                      <div class="space-y-2">
                        <p class="text-sm font-semibold text-highlighted">{{ item.title }}</p>
                        <p class="text-xs text-toned">
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
              <span v-if="item.filename" class="play-overlay" @click="playVideo(item)">
                <span class="play-icon" aria-hidden="true">
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

              <span
                v-else-if="isEmbedable(item.url)"
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

          <div class="flex flex-wrap gap-2 text-sm *:min-w-32 *:flex-1">
            <button
              type="button"
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
              @click="toggleExpand(item._id, 'status')"
            >
              <span class="inline-flex w-full items-center justify-center gap-2">
                <UIcon
                  :name="setIcon(item)"
                  :class="[setIconColor(item), isQueuedAnimation(item), 'size-4 shrink-0']"
                />
                <span :class="['min-w-0 text-center', expandClass(item._id, 'status')]">
                  {{ setStatus(item) }}
                </span>
              </span>
            </button>

            <button
              type="button"
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
              @click="toggleExpand(item._id, 'preset')"
            >
              <span class="inline-flex w-full items-center justify-center gap-2">
                <UIcon name="i-lucide-sliders-horizontal" class="size-4 shrink-0 text-toned" />
                <span :class="['min-w-0 text-center', expandClass(item._id, 'preset')]">
                  {{ item.preset }}
                </span>
              </span>
            </button>

            <button
              v-if="'not_live' === item.status && (item.live_in || item.extras?.release_in)"
              type="button"
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
              @click="toggleExpand(item._id, 'retry_at')"
            >
              <UTooltip
                :text="`Retry at: ${moment(item.live_in || item.extras?.release_in).format('YYYY-M-DD H:mm Z')}`"
              >
                <span class="inline-flex w-full items-center justify-center gap-2">
                  <UIcon name="i-lucide-calendar" class="size-4 shrink-0 text-toned" />
                  <span
                    :class="['min-w-0 text-center', expandClass(item._id, 'retry_at')]"
                    :date-datetime="item.live_in || item.extras?.release_in"
                    v-rtime="item.live_in || item.extras?.release_in"
                  />
                </span>
              </UTooltip>
            </button>

            <button
              type="button"
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
              @click="toggleExpand(item._id, 'datetime')"
            >
              <UTooltip :text="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                <span class="inline-flex w-full items-center justify-center gap-2">
                  <UIcon name="i-lucide-clock-3" class="size-4 shrink-0 text-toned" />
                  <span
                    :class="['min-w-0 text-center', expandClass(item._id, 'datetime')]"
                    :date-datetime="item.datetime"
                    v-rtime="item.datetime"
                  />
                </span>
              </UTooltip>
            </button>

            <button
              v-if="item.file_size"
              type="button"
              class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
              @click="toggleExpand(item._id, 'size')"
            >
              <span class="inline-flex w-full items-center justify-center gap-2">
                <UIcon name="i-lucide-hard-drive" class="size-4 shrink-0 text-toned" />
                <span :class="['min-w-0 text-center', expandClass(item._id, 'size')]">
                  {{ formatBytes(item.file_size) }}
                </span>
              </span>
            </button>
          </div>

          <div
            v-if="item.error || showMessage(item)"
            class="space-y-2 border-t border-default pt-3"
          >
            <p
              v-if="item.error"
              :class="messageClass(item._id, 'error', 'card')"
              @click="toggleMessage(item._id, 'error', 'card')"
            >
              {{ item.error }}
            </p>

            <p
              v-if="showMessage(item)"
              :class="messageClass(item._id, 'msg', 'card')"
              @click="toggleMessage(item._id, 'msg', 'card')"
            >
              {{ item.msg }}
            </p>
          </div>

          <template #footer>
            <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
              <UButton
                v-if="showRetryAction(item)"
                color="neutral"
                variant="outline"
                icon="i-lucide-rotate-cw"
                class="w-full justify-center"
                @click="() => void retryItem(item, false)"
              >
                Retry
              </UButton>

              <UButton
                v-if="item.filename"
                color="neutral"
                variant="outline"
                icon="i-lucide-download"
                class="w-full justify-center"
                external
                :href="makeDownload(config, item)"
                :download="item.filename?.split('/').reverse()[0]"
              >
                Download
              </UButton>

              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-trash"
                class="w-full justify-center"
                @click="() => void removeItem(item)"
              >
                {{ config.app.remove_files ? 'Remove' : 'Clear' }}
              </UButton>

              <UDropdownMenu :items="itemActionGroups(item)" :modal="false" class="w-full">
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
          </template>
        </UCard>
      </LateLoader>
    </div>

    <div v-if="!hasItems && !paginationInfo.isLoading" class="space-y-4">
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
          </div>
        </template>
      </UAlert>

      <UEmpty
        v-else
        icon="i-lucide-triangle-alert"
        title="No items"
        description="Download history is empty."
        class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
      />
    </div>

    <div
      v-if="paginationInfo.isLoaded && paginationInfo.page < paginationInfo.total_pages"
      ref="loadMoreTrigger"
      class="flex justify-center pt-2"
    >
      <div v-if="paginationInfo.isLoading" class="text-center text-sm text-toned">
        <UIcon name="i-lucide-loader-circle" class="mx-auto size-7 animate-spin text-info" />
        <p class="mt-2">Loading more items...</p>
      </div>
    </div>

    <UModal
      v-if="video_item"
      :open="Boolean(video_item)"
      :dismissible="true"
      :title="video_item?.title || 'Player'"
      :ui="{ content: 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && closeVideo()"
    >
      <template #body>
        <VideoPlayer
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="video_item"
          class="w-full"
          @closeModel="closeVideo"
          @error="async (error: string) => await box.alert(error)"
        />
      </template>
    </UModal>

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
import { useStorage, useIntersectionObserver } from '@vueuse/core';
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import type { StoreItem } from '~/types/store';
import { useConfirm } from '~/composables/useConfirm';
import { deepIncludes, getPath, getImage, isDownloadSkipped } from '~/utils';
import type { item_request } from '~/types/item';

const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string, cli: string): void;
  (e: 'add_new', item: item_request): void;
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
const toast = useNotification();
const box = useConfirm();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();

const showCompleted = useStorage<boolean>('showCompleted', true);
const hideThumbnail = useStorage<boolean>('hideThumbnailHistory', false);
const direction = useStorage<'asc' | 'desc'>('sortCompleted', 'desc');
const display_style = useStorage<'grid' | 'list'>('display_style', 'grid');
const isMobile = useMediaQuery({ maxWidth: 639 });
const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1');
const show_popover = useStorage<boolean>('show_popover', true);

const selectedElms = ref<string[]>([]);
const masterSelectAll = ref(false);
const embed_url = ref('');
const video_item = ref<StoreItem | null>(null);
const loadMoreTrigger = ref<HTMLElement | null>(null);
const expandedMessages = reactive<Record<string, Set<string>>>({});

const contentStyle = computed<'grid' | 'list'>(() =>
  isMobile.value ? 'grid' : display_style.value,
);

const paginationInfo = computed(() => stateStore.getPagination());

// Function to load more history items
const loadMoreHistory = async (): Promise<void> => {
  if (
    paginationInfo.value.isLoading ||
    paginationInfo.value.page >= paginationInfo.value.total_pages
  ) {
    return;
  }

  try {
    await stateStore.loadPaginated(
      'history',
      paginationInfo.value.page + 1,
      config.app.default_pagination,
      'DESC',
      true,
    );
  } catch (error) {
    console.error('Failed to load more history:', error);
    toast.error('Failed to load more history');
  }
};

// Setup intersection observer for infinite scroll
useIntersectionObserver(
  loadMoreTrigger,
  ([entry]) => {
    if (!socket.isConnected) {
      return;
    }
    if (
      entry?.isIntersecting &&
      !paginationInfo.value.isLoading &&
      paginationInfo.value.page < paginationInfo.value.total_pages
    ) {
      loadMoreHistory();
    }
  },
  { threshold: 0.5 },
);

watch(showCompleted, async (isShown) => {
  if (isShown && !paginationInfo.value.isLoaded && socket.isConnected) {
    try {
      await stateStore.loadPaginated('history', 1, config.app.default_pagination, 'DESC', true);
    } catch (error) {
      console.error('Failed to load history:', error);
    }
  }
});

onMounted(async () => {
  if (showCompleted.value && !paginationInfo.value.isLoaded) {
    try {
      await stateStore.loadPaginated('history', 1, config.app.default_pagination, 'DESC', true);
    } catch (error) {
      console.error('Failed to load history on mount:', error);
      toast.error('Failed to load history');
    }
  }
});

watch(
  () => socket.isConnected,
  async (connected) => {
    if (connected && showCompleted.value && !paginationInfo.value.isLoaded) {
      try {
        await stateStore.loadPaginated('history', 1, config.app.default_pagination, 'DESC', true);
      } catch (error) {
        console.error('Failed to load history after socket connection:', error);
      }
    }
  },
);

const showThumbnails = computed(() => (props.thumbnails ?? true) && !hideThumbnail.value);

const playVideo = (item: StoreItem) => {
  video_item.value = item;
};
const closeVideo = () => {
  video_item.value = null;
};

const filteredItems = (items: StoreItem[]) => (!props.query ? items : items.filter(filterItem));

const filterItem = (item: StoreItem) => {
  const q = props.query?.toLowerCase();
  if (!q) {
    return true;
  }
  return deepIncludes(item, q, new WeakSet());
};

const sortCompleted = computed(() => {
  const thisDirection = direction.value;
  return Object.values(stateStore.history as Record<string, StoreItem>).sort((a, b) => {
    if ('asc' === thisDirection) {
      return new Date(a.datetime).getTime() - new Date(b.datetime).getTime();
    }
    return new Date(b.datetime).getTime() - new Date(a.datetime).getTime();
  });
});

const displayedItems = computed(() => filteredItems(sortCompleted.value as StoreItem[]));

const hasSelected = computed(() => selectedElms.value.length > 0);
const hasItems = computed(() => displayedItems.value.length > 0);

const displayedItemIds = computed(() => displayedItems.value.map((item) => item._id));

const selectedDownloadableCount = computed(() =>
  selectedElms.value.reduce((count, itemId) => {
    const item = stateStore.get('history', itemId, {} as StoreItem) as StoreItem;
    return item?.filename ? count + 1 : count;
  }, 0),
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

const toggleDirection = () => {
  direction.value = direction.value === 'desc' ? 'asc' : 'desc';
};

watch(
  displayedItemIds,
  (ids) => {
    if (!masterSelectAll.value) {
      return;
    }
    selectedElms.value = [...ids];
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

const showRetryAction = (item: StoreItem): boolean => !item.filename && !isDownloadSkipped(item);

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [
    [
      {
        label: 'Download',
        icon: 'i-lucide-download',
        disabled: !hasSelected.value || selectedDownloadableCount.value < 1,
        onSelect: () => void downloadSelected(),
      },
      {
        label: config.app.remove_files ? 'Remove' : 'Clear',
        icon: 'i-lucide-trash',
        disabled: !hasSelected.value,
        onSelect: () => void deleteSelectedItems(),
      },
    ],
  ];

  const cleanupActions: Array<Record<string, unknown>> = [];

  if (hasCompleted.value) {
    cleanupActions.push({
      label: 'Clear Completed',
      icon: 'i-lucide-circle-check-big',
      onSelect: () => void clearCompleted(),
    });
  }

  if (hasIncomplete.value) {
    cleanupActions.push(
      {
        label: 'Clear Incomplete',
        icon: 'i-lucide-circle-x',
        onSelect: () => void clearIncomplete(),
      },
      {
        label: 'Retry Incomplete',
        icon: 'i-lucide-rotate-cw',
        onSelect: () => void retryIncomplete(),
      },
    );
  }

  if (cleanupActions.length > 0) {
    groups.push(cleanupActions);
  }

  return groups;
});

const itemActionGroups = (item: StoreItem) => {
  const groups: Array<Array<Record<string, unknown>>> = [];
  const mediaActions: Array<Record<string, unknown>> = [];

  if (item.filename) {
    mediaActions.push({
      label: 'Play video',
      icon: 'i-lucide-play',
      onSelect: () => playVideo(item),
    });

    if ('error' === item.status) {
      mediaActions.push({
        label: 'Retry download',
        icon: 'i-lucide-rotate-cw',
        onSelect: () => void retryItem(item, true),
      });
    }

    mediaActions.push({
      label: 'Generate NFO',
      icon: 'i-lucide-file-code-2',
      onSelect: () => void generateNfo(item),
    });
  } else if (isEmbedable(item.url)) {
    mediaActions.push({
      label: 'Play video',
      icon: 'i-lucide-play',
      onSelect: () => {
        embed_url.value = getEmbedable(item.url) as string;
      },
    });
  }

  if (mediaActions.length > 0) {
    groups.push(mediaActions);
  }

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
    {
      label: 'Add to download form',
      icon: 'i-lucide-copy',
      onSelect: () => void retryItem(item, true),
    },
  ]);

  if (item.is_archivable && !item.is_archived) {
    groups.push([
      {
        label: 'Add to archive',
        icon: 'i-lucide-archive',
        onSelect: () => addArchiveDialog(item),
      },
    ]);
  }

  if (item.is_archivable && item.is_archived) {
    groups.push([
      {
        label: 'Remove from archive',
        icon: 'i-lucide-archive-x',
        onSelect: () => removeFromArchiveDialog(item),
      },
    ]);
  }

  return groups;
};

const showMessage = (item: StoreItem) => {
  if (!item?.msg || item.msg === item?.error) {
    return false;
  }
  return (item.msg?.length || 0) > 0;
};

const hasIncomplete = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false;
  }
  for (const key in stateStore.history) {
    const element = stateStore.history[key] as StoreItem;
    if (element.status !== 'finished') {
      return true;
    }
  }
  return false;
});

const hasCompleted = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false;
  }
  for (const key in stateStore.history) {
    const element = stateStore.history[key] as StoreItem;
    if (element.status === 'finished') {
      return true;
    }
  }
  return false;
});

const deleteSelectedItems = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.');
    return;
  }

  let msg = `${config.app.remove_files ? 'Remove' : 'Clear'} '${selectedElms.value.length}' items?`;
  if (true === config.app.remove_files) {
    msg += ' This will remove any associated files if they exists.';
  }

  if (false === (await box.confirm(msg))) {
    return;
  }

  await stateStore.removeItems('history', [...selectedElms.value], config.app.remove_files);
  selectedElms.value = [];
};

const clearCompleted = async () => {
  const msg = 'Clear all completed downloads? No files will be removed.';
  if (false === (await box.confirm(msg))) {
    return;
  }
  selectedElms.value = [];
  Promise.all([
    stateStore.deleteItems('history', { status: 'finished', removeFile: false }),
    stateStore.deleteItems('history', { status: 'skip', removeFile: false }),
  ]);
};

const clearIncomplete = async () => {
  if (false === (await box.confirm('Clear all in-complete downloads?'))) {
    return;
  }
  selectedElms.value = [];
  await stateStore.deleteItems('history', { status: '!finished', removeFile: false });
};

const setIcon = (item: StoreItem) => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'i-lucide-ban';
    }
    if (!item.filename) {
      return 'i-lucide-triangle-alert';
    }
    if (item.extras?.is_premiere) {
      return 'i-lucide-star';
    }
    return item.is_live ? 'i-lucide-globe' : 'i-lucide-circle-check-big';
  }
  if ('error' === item.status) {
    return 'i-lucide-circle-x';
  }
  if ('cancelled' === item.status) {
    return 'i-lucide-circle-off';
  }
  if ('not_live' === item.status) {
    return item.extras?.is_premiere ? 'i-lucide-star' : 'i-lucide-headphones';
  }
  if ('skip' === item.status) {
    return 'i-lucide-ban';
  }
  return 'i-lucide-circle';
};

const setIconColor = (item: StoreItem) => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'text-info';
    }
    if (!item.filename) {
      return 'text-warning';
    }
    return 'text-success';
  }
  if ('not_live' === item.status) {
    return 'text-info';
  }
  if ('cancelled' === item.status || 'skip' === item.status) {
    return 'text-warning';
  }

  if ('error' === item.status && item.filename) {
    return 'text-warning';
  }

  return 'text-error';
};

const setStatus = (item: StoreItem) => {
  if ('finished' === item.status) {
    if (isDownloadSkipped(item)) {
      return 'Download skipped';
    }
    if (item.extras?.is_premiere) {
      return 'Premiered';
    }
    return item.is_live ? 'Streamed' : 'Completed';
  }
  if ('error' === item.status) {
    if (item.filename) {
      return 'Partial Error';
    }
    return 'Error';
  }
  if ('cancelled' === item.status) {
    return 'Cancelled';
  }
  if ('not_live' === item.status) {
    if (item.extras?.is_premiere) {
      return 'Premiere';
    }
    return 'Live';
  }
  if ('skip' === item.status) {
    return 'Skipped';
  }
  return item.status;
};

const retryIncomplete = async () => {
  if (false === (await box.confirm('Retry all incomplete downloads?'))) {
    return false;
  }
  for (const key in stateStore.history) {
    const item = stateStore.get('history', key, {} as StoreItem) as StoreItem;
    if ('finished' === item.status) {
      continue;
    }
    await retryItem(item);
  }
};

const addArchiveDialog = async (item: StoreItem): Promise<void> => {
  const { status, value } = await confirmDialog({
    title: 'Archive Item',
    message: `Archive '${item.title || item.id || item.url || '??'}'?`,
    confirmText: 'Archive',
    confirmColor: 'warning',
    options: [{ key: 'remove_history', label: 'Also, Remove from history.' }],
  });

  if (!status) {
    return;
  }

  await archiveItem(item, value ?? undefined);
};

const archiveItem = async (item: StoreItem, opts = {}) => {
  try {
    const req = await request(`/api/history/${item._id}/archive`, { method: 'POST' });
    const data = await req.json();
    if (!req.ok) {
      toast.error(data.error);
      return;
    }
    toast.success(data.message ?? `Archived '${item.title || item.id || item.url || '??'}'.`);
  } catch (e: any) {
    console.error(e);
  }
  if (!(opts as any)?.remove_history) {
    return;
  }
  await stateStore.removeItems('history', [item._id], false);
};

const removeItem = async (item: StoreItem) => {
  let msg = `${config.app.remove_files ? 'Remove' : 'Clear'} '${item.title || item.id || item.url || '??'}'?`;
  if (item.status === 'finished' && config.app.remove_files) {
    msg += ' This will remove any associated files if they exists.';
  }
  if (false === (await box.confirm(msg))) {
    return false;
  }

  socket.emit('item_delete', {
    id: item._id,
    remove_file: config.app.remove_files,
  });

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((i) => i !== item._id);
  }
};

const retryItem = async (
  item: StoreItem,
  re_add: boolean = false,
  remove_file: boolean = false,
) => {
  const item_req: item_request = {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    cookies: item.cookies,
    template: item.template,
    cli: item?.cli,
    extras: toRaw(item?.extras || {}) ?? {},
    auto_start: item.auto_start,
  };

  await stateStore.removeItems('history', [item._id], remove_file);

  if (selectedElms.value.includes(item._id || '')) {
    selectedElms.value = selectedElms.value.filter((i) => i !== item._id);
  }

  if (true === re_add) {
    toast.info('Cleared the item from history, and added it to the new download form.');
    emitter('add_new', item_req);
    return;
  }
  await stateStore.addDownload(item_req);
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

watch(video_item, (v) => {
  if (!bg_enable.value) {
    return;
  }
  document.querySelector('body')?.setAttribute('style', `opacity: ${v ? 1 : bg_opacity.value}`);
});

watch(embed_url, (v) => {
  if (!bg_enable.value) {
    return;
  }
  document.querySelector('body')?.setAttribute('style', `opacity: ${v ? 1 : bg_opacity.value}`);
});

const downloadSelected = async () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.');
    return;
  }
  const files_list: string[] = [];
  for (const key in selectedElms.value) {
    const item_id = selectedElms.value[key];
    if (!item_id) {
      continue;
    }
    const item = stateStore.get('history', item_id, {} as StoreItem) as StoreItem;
    if (!item.filename) {
      continue;
    }
    files_list.push(item.folder ? item.folder + '/' + item.filename : item.filename);
  }
  selectedElms.value = [];
  try {
    const response = await request('/api/file/download', {
      method: 'POST',
      body: JSON.stringify(files_list),
    });
    const json = await response.json();
    if (!response.ok) {
      toast.error(json.error || 'Failed to start download.');
      return;
    }
    const token = json.token;
    const body = document.querySelector('body');
    const link = document.createElement('a');
    link.href = uri(`/api/file/download/${token}`);
    link.setAttribute('target', '_blank');
    body?.appendChild(link);
    link.click();
    body?.removeChild(link);
  } catch (e: any) {
    console.error(e);
    toast.error(`Error: ${e.message}`);
    return;
  }
};

const toggleMessage = (itemId: string, field: 'error' | 'msg', view: 'list' | 'card') => {
  const key = `${itemId}:${view}`;

  if (!expandedMessages[key]) {
    expandedMessages[key] = new Set();
  }

  if (expandedMessages[key].has(field)) {
    expandedMessages[key].delete(field);
    return;
  }

  expandedMessages[key].add(field);
};

const isMessageExpanded = (itemId: string, field: 'error' | 'msg', view: 'list' | 'card') =>
  expandedMessages[`${itemId}:${view}`]?.has(field) ?? false;

const messageClass = (
  itemId: string,
  field: 'error' | 'msg',
  view: 'list' | 'card',
  spacingClass = '',
) => {
  const expanded = isMessageExpanded(itemId, field, view);
  const base = ['cursor-pointer', 'text-sm', 'text-error'];

  if (spacingClass) {
    base.push(spacingClass);
  }

  if ('card' === view) {
    base.push(expanded ? 'whitespace-pre-wrap break-words' : 'line-clamp-2 break-words');
    return base;
  }

  base.push(expanded ? 'whitespace-pre-wrap break-words' : 'block max-w-full truncate');
  return base;
};

const removeFromArchiveDialog = async (item: StoreItem): Promise<void> => {
  const options = [
    { key: 'remove_history', label: 'Remove from history.' },
    { key: 're_add', label: 'Re-add to download form.' },
  ];

  if (config.app.remove_files) {
    options.push({ key: 'dont_remove_file', label: "Don't remove associated files." });
  }

  const { status, value } = await confirmDialog({
    title: 'Remove from Archive',
    message: `Remove '${item.title || item.id || item.url || '??'}' from archive?`,
    confirmText: 'Remove',
    confirmColor: 'error',
    options,
  });

  if (!status) {
    return;
  }

  await removeFromArchive(item, value ?? undefined);
};

const removeFromArchive = async (
  item: StoreItem,
  opts?: { re_add?: boolean; remove_history?: boolean; dont_remove_file?: boolean },
) => {
  try {
    const req = await request(`/api/history/${item._id}/archive`, { method: 'DELETE' });
    const data = await req.json();
    if (!req.ok) {
      toast.error(data.error);
    } else {
      toast.success(
        data.message || `Removed '${item.title || item.id || item.url || '??'}' from archive.`,
      );
    }
  } catch (e: any) {
    console.error(e);
    toast.error(`Error: ${e.message}`);
  }

  let file_delete = config.app.remove_files;
  if (opts?.dont_remove_file) {
    file_delete = false;
  }

  if (opts?.re_add) {
    await retryItem(item, true, file_delete);
    return;
  }

  if (opts?.remove_history) {
    await stateStore.removeItems('history', [item._id], file_delete);
  }
};

const isQueuedAnimation = (item: StoreItem) => {
  if (!item?.status || 'not_live' !== item.status) {
    return '';
  }
  return item.live_in || item.extras?.live_in || item.extras?.release_in ? 'animate-spin' : '';
};

const generateNfo = async (item: StoreItem) => {
  try {
    toast.info('Generating please wait...', { timeout: 2000 });
    const response = await request(`/api/history/${item._id}/nfo`, {
      method: 'POST',
      body: JSON.stringify({ type: 'tv', overwrite: true }),
    });
    const data = await response.json();
    if (!response.ok) {
      toast.error(data.error || 'Failed to generate NFO');
      return;
    }
    toast.success(data.message || 'NFO file generated');
  } catch (e: any) {
    toast.error(`Error: ${e.message}`);
  }
};
</script>
