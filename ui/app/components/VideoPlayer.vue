<template>
  <div v-if="loading" class="flex justify-center py-10">
    <UIcon name="i-lucide-loader-circle" class="size-16 animate-spin text-toned" />
  </div>

  <div v-else class="space-y-4">
    <div v-if="loadingError || playbackError" class="ytp-card p-4 text-error" role="alert">
      {{ loadingError || playbackError }}
    </div>
    <div
      ref="playerContainer"
      tabindex="-1"
      class="relative flex w-full overflow-hidden rounded-sm bg-black"
      :class="
        isFullscreen
          ? 'h-screen w-screen max-h-screen max-w-none items-center justify-center rounded-none'
          : 'min-h-72 max-h-[70vh] max-w-full items-center justify-center sm:min-h-88 sm:max-h-[72vh]'
      "
    >
      <button
        v-if="!active"
        :disabled="!canPlay || switching"
        type="button"
        class="group absolute inset-0 z-40 block overflow-hidden bg-black text-start"
        @click="activatePlayer"
      >
        <img
          v-if="poster"
          :src="uri(poster)"
          :alt="`${title || t('common.untitledMedia')} preview`"
          class="block h-full w-full bg-black object-contain opacity-90 transition duration-200 group-hover:opacity-100"
          @error="handlePosterError"
        />
        <div
          v-else
          class="flex h-full w-full items-center justify-center bg-black/90 text-white/80"
        >
          <UIcon :name="isAudio ? 'i-lucide-disc-3' : 'i-lucide-film'" class="size-12" />
        </div>
        <div
          class="pointer-events-none absolute inset-0 bg-linear-to-t from-black/70 via-transparent to-black/20"
        />
      </button>

      <div
        v-if="!active"
        class="pointer-events-none absolute inset-0 z-50 flex min-h-0 flex-col justify-end gap-3 overflow-y-auto p-4 sm:p-6"
      >
        <div
          v-if="canPlay && ((session?.audio_tracks.length || 0) > 0 || hasSubtitles)"
          class="ytp-card pointer-events-auto grid gap-3 p-4 backdrop-blur-xl sm:grid-cols-2"
        >
          <UFormField
            v-if="session?.audio_tracks.length"
            :label="t('player.audio')"
            class="min-w-0"
          >
            <USelect
              v-model="audioValue"
              :items="audioItems"
              :disabled="switching"
              color="neutral"
              size="sm"
              icon="i-lucide-languages"
              class="w-full"
              :portal="helpPortal"
              :ui="{ content: 'z-[70]' }"
            />
          </UFormField>
          <UFormField v-if="hasSubtitles" :label="t('common.subtitles')" class="min-w-0">
            <USelect
              v-model="subtitleSelectValue"
              :items="subtitleSelectItems"
              :disabled="switching"
              color="neutral"
              size="sm"
              icon="i-lucide-captions"
              class="w-full"
              :portal="helpPortal"
              :ui="{ content: 'z-[70]' }"
            />
          </UFormField>
        </div>
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <div class="text-xs uppercase tracking-[0.2em] text-white/70">
              {{ t('common.clickToPlay') }}
            </div>
            <div class="mt-1 truncate text-lg font-semibold text-white">
              {{ title || t('common.untitledMedia') }}
            </div>
          </div>
          <UButton
            color="neutral"
            variant="soft"
            size="xl"
            icon="i-lucide-play"
            class="pointer-events-auto shrink-0"
            :loading="switching"
            :disabled="!canPlay || switching"
            :aria-label="t('common.playVideo')"
            @click="activatePlayer"
          />
        </div>
      </div>

      <video
        ref="videoElement"
        class="share-video-element block bg-black object-contain"
        :class="
          isFullscreen
            ? 'h-full w-full max-h-screen max-w-screen'
            : 'h-full min-h-72 w-full max-w-full max-h-[70vh] sm:min-h-88 sm:max-h-[72vh]'
        "
        playsinline
        webkit-playsinline
        preload="metadata"
        crossorigin="anonymous"
        :poster="poster ? uri(poster) : undefined"
        @error="handleMediaError"
        @loadeddata="handleVideoLoadedData"
        @loadedmetadata="handleVideoLoadedMetadata"
        @canplay="recordEvent('canplay')"
        @waiting="recordEvent('waiting')"
        @stalled="recordEvent('stalled')"
        @seeking="recordEvent('seeking')"
        @seeked="recordEvent('seeked')"
        @timeupdate="handleVideoTimeUpdate"
        @play="handleVideoPlay"
        @pause="handleVideoPause"
        @ended="flushProgress"
        @click="handleVideoClick"
        @dblclick="handleVideoDoubleClick"
        @pointermove="handlePointerMove"
        @resize="scheduleAssLayoutRefresh"
        @volumechange="handleMediaVolumeChange"
        @webkitbeginfullscreen="handleVideoWebkitBeginFullscreen"
        @webkitendfullscreen="handleVideoWebkitEndFullscreen"
      >
        <source
          v-for="source in sources"
          :key="source.src"
          :src="source.src"
          :type="source.type"
          @error="source.onerror"
        />
        <track
          v-if="nativeSubtitleTrack && subtitleEnabled"
          ref="nativeTrackElement"
          :key="nativeSubtitleTrack.url"
          kind="subtitles"
          :srclang="nativeSubtitleTrack.lang || 'und'"
          :label="nativeSubtitleTrack.name || t('common.subtitles')"
          default
          :src="uri(nativeSubtitleTrack.url)"
          @load="handleNativeTrackLoad"
        />
        {{ t('common.browserNoSupport') }}
      </video>

      <button
        v-if="active && isTouchDevice && !controlsVisible"
        type="button"
        class="absolute inset-0 z-10"
        :aria-label="t('common.showControls')"
        @click="toggleControls"
      />

      <div
        v-if="usesAssSubtitleTrack"
        ref="assOverlayElement"
        class="pointer-events-none absolute inset-0 z-20 overflow-hidden"
        aria-hidden="true"
      />

      <div
        v-if="active"
        class="absolute inset-x-0 bottom-0 z-30 bg-linear-to-t from-black/36 via-black/8 to-transparent px-3 pb-3 pt-10 text-white transition-opacity duration-150"
        :class="controlsVisible ? 'opacity-100' : 'pointer-events-none opacity-0'"
        @pointermove="showControls"
      >
        <div
          class="rounded-sm border border-white/8 bg-black/8 p-2.5 shadow-lg backdrop-blur-sm"
          dir="ltr"
        >
          <div
            class="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2.5 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:gap-3"
          >
            <div class="order-2 min-w-0 sm:order-1 sm:flex sm:min-w-0 sm:items-center sm:gap-3">
              <div class="flex min-w-0 items-center gap-2">
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="paused ? 'i-lucide-play' : 'i-lucide-pause'"
                  :aria-label="paused ? t('common.playVideo') : t('common.pauseVideoAria')"
                  @click="togglePlayback"
                />
                <div class="min-w-0 truncate whitespace-nowrap text-xs font-medium text-white/60">
                  {{ timeLabel }}
                </div>
              </div>
            </div>
            <div class="order-1 col-span-2 sm:order-2 sm:col-span-1 sm:min-w-0 sm:flex-1">
              <input
                :value="progress"
                type="range"
                min="0"
                max="1000"
                step="1"
                class="h-1.5 w-full accent-white opacity-55 transition-opacity hover:opacity-100 seek-bar"
                :aria-label="t('common.seekVideoAria')"
                @input="handleSeekInput"
                @touchstart.prevent="handleSeekTouch"
                @touchmove.prevent="handleSeekTouch"
              />
            </div>
            <div class="order-3 flex items-center justify-end sm:order-3 sm:shrink-0">
              <div class="flex shrink-0 items-center gap-1.5 sm:gap-2">
                <UTooltip v-if="!usingHls && hasVideo" side="top" :text="t('common.switchToHls')">
                  <UButton
                    color="neutral"
                    variant="soft"
                    size="sm"
                    class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                    icon="i-lucide-refresh-cw"
                    :aria-label="t('common.switchToHlsAria')"
                    @click="forceSwitchToHls"
                  />
                </UTooltip>
                <USelect
                  v-if="(session?.audio_tracks.length || 0) > 1"
                  v-model="audioValue"
                  :items="audioItems"
                  :disabled="switching"
                  :portal="helpPortal"
                  :aria-label="audioButtonLabel"
                  size="sm"
                  color="neutral"
                  variant="soft"
                  trailing-icon=""
                  :content="subtitleSelectContent"
                  :ui="subtitleSelectUi"
                  class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                >
                  <template #default>
                    <span class="sr-only">{{ audioButtonLabel }}</span>
                    <UIcon
                      :name="switching ? 'i-lucide-loader-circle' : 'i-lucide-languages'"
                      class="size-4 shrink-0"
                      :class="{ 'animate-spin': switching }"
                    />
                  </template>
                </USelect>
                <USelect
                  v-if="hasSubtitles"
                  :disabled="switching"
                  v-model="subtitleSelectValue"
                  :items="subtitleSelectItems"
                  value-key="value"
                  label-key="label"
                  color="neutral"
                  variant="soft"
                  size="sm"
                  trailing-icon=""
                  :content="subtitleSelectContent"
                  :portal="helpPortal"
                  :ui="subtitleSelectUi"
                  class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :aria-label="subtitleButtonLabel"
                >
                  <template #default>
                    <span class="sr-only">{{ subtitleButtonLabel }}</span>
                    <UIcon
                      :name="subtitleEnabled ? 'i-lucide-captions' : 'i-lucide-captions-off'"
                      class="size-4 shrink-0"
                    />
                  </template>
                </USelect>
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="muted || mediaVol <= 0 ? 'i-lucide-volume-x' : 'i-lucide-volume-2'"
                  :aria-label="
                    muted || mediaVol <= 0 ? t('common.unmuteVideoAria') : t('common.muteVideoAria')
                  "
                  @click="toggleMute"
                />
                <input
                  v-if="!isTouchDevice"
                  :value="Math.round(mediaVol * 100)"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  class="w-16 accent-white opacity-55 transition-opacity hover:opacity-100 sm:w-18"
                  :aria-label="t('common.videoVolumeAria')"
                  @input="handleVolumeInput"
                />
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="isFullscreen ? 'i-lucide-minimize' : 'i-lucide-maximize'"
                  :aria-label="
                    isFullscreen ? t('common.exitFullscreenAria') : t('common.enterFullscreenAria')
                  "
                  @click="toggleFullscreen"
                />
                <UTooltip side="top" :text="t('common.shortcutsTooltip')">
                  <UButton
                    color="neutral"
                    variant="soft"
                    size="sm"
                    class="opacity-65 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                    icon="i-lucide-keyboard"
                    :aria-label="t('common.shortcutsAria')"
                    @click="
                      () => {
                        showHelp = !showHelp;
                      }
                    "
                  />
                </UTooltip>
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  icon="i-lucide-bug"
                  aria-label="Playback diagnostics"
                  @click="openDiagnostics"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        v-if="switching"
        class="pointer-events-none absolute inset-0 z-40 flex items-center justify-center bg-black/40 text-white"
        role="status"
      >
        <UIcon name="i-lucide-loader-circle" class="size-8 animate-spin" />
        <span class="ms-3">{{ t('player.preparing') }}</span>
      </div>
    </div>

    <div v-if="subtitleLoadError" class="flex flex-wrap items-center gap-3 text-sm">
      <span class="text-warning">{{ subtitleLoadError }}</span>
    </div>

    <Teleport :to="playerContainer || 'body'" :disabled="!playerContainer">
      <section
        v-if="showHelp"
        tabindex="-1"
        data-player-help
        role="dialog"
        :aria-label="t('common.keyboardShortcuts')"
        class="ytp-card player-panel absolute inset-3 z-50 overflow-y-auto p-4 sm:inset-6"
        @keydown.esc.stop="showHelp = false"
      >
        <div class="mb-4 flex items-center justify-between gap-3">
          <h3 class="flex items-center gap-2 font-semibold text-highlighted">
            <UIcon name="i-lucide-keyboard" class="size-4" />
            {{ t('common.keyboardShortcuts') }}
          </h3>
          <UButton
            icon="i-lucide-x"
            color="neutral"
            variant="ghost"
            :aria-label="t('common.close')"
            @click="showHelp = false"
          />
        </div>
        <div class="grid gap-x-8 gap-y-6 text-sm sm:grid-cols-2">
          <section v-for="group in shortcutGroups" :key="group.title">
            <h4 class="font-semibold text-highlighted">{{ group.title }}</h4>
            <dl class="mt-3 space-y-2">
              <div
                v-for="shortcut in group.items"
                :key="shortcut.label"
                class="flex min-h-7 items-center justify-between gap-4"
              >
                <dt class="text-toned">{{ shortcut.label }}</dt>
                <dd class="flex shrink-0 items-center gap-1.5">
                  <template v-for="(key, index) in shortcut.keys" :key="key">
                    <span v-if="index" class="text-dimmed">/</span>
                    <UKbd size="lg" class="h-auto min-h-8 min-w-8 px-2 py-1 text-sm font-bold">{{
                      key
                    }}</UKbd>
                  </template>
                </dd>
              </div>
            </dl>
          </section>
        </div>
      </section>
      <section
        v-if="diagnosticsOpen"
        tabindex="-1"
        data-player-diagnostics
        role="dialog"
        aria-label="Playback diagnostics"
        class="ytp-card player-panel absolute inset-3 z-50 overflow-y-auto p-4 sm:inset-6"
        @keydown.esc.stop="diagnosticsOpen = false"
      >
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 class="flex items-center gap-2 font-semibold">
            <UIcon name="i-lucide-bug" class="size-4" />Playback diagnostics
          </h3>
          <div class="flex gap-2">
            <UButton
              size="sm"
              color="neutral"
              variant="outline"
              icon="i-lucide-refresh-cw"
              :label="t('common.refresh')"
              @click="openDiagnostics"
            />
            <UButton
              size="sm"
              color="neutral"
              variant="outline"
              icon="i-lucide-copy"
              :label="t('common.copy')"
              @click="copyDiagnostics"
            />
            <UButton
              icon="i-lucide-x"
              color="neutral"
              variant="ghost"
              :aria-label="t('common.close')"
              @click="diagnosticsOpen = false"
            />
          </div>
        </div>
        <div class="space-y-4">
          <UAlert
            v-if="loadingError || playbackError || subtitleLoadError"
            color="error"
            variant="soft"
            :description="loadingError || playbackError || subtitleLoadError"
          />
          <section v-for="section in diagnosticSections" :key="section.title" class="ytp-card p-3">
            <h4 class="font-semibold text-highlighted">{{ section.title }}</h4>
            <dl class="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2">
              <div v-for="row in section.rows" :key="row.label">
                <dt class="text-xs text-toned">{{ row.label }}</dt>
                <dd class="mt-1 wrap-break-word text-sm font-medium">{{ row.value }}</dd>
              </div>
            </dl>
          </section>
          <section v-if="diagnosticEvents.length" class="ytp-card p-3">
            <h4 class="font-semibold text-highlighted">Recent events</h4>
            <ol class="mt-2 divide-y divide-default">
              <li
                v-for="(event, index) in diagnosticEvents"
                :key="index"
                class="flex items-start gap-3 py-2 text-sm"
              >
                <span class="shrink-0 text-xs tabular-nums text-toned">{{
                  new Date(event.time).toLocaleTimeString()
                }}</span>
                <code class="min-w-0 wrap-break-word">
                  {{ event.event }} {{ event.message || '' }}
                </code>
              </li>
            </ol>
          </section>
        </div>
      </section>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useStorage } from '@vueuse/core';
