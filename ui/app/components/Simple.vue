<template>
  <div
    class="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col gap-4 px-3 py-4 sm:px-4 sm:py-5"
  >
    <div
      class="transition-transform duration-300"
      :class="{
        'lg:-translate-x-72': settingsOpen,
      }"
    >
      <div class="mx-auto w-full transition-all duration-300" :class="formContainerClass">
        <UPageCard variant="outline" :ui="formCardUi">
          <template #body>
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
                      color="info"
                      variant="ghost"
                      size="sm"
                      icon="i-lucide-refresh-cw"
                      :loading="isRefreshing"
                      :disabled="isRefreshing"
                      :square="isMobile"
                      @click="() => void refreshQueue()"
                    >
                      <span v-if="!isMobile">Reload Queue</span>
                    </UButton>
                  </UTooltip>

                  <UTooltip :text="colorModeButtonTitle">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      :icon="colorModeButtonIcon"
                      :square="isMobile"
                      :aria-label="colorModeButtonTitle"
                      :title="colorModeButtonTitle"
                      @click="colorMode.preference = nextColorModePreference"
                    >
                      <span v-if="!isMobile">{{ colorModeButtonTitle }}</span>
                    </UButton>
                  </UTooltip>

                  <UTooltip text="WebUI Settings">
                    <UButton
                      color="neutral"
                      variant="ghost"
                      size="sm"
                      icon="i-lucide-settings-2"
                      :square="isMobile"
                      @click="$emit('show_settings')"
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
                    color="info"
                    variant="outline"
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

              <div v-if="showExtras" class="space-y-3 border-t border-default pt-4">
                <UFormField label="Preset" :ui="fieldUi" class="w-full">
                  <template #label>
                    <span class="inline-flex items-center gap-2 font-semibold">
                      <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
                      <span>Preset</span>
                    </span>
                  </template>

                  <USelect
                    id="preset"
                    v-model="formPreset"
                    :items="presetItems"
                    value-key="value"
                    label-key="label"
                    size="lg"
                    class="w-full"
                    :ui="selectUi"
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
          </template>
        </UPageCard>
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

            <UBadge color="info" variant="soft" size="sm">{{ queueItems.length }} items</UBadge>
          </div>

          <Transition name="section-collapse">
            <div v-if="!queueCollapsed" id="simple-queue-section" class="overflow-hidden">
              <TransitionGroup
                v-if="queueItems.length > 0"
                name="queue-card"
                tag="div"
                class="grid grid-cols-1 gap-3 lg:grid-cols-2"
              >
                <UCard
                  v-for="item in queueItems"
                  :key="`queue-${item._id}`"
                  class="w-full min-w-0 max-w-full overflow-hidden border bg-default"
                  :ui="queueCardUi"
                >
                  <template #header>
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
                  </template>

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
                          <UIcon name="i-lucide-play" class="size-6 translate-x-px text-white" />
                        </span>
                        <img
                          :src="resolveThumbnail(item)"
                          :alt="item.title || 'Video thumbnail'"
                          loading="lazy"
                          class="aspect-video h-full w-full object-cover"
                          @error="onImgError"
                        />
                      </span>

                      <img
                        v-else
                        :src="resolveThumbnail(item)"
                        :alt="item.title || 'Video thumbnail'"
                        loading="lazy"
                        class="aspect-video h-full w-full object-cover"
                        @error="onImgError"
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
                            :color="downloadingStatuses.has(item.status) ? 'info' : 'warning'"
                            variant="soft"
                            size="sm"
                          >
                            {{ downloadingStatuses.has(item.status) ? 'Active' : 'Queued' }}
                          </UBadge>

                          <UBadge :color="getStatusColor(item)" variant="soft" size="sm">
                            {{ getStatusLabel(item) }}
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

                      <div class="mt-auto flex flex-wrap items-center justify-end gap-2 pt-1">
                        <UButton
                          v-if="!item.status && item.auto_start === false"
                          color="success"
                          variant="soft"
                          size="xs"
                          icon="i-lucide-play-circle"
                          @click="void stateStore.startItems([item._id])"
                        >
                          Start
                        </UButton>

                        <UButton
                          v-if="!item.status && item.auto_start === true"
                          color="warning"
                          variant="soft"
                          size="xs"
                          icon="i-lucide-pause"
                          @click="void stateStore.pauseItems([item._id])"
                        >
                          Pause
                        </UButton>

                        <UButton
                          color="error"
                          variant="outline"
                          size="xs"
                          icon="i-lucide-x"
                          @click="void stateStore.cancelItems([item._id])"
                        >
                          {{ item.is_live ? 'Stop' : 'Cancel' }}
                        </UButton>
                      </div>
                    </div>
                  </div>
                </UCard>
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
                    loadHistory(page, {
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
                  void reloadHistory({ order: 'DESC', perPage: configStore.app.default_pagination })
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
              <div v-if="historyEntries.length > 0" class="grid grid-cols-1 gap-3 lg:grid-cols-2">
                <UCard
                  v-for="item in historyEntries"
                  :key="`history-${historyPagination.page}-${item._id}`"
                  class="w-full min-w-0 max-w-full overflow-hidden border bg-default"
                  :ui="queueCardUi"
                >
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
                          <UIcon name="i-lucide-play" class="size-6 translate-x-px text-white" />
                        </span>
                        <img
                          :src="resolveThumbnail(item)"
                          :alt="item.title || 'Video thumbnail'"
                          loading="lazy"
                          class="aspect-video h-full w-full object-cover"
                          @error="onImgError"
                        />
                      </span>

                      <img
                        v-else
                        :src="resolveThumbnail(item)"
                        :alt="item.title || 'Video thumbnail'"
                        loading="lazy"
                        class="aspect-video h-full w-full object-cover"
                        @error="onImgError"
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

                          <UBadge :color="getStatusColor(item)" variant="soft" size="sm">
                            {{ getStatusLabel(item) }}
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

                      <div class="mt-auto flex flex-wrap items-center justify-end gap-2 pt-1">
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
                          color="info"
                          variant="soft"
                          size="xs"
                          icon="i-lucide-rotate-cw"
                          @click="() => void requeueItem(item)"
                        >
                          Requeue
                        </UButton>

                        <UButton
                          color="error"
                          variant="outline"
                          size="xs"
                          icon="i-lucide-trash"
                          @click="() => void deleteHistoryItem(item)"
                        >
                          Delete
                        </UButton>
                      </div>
                    </div>
                  </div>
                </UCard>
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
                      loadHistory(page, {
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

    <UAlert
      v-if="historyInitialized && !showSections"
      color="neutral"
      variant="soft"
      icon="i-lucide-inbox"
      title="No queue or history items"
    />

    <UModal
      v-if="videoItem"
      :open="Boolean(videoItem)"
      title="Video"
      :dismissible="true"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && closePlayer()"
    >
      <template #body>
        <VideoPlayer
          type="default"
          :isMuted="false"
          autoplay="true"
          :isControls="true"
          :item="videoItem"
          class="w-full"
          @closeModel="closePlayer"
          @error="async (error: string) => await box.alert(error)"
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
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from 'vue';
import { useStorage } from '@vueuse/core';
import type { item_request } from '~/types/item';
import type { ItemStatus, StoreItem } from '~/types/store';
import { useConfirm } from '~/composables/useConfirm';
import { useHistoryState } from '~/composables/useHistoryState';
import { useMediaQuery } from '~/composables/useMediaQuery';
import { usePresetOptions } from '~/composables/usePresetOptions';
import { useNotification } from '~/composables/useNotification';
import EmbedPlayer from '~/components/EmbedPlayer.vue';
import { getEmbedable, isEmbedable } from '~/utils/embedable';
import {
  ag,
  formatTime,
  getImage,
  isDownloadSkipped,
  makeDownload,
  request,
  ucFirst,
} from '~/utils';

defineEmits<{ (e: 'show_settings'): void }>();

withDefaults(
  defineProps<{
    settingsOpen?: boolean;
  }>(),
  {
    settingsOpen: false,
  },
);

type ColorModePreference = 'system' | 'light' | 'dark';

const configStore = useYtpConfig();
const stateStore = useQueueState();
const socketStore = useAppSocket();
const route = useRoute();
const colorMode = useColorMode();
const simpleMode = useStorage<boolean>('simple_mode', configStore.app.simple_mode || false);
const toast = useNotification();
const dlFields = useStorage<Record<string, any>>('dl_fields', {});
const show_thumbnail = useStorage<boolean>('show_thumbnail', true);
const autoRefreshEnabled = useStorage<boolean>('queue_auto_refresh', true);
const autoRefreshDelay = useStorage<number>('queue_auto_refresh_delay', 10000);
const queueCollapsed = useStorage<boolean>('simple_queue_collapsed', false);
const historyCollapsed = useStorage<boolean>('simple_history_collapsed', false);
const isMobile = useMediaQuery({ maxWidth: 1024 });
const box = useConfirm();
const colorModePreferences: Array<ColorModePreference> = ['system', 'light', 'dark'];

const app = toRef(configStore, 'app');
const paused = toRef(configStore, 'paused');
const presets = toRef(configStore, 'presets');
const { selectItems: presetItems } = usePresetOptions(presets);
const {
  items: historyItems,
  pagination,
  isLoading,
  loadHistory,
  reloadHistory,
  deleteHistoryItems,
  historyMoveHandler,
} = useHistoryState();

const embedUrl = ref('');
const videoItem = ref<StoreItem | null>(null);
const autoRefreshInterval = ref<ReturnType<typeof setInterval> | null>(null);

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

const formCardUi = {
  root: 'w-full border bg-default',
  container: 'w-full p-4 sm:p-5',
  wrapper: 'w-full items-stretch',
  body: 'w-full',
};

const queueCardUi = {
  root: 'w-full',
  header: 'p-4 pb-0',
  body: 'p-4',
};

const urlInputUi = {
  root: 'w-full',
  base: 'bg-elevated/60 ring-default focus-visible:ring-primary',
};

const selectUi = {
  base: 'w-full',
};

const historyPagination = computed(() => pagination.value);
const historyIsLoading = computed(() => isLoading.value);
const queueItems = computed<StoreItem[]>(() => Object.values(stateStore.queue));
const historyEntries = computed<StoreItem[]>(() => historyItems.value);
const hasAnyItems = computed(() => queueItems.value.length > 0 || historyEntries.value.length > 0);
const showSections = computed(() => hasAnyItems.value || historyIsLoading.value);
const isFormDisabled = computed(() => addInProgress.value);
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

const colorModePreference = computed<ColorModePreference>(() => {
  const preference = colorMode.preference;

  return colorModePreferences.includes(preference as ColorModePreference)
    ? (preference as ColorModePreference)
    : 'system';
});

const colorModeButtonIcon = computed(() => {
  switch (colorModePreference.value) {
    case 'light':
      return 'i-lucide-sun';
    case 'dark':
      return 'i-lucide-moon';
    default:
      return 'i-lucide-monitor';
  }
});

const nextColorModePreference = computed<ColorModePreference>(() => {
  const currentIndex = colorModePreferences.indexOf(colorModePreference.value);
  return colorModePreferences[(currentIndex + 1) % colorModePreferences.length] ?? 'system';
});

const colorModeButtonTitle = computed(() => {
  switch (colorModePreference.value) {
    case 'light':
      return 'Light';
    case 'dark':
      return 'Dark';
    default:
      return 'System';
  }
});

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

const applySimpleQuery = async (): Promise<void> => {
  if (route.query?.simple === undefined) {
    return;
  }

  simpleMode.value = ['true', '1', 'yes', 'on'].includes(route.query.simple as string);
  await nextTick();

  const url = new URL(window.location.href);
  url.searchParams.delete('simple');
  window.history.replaceState({}, '', url.toString());
};

const normalizeSimpleRoute = async (): Promise<void> => {
  if ('/' === route.path) {
    return;
  }

  await navigateTo('/', { replace: true });
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
  embedUrl.value = '';
  videoItem.value = null;
};

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

  await deleteHistoryItems({ ids: [item._id], removeFile: false });
  await reloadHistory({ order: 'DESC', perPage: configStore.app.default_pagination });
  await stateStore.addDownload(payload);
};

const deleteHistoryItem = async (item: StoreItem): Promise<void> => {
  await deleteHistoryItems({ ids: [item._id], removeFile: app.value.remove_files });
  await reloadHistory({ order: 'DESC', perPage: configStore.app.default_pagination });
  toast.info('Removed from history queue.');
};

const handleHistoryItemMoved = historyMoveHandler(
  () => simpleMode.value && historyInitialized.value,
);

const showMessage = (item: StoreItem): boolean => {
  if (!item?.msg || item.msg === item?.error) {
    return false;
  }

  return (item.msg?.length || 0) > 0;
};

const onImgError = (event: Event): void => {
  const target = event.target as HTMLImageElement;
  if (target.src.endsWith('/images/placeholder.png')) {
    return;
  }

  target.src = '/images/placeholder.png';
};

onMounted(async () => {
  await applySimpleQuery();

  if (!simpleMode.value) {
    return;
  }

  await normalizeSimpleRoute();
  historyInitialized.value = true;
  socketStore.on('item_moved', handleHistoryItemMoved);
  await loadHistory(1, { order: 'DESC', perPage: configStore.app.default_pagination });

  if (!socketStore.isConnected && autoRefreshEnabled.value) {
    startAutoRefresh();
  }
});

onBeforeUnmount(() => {
  socketStore.off('item_moved', handleHistoryItemMoved);
  stopAutoRefresh();
});

watch(
  () => route.query.simple,
  async (value, oldValue) => {
    if (value === undefined || value === oldValue) {
      return;
    }

    await applySimpleQuery();

    if (simpleMode.value) {
      await normalizeSimpleRoute();
    }
  },
);

watch(
  () => route.path,
  () => {
    if (simpleMode.value) {
      void normalizeSimpleRoute();
    }
  },
);

watch(
  () => socketStore.isConnected,
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
    if (
      !simpleMode.value ||
      !configStore.is_loaded ||
      value === oldValue ||
      !historyInitialized.value
    ) {
      return;
    }

    void loadHistory(1, { order: 'DESC', perPage: configStore.app.default_pagination });
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
