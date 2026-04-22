<template>
  <div class="space-y-6">
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
          color="neutral"
          :variant="toggleFilter ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-filter"
          @click="toggleFilter = !toggleFilter"
        >
          <span>Filter</span>
        </UButton>

        <UButton
          v-if="false === config.paused"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-pause"
          @click="() => void pauseDownload()"
        >
          <span>Pause</span>
        </UButton>

        <UButton
          v-else
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-play"
          @click="() => void resumeDownload()"
        >
          <span>Resume</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="config.showForm = !config.showForm"
        >
          <span>Add</span>
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          :icon="display_style === 'list' ? 'i-lucide-list' : 'i-lucide-grid-2x2'"
          class="hidden sm:inline-flex"
          @click="changeDisplay"
        >
          <span class="hidden sm:inline">{{ display_style === 'list' ? 'List' : 'Grid' }}</span>
        </UButton>

        <UInput
          v-if="toggleFilter"
          id="filter"
          v-model.lazy="query"
          type="search"
          placeholder="Filter displayed content"
          icon="i-lucide-filter"
          size="sm"
          class="order-last w-full sm:order-first sm:w-80"
        />
      </div>
    </div>

    <div v-if="config.showForm" ref="formSection" class="page-form-wrap scroll-mt-24">
      <NewDownload
        :item="item_form"
        @clear_form="item_form = {}"
        @getInfo="
          (url: string, preset: string = '', cli: string = '') => view_info(url, false, preset, cli)
        "
      />
    </div>

    <UEmpty
      v-if="!hasQueueContent"
      icon="i-lucide-triangle-alert"
      title="No active or queued downloads yet"
      class="rounded-lg border border-dashed border-default bg-muted/10 py-10"
    />

    <section v-else id="queue" class="scroll-mt-24 space-y-4">
      <div class="w-full min-w-0 max-w-full space-y-4">
        <div v-if="!socket.isConnected" class="flex justify-end">
          <UButton
            color="info"
            variant="outline"
            size="sm"
            icon="i-lucide-refresh-cw"
            :loading="isRefreshing"
            @click="() => void refreshQueue()"
          >
            Refresh
          </UButton>
        </div>

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
                <UIcon name="i-lucide-list-ordered" class="size-3.5" />
                <span>Total: {{ stateStore.count() }}</span>
              </span>
            </UBadge>
          </div>
        </div>

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
                  <th class="w-full text-left">Video Title</th>
                  <th class="w-56">Progress</th>
                  <th class="w-32 whitespace-nowrap">Status</th>
                  <th class="w-36 whitespace-nowrap">Created</th>
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

                  <td class="border-r border-default/60 px-3 py-3 align-top">
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
                        <UBadge
                          v-if="item.downloaded_bytes"
                          color="neutral"
                          variant="soft"
                          size="sm"
                        >
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
                                  <p class="text-sm font-semibold text-highlighted">
                                    {{ item.title }}
                                  </p>
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

                  <td class="w-56 border-r border-default/60 px-3 py-3 align-top">
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
                              ['i-lucide-settings-2', 'i-lucide-loader-circle'].includes(
                                progressIcon(item),
                              )
                                ? 'animate-spin'
                                : '',
                            ]"
                          />
                        </template>
                        <span>{{ progressText(item) }}</span>
                      </div>
                    </div>
                  </td>

                  <td class="border-r border-default/60 px-3 py-3 text-center align-top text-sm">
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

                  <td
                    class="border-r border-default/60 px-3 py-3 text-center align-top text-sm text-toned whitespace-nowrap"
                  >
                    <UTooltip :text="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                      <span :data-datetime="item.datetime" v-rtime="item.datetime" />
                    </UTooltip>
                  </td>

                  <td class="w-80 px-3 py-3 align-top whitespace-nowrap">
                    <div class="flex items-center justify-end gap-1">
                      <UButton
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-circle-off"
                        @click="() => void confirmCancel(item)"
                      >
                        {{ item.is_live ? 'Stop Stream' : 'Cancel' }}
                      </UButton>

                      <UButton
                        v-if="canStartItem(item)"
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-circle-play"
                        @click="() => void startItem(item)"
                      >
                        Start
                      </UButton>

                      <UButton
                        v-if="canPauseItem(item)"
                        color="neutral"
                        variant="outline"
                        size="xs"
                        icon="i-lucide-pause"
                        @click="() => void pauseItem(item)"
                      >
                        Pause
                      </UButton>

                      <UDropdownMenu :items="itemActionGroups(item)" :modal="false">
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
                      v-if="show_thumbnail"
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

              <div class="flex flex-wrap gap-2 text-sm *:min-w-32 *:flex-1">
                <button
                  type="button"
                  class="rounded-md border border-default bg-muted/20 px-3 py-2 text-default transition hover:border-primary hover:text-default"
                  @click="toggleExpand(item._id, 'status')"
                >
                  <span class="inline-flex w-full items-center justify-center gap-2">
                    <UIcon
                      :name="setIcon(item)"
                      :class="[setIconColor(item), setIconAnimation(item), 'size-4 shrink-0']"
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
                  type="button"
                  class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                  @click="toggleExpand(item._id, 'datetime')"
                >
                  <UTooltip :text="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                    <span class="inline-flex w-full items-center justify-center gap-2">
                      <UIcon name="i-lucide-clock-3" class="size-4 shrink-0 text-toned" />
                      <span
                        :class="['min-w-0 text-center', expandClass(item._id, 'datetime')]"
                        :data-datetime="item.datetime"
                        v-rtime="item.datetime"
                      />
                    </span>
                  </UTooltip>
                </button>

                <button
                  v-if="item.downloaded_bytes"
                  type="button"
                  class="rounded-md border border-default bg-muted/20 px-3 py-2 text-toned transition hover:border-primary hover:text-default"
                  @click="toggleExpand(item._id, 'size')"
                >
                  <span class="inline-flex w-full items-center justify-center gap-2">
                    <UIcon name="i-lucide-hard-drive" class="size-4 shrink-0 text-toned" />
                    <span :class="['min-w-0 text-center', expandClass(item._id, 'size')]">
                      {{ formatBytes(item.downloaded_bytes) }}
                    </span>
                  </span>
                </button>
              </div>

              <template #footer>
                <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
                  <UButton
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-circle-off"
                    class="w-full justify-center"
                    @click="() => void confirmCancel(item)"
                  >
                    {{ item.is_live ? 'Stop Stream' : 'Cancel' }}
                  </UButton>

                  <UButton
                    v-if="canStartItem(item)"
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-circle-play"
                    class="w-full justify-center"
                    @click="() => void startItem(item)"
                  >
                    Start
                  </UButton>

                  <UButton
                    v-if="canPauseItem(item)"
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-pause"
                    class="w-full justify-center"
                    @click="() => void pauseItem(item)"
                  >
                    Pause
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
                  You can search using any value shown in the item's <code>Local Information</code>.
                  You can also do a targeted search using <code><u>key</u>:value</code>.
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
    </section>

    <GetInfo
      v-if="info_view.url"
      :link="info_view.url"
      :preset="info_view.preset"
      :cli="info_view.cli"
      :useUrl="info_view.useUrl"
      @closeModel="close_info()"
    />
  </div>