import type Hls from 'hls.js';
import {
  disableOpacity,
  enableOpacity,
  formatPageTitle,
  getRemoteImage,
  makeDownload,
  request,
  uri,
} from '~/utils';
import { usePlayerShortcutHelp } from '~/composables/usePlayerShortcutHelp';
import { usePlayerShortcuts } from '~/composables/usePlayerShortcuts';
import { usePlayerSubtitles } from '~/composables/usePlayerSubtitles';
import { useApiErrorMessage } from '~/composables/useApiErrorMessage';
import { useAuth } from '~/composables/useAuth';
import {
  canRequestFullscreen,
  exitDocumentFullscreen,
  getFullscreenElement,
  requestElementFullscreen,
} from '~/utils/fullscreen';
import { clampMediaVolume } from '~/utils/keyboard';
import { clear, clampResumeTime, nearEnd, read, readRemote, save, saveRemote } from '~/utils/media';
import { nextTapVisible } from '~/utils/playerControls';
import { playbackMediaHasNoVideo, playbackMediaSnapshot } from '~/utils/playback';

import type { StoreItem } from '~/types/store';
import type { PlayerSourceElement, PlayerSession } from '~/types/video';
import type { SubtitleTrack } from '~/types/subtitles';
import type { ApiErrorPayload } from '~/types/responses';

