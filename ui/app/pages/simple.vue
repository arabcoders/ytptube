<template>
  <div>
    <AppRoot mode="simple" @ready="init" v-slot="{ openSettings }">
      <div class="shell-stage shell-surface flex min-h-screen flex-col">
        <ConnectionBanner />

        <div
          class="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col gap-4 px-3 py-4 sm:px-4 sm:py-5"
        >
          <div
            class="pointer-events-none fixed inset-0 z-20 bg-black/45 backdrop-blur-[1px] transition-all duration-500 ease-out"
            :class="lightsOut ? 'opacity-100' : 'opacity-0'"
            aria-hidden="true"
          />

          <div class="transition-transform duration-300">
            <div class="mx-auto w-full transition-all duration-300" :class="formContainerClass">
              <div class="ytp-card p-4 sm:p-5">
                <form autocomplete="off" class="space-y-4" @submit.prevent="addDownload">
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0 space-y-1">
                      <div class="flex items-center gap-2 text-base font-semibold text-highlighted">
                        <UIcon name="i-lucide-link" class="size-4 text-toned" />
                        <span>{{
                          isMobile ? 'What would you like to download?' : greetingMessage
                        }}</span>
                      </div>
                    </div>

                    <div class="flex shrink-0 items-center gap-1 sm:gap-2">
                      <UTooltip v-if="!socketStore.isConnected" text="Reload queue">
                        <UButton
                          color="neutral"
                          variant="ghost"
                          size="sm"
                          icon="i-lucide-refresh-cw"
                          :loading="isRefreshing"
                          :disabled="isRefreshing"
                          :square="isMobile"
                          @click="() => refreshQueue()"
                        >
                          <span v-if="!isMobile">Reload Queue</span>
                        </UButton>
                      </UTooltip>

                      <ThemeButton :square="isMobile" :show-label="!isMobile" />

                      <UTooltip text="WebUI Settings">
                        <UButton
                          color="neutral"
                          variant="ghost"
                          size="sm"
                          icon="i-lucide-settings-2"
                          :square="isMobile"
                          @click="openSettings"
                        >
                          <span v-if="!isMobile">WebUI Settings</span>
                        </UButton>
                      </UTooltip>
                    </div>
                  </div>

                  <div class="flex items-stretch gap-2">
                    <UTooltip :text="showExtras ? 'Hide extra options' : 'Show extra options'">
                      <UButton
                        type="button"
                        color="neutral"
                        :variant="showExtras ? 'soft' : 'outline'"
                        size="lg"
                        :icon="showExtras ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                        class="shrink-0 justify-center w-12"
                        :disabled="addInProgress"
                        @click="showExtras = !showExtras"
                      />
                    </UTooltip>

                    <UInput
                      id="download-url"
                      v-model="formUrl"
                      type="url"
                      placeholder="https://..."
                      size="lg"
                      required
                      :disabled="isFormDisabled"
                      class="min-w-0 flex-1"
                      :ui="urlInputUi"
                    />

                    <UButton
                      type="submit"
                      color="primary"
                      size="lg"
                      icon="i-lucide-plus"
                      :loading="addInProgress"
                      :disabled="isFormDisabled || !formUrl.trim()"
                      class="shrink-0 justify-center min-w-20 sm:min-w-28"
                    >
                      Add
                    </UButton>
                  </div>

                  <div v-if="showExtras" class="space-y-3 ytp-border-top-soft pt-4">
                    <UFormField label="Preset" :ui="fieldUi" class="w-full">
                      <template #label>
                        <span class="inline-flex items-center gap-2 font-semibold">
                          <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
                          <span>Preset</span>
                        </span>
                      </template>

                      <USelectMenu
                        id="preset"
                        v-model="formPreset"
                        :items="presetItems"
                        value-key="value"
                        label-key="label"
                        color="neutral"
                        size="lg"
                        class="w-full"
                        :ui="{ content: 'min-w-[13rem]', item: 'pl-6' }"
                        :search-input="{ placeholder: 'Search presets' }"
                        :disabled="isFormDisabled"
                        placeholder="Select preset"
                      />
                    </UFormField>

                    <div
                      v-if="configStore.dl_fields.length > 0"
                      class="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
                    >
                      <DLInput
                        id="force_download"
                        v-model="dlFields['--no-download-archive']"
                        type="bool"
                        label="Force download"
                        icon="i-lucide-download"
                        :disabled="isFormDisabled"
                        description="Ignore archive and re-download."
                        compact
                      />

                      <DLInput
                        v-for="(fi, index) in sortedDLFields"
                        :id="fi?.id || `dlf-${index}`"
                        :key="fi.id || `dlf-${index}`"
                        v-model="dlFields[fi.field]"
                        :type="fi.kind"
                        :description="fi.description"
                        :label="fi.name"
                        :icon="fi.icon"
                        :field="fi.field"
                        :disabled="isFormDisabled"
                        compact
                      />
                    </div>
                  </div>
                </form>
              </div>
            </div>
          </div>

          <Transition name="queue-fade">
            <section v-if="showSections" class="w-full space-y-6">
              <section class="space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <button
                    type="button"
                    class="inline-flex items-center gap-2 text-sm font-semibold text-highlighted transition-colors hover:text-default"
                    :aria-expanded="!queueCollapsed"
                    aria-controls="simple-queue-section"
                    @click="queueCollapsed = !queueCollapsed"
                  >
                    <UIcon
                      :name="queueCollapsed ? 'i-lucide-chevron-right' : 'i-lucide-chevron-down'"
                      class="size-3.5 text-toned"
                    />
                    <UIcon name="i-lucide-list-video" class="size-4 text-toned" />
                    <span>Queue</span>
                  </button>

                  <div class="flex flex-wrap items-center gap-2">
                    <UBadge color="info" variant="soft" size="sm">{{ queueCountLabel }}</UBadge>

                    <UButton
                      v-if="stateStore.hasMore()"
                      color="neutral"
                      variant="outline"
                      size="xs"
                      :loading="isRefreshing"
                      @click="() => loadMoreQueue()"
                    >
                      Show more
                    </UButton>
                  </div>
                </div>

                <Transition name="section-collapse">
                  <div v-if="!queueCollapsed" id="simple-queue-section" class="overflow-hidden">
                    <TransitionGroup
                      v-if="queueItems.length > 0"
                      name="queue-card"
                      tag="div"
                      class="grid grid-cols-1 gap-3 lg:grid-cols-2"
                    >
                      <div
                        v-for="item in queueItems"
                        :key="`queue-${item._id}`"
                        class="ytp-card w-full min-w-0 max-w-full overflow-hidden"
                      >
                        <div class="p-4 pb-0 ytp-border-bottom-soft">
                          <div
                            v-if="downloadingStatuses.has(item.status) || item.status === null"
                            class="queue-progress rounded-md border border-default bg-muted/20"
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
                              <span>{{ updateProgress(item) }}</span>
                            </div>
                          </div>
                        </div>

                        <div class="p-4">
                          <div class="flex min-w-0 flex-col gap-4 sm:flex-row">
                            <figure
                              class="relative w-full shrink-0 overflow-hidden rounded-lg border border-default bg-muted/20 sm:w-52"
                            >
                              <span
                                v-if="item.filename || isEmbedable(item.url)"
                                class="play-overlay"
                                @click="openPlayer(item)"
                              >
                                <span
                                  :class="[
                                    'play-icon',
                                    isEmbedable(item.url) && !item.filename ? 'embed-icon' : '',
                                  ]"
                                  aria-hidden="true"
                                >
                                  <UIcon
                                    name="i-lucide-play"
                                    class="size-6 translate-x-px text-white"
                                  />
                                </span>
                                <img
                                  :src="resolveThumbnail(item)"
                                  :alt="item.title || 'Video thumbnail'"
                                  loading="lazy"
                                  class="aspect-video h-full w-full object-cover"
                                  @error="onImgError($event, item)"
                                />
                              </span>

                              <img
                                v-else
                                :src="resolveThumbnail(item)"
                                :alt="item.title || 'Video thumbnail'"
                                loading="lazy"
                                class="aspect-video h-full w-full object-cover"
                                @error="onImgError($event, item)"
                              />

                              <span
                                v-if="getDurationLabel(item)"
                                class="absolute top-2 right-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-medium text-white"
                              >
                                {{ getDurationLabel(item) }}
                              </span>
                            </figure>

                            <div class="min-w-0 flex-1 space-y-3">
                              <div class="space-y-2">
                                <UTooltip :text="item.title">
                                  <a
                                    :href="item.url"
                                    target="_blank"
                                    rel="noreferrer"
                                    class="block truncate text-sm font-semibold text-highlighted hover:underline"
                                  >
                                    {{ item.title || 'Untitled' }}
                                  </a>
                                </UTooltip>

                                <div class="flex flex-wrap items-center gap-2 text-xs">
                                  <UBadge
                                    :color="
                                      downloadingStatuses.has(item.status) ? 'info' : 'warning'
                                    "
                                    variant="soft"
                                    size="sm"
                                    class="gap-1"
                                  >
                                    <UIcon
                                      :name="getQueueIcon(item)"
                                      :class="['size-3.5', getStatusIconAnimation(item)]"
                                    />
                                    <span>{{
                                      downloadingStatuses.has(item.status) ? 'Active' : 'Queued'
                                    }}</span>
                                  </UBadge>

                                  <UBadge
                                    :color="getStatusColor(item)"
                                    variant="soft"
                                    size="sm"
                                    class="gap-1"
                                  >
                                    <UIcon
                                      :name="getStatusIcon(item)"
                                      :class="['size-3.5', getStatusIconAnimation(item)]"
                                    />
                                    <span>{{ getStatusLabel(item) }}</span>
                                  </UBadge>

                                  <span
                                    class="inline-flex items-center rounded-full border border-default px-2 py-0.5 text-toned"
                                    :date-datetime="item.datetime"
                                    v-rtime="item.datetime"
                                  />
                                </div>
                              </div>

                              <p class="line-clamp-3 text-xs leading-5 text-toned wrap-break-word">
                                <template v-if="item.error || showMessage(item)">
                                  <template v-if="item.error">
                                    <span class="text-error">{{ item.error }}</span>
                                  </template>
                                  <template v-if="showMessage(item)">
                                    <span class="text-error">{{ item.msg }}</span>
                                  </template>
                                </template>
                                <template v-else>
                                  {{ getDescription(item) || 'No description available.' }}
                                </template>
                              </p>

                              <div
                                class="mt-auto flex flex-wrap items-center justify-end gap-2 pt-1"
                              >
                                <UButton
                                  v-if="!item.status && item.auto_start === false"
                                  color="neutral"
                                  variant="soft"
                                  size="xs"
                                  icon="i-lucide-play-circle"
                                  @click="() => stateStore.startItems([item._id])"
                                >
                                  Start
                                </UButton>

                                <UButton
                                  v-if="!item.status && item.auto_start === true"
                                  color="neutral"
                                  variant="soft"
                                  size="xs"
                                  icon="i-lucide-pause"
                                  @click="() => stateStore.pauseItems([item._id])"
                                >
                                  Pause
                                </UButton>

                                <UButton
                                  color="neutral"
                                  variant="outline"
                                  size="xs"
                                  icon="i-lucide-x"
                                  @click="() => stateStore.cancelItems([item._id])"
                                >
                                  {{ item.is_live ? 'Stop' : 'Cancel' }}
                                </UButton>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </TransitionGroup>

                    <UAlert
                      v-else
                      color="neutral"
                      variant="soft"
                      icon="i-lucide-inbox"
                      title="Queue is empty"
                    />
                  </div>
                </Transition>
              </section>

              <section class="space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-3">
                  <button
                    type="button"
                    class="inline-flex items-center gap-2 text-sm font-semibold text-highlighted transition-colors hover:text-default"
                    :aria-expanded="!historyCollapsed"
                    aria-controls="simple-history-section"
                    @click="historyCollapsed = !historyCollapsed"
                  >
                    <UIcon
                      :name="historyCollapsed ? 'i-lucide-chevron-right' : 'i-lucide-chevron-down'"
                      class="size-3.5 text-toned"
                    />
                    <UIcon name="i-lucide-history" class="size-4 text-toned" />
                    <span>History</span>
                  </button>

                  <div v-if="!historyCollapsed" class="flex flex-wrap items-center gap-2">
                    <UPagination
                      v-if="historyPagination.total_pages > 1"
                      :page="historyPagination.page"
                      :total="historyPagination.total"
                      :items-per-page="historyPagination.per_page"
                      :disabled="historyIsLoading"
                      show-edges
                      size="sm"
                      :sibling-count="0"
                      @update:page="
                        (page) =>
                          load(page, {
                            order: 'DESC',
                            perPage: configStore.app.default_pagination,
                          })
                      "
                    />

                    <UButton
                      color="neutral"
                      variant="outline"
                      size="xs"
                      icon="i-lucide-refresh-cw"
                      :loading="historyIsLoading"
                      :disabled="historyIsLoading"
                      @click="
                        () => reload({ order: 'DESC', perPage: configStore.app.default_pagination })
                      "
                    >
                      Reload
                    </UButton>
                  </div>
                </div>

                <Transition name="section-collapse">
                  <div
                    v-if="!historyCollapsed"
                    id="simple-history-section"
                    class="space-y-3 overflow-hidden"
                  >
                    <div
                      v-if="historyEntries.length > 0"
                      class="grid grid-cols-1 gap-3 lg:grid-cols-2"
                    >
                      <div
                        v-for="item in historyEntries"
                        :key="`history-${historyPagination.page}-${item._id}`"
                        class="ytp-card w-full min-w-0 max-w-full overflow-hidden"
                      >
                        <div class="p-4">
                          <div class="flex min-w-0 flex-col gap-4 sm:flex-row">
                            <figure
                              class="relative w-full shrink-0 overflow-hidden rounded-lg border border-default bg-muted/20 sm:w-52"
                            >
                              <span
                                v-if="item.filename || isEmbedable(item.url)"
                                class="play-overlay"
                                @click="openPlayer(item)"
                              >
                                <span
                                  :class="[
                                    'play-icon',
                                    isEmbedable(item.url) && !item.filename ? 'embed-icon' : '',
                                  ]"
                                  aria-hidden="true"
                                >
                                  <UIcon
                                    name="i-lucide-play"
                                    class="size-6 translate-x-px text-white"
                                  />
                                </span>
                                <img
                                  :src="resolveThumbnail(item)"
                                  :alt="item.title || 'Video thumbnail'"
                                  loading="lazy"
                                  class="aspect-video h-full w-full object-cover"
                                  @error="onImgError($event, item)"
                                />
                              </span>

                              <img
                                v-else
                                :src="resolveThumbnail(item)"
                                :alt="item.title || 'Video thumbnail'"
                                loading="lazy"
                                class="aspect-video h-full w-full object-cover"
                                @error="onImgError($event, item)"
                              />

                              <span
                                v-if="getDurationLabel(item)"
                                class="absolute top-2 right-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-medium text-white"
                              >
                                {{ getDurationLabel(item) }}
                              </span>
                            </figure>

                            <div class="min-w-0 flex-1 space-y-3">
                              <div class="space-y-2">
                                <UTooltip :text="item.title">
                                  <a
                                    :href="item.url"
                                    target="_blank"
                                    rel="noreferrer"
                                    class="block truncate text-sm font-semibold text-highlighted hover:underline"
                                  >
                                    {{ item.title || 'Untitled' }}
                                  </a>
                                </UTooltip>

                                <div class="flex flex-wrap items-center gap-2 text-xs">
                                  <UBadge color="neutral" variant="soft" size="sm">History</UBadge>

                                  <UBadge
                                    :color="getStatusColor(item)"
                                    variant="soft"
                                    size="sm"
                                    class="gap-1"
                                  >
                                    <UIcon
                                      :name="getStatusIcon(item)"
                                      :class="['size-3.5', getStatusIconAnimation(item)]"
                                    />
                                    <span>{{ getStatusLabel(item) }}</span>
                                  </UBadge>

                                  <span
                                    class="inline-flex items-center rounded-full border border-default px-2 py-0.5 text-toned"
                                    :date-datetime="item.datetime"
                                    v-rtime="item.datetime"
                                  />
                                </div>
                              </div>

                              <p class="line-clamp-3 text-xs leading-5 text-toned wrap-break-word">
                                <template v-if="item.error || showMessage(item)">
                                  <template v-if="item.error">
                                    <span class="text-error">{{ item.error }}</span>
                                  </template>
                                  <template v-if="showMessage(item)">
                                    <span class="text-error">{{ item.msg }}</span>
                                  </template>
                                </template>
                                <template v-else>
                                  {{ getDescription(item) || 'No description available.' }}
                                </template>
                              </p>

                              <div
                                class="mt-auto flex flex-wrap items-center justify-end gap-2 pt-1"
                              >
                                <UButton
                                  v-if="getDownloadLink(item)"
                                  color="primary"
                                  variant="soft"
                                  size="xs"
                                  icon="i-lucide-download"
                                  external
                                  :href="getDownloadLink(item)"
                                  :download="getDownloadName(item)"
                                >
                                  Download
                                </UButton>

                                <UButton
                                  v-if="!item.filename"
                                  color="neutral"
                                  variant="soft"
                                  size="xs"
                                  icon="i-lucide-rotate-cw"
                                  @click="() => requeueItem(item)"
                                >
                                  Requeue
                                </UButton>

                                <UButton
                                  color="neutral"
                                  variant="outline"
                                  size="xs"
                                  icon="i-lucide-trash"
                                  @click="() => deleteHistoryItem(item)"
                                >
                                  Delete
                                </UButton>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <UAlert
                      v-else-if="historyIsLoading"
                      color="info"
                      variant="soft"
                      icon="i-lucide-loader-circle"
                      title="Loading history..."
                    />

                    <UAlert
                      v-else
                      color="neutral"
                      variant="soft"
                      icon="i-lucide-history"
                      title="History is empty"
                    />

                    <div v-if="historyPagination.total_pages > 1" class="flex justify-end py-2">
                      <UPagination
                        :page="historyPagination.page"
                        :total="historyPagination.total"
                        :items-per-page="historyPagination.per_page"
                        :disabled="historyIsLoading"
                        show-edges
                        size="sm"
                        :sibling-count="0"
                        @update:page="
                          (page) =>
                            load(page, {
                              order: 'DESC',
                              perPage: configStore.app.default_pagination,
                            })
                        "
                      />
                    </div>
                  </div>
                </Transition>
              </section>
            </section>
          </Transition>

          <UModal
            v-if="videoItem"
            :open="videoOpen"
            title="Video"
            :dismissible="true"
            :ui="{
              content: lightsOut ? 'w-full sm:max-w-5xl shadow-2xl' : 'w-full sm:max-w-5xl',
              body: 'p-0',
            }"
            @update:open="handleVideoOpenChange"
          >
            <template #body>
              <VideoPlayer
                type="default"
                :isMuted="false"
                autoplay="true"
                :isControls="true"
                :item="videoItem"
                class="w-full"
                @closeModel="() => requestCloseVideo()"
                @error="async (error: string) => await box.alert(error)"
                @playback-state-change="(playing: boolean) => (playingNow = playing)"
              />
            </template>
          </UModal>

          <UModal
            v-if="embedUrl"
            :open="Boolean(embedUrl)"
            title="Embed"
            :dismissible="true"
            :ui="{ content: 'w-full sm:max-w-5xl', body: 'p-0' }"
            @update:open="(open) => !open && closePlayer()"
          >
            <template #body>
              <EmbedPlayer :url="embedUrl" @closeModel="closePlayer" />
            </template>
          </UModal>

          <ClientOnly>
            <Dialog />
          </ClientOnly>
        </div>
      </div>
    </AppRoot>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue';