</template>

<script setup lang="ts">
import moment from 'moment';
import { useStorage } from '@vueuse/core';
import { useConfirm } from '~/composables/useConfirm';
import { useDialog } from '~/composables/useDialog';
import { useExpandableMeta } from '~/composables/useExpandableMeta';
import { useMediaQuery } from '~/composables/useMediaQuery';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import {
  ag,
  deepIncludes,
  formatBytes,
  formatTime,
  getImage,
  getPath,
  request,
  ucFirst,
} from '~/utils';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import { requirePageShell } from '~/utils/topLevelNavigation';

const config = useYtpConfig();
const stateStore = useQueueState();
const socket = useAppSocket();
const route = useRoute();
const toast = useNotification();
const box = useConfirm();
const { confirmDialog } = useDialog();
const { toggleExpand, expandClass } = useExpandableMeta();
const pendingDownloadFormItem = useState<item_request | Record<string, never>>(
  'pending-download-form-item',
  () => ({}),
);

const bg_enable = useStorage<boolean>('random_bg', true);
const bg_opacity = useStorage<number>('random_bg_opacity', 0.95);
const display_style = useStorage<'grid' | 'list'>('queue_display_style', 'grid');
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const hideThumbnail = useStorage<boolean>('hideThumbnailQueue', false);
const thumbnail_ratio = useStorage<'is-16by9' | 'is-3by1'>('thumbnail_ratio', 'is-3by1');
const show_popover = useStorage<boolean>('show_popover', true);
const autoRefreshEnabled = useStorage<boolean>('queue_auto_refresh', true);
const autoRefreshDelay = useStorage<number>('queue_auto_refresh_delay', 10000);
const isMobile = useMediaQuery({ maxWidth: 639 });