const { t } = useI18n();
const config = useYtpConfig();
const { status: auth } = useAuth();
const scope = computed(() => {
  if (auth.value?.disabled) return 'shared';
  return auth.value?.user ? `user:${auth.value.user.id}` : null;
});

const props = defineProps<{ item: StoreItem }>();
const emitter = defineEmits<{
  (e: 'closeModel'): void;
  (e: 'error', message: string): void;
  (e: 'playback-state-change', isPlaying: boolean): void;
}>();

const showShortcutHelp = usePlayerShortcutHelp();
const { messageFor } = useApiErrorMessage();
const shortcutGroups = computed(() => [
  {
    title: t('common.playbackHelp'),
    items: [
      { label: t('common.playOrPause'), keys: ['Space', 'K'] },
      { label: t('common.back10Seconds'), keys: ['J'] },
      { label: t('common.forward10Seconds'), keys: ['L'] },
      { label: t('common.muteHelp'), keys: ['M'] },
    ],
  },
  {
    title: t('common.navigationHelp'),
    items: [
      { label: t('common.back5Seconds'), keys: ['←'] },
      { label: t('common.forward5Seconds'), keys: ['→'] },
      { label: t('common.goToStartOrEnd'), keys: ['Home', 'End'] },
      { label: t('common.jumpThroughTimeline'), keys: ['0–9'] },
    ],
  },
  {
    title: t('common.volumeAndSpeedHelp'),
    items: [
      { label: t('common.volumeUpOrDown'), keys: ['↑', '↓'] },
      { label: t('common.fasterHelp'), keys: ["'"] },
      { label: t('common.slowerHelp'), keys: [';'] },
      { label: t('common.stepFrameByFrame'), keys: [',', '.'] },
    ],
  },
  {
    title: t('common.displayHelp'),
    items: [
      { label: t('common.fullscreenHelp'), keys: ['F'] },
      { label: t('common.showOrHideSubtitles'), keys: ['C'] },
      { label: t('common.openThisHelp'), keys: ['?', '/'] },
      { label: t('common.closeHelpOrPlayer'), keys: ['Esc'] },
    ],
  },
]);

const playerContainer = ref<HTMLElement | null>(null);
const videoElement = ref<HTMLVideoElement | null>(null);
const nativeTrackElement = ref<HTMLTrackElement | null>(null);
const assOverlayElement = ref<HTMLElement | null>(null);
const sources = ref<Array<PlayerSourceElement>>([]);
const loading = ref(true);
const loadingError = ref('');
const playbackError = ref('');
const switching = ref(false);
const session = ref<PlayerSession | null>(null);
const sessionTracks = ref<SubtitleTrack[]>([]);
const selectedAudio = ref<number | null>(null);
const diagnosticsOpen = ref(false);
const diagnosticsReport = ref('');
const diagnosticSections = ref<
  Array<{ title: string; rows: Array<{ label: string; value: string }> }>
>([]);
const diagnosticEvents = ref<Array<{ time: number; event: string; message?: string }>>([]);
const recentEvents: Array<{ time: number; event: string; message?: string }> = [];
const active = ref(false);
const isFullscreen = ref(false);
const assLayoutVersion = ref(0);
const controlsVisible = ref(true);
const currentTime = ref(0);
const duration = ref(0);
const paused = ref(true);
const isTouchDevice = ref(false);
const title = ref('');
const artist = ref('');
const poster = ref('/images/placeholder.png');
const hasPoster = ref(false);
const isAudio = ref(false);
const hasVideo = ref(false);
const usingHls = ref(false);
const preferHls = ref(false);
const destroyed = ref(false);
const mediaVol = useStorage<number>('player_volume', 1);
const muted = useStorage<boolean>('player_muted', false);
const showHelp = computed({
  get: () => showShortcutHelp.value,
  set: (value: boolean) => {
    showShortcutHelp.value = value;
  },
});
const helpPortal = computed<boolean | HTMLElement>(() => {
  if (isFullscreen.value) {
    return playerContainer.value || false;
  }

  return true;
});

let assLayoutRefreshFrame = 0;
let controlsHideTimeout = 0;
let pendingVideoClickTimeout = 0;
let unbindMediaSession: null | (() => void) = null;
let hls: Hls | null = null;
let pendingSeek: number | null = null;
let pendingPlay = false;
let lastSaveAt = 0;
let resumeVersion = 0;
let lastRemote: number | null | undefined;
let remoteWrite = Promise.resolve();
let savedProgress: Promise<number> = Promise.resolve(0);
let switchVersion = 0;
let attachedSwitch = 0;
let pendingRate = 1;
let automaticFallback = false;
let nativeHls = false;
let nativeFallback = false;
let hlsEngine: 'native-hls' | 'hls.js' | null = null;
let switchTimeout = 0;
let refreshTimer = 0;
let switchAbort: AbortController | null = null;
const initAbort = new AbortController();