import { useStorage } from '@vueuse/core';
import type { item_request } from '~/types/item';
import type { ItemStatus, StoreItem } from '~/types/store';
import AppRoot from '~/components/AppRoot.vue';
import ConnectionBanner from '~/components/ConnectionBanner.vue';
import ThemeButton from '~/components/ThemeButton.vue';
import { useConfirm } from '~/composables/useConfirm';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import { useHistoryState } from '~/composables/useHistoryState';
import { useMediaQuery } from '~/composables/useMediaQuery';
import { usePresetOptions } from '~/composables/usePresetOptions';
import { useNotification } from '~/composables/useNotification';
import EmbedPlayer from '~/components/EmbedPlayer.vue';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import {
  ag,
  formatTime,
  getHistoryImage,
  getImage,
  getRemoteImage,
  isDownloadSkipped,
  makeDownload,
  request,
  ucFirst,
} from '~/utils';

definePageMeta({ layout: 'empty' });

const configStore = useYtpConfig();
const stateStore = useQueueState();
const socketStore = useAppSocket();
const toast = useNotification();
const dlFields = useStorage<Record<string, any>>('dl_fields', {});
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const autoRefreshEnabled = useStorage<boolean>('queue_auto_refresh', true);
const autoRefreshDelay = useStorage<number>('queue_auto_refresh_delay', 10000);
const queueCollapsed = useStorage<boolean>('simple_queue_collapsed', false);
const historyCollapsed = useStorage<boolean>('simple_history_collapsed', false);
const isMobile = useMediaQuery({ maxWidth: 1024 });
const box = useConfirm();