const pageShell = requirePageShell('downloads');
const formSection = ref<HTMLElement | null>(null);
const info_view = ref<{ url: string; preset: string; cli: string; useUrl: boolean }>({
  url: '',
  preset: '',
  cli: '',
  useUrl: false,
});
const item_form = ref<item_request | object>({});
const query = ref('');
const toggleFilter = ref(false);
const selectedElms = ref<string[]>([]);
const masterSelectAll = ref(false);
const embed_url = ref('');
const isRefreshing = ref(false);
const autoRefreshInterval = ref<ReturnType<typeof setInterval> | null>(null);

const hasQueueContent = computed(() => stateStore.count() > 0 || query.value.trim().length > 0);
const contentStyle = computed<'grid' | 'list'>(() =>
  isMobile.value ? 'grid' : display_style.value,
);
const showThumbnails = computed(() => show_thumbnail.value && !hideThumbnail.value);

const displayedItems = computed<StoreItem[]>(() => {
  const normalizedQuery = query.value.trim().toLowerCase();
  const items = Object.values(stateStore.queue);

  if (!normalizedQuery) {
    return items;
  }

  return items.filter((item) => deepIncludes(item, normalizedQuery, new WeakSet()));
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

const refreshQueue = async (): Promise<void> => {
  if (isRefreshing.value) {
    return;
  }

  isRefreshing.value = true;

  try {
    await stateStore.loadQueue();
  } catch {
    toast.error('Failed to refresh queue');
  } finally {
    isRefreshing.value = false;
  }
};

const startAutoRefresh = (): void => {
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

const stopAutoRefresh = (): void => {
  if (!autoRefreshInterval.value) {
    return;
  }

  clearInterval(autoRefreshInterval.value);
  autoRefreshInterval.value = null;
};

onMounted(async () => {
  if (route.query?.simple !== undefined) {
    const simpleMode = useStorage<boolean>('simple_mode', config.app.simple_mode || false);
    simpleMode.value = ['true', '1', 'yes', 'on'].includes(route.query.simple as string);
    await nextTick();
    const url = new URL(window.location.href);
    url.searchParams.delete('simple');
    window.history.replaceState({}, '', url.toString());
  }

  if (Object.keys(pendingDownloadFormItem.value).length > 0) {
    await toNewDownload(pendingDownloadFormItem.value);
    pendingDownloadFormItem.value = {};
  }

  if (!socket.isConnected && autoRefreshEnabled.value) {
    startAutoRefresh();
  }
});

onBeforeUnmount(() => stopAutoRefresh());

watch(toggleFilter, () => {
  if (!toggleFilter.value) {
    query.value = '';
  }
});

watch(
  () => socket.isConnected,
  (connected) => {
    if (connected) {
      stopAutoRefresh();
      return;
    }

    if (autoRefreshEnabled.value) {
      startAutoRefresh();
    }
  },
);

watch(autoRefreshEnabled, (enabled) => {
  if (enabled && !socket.isConnected) {
    startAutoRefresh();
    return;
  }

  stopAutoRefresh();
});

watch(autoRefreshDelay, () => {
  if (autoRefreshEnabled.value && !socket.isConnected) {
    startAutoRefresh();
  }
});

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

watch(
  () => info_view.value.url,
  (value) => {
    if (!bg_enable.value) {
      return;
    }

    document
      .querySelector('body')
      ?.setAttribute('style', `opacity: ${value ? 1 : bg_opacity.value}`);
  },
);

watch(embed_url, (value) => {
  if (!bg_enable.value) {
    return;
  }

  document.querySelector('body')?.setAttribute('style', `opacity: ${value ? 1 : bg_opacity.value}`);
});

const toggleMasterSelection = (): void => {
  if (masterSelectAll.value) {
    selectedElms.value = [];
    masterSelectAll.value = false;
    return;
  }

  selectedElms.value = [...displayedItemIds.value];
  masterSelectAll.value = true;
};

const resumeDownload = async (): Promise<void> => {
  await request('/api/system/resume', { method: 'POST' });
};

const pauseDownload = async (): Promise<void> => {
  const { status } = await confirmDialog({
    title: 'Pause Downloads',
    confirmText: 'Pause',
    cancelText: 'Cancel',
    confirmColor: 'warning',
    message: 'Are you sure you want to pause all non-active downloads?',
  });

  if (!status) {
    return;
  }

  await request('/api/system/pause', { method: 'POST' });
};

const close_info = (): void => {
  info_view.value.url = '';
  info_view.value.preset = '';
  info_view.value.cli = '';
  info_view.value.useUrl = false;
};

const view_info = (
  url: string,
  useUrl: boolean = false,
  preset: string = '',
  cli: string = '',
): void => {
  info_view.value.url = url;
  info_view.value.useUrl = useUrl;
  info_view.value.preset = preset;
  info_view.value.cli = cli;
};

const changeDisplay = (): void => {
  display_style.value = display_style.value === 'grid' ? 'list' : 'grid';
};

const toNewDownload = async (item: item_request | Partial<StoreItem>): Promise<void> => {
  if (!item) {
    return;
  }

  if (config.showForm) {
    config.showForm = false;
    await nextTick();
  }

  item_form.value = item;

  await nextTick();
  config.showForm = true;
  await nextTick();
  formSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const getItemPath = (item: StoreItem): string => getPath(config.app.download_path, item) || '';
const getListImage = (item: StoreItem): string =>
  getImage(config.app.download_path, item, false) || '';
const getGridImage = (item: StoreItem): string => getImage(config.app.download_path, item) || '';
const canStartItem = (item: StoreItem): boolean => !item.auto_start && !item.status;
const canPauseItem = (item: StoreItem): boolean => item.auto_start && !item.status;

const bulkActionGroups = computed(() => {
  const groups: Array<Array<Record<string, unknown>>> = [[]];
  const selectedLiveOnly =
    selectedElms.value.length > 0 &&
    selectedElms.value.every((id) => {
      const item = stateStore.get(id);
      return Boolean(item?.is_live);
    });

  if (hasManualStart.value) {
    groups[0]?.push({
      label: 'Start',
      icon: 'i-lucide-circle-play',
      disabled: !hasSelected.value,
      onSelect: () => void startItems(),
    });
  }

  if (hasPausable.value) {
    groups[0]?.push({
      label: 'Pause',
      icon: 'i-lucide-pause',
      disabled: !hasSelected.value,
      onSelect: () => void pauseSelected(),
    });
  }

  groups[0]?.push({
    label: selectedLiveOnly ? 'Stop' : 'Cancel',
    icon: 'i-lucide-circle-off',
    disabled: !hasSelected.value,
    onSelect: () => void cancelSelected(),
  });

  return groups;
});

const itemActionGroups = (item: StoreItem): Array<Array<Record<string, unknown>>> => {
  const groups: Array<Array<Record<string, unknown>>> = [];
  const primaryActions: Array<Record<string, unknown>> = [];

  if (isEmbedable(item.url)) {
    primaryActions.push({
      label: 'Play video',
      icon: 'i-lucide-play',
      onSelect: () => {
        embed_url.value = getEmbedable(item.url) as string;
      },
    });
  }

  primaryActions.push({
    label: item.is_live ? 'Stop Stream' : 'Cancel Download',
    icon: 'i-lucide-circle-off',
    onSelect: () => void confirmCancel(item),
  });

  if (canStartItem(item)) {
    primaryActions.push({
      label: 'Start Download',
      icon: 'i-lucide-circle-play',
      onSelect: () => void startItem(item),
    });
  }

  if (canPauseItem(item)) {
    primaryActions.push({
      label: 'Pause Download',
      icon: 'i-lucide-pause',
      onSelect: () => void pauseItem(item),
    });
  }

  groups.push(primaryActions);

  groups.push([
    {
      label: 'yt-dlp Information',
      icon: 'i-lucide-info',
      onSelect: () => view_info(item.url, false, item.preset, item.cli),
    },
    {
      label: 'Local Information',
      icon: 'i-lucide-info',
      onSelect: () => view_info(`/api/history/${item._id}`, true),
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
  if (null != item.status && item.is_live && !item.speed) {
    return 'i-lucide-loader-circle';
  }

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

  if (null != item.status && item.is_live && !item.speed) {
    return 'Recording live stream';
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

const confirmCancel = async (item: StoreItem): Promise<boolean> => {
  if (true !== (await box.confirm(`${item.is_live ? 'Stop' : 'Cancel'} '${item.title}'?`))) {
    return false;
  }

  cancelItems(item._id);
  return true;
};

const cancelSelected = async (): Promise<boolean> => {
  const selectedLiveOnly =
    selectedElms.value.length > 0 &&
    selectedElms.value.every((id) => {
      const item = stateStore.get(id);
      return Boolean(item?.is_live);
    });

  if (
    true !==
    (await box.confirm(
      `${selectedLiveOnly ? 'Stop' : 'Cancel'} '${selectedElms.value.length}' selected items?`,
    ))
  ) {
    return false;
  }

  cancelItems(selectedElms.value);
  selectedElms.value = [];
  masterSelectAll.value = false;
  return true;
};

const cancelItems = (item: string | string[]): void => {
  const items = Array.isArray(item) ? [...item] : [item];

  if (items.length < 1) {
    return;
  }

  void stateStore.cancelItems(items);
};

const startItem = async (item: StoreItem): Promise<void> => await stateStore.startItems([item._id]);
const pauseItem = async (item: StoreItem): Promise<void> => await stateStore.pauseItems([item._id]);

const startItems = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get(id);
    return Boolean(item && !item.auto_start && !item.status);
  });

  selectedElms.value = [];

  if (eligible.length < 1) {
    toast.error('No eligible items to start.');
    return;
  }

  if (true !== (await box.confirm(`Start '${eligible.length}' selected items?`))) {
    return;
  }

  await stateStore.startItems(eligible);
};

const pauseSelected = async (): Promise<void> => {
  if (selectedElms.value.length < 1) {
    return;
  }

  const eligible = selectedElms.value.filter((id) => {
    const item = stateStore.get(id);
    return Boolean(item && item.auto_start && !item.status);
  });

  selectedElms.value = [];

  if (eligible.length < 1) {
    toast.error('No eligible items to pause.');
    return;
  }

  if (true !== (await box.confirm(`Pause '${eligible.length}' selected items?`))) {
    return;
  }

  await stateStore.pauseItems(eligible);
};

const pImg = (event: Event): void => {
  const target = event.target as HTMLImageElement;

  if (target.naturalHeight > target.naturalWidth) {
    target.classList.add('image-portrait');
  }
};

const onImgError = (event: Event): void => {
  const target = event.target as HTMLImageElement;

  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  target.src = '/images/placeholder.png';
};
</script>

<style scoped>
.page-form-wrap {
  max-width: 100%;
}

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