const isApple = /(iPhone|iPod|iPad).*AppleWebKit/i.test(navigator.userAgent);
const mediaFile = computed(() => props.item.filename || '');
const id = computed(() => props.item._id || '');
const canPlay = computed(() => Boolean(mediaFile.value && !loadingError.value));
const shouldRender = computed(() => active.value && !loading.value);
const progress = computed(() => {
  if (!duration.value) return 0;
  return Math.round((currentTime.value / duration.value) * 1000);
});
const timeLabel = computed(() => {
  const currentLabel = formatDuration(Math.round(currentTime.value));
  const durationLabel = duration.value ? formatDuration(Math.round(duration.value)) : '--:--';
  return `${currentLabel} / ${durationLabel}`;
});
const {
  subtitleTracks,
  subtitleLoadError,
  subtitleEnabled,
  selectedSubtitleTrack,
  selectedSubtitleTrackId,
  nativeSubtitleTrack,
  usesAssSubtitleTrack,
  hasSubtitles,
} = usePlayerSubtitles({
  canPlay,
  shouldRender,
  assLayoutVersion,
  video: videoElement,
  overlay: assOverlayElement,
  tracks: sessionTracks,
  fonts: computed(() => session.value?.fonts || []),
});

const SUBTITLE_OFF_VALUE = '__off__';
const subtitleSelectContent = { align: 'end' as const } as const;
const subtitleSelectUi = {
  base: 'size-8 min-h-8 min-w-8 justify-center rounded-md px-0',
  value: 'flex items-center justify-center px-0',
  trailing: 'hidden',
  leading: 'hidden',
  content: 'z-40 min-w-56 w-auto max-w-[min(24rem,calc(100vw-2rem))]',
} as const;
const subtitleSelectItems = computed(() => [
  { label: t('common.subtitlesOff'), value: SUBTITLE_OFF_VALUE },
  ...subtitleTracks.value.map((track) => ({
    label: track.renderer === 'bitmap' ? `${track.name} (${t('player.burnIn')})` : track.name,
    value: track.id,
    disabled: track.renderer === 'unsupported',
  })),
]);
const subtitleButtonLabel = computed(() => {
  if (!subtitleEnabled.value || !selectedSubtitleTrack.value) {
    return t('common.subtitlesOff');
  }
  return selectedSubtitleTrack.value.name || t('common.subtitles');
});

const audioItems = computed(() => [
  ...(!usingHls.value ? [{ label: t('player.browserAudio'), value: 'browser' }] : []),
  ...(session.value?.audio_tracks || []).map((track, index) => ({
    label: [
      track.name || `${t('player.audio')} ${index + 1}`,
      track.lang,
      track.codec.toUpperCase(),
      track.channel_layout || track.channels,
      track.default ? t('common.defaultSource') : '',
    ]
      .filter(Boolean)
      .join(' · '),
    value: String(track.stream_index),
  })),
]);
const audioValue = computed({
  get: () => {
    if (!active.value && selectedAudio.value !== null) return String(selectedAudio.value);
    if (!usingHls.value) return 'browser';
    return String(
      selectedAudio.value ??
        session.value?.audio_tracks.find((track) => track.default)?.stream_index ??
        session.value?.audio_tracks[0]?.stream_index ??
        '',
    );
  },
  set: (value: string) => {
    selectedAudio.value = value === 'browser' ? null : Number(value);
    if (active.value) void switchSelection(true);
  },
});
const audioButtonLabel = computed(
  () =>
    audioItems.value.find((track) => track.value === audioValue.value)?.label || t('player.audio'),
);

function recordEvent(event: string, message?: string) {
  recentEvents.push({ time: Date.now(), event, message });
  if (recentEvents.length > 30) recentEvents.shift();
}

function openDiagnostics() {
  const probe = session.value?.ffprobe;
  const media = playbackMediaSnapshot(videoElement.value);
  const row = (label: string, value: unknown) => ({
    label,
    value:
      value === undefined || value === null || value === ''
        ? 'Not reported'
        : typeof value === 'object'
          ? JSON.stringify(value)
          : String(value),
  });
  diagnosticSections.value = [
    {
      title: 'Playback',
      rows: [
        row(
          'Delivery',
          usingHls.value ? (hlsEngine === 'hls.js' ? 'HLS (hls.js)' : 'HLS (browser)') : 'Direct',
        ),
        row(
          'Position (seconds)',
          media ? `${media.current_time.toFixed(1)} / ${media.duration?.toFixed(1) || '?'}` : null,
        ),
        row('Speed', media?.rate),
        row(
          'Audio track',
          usingHls.value ? (selectedAudio.value ?? 'Default') : 'Browser-selected (Direct)',
        ),
        row('Buffered ranges', media?.buffered),
        row('Seekable ranges', media?.seekable),
        row(
          'Frames processed / dropped',
          media?.frames ? `${media.frames.total} / ${media.frames.dropped}` : null,
        ),
        row(
          'Ready / network state',
          media ? `${media.ready_state} / ${media.network_state}` : null,
        ),
      ],
    },
    {
      title: 'Source',
      rows: [
        row('Video codec', probe?.video[0]?.codec_name),
        row('Container', probe?.metadata.format_name),
        row(
          'Source resolution',
          probe?.video[0] ? `${probe.video[0].width} × ${probe.video[0].height}` : null,
        ),
        row('Browser video size', media ? `${media.width} × ${media.height}` : null),
      ],
    },
    {
      title: 'Browser',
      rows: [
        row('User agent', navigator.userAgent),
        row('Tab visibility', document.visibilityState),
        row('Secure context', window.isSecureContext),
      ],
    },
  ];
  diagnosticEvents.value = [...recentEvents].reverse();
  const report = {
    transport: usingHls.value ? hlsEngine : 'direct',
    source: {
      file: currentPlaybackUrl('api/download'),
      video: probe?.video,
      audio: session.value?.audio_tracks,
      duration: probe?.metadata.duration,
      container: probe?.metadata.format_name,
    },
    selected_audio: selectedAudio.value,
    selected_subtitle: selectedSubtitleTrackId.value,
    browser: {
      user_agent: navigator.userAgent,
      vendor: navigator.vendor,
      secure_context: window.isSecureContext,
      visibility: document.visibilityState,
    },
    media,
    errors: {
      initialization: loadingError.value ? 'Initialization failed' : null,
      playback: playbackError.value ? 'Playback failed' : null,
      subtitles: subtitleLoadError.value ? 'Subtitle loading or rendering failed' : null,
    },
    recent_events: recentEvents,
  };
  diagnosticsReport.value = JSON.stringify(report, null, 2);
  diagnosticsOpen.value = true;
}

async function copyDiagnostics() {
  openDiagnostics();
  try {
    await navigator.clipboard.writeText(diagnosticsReport.value);
  } catch {
    useNotification().error(t('common.copyFailed'));
  }
}
const subtitleSelectValue = computed<string>({
  get: () =>
    subtitleEnabled.value
      ? (selectedSubtitleTrackId.value ?? SUBTITLE_OFF_VALUE)
      : SUBTITLE_OFF_VALUE,
  set: (value: string) => {
    if (SUBTITLE_OFF_VALUE === value) {
      subtitleEnabled.value = false;
      return;
    }
    selectedSubtitleTrackId.value = value;
    subtitleEnabled.value = true;
  },
});

useHead(() =>
  title.value ? { title: formatPageTitle(t('common.playing', { title: title.value })) } : {},
);