const app = toRef(configStore, 'app');
const paused = toRef(configStore, 'paused');
const presets = toRef(configStore, 'presets');
const { selectItems: presetItems } = usePresetOptions(presets);
const {
  items: historyItems,
  pagination,
  isLoading,
  load,
  reload,
  remove,
  moveHandler,
} = useHistoryState();

const embedUrl = ref('');
const videoItem = ref<StoreItem | null>(null);
const playingNow = ref(false);
const autoRefreshInterval = ref<ReturnType<typeof setInterval> | null>(null);
const hadSocketDisconnect = ref(false);
const videoOpen = computed<boolean>({
  get: () => Boolean(videoItem.value),
  set: (value: boolean) => {
    if (value) {
      return;
    }

    closePlayer();
  },
});

const formUrl = ref('');
const formPreset = ref(app.value.default_preset || '');
const addInProgress = ref(false);
const showExtras = ref(false);
const isRefreshing = ref(false);
const historyInitialized = ref(false);

const downloadingStatuses: ReadonlySet<ItemStatus | null> = new Set([
  'downloading',
  'postprocessing',
  'preparing',
]);

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
};

const urlInputUi = {
  root: 'w-full',
  base: 'bg-elevated/60 ring-default focus-visible:ring-primary',
};

const historyPagination = computed(() => pagination.value);
const historyIsLoading = computed(() => isLoading.value);
const queueItems = computed<StoreItem[]>(() => Object.values(stateStore.queue));
const queueCountLabel = computed(() => {
  if (stateStore.hasMore()) {
    return `${stateStore.shown()} displayed / ${stateStore.count()} queued`;
  }

  return `${stateStore.count()} queued`;
});
const historyEntries = computed<StoreItem[]>(() => historyItems.value);
const hasAnyItems = computed(() => queueItems.value.length > 0 || historyEntries.value.length > 0);
const showSections = computed(() => hasAnyItems.value || historyIsLoading.value);
const isFormDisabled = computed(() => addInProgress.value);
const lightsOut = computed(() => Boolean(videoItem.value && playingNow.value));
const formContainerClass = computed(() => {
  if (showSections.value) {
    return 'max-w-full';
  }

  return 'max-w-2xl simple-form-center';
});
const greetingMessage = computed(() => {
  const hour = new Date().getHours();

  if (hour >= 5 && hour < 12) {
    return 'Good morning, what would you like to download?';
  }

  if (hour >= 12 && hour < 17) {
    return 'Good afternoon, what would you like to download?';
  }

  if (hour >= 17 && hour < 21) {
    return 'Good evening, what would you like to download?';
  }

  return 'Hello, what would you like to download?';
});
const sortedDLFields = computed(() =>
  [...configStore.dl_fields].sort((left, right) => (left.order || 0) - (right.order || 0)),
);