watch(
  [mediaVol, muted],
  ([nextVol]) => {
    const normalizedVolume = clampMediaVolume(nextVol);
    if (normalizedVolume !== nextVol) {
      mediaVol.value = normalizedVolume;
      return;
    }

    applyMediaState(videoElement.value);
    syncVideoState();
  },
  { immediate: true },
);

watch(
  videoElement,
  (element, previousElement) => {
    if (previousElement && previousElement !== element) {
      previousElement.muted = true;
    }

    applyMediaState(element);
    syncVideoState();
  },
  { immediate: true },
);

watch(hasSubtitles, (enabled) => {
  if (!enabled) {
    subtitleEnabled.value = false;
  }
});

function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':');
  }

  return [minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':');
}

function currentPlaybackUrl(base: string): string {
  if (!props.item.filename) {
    return '';
  }

  return makeDownload(config, props.item, base);
}

async function activatePlayer() {
  if (!canPlay.value || switching.value || active.value) return;
  const resume = ++resumeVersion;
  active.value = true;
  await nextTick();
  try {
    const time = await savedProgress;
    if (destroyed.value || resume !== resumeVersion) return;
    if (
      selectedAudio.value !== null ||
      (subtitleEnabled.value && selectedSubtitleTrack.value?.renderer === 'bitmap') ||
      usingHls.value ||
      preferHls.value
    ) {
      await switchSelection(true, time, true);
      return;
    }
    applyMediaState(videoElement.value);
    pendingSeek = time;
    pendingPlay = true;
    pendingRate = videoElement.value?.playbackRate || 1;
    const version = switchVersion;
    window.clearTimeout(switchTimeout);
    switchTimeout = window.setTimeout(
      () => failPlayback(t('player.preparationFailed'), version),
      300000,
    );
    if (videoElement.value && videoElement.value.readyState >= 1) {
      pendingSeek = null;
      await restoreSwitch(time, true, version);
      if (destroyed.value || version !== switchVersion) return;
      pendingPlay = isPlaying();
      window.clearTimeout(switchTimeout);
    }
  } catch {
    playbackError.value = t('player.playFailed');
  } finally {
    syncVideoState();
    showControls();
  }
}

function handleVideoLoadedData() {
  recordEvent('loadeddata');
  syncVideoState();
}

function handleVideoLoadedMetadata() {
  if (switching.value && attachedSwitch !== switchVersion) return;
  recordEvent('loadedmetadata');
  loadingError.value = '';
  syncVideoState();
  showControls();
  scheduleAssLayoutRefresh();
  if (videoElement.value) {
    updateMediaSessionPosition(videoElement.value);
  }

  if (pendingSeek !== null) {
    const time = pendingSeek;
    const play = pendingPlay;
    const version = switchVersion;
    pendingSeek = null;
    void restoreSwitch(time, play, version).finally(() => {
      if (destroyed.value || version !== switchVersion) return;
      pendingPlay = isPlaying();
      switching.value = false;
      window.clearTimeout(switchTimeout);
      syncVideoState();
      showControls();
    });
  }
}

function handleVideoTimeUpdate() {
  if (
    !usingHls.value &&
    !automaticFallback &&
    playbackMediaHasNoVideo(videoElement.value, hasVideo.value)
  ) {
    recordEvent('missing-video');
    void src_error(new Event('missing-video'));
  }
  syncVideoState();
  if (videoElement.value) {
    updateMediaSessionPosition(videoElement.value);
  }

  persistProgress(false);
}

function handleVideoPlay() {
  recordEvent('play');
  pendingPlay = true;
  resumeVersion += 1;
  loadingError.value = '';
  syncVideoState();
  showControls();
  emitter('playback-state-change', true);
}

function handleVideoPause() {
  recordEvent('pause');
  if (!switching.value && !videoElement.value?.error) pendingPlay = false;
  syncVideoState();
  clearControlsHideTimeout();
  controlsVisible.value = true;
  persistProgress(true);
  emitter('playback-state-change', switching.value ? pendingPlay : false);
}

const flushProgress = () => persistProgress(true);
const handleVisibilityChange = () =>
  document.visibilityState === 'hidden' ? persistProgress(true) : undefined;

function handleVideoClick() {
  if (isTouchDevice.value) {
    toggleControls();
    return;
  }

  clearPendingVideoClickTimeout();
  pendingVideoClickTimeout = window.setTimeout(() => {
    pendingVideoClickTimeout = 0;
    if (controlsVisible.value && !videoElement.value?.paused) {
      clearControlsHideTimeout();
      controlsVisible.value = false;
    }
  }, 180);
}

function handleVideoDoubleClick() {
  clearPendingVideoClickTimeout();
  void toggleFullscreen();
}

function handleVideoWebkitBeginFullscreen() {
  scheduleAssLayoutRefresh();
}

function handleVideoWebkitEndFullscreen() {
  scheduleAssLayoutRefresh();
}

function handleMediaError(event: Event) {
  void src_error(event);
}

function handlePosterError(event: Event) {
  const target = event.target as HTMLImageElement | null;
  if (!target || poster.value === '/images/placeholder.png') {
    return;
  }

  const fallback = getRemoteImage(props.item, false);
  if (fallback && poster.value !== fallback) {
    poster.value = fallback;
    hasPoster.value = true;
    target.src = uri(fallback);
    return;
  }

  poster.value = '/images/placeholder.png';
  hasPoster.value = false;
  target.src = uri('/images/placeholder.png');
}

function handleMediaVolumeChange(event: Event) {
  const target = event.target as HTMLMediaElement | null;
  if (!target || typeof target.volume !== 'number') return;

  if (target.muted !== muted.value) {
    muted.value = target.muted;
  }

  const normalizedVolume = clampMediaVolume(target.volume);
  if (Math.abs(mediaVol.value - normalizedVolume) > 0.001) {
    mediaVol.value = normalizedVolume;
  }

  syncVideoState();
  updateMediaSessionPosition(target);
}

function readSwitchTime() {
  const video = videoElement.value;
  if (!video) {
    return 0;
  }

  return Number.isFinite(video.currentTime) && video.currentTime > 0 ? video.currentTime : 0;
}

function isPlaying() {
  const video = videoElement.value;
  return Boolean(video && !video.paused && !video.ended);
}

async function seekTo(time: number) {
  const video = videoElement.value;
  if (!video) {
    return;
  }

  const nextTime = clampResumeTime(video, time);
  if (nextTime > 0) {
    try {
      video.currentTime = nextTime;
    } catch {}
  }
}

async function restoreSwitch(time: number, play: boolean, version = switchVersion) {
  await seekTo(time);
  if (destroyed.value || version !== switchVersion) return;
  if (videoElement.value) videoElement.value.playbackRate = pendingRate;

  if (play) {
    try {
      await videoElement.value?.play();
    } catch {
      if (destroyed.value || version !== switchVersion) return;
      if (videoElement.value?.error) await src_error(new Event('error'));
      else if (pendingPlay) playbackError.value = t('player.playFailed');
    }
  }
}

function syncProgress(position: number | null) {
  if (lastRemote === position) return;
  lastRemote = position;
  const mediaId = id.value;
  const localScope = scope.value;
  remoteWrite = remoteWrite.then(async () => {
    if (localScope !== scope.value) return;
    if (!(await saveRemote(mediaId, position)) && lastRemote === position) lastRemote = undefined;
  });
}

function persistProgress(force: boolean) {
  const video = videoElement.value;
  if (!id.value || !video || destroyed.value || switching.value) {
    return;
  }

  if (nearEnd(video)) {
    clear(id.value, scope.value);
    syncProgress(null);
    lastSaveAt = 0;
    return;
  }

  const time = Number.isFinite(video.currentTime) && video.currentTime > 0 ? video.currentTime : 0;
  if (time <= 0) {
    return;
  }

  const now = Date.now();
  if (!force && now - lastSaveAt < 1000) {
    return;
  }

  save(id.value, time, scope.value);
  if (force) syncProgress(time);
  lastSaveAt = now;
}

function handlePointerMove(event: PointerEvent) {
  if (!playerContainer.value || isTouchDevice.value) {
    return;
  }

  const rect = playerContainer.value.getBoundingClientRect();
  const y = event.clientY - rect.top;
  const bottomZone = Math.min(Math.max(rect.height * 0.28, 96), 180);

  if (y >= rect.height - bottomZone) {
    showControls();
  }
}

function handleSeekInput(event: Event) {
  resumeVersion += 1;
  const target = event.target as HTMLInputElement | null;
  if (!target || !videoElement.value || !duration.value) return;

  const sliderValue = Number(target.value);
  if (!Number.isFinite(sliderValue)) return;

  videoElement.value.currentTime = (sliderValue / 1000) * duration.value;
  syncVideoState();
  showControls();
}

function handleSeekTouch(event: TouchEvent) {
  resumeVersion += 1;
  const target = event.currentTarget as HTMLInputElement | null;
  const touch = event.touches[0];
  if (!target || !touch || !videoElement.value || !duration.value) return;

  const rect = target.getBoundingClientRect();
  const fraction = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
  videoElement.value.currentTime = fraction * duration.value;
  syncVideoState();
  showControls();
}

function handleVolumeInput(event: Event) {
  const target = event.target as HTMLInputElement | null;
  if (!target || !videoElement.value) return;

  const nextVol = clampMediaVolume(Number(target.value) / 100);
  mediaVol.value = nextVol;
  muted.value = nextVol <= 0;
  applyMediaState(videoElement.value);
  syncVideoState();
  showControls();
}

async function togglePlayback() {
  if (!videoElement.value) return;

  try {
    if (videoElement.value.paused) {
      await videoElement.value.play();
      syncVideoState();
      showControls();
      return;
    }

    videoElement.value.pause();
    syncVideoState();
  } catch {}
}

function toggleMute() {
  if (muted.value || mediaVol.value <= 0) {
    mediaVol.value = mediaVol.value > 0 ? clampMediaVolume(mediaVol.value) : 1;
    muted.value = false;
  } else {
    muted.value = true;
  }

  applyMediaState(videoElement.value);
  syncVideoState();
  showControls();
}

function applyMediaState(element: HTMLMediaElement | null) {
  if (!element) return;

  const normalizedVolume = clampMediaVolume(mediaVol.value);
  if (Math.abs(element.volume - normalizedVolume) > 0.001) {
    element.volume = normalizedVolume;
  }

  if (element.muted !== muted.value) {
    element.muted = muted.value;
  }
}

function syncVideoState() {
  const video = videoElement.value;
  if (!video) {
    currentTime.value = 0;
    duration.value = 0;
    paused.value = true;
    emitter('playback-state-change', false);
    return;
  }

  const nextDuration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0;
  const nextTime =
    Number.isFinite(video.currentTime) && video.currentTime > 0 ? video.currentTime : 0;

  duration.value = nextDuration;
  currentTime.value = nextTime;
  paused.value = video.paused;

  if (video.ended || nearEnd(video)) {
    clear(id.value, scope.value);
    lastSaveAt = 0;
  }

  emitter('playback-state-change', switching.value ? pendingPlay : !video.paused);
}

function scheduleAssLayoutRefresh() {
  if (!usesAssSubtitleTrack.value) return;

  if (assLayoutRefreshFrame) {
    window.cancelAnimationFrame(assLayoutRefreshFrame);
  }

  void nextTick(() => {
    assLayoutRefreshFrame = window.requestAnimationFrame(() => {
      assLayoutRefreshFrame = 0;
      assLayoutVersion.value += 1;
    });
  });
}

function showControls() {
  controlsVisible.value = true;
  clearControlsHideTimeout();

  if (videoElement.value?.paused) {
    return;
  }

  controlsHideTimeout = window.setTimeout(() => {
    controlsVisible.value = false;
  }, 2500);
}

function toggleControls() {
  const nextVisible = nextTapVisible({
    touch: isTouchDevice.value,
    paused: Boolean(videoElement.value?.paused),
    visible: controlsVisible.value,
  });

  if (nextVisible === controlsVisible.value) {
    return;
  }

  if (nextVisible) {
    showControls();
    return;
  }

  clearControlsHideTimeout();
  controlsVisible.value = false;
}

function clearControlsHideTimeout() {
  if (controlsHideTimeout) {
    window.clearTimeout(controlsHideTimeout);
    controlsHideTimeout = 0;
  }
}

function clearPendingVideoClickTimeout() {
  if (pendingVideoClickTimeout) {
    window.clearTimeout(pendingVideoClickTimeout);
    pendingVideoClickTimeout = 0;
  }
}

function syncFullscreenState() {
  const fullscreenElement = getFullscreenElement();
  isFullscreen.value = Boolean(
    fullscreenElement && playerContainer.value && fullscreenElement === playerContainer.value,
  );
  if (!isFullscreen.value && isTouchDevice.value) {
    showControls();
  }
  scheduleAssLayoutRefresh();
}

async function toggleFullscreen() {
  if (!playerContainer.value || !canRequestFullscreen(playerContainer.value)) return;

  try {
    if (isFullscreen.value) {
      await exitDocumentFullscreen();
    } else {
      await requestElementFullscreen(playerContainer.value);
    }
  } catch {}
}

function bindMediaSessionListeners(el: HTMLVideoElement) {
  const onLoadedMetadata = (event: Event) => updateMediaSessionPosition(event.currentTarget);
  const onTimeUpdate = (event: Event) => updateMediaSessionPosition(event.currentTarget);
  const onRateChange = (event: Event) => updateMediaSessionPosition(event.currentTarget);
  const onSeeked = (event: Event) => updateMediaSessionPosition(event.currentTarget);

  el.addEventListener('loadedmetadata', onLoadedMetadata);
  el.addEventListener('timeupdate', onTimeUpdate);
  el.addEventListener('ratechange', onRateChange);
  el.addEventListener('seeked', onSeeked);

  return () => {
    el.removeEventListener('loadedmetadata', onLoadedMetadata);
    el.removeEventListener('timeupdate', onTimeUpdate);
    el.removeEventListener('ratechange', onRateChange);
    el.removeEventListener('seeked', onSeeked);
  };
}

function updateMediaSessionPosition(target: EventTarget | null) {
  if (false === 'mediaSession' in navigator) {
    return;
  }
  const el = (target as HTMLVideoElement) ?? null;
  if (!el || destroyed.value) {
    return;
  }
  const duration = el.duration;
  if (false === Number.isFinite(duration) || duration <= 0) {
    return;
  }
  try {
    navigator.mediaSession.setPositionState({
      duration,
      playbackRate: el.playbackRate,
      position: el.currentTime,
    });
  } catch {}
}