const refreshQueue = async (): Promise<void> => {
  if (isRefreshing.value) {
    return;
  }

  isRefreshing.value = true;

  try {
    await stateStore.loadQueue();
  } catch (error) {
    console.error('Failed to refresh queue:', error);
    toast.error('Failed to refresh queue');
  } finally {
    isRefreshing.value = false;
  }
};

const loadMoreQueue = async (): Promise<void> => {
  if (isRefreshing.value) {
    return;
  }

  isRefreshing.value = true;

  try {
    await stateStore.loadMore();
  } catch (error) {
    console.error('Failed to load more queue items:', error);
    toast.error('Failed to load more queue items');
  } finally {
    isRefreshing.value = false;
  }
};

const startAutoRefresh = (): void => {
  if (autoRefreshInterval.value) {
    clearInterval(autoRefreshInterval.value);
  }

  if (!autoRefreshEnabled.value || socketStore.isConnected) {
    return;
  }

  autoRefreshInterval.value = setInterval(async () => {
    if (!socketStore.isConnected && autoRefreshEnabled.value) {
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

const addDownload = async (): Promise<void> => {
  const url = formUrl.value.trim();

  if (!url) {
    toast.error('Please enter a valid URL.');
    return;
  }

  let cli = '';
  const dlFieldsExtra = ['--no-download-archive'];

  const is_valid = (dl_field: string): boolean => {
    if (dlFieldsExtra.includes(dl_field)) {
      return true;
    }

    if (configStore.dl_fields && configStore.dl_fields.length > 0) {
      return configStore.dl_fields.some((field) => dl_field === field.field);
    }

    return false;
  };

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = [];

    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid(key)) {
        continue;
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue;
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);

      if (cli && keyRegex.test(cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`);
    }

    if (joined.length > 0) {
      cli = joined.join(' ');
    }
  }

  const payload: item_request[] = [
    {
      url,
      preset: formPreset.value || app.value.default_preset,
      cli: cli || '',
      auto_start: true,
    },
  ];

  try {
    addInProgress.value = true;

    const response = await request('/api/history', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      toast.error(`Error: ${data?.error || 'Failed to add download.'}`);
      return;
    }

    let had_errors = false;

    if (200 === response.status && Array.isArray(data)) {
      data.forEach((item: Record<string, any>) => {
        if (false !== item.status) {
          return;
        }

        had_errors = true;

        if (item?.hidden) {
          return;
        }

        toast.error(`Error: ${item.msg || 'Failed to add download.'}`);
      });
    }

    if (202 === response.status) {
      toast.success(data.message, { timeout: 2000 });
    }

    if (false === had_errors) {
      formUrl.value = '';
      formPreset.value = app.value.default_preset || '';
      dlFields.value = {};
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to add download.';
    toast.error(`Error: ${message}`);
  } finally {
    addInProgress.value = false;
  }
};

const resolveThumbnail = (item: StoreItem): string => {
  if (!show_thumbnail.value) {
    return '/images/placeholder.png';
  }

  if (historyEntries.value.some((entry) => entry._id === item._id)) {
    return getHistoryImage(item);
  }

  return getImage(configStore.app.download_path, item);
};

const openPlayer = (item: StoreItem): void => {
  if (item.filename) {
    videoItem.value = item;
    return;
  }

  if (!isEmbedable(item.url)) {
    return;
  }

  const embed = getEmbedable(item.url);
  if (embed) {
    embedUrl.value = embed;
  }
};

const closePlayer = (): void => {
  playingNow.value = false;
  embedUrl.value = '';
  videoItem.value = null;
};

const { handleOpenChange: handleVideoOpenChange, requestClose: requestCloseVideo } =
  useDirtyCloseGuard(videoOpen, {
    dirty: playingNow,
    title: 'Close player?',
    message: 'Playback is active. Do you want to close the player?',
    confirmText: 'Close player',
    cancelText: 'Keep playing',
    onDiscard: async () => {
      closePlayer();
    },
  });

const getDescription = (item: StoreItem): string => {
  const direct = (item.description ?? '').toString().trim();
  if (direct) {
    return direct;
  }

  const extrasDescription = ag<string | null>(item, 'extras.description', null)?.toString().trim();
  if (extrasDescription) {
    return extrasDescription;
  }

  const errorDescription = item.error?.trim();
  if (errorDescription) {
    return errorDescription;
  }

  const message = ag<string | null>(item, 'msg', null)?.toString().trim();
  if (message) {
    return message;
  }

  return '';
};

const getDurationLabel = (item: StoreItem): string | null => {
  const duration = ag<number | null>(item, 'extras.duration', null);
  if (duration == null || Number.isNaN(duration) || duration <= 0) {
    return null;
  }

  return formatTime(duration);
};

const statusOverrides: Record<string, string> = {
  downloading: 'Downloading',
  postprocessing: 'Post-processing',
  preparing: 'Preparing',
  finished: 'Completed',
  error: 'Error',
  cancelled: 'Cancelled',
  not_live: 'Not live yet',
  skip: 'Skipped',
};

const getStatusLabel = (item: StoreItem): string => {
  if (item.status === null) {
    return 'Queued';
  }

  if (isDownloadSkipped(item)) {
    return 'Download skipped';
  }

  if (item.status === 'error' && item.filename) {
    return 'Partial Error';
  }

  return statusOverrides[item.status] ?? ucFirst(item.status.replace(/_/g, ' '));
};

const getQueueIcon = (item: StoreItem): string => {
  if (downloadingStatuses.has(item.status)) {
    return item.is_live ? 'i-lucide-globe' : 'i-lucide-download';
  }

  return 'i-lucide-clock-3';
};

const getStatusIcon = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'i-lucide-clock-3';
  }

  if (item.status === null && paused.value === true) {
    return 'i-lucide-circle-pause';
  }

  if (item.status === null) {
    return 'i-lucide-circle-question-mark';
  }

  if (isDownloadSkipped(item)) {
    return 'i-lucide-circle-slash';
  }

  if (item.status === 'downloading' && item.is_live) {
    return 'i-lucide-globe';
  }

  const map: Record<string, string> = {
    downloading: 'i-lucide-download',
    postprocessing: 'i-lucide-settings-2',
    preparing: 'i-lucide-loader-circle',
    finished: 'i-lucide-circle-check',
    error: 'i-lucide-triangle-alert',
    cancelled: 'i-lucide-circle-x',
    not_live: 'i-lucide-clock-3',
    skip: 'i-lucide-circle-slash',
  };

  return map[item.status] ?? 'i-lucide-circle-question-mark';
};

const getStatusIconAnimation = (item: StoreItem): string => {
  const icon = getStatusIcon(item);

  return ['i-lucide-globe', 'i-lucide-settings-2', 'i-lucide-loader-circle'].includes(icon)
    ? 'animate-spin'
    : '';
};

const getStatusColor = (item: StoreItem): 'neutral' | 'info' | 'success' | 'error' | 'warning' => {
  if (item.status === null) {
    return 'neutral';
  }

  if (isDownloadSkipped(item)) {
    return 'info';
  }

  if (item.status === 'error' && item.filename) {
    return 'warning';
  }

  const map: Record<string, 'neutral' | 'info' | 'success' | 'error' | 'warning'> = {
    downloading: 'info',
    postprocessing: 'info',
    preparing: 'info',
    finished: 'success',
    error: 'error',
    cancelled: 'neutral',
    not_live: 'warning',
    skip: 'neutral',
  };

  return map[item.status] ?? 'info';
};

const percentPipe = (value: number | null): string => {
  if (value === null || Number.isNaN(value)) {
    return '00.00';
  }

  return parseFloat(String(value)).toFixed(2);
};

const ETAPipe = (value: number | null): string => {
  if (value === null || value === 0) {
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
  if (value === null || value === 0) {
    return '0KB/s';
  }

  const k = 1024;
  const dm = 2;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s', 'EB/s', 'ZB/s', 'YB/s'];
  const i = Math.floor(Math.log(value) / Math.log(k));
  return `${parseFloat((value / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
};

const updateProgress = (item: StoreItem): string => {
  let text = '';

  if (!item.auto_start) {
    return 'Manual start';
  }

  if (item.status === null && paused.value === true) {
    return 'Global Pause';
  }

  if (item.status === 'postprocessing') {
    return 'Post-processors are running.';
  }

  if (item.status === 'preparing') {
    return ag(item, 'extras.external_downloader') ? 'External downloader.' : 'Preparing';
  }

  if (item.status !== null && item.is_live && !item.speed) {
    return 'Recording live stream';
  }

  if (item.status !== null) {
    text += item.percent && !item.is_live ? `${percentPipe(item.percent)}%` : 'Live';
  }

  text += item.speed ? ` - ${speedPipe(item.speed)}` : ' - Waiting..';

  if (item.status !== null && item.eta) {
    text += ` - ${ETAPipe(item.eta)}`;
  }

  return text;
};

const progressWidth = (item: StoreItem): string => {
  if (!item.auto_start || (null === item.status && true === paused.value)) {
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

const getDownloadLink = (item: StoreItem): string => {
  if (!item.filename) {
    return '';
  }

  return makeDownload(app.value, item);
};

const getDownloadName = (item: StoreItem): string => {
  if (!item.filename) {
    return 'download';
  }

  const segments = item.filename.split('/');
  return segments[segments.length - 1] || 'download';
};

const requeueItem = async (item: StoreItem): Promise<void> => {
  if (!item.url) {
    toast.error('Unable to requeue item; missing URL.');
    return;
  }

  const payload: item_request = {
    url: item.url,
    preset: item.preset || app.value.default_preset,
    folder: item.folder,
    template: item.template,
    cookies: item.cookies,
    cli: item.cli,
    auto_start: item.auto_start ?? true,
  };

  if (item.extras && Object.keys(item.extras).length > 0) {
    payload.extras = JSON.parse(JSON.stringify(item.extras));
  }

  await remove({ ids: [item._id], removeFile: false });
  await reload({ order: 'DESC', perPage: configStore.app.default_pagination });
  await stateStore.addDownload(payload);
};

const deleteHistoryItem = async (item: StoreItem): Promise<void> => {
  await remove({ ids: [item._id], removeFile: app.value.remove_files });
  await reload({ order: 'DESC', perPage: configStore.app.default_pagination });
  toast.info('Removed from history queue.');
};

const handleHistoryItemMoved = moveHandler(() => historyInitialized.value);

const showMessage = (item: StoreItem): boolean => {
  if (!item?.msg || item.msg === item?.error) {
    return false;
  }

  return (item.msg?.length || 0) > 0;
};

const onImgError = (event: Event, item: StoreItem): void => {
  const target = event.target as HTMLImageElement;
  const currentSrc = target.getAttribute('src') || '';

  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  if (item) {
    const fallback = getRemoteImage(item, false);
    if (fallback && currentSrc !== fallback) {
      target.src = fallback;
      return;
    }
  }

  target.src = '/images/placeholder.png';
};

const init = async (): Promise<void> => {
  historyInitialized.value = true;
  socketStore.on('item_moved', handleHistoryItemMoved);
  await Promise.allSettled([
    refreshQueue(),
    load(1, { order: 'DESC', perPage: configStore.app.default_pagination }),
  ]);

  if (!socketStore.isConnected && autoRefreshEnabled.value) {
    startAutoRefresh();
  }
};

onBeforeUnmount(() => {
  socketStore.off('item_moved', handleHistoryItemMoved);
  stopAutoRefresh();
});

watch(
  () => socketStore.isConnected,
  (connected) => {
    if (connected) {
      stopAutoRefresh();

      if (hadSocketDisconnect.value) {
        hadSocketDisconnect.value = false;
        refreshQueue();
      }

      return;
    }

    hadSocketDisconnect.value = true;

    if (autoRefreshEnabled.value) {
      startAutoRefresh();
    }
  },
);

watch(autoRefreshEnabled, (enabled) => {
  if (enabled && !socketStore.isConnected) {
    startAutoRefresh();
    return;
  }

  stopAutoRefresh();
});

watch(autoRefreshDelay, () => {
  if (autoRefreshEnabled.value && !socketStore.isConnected) {
    startAutoRefresh();
  }
});

watch(
  () => app.value.default_preset,
  (value) => {
    if (!formPreset.value) {
      formPreset.value = value || '';
    }
  },
);

watch(
  () => app.value.default_pagination,
  (value, oldValue) => {
    if (!configStore.is_loaded || value === oldValue || !historyInitialized.value) {
      return;
    }

    load(1, { order: 'DESC', perPage: configStore.app.default_pagination });
  },
);
</script>

<style scoped>
.simple-form-center {
  transform: translateY(24vh);
}

.queue-fade-enter-active,
.queue-fade-leave-active {
  transition:
    opacity 0.28s ease,
    transform 0.32s ease;
}

.queue-fade-enter-from,
.queue-fade-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

.section-collapse-enter-active,
.section-collapse-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.24s ease,
    max-height 0.28s ease;
}

.section-collapse-enter-from,
.section-collapse-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  max-height: 0;
}

.section-collapse-enter-to,
.section-collapse-leave-from {
  opacity: 1;
  transform: translateY(0);
  max-height: 2000px;
}

.queue-card-enter-active,
.queue-card-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.28s ease;
}

.queue-card-enter-from,
.queue-card-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.queue-card-leave-active {
  position: absolute;
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

@media (max-width: 768px) {
  .simple-form-center {
    transform: translateY(16vh);
  }
}
</style>