function restoreDefaultTextTrack() {
  if (destroyed.value) return;
  const el = videoElement.value;
  if (!el) return;
  const selected = nativeTrackElement.value?.track;
  for (const track of Array.from(el.textTracks)) {
    track.mode =
      subtitleEnabled.value && nativeSubtitleTrack.value && track === selected
        ? 'showing'
        : 'disabled';
  }
}

function handleNativeTrackLoad(event: Event) {
  if (event.currentTarget !== nativeTrackElement.value) return;
  if (true === destroyed.value) {
    return;
  }
  void restoreDefaultTextTrack();
}

function applyMediaSessionMetadata() {
  if (false === 'mediaSession' in navigator) {
    return;
  }
  const metadata: MediaMetadataInit = { title: title.value };
  if (artist.value) {
    metadata.artist = artist.value;
  }
  if (poster.value) {
    metadata.artwork = [{ src: poster.value, sizes: '1920x1080', type: 'image/jpeg' }];
  }
  try {
    navigator.mediaSession.metadata = new MediaMetadata(metadata);
  } catch {}
}

async function loadPlayerInfo() {
  if (!props.item.filename) {
    loading.value = false;
    loadingError.value = t('common.noMediaFile');
    emitter('error', loadingError.value);
    emitter('closeModel');
    return;
  }

  loading.value = true;
  loadingError.value = '';

  const opened = await request(currentPlaybackUrl('api/player/open'), {
    method: 'POST',
    signal: initAbort.signal,
  });
  const response = (await opened.json()) as PlayerSession & ApiErrorPayload;
  if (!opened.ok) {
    recordEvent('open-error', response.code);
    loading.value = false;
    loadingError.value =
      opened.status === 404
        ? t('errors.FILE_UNAVAILABLE', { file: props.item.filename })
        : messageFor(response, 'common.failedFetch');
    emitter('error', loadingError.value);
    emitter('closeModel');
    return;
  }
  if (destroyed.value) {
    void request(`/api/player/leases/${encodeURIComponent(response.player_id)}`, {
      method: 'DELETE',
    }).catch(() => {});
    return;
  }
  session.value = response;
  sessionTracks.value = response.subtitles;
  const mediaId = id.value;
  const localScope = scope.value;
  savedProgress = readRemote(mediaId).then((remoteTime) => {
    if (destroyed.value || mediaId !== id.value || localScope !== scope.value) return 0;
    const time = remoteTime === undefined ? read(mediaId, localScope) : (remoteTime ?? 0);
    if (remoteTime !== undefined) {
      lastRemote = remoteTime;
      if (time > 0) save(mediaId, time, localScope);
      else clear(mediaId, localScope);
    }
    return time;
  });

  poster.value = '/images/placeholder.png';
  hasPoster.value = false;

  if (props.item._id && props.item.filename) {
    poster.value = `/api/history/${encodeURIComponent(props.item._id)}/thumbnail`;
    hasPoster.value = true;
  } else if (response.poster) {
    poster.value = makeDownload(config, { filename: response.poster });
    hasPoster.value = true;
  } else if (props.item.extras?.thumbnail) {
    poster.value = getRemoteImage(props.item);
    hasPoster.value = true;
  }

  hasVideo.value =
    Array.isArray(response.ffprobe?.video) &&
    response.ffprobe.video.some((stream) => stream.codec_type === 'video');

  if (!props.item.extras?.is_video && props.item.extras?.is_audio) {
    isAudio.value = true;
  } else if (hasVideo.value === false) {
    isAudio.value = true;
  }

  sources.value = [];
  if (isApple) {
    const allowedCodec = response.mimetype && response.mimetype.includes('video/mp4');
    const src = uri(response.media_url);
    sources.value.push({
      src,
      type: response.mimetype,
      onerror: (err: Event) => void src_error(err),
    });
    preferHls.value = !allowedCodec;
    usingHls.value = false;
  } else {
    sources.value.push({
      src: uri(response.media_url),
      type: response.mimetype,
      onerror: (err: Event) => void src_error(err),
    });
    usingHls.value = false;
  }

  if (props.item.extras?.channel) {
    artist.value = props.item.extras.channel;
  } else if (props.item.extras?.uploader) {
    artist.value = props.item.extras.uploader;
  }

  if (props.item.title) {
    title.value = props.item.title;
  } else if (response.title) {
    title.value = response.title;
  } else if (response.ffprobe?.metadata?.tags?.title) {
    title.value = response.ffprobe.metadata.tags.title;
  }

  loading.value = false;
  await nextTick();

  if (videoElement.value) {
    unbindMediaSession = bindMediaSessionListeners(videoElement.value);
  }

  prepareVideoPlayer();
}

function prepareVideoPlayer() {
  if (loading.value) {
    return;
  }

  applyMediaSessionMetadata();

  if (!videoElement.value) {
    return;
  }

  applyMediaState(videoElement.value);
  restoreDefaultTextTrack();
}

async function src_error(event: Event) {
  recordEvent('source-error', event.type);
  if (destroyed.value || (switching.value && attachedSwitch !== switchVersion)) return;
  if (!active.value) {
    preferHls.value = true;
    return;
  }
  if (usingHls.value) {
    if (!videoElement.value?.error) return;
    if (nativeHls && !nativeFallback) {
      const time = pendingSeek ?? readSwitchTime();
      const play = pendingPlay || isPlaying();
      nativeFallback = true;
      recordEvent('native-hls-fallback');
      await switchSelection(true, time, play, true);
    } else if (!playbackError.value) {
      failPlayback(t('player.playbackFailed'));
    }
    return;
  }
  if (automaticFallback) return;
  if (switching.value || destroyed.value) {
    return;
  }
  automaticFallback = true;
  await switchSelection(true, pendingSeek ?? readSwitchTime(), pendingPlay || isPlaying());
}

async function attach_hls(link: string, version: number): Promise<void> {
  const video = videoElement.value;
  if (!video || destroyed.value || version !== switchVersion) return;
  hls?.destroy();
  hls = null;
  sources.value = [];
  video.removeAttribute('src');
  video.querySelectorAll('source').forEach((source) => source.removeAttribute('src'));
  usingHls.value = true;
  nativeHls = false;
  if (!nativeFallback && video.canPlayType('application/vnd.apple.mpegurl')) {
    nativeHls = true;
    hlsEngine = 'native-hls';
    attachedSwitch = version;
    video.src = uri(link);
    video.load();
    return;
  }
  const { default: Hls } = await import('hls.js');
  if (destroyed.value || version !== switchVersion || video !== videoElement.value) return;
  if (!Hls.isSupported()) throw new Error(t('player.hlsUnsupported'));
  hlsEngine = 'hls.js';
  hls = new Hls({
    debug: false,
    enableWorker: true,
    startPosition: pendingSeek ?? -1,
    backBufferLength: 120,
    fragLoadingTimeOut: 300000,
  });
  const instance = hls;
  hls.on(Hls.Events.ERROR, (_event, data) => {
    if (destroyed.value || version !== switchVersion || hls !== instance) return;
    recordEvent('hls-error', data.details);
    if (!data.fatal) return;
    failPlayback(t('player.playbackFailed'), version);
  });
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    if (version === switchVersion) applyMediaSessionMetadata();
  });
  hls.loadSource(uri(link));
  attachedSwitch = version;
  hls.attachMedia(video);
}

function failPlayback(message: string, version = switchVersion) {
  if (destroyed.value || version !== switchVersion) return;
  switchAbort?.abort();
  switchVersion += 1;
  hls?.destroy();
  hls = null;
  nativeHls = false;
  pendingSeek = null;
  pendingPlay = false;
  switching.value = false;
  window.clearTimeout(switchTimeout);
  playbackError.value = message;
  videoElement.value?.pause();
}

async function switchSelection(
  forceHls = false,
  time = readSwitchTime(),
  play = isPlaying(),
  nativeRetry = false,
) {
  if ((switching.value && !nativeRetry) || destroyed.value || !session.value) return;
  const rate = nativeRetry && switching.value ? pendingRate : videoElement.value?.playbackRate || 1;
  persistProgress(true);
  switching.value = true;
  playbackError.value = '';
  const version = ++switchVersion;
  switchAbort?.abort();
  switchAbort = new AbortController();
  pendingSeek = time;
  pendingPlay = play;
  pendingRate = rate;
  videoElement.value?.pause();
  window.clearTimeout(switchTimeout);
  switchTimeout = window.setTimeout(() => {
    if (version !== switchVersion || destroyed.value) return;
    failPlayback(t('player.preparationFailed'), version);
  }, 300000);
  try {
    const response = await request(
      `/api/player/leases/${encodeURIComponent(session.value.player_id)}`,
      {
        method: 'PUT',
        signal: switchAbort.signal,
        body: JSON.stringify({
          audio_stream_index: selectedAudio.value,
          subtitle_track_id: subtitleEnabled.value ? selectedSubtitleTrackId.value : null,
        }),
      },
    );
    const body = (await response.json()) as PlayerSession & ApiErrorPayload;
    if (destroyed.value || version !== switchVersion) return;
    if (!response.ok) {
      recordEvent('selection-error', body.code);
      throw new Error(messageFor(body, 'player.preparationFailed'));
    }
    session.value = body;
    if (
      forceHls ||
      usingHls.value ||
      selectedAudio.value !== null ||
      (subtitleEnabled.value && selectedSubtitleTrack.value?.renderer === 'bitmap')
    ) {
      recordEvent('hls-switch');
      await attach_hls(body.stream_url, version);
    } else {
      await restoreSwitch(time, play);
      switching.value = false;
      window.clearTimeout(switchTimeout);
    }
  } catch (error) {
    if (destroyed.value || version !== switchVersion) return;
    failPlayback(error instanceof Error ? error.message : t('player.preparationFailed'), version);
  }
}

function forceSwitchToHls() {
  if (usingHls.value || switching.value) return;
  if (!hasVideo.value) {
    useNotification().error(t('common.switchToHlsFailed'));
    return;
  }

  void switchSelection(true);
}

usePlayerShortcuts({
  enabled: computed(
    () => active.value && !switching.value && !diagnosticsOpen.value && Boolean(videoElement.value),
  ),
  container: playerContainer,
  media: videoElement,
  video: videoElement,
  adjustVolume: (delta) => {
    mediaVol.value = clampMediaVolume(mediaVol.value + delta);
    muted.value = mediaVol.value <= 0;
    applyMediaState(videoElement.value);
    syncVideoState();
    showControls();
  },
  canToggleSubs: hasSubtitles,
  helpOpen: showShortcutHelp,
  toggleSubtitles: () => {
    subtitleEnabled.value = !subtitleEnabled.value;
    void nextTick(() => restoreDefaultTextTrack());
  },
  toggleFullscreen,
  toggleMute,
  closePlayer: () => emitter('closeModel'),
});

watch(subtitleEnabled, () => {
  void nextTick(() => restoreDefaultTextTrack());
});

watch(selectedSubtitleTrack, () => {
  void nextTick(() => restoreDefaultTextTrack());
});

watch([showHelp, diagnosticsOpen], () => {
  void nextTick(() => {
    const selector = diagnosticsOpen.value
      ? '[data-player-diagnostics]'
      : showHelp.value
        ? '[data-player-help]'
        : '';
    if (selector) playerContainer.value?.querySelector<HTMLElement>(selector)?.focus();
    else if (active.value) playerContainer.value?.focus();
  });
});

watch(
  () =>
    subtitleEnabled.value && selectedSubtitleTrack.value?.renderer === 'bitmap'
      ? selectedSubtitleTrackId.value
      : null,
  (next, previous) => {
    if (active.value && next !== previous) void switchSelection(true);
  },
);

onMounted(async () => {
  disableOpacity();
  isTouchDevice.value = window.matchMedia('(pointer: coarse)').matches;
  document.addEventListener('fullscreenchange', syncFullscreenState);
  document.addEventListener('webkitfullscreenchange', syncFullscreenState as EventListener);
  window.addEventListener('resize', scheduleAssLayoutRefresh);
  window.addEventListener('orientationchange', scheduleAssLayoutRefresh);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('pagehide', flushProgress);
  syncFullscreenState();
  try {
    await loadPlayerInfo();
  } catch {
    if (!destroyed.value) {
      loading.value = false;
      loadingError.value = t('player.preparationFailed');
      emitter('error', loadingError.value);
      emitter('closeModel');
    }
    return;
  }
  if (!session.value || destroyed.value) return;
  refreshTimer = window.setInterval(() => {
    if (!session.value || destroyed.value || switching.value) return;
    void request(`/api/player/leases/${encodeURIComponent(session.value.player_id)}`, {
      method: 'PUT',
      body: '{}',
    })
      .then((response) => {
        if (!response.ok) playbackError.value = t('player.sessionExpired');
      })
      .catch(() => {
        if (!destroyed.value) playbackError.value = t('player.sessionExpired');
      });
  }, 240000);
});

onBeforeUnmount(() => {
  initAbort.abort();
  switchAbort?.abort();
  switchVersion += 1;
  window.clearTimeout(switchTimeout);
  window.clearInterval(refreshTimer);
  if (session.value)
    void request(`/api/player/leases/${encodeURIComponent(session.value.player_id)}`, {
      method: 'DELETE',
    }).catch(() => {});
  resumeVersion += 1;
  enableOpacity();
  document.removeEventListener('fullscreenchange', syncFullscreenState);
  document.removeEventListener('webkitfullscreenchange', syncFullscreenState as EventListener);
  window.removeEventListener('resize', scheduleAssLayoutRefresh);
  window.removeEventListener('orientationchange', scheduleAssLayoutRefresh);
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  window.removeEventListener('pagehide', flushProgress);

  persistProgress(true);

  if (assLayoutRefreshFrame) {
    window.cancelAnimationFrame(assLayoutRefreshFrame);
  }

  clearControlsHideTimeout();
  clearPendingVideoClickTimeout();

  if (hls) {
    hls.destroy();
    hls = null;
  }

  if (unbindMediaSession) {
    unbindMediaSession();
    unbindMediaSession = null;
  }

  if (videoElement.value) {
    try {
      videoElement.value.pause();
      videoElement.value
        .querySelectorAll('source')
        .forEach((source) => source.removeAttribute('src'));
      videoElement.value.load();
    } catch (error) {
      console.error(error);
    }
  }
  destroyed.value = true;
});
</script>

<style scoped>
.player-panel {
  background-color: color-mix(in oklab, var(--ui-bg) 90%, transparent);
  backdrop-filter: blur(12px);
  color: var(--ui-text);
  border-color: var(--ui-border);
}

.share-video-element::-webkit-media-controls {
  display: none;
}

.share-video-element::-webkit-media-controls-fullscreen-button {
  display: none;
}

.seek-bar {
  touch-action: none;
}
</style>
