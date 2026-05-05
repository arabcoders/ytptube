<template>
  <div v-if="loading" class="flex justify-center py-10">
    <UIcon name="i-lucide-loader-circle" class="size-16 animate-spin text-toned" />
  </div>

  <div v-else class="space-y-4">
    <div
      ref="playerContainer"
      class="relative flex w-full overflow-hidden rounded-sm bg-black"
      :class="
        isFullscreen
          ? 'h-screen w-screen max-h-screen max-w-none items-center justify-center rounded-none'
          : 'min-h-72 max-h-[70vh] max-w-full items-center justify-center sm:min-h-88 sm:max-h-[72vh]'
      "
    >
      <button
        v-if="!active"
        type="button"
        class="group absolute inset-0 z-40 block overflow-hidden bg-black text-left"
        @click="activatePlayer"
      >
        <img
          v-if="poster"
          :src="uri(poster)"
          :alt="`${title || 'Untitled media'} preview`"
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
        <div
          class="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between gap-4 px-4 py-4 sm:px-6"
        >
          <div class="min-w-0">
            <div class="text-xs uppercase tracking-[0.2em] text-white/70">Click to play</div>
            <div class="mt-1 truncate text-lg font-semibold text-white">
              {{ title || 'Untitled media' }}
            </div>
          </div>
          <div
            class="flex size-16 shrink-0 items-center justify-center rounded-full bg-white/12 text-white backdrop-blur ring-1 ring-white/25"
          >
            <UIcon name="i-lucide-play" class="ml-1 size-8" />
          </div>
        </div>
      </button>

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
        @timeupdate="handleVideoTimeUpdate"
        @play="handleVideoPlay"
        @pause="handleVideoPause"
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
          :key="nativeSubtitleTrack.url"
          kind="subtitles"
          :srclang="nativeSubtitleTrack.lang || 'und'"
          :label="nativeSubtitleTrack.name || 'Subtitles'"
          default
          :src="uri(nativeSubtitleTrack.url)"
        />
        Your browser does not support the video tag.
      </video>

      <button
        v-if="active && showSeekZones"
        type="button"
        class="absolute inset-y-0 left-0 z-10 w-1/3"
        aria-label="Back 10 seconds"
        @click="seekBy(-10)"
      />
      <button
        v-if="active && isTouchDevice"
        type="button"
        class="absolute inset-y-0 left-1/3 z-10 w-1/3"
        :aria-label="controlsVisible ? 'Hide controls' : 'Show controls'"
        @click="toggleControls"
      />
      <button
        v-if="active && showSeekZones"
        type="button"
        class="absolute inset-y-0 right-0 z-10 w-1/3"
        aria-label="Forward 10 seconds"
        @click="seekBy(10)"
      />

      <div
        v-if="usesAssSubtitleTrack"
        ref="assOverlayElement"
        class="pointer-events-none absolute inset-0 z-20 overflow-hidden"
        aria-hidden="true"
      />

      <div
        v-if="active && showSeekZones && controlsVisible"
        class="pointer-events-none absolute inset-y-0 left-0 z-20 flex w-1/3 items-center justify-start px-5"
      >
        <div
          class="rounded-full bg-black/60 px-4 py-2 text-sm font-semibold text-white backdrop-blur-sm"
        >
          -10s
        </div>
      </div>
      <div
        v-if="active && showSeekZones && controlsVisible"
        class="pointer-events-none absolute inset-y-0 right-0 z-20 flex w-1/3 items-center justify-end px-5"
      >
        <div
          class="rounded-full bg-black/60 px-4 py-2 text-sm font-semibold text-white backdrop-blur-sm"
        >
          +10s
        </div>
      </div>

      <div
        v-if="active"
        class="absolute inset-x-0 bottom-0 z-30 bg-linear-to-t from-black/60 via-black/22 to-transparent px-3 pb-3 pt-10 text-white transition-opacity duration-150"
        :class="controlsVisible ? 'opacity-100' : 'pointer-events-none opacity-0'"
        @click.self="toggleControls"
        @pointermove="showControls"
      >
        <div
          class="rounded-sm border border-white/8 bg-black/18 p-2.5 shadow-lg backdrop-blur-sm sm:p-3"
        >
          <div class="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:gap-3">
            <div class="sm:min-w-0 sm:flex-1">
              <input
                :value="progress"
                type="range"
                min="0"
                max="1000"
                step="1"
                class="h-1.5 w-full accent-white opacity-70 transition-opacity hover:opacity-100"
                aria-label="Seek video"
                @input="handleSeekInput"
              />
            </div>
            <div class="flex items-center justify-between gap-2 sm:shrink-0 sm:justify-end">
              <div class="flex min-w-0 items-center gap-2">
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-75 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="paused ? 'i-lucide-play' : 'i-lucide-pause'"
                  :aria-label="paused ? 'Play video' : 'Pause video'"
                  @click="togglePlayback"
                />
                <div class="min-w-0 whitespace-nowrap text-xs font-medium text-white/70">
                  {{ timeLabel }}
                </div>
              </div>
              <div class="flex items-center gap-2">
                <UButton
                  v-if="hasSubtitles"
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-75 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="subtitleEnabled ? 'i-lucide-captions' : 'i-lucide-captions-off'"
                  :aria-label="subtitleEnabled ? 'Disable subtitles' : 'Enable subtitles'"
                  @click="subtitleEnabled = !subtitleEnabled"
                />
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-75 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="effectiveVolume <= 0 ? 'i-lucide-volume-x' : 'i-lucide-volume-2'"
                  :aria-label="effectiveVolume <= 0 ? 'Unmute video' : 'Mute video'"
                  @click="toggleMute"
                />
                <input
                  :value="Math.round(effectiveVolume * 100)"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  class="w-16 accent-white opacity-70 transition-opacity hover:opacity-100 sm:w-20"
                  aria-label="Video volume"
                  @input="handleVolumeInput"
                />
                <UButton
                  color="neutral"
                  variant="soft"
                  size="sm"
                  class="opacity-75 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                  :icon="isFullscreen ? 'i-lucide-minimize' : 'i-lucide-maximize'"
                  :aria-label="isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'"
                  @click="toggleFullscreen"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-3 text-sm">
        <button
          v-if="!usingHls && hasVideo"
          type="button"
          class="inline-flex items-center gap-2 text-info transition-colors hover:text-info/80"
          @click.prevent="forceSwitchToHls"
        >
          <UIcon name="i-lucide-refresh-cw" class="size-4" />
          <span>Trouble playing? switch to HLS stream.</span>
        </button>
        <span v-if="subtitleLoading" class="text-toned">Looking for matching subtitles...</span>
        <span v-else-if="subtitleLoadError" class="text-warning">{{ subtitleLoadError }}</span>
      </div>

      <button
        type="button"
        class="inline-flex items-center gap-2 text-toned transition-colors hover:text-default"
        @click="showHelp = !showHelp"
      >
        <UIcon name="i-lucide-circle-help" class="size-4" />
        <span>Show keyboard shortcuts with <kbd>?</kbd> or <kbd>/</kbd></span>
      </button>
    </div>

    <UModal
      v-model:open="showHelp"
      title="Keyboard Shortcuts"
      :portal="helpPortal"
      :ui="{ content: 'sm:max-w-3xl' }"
    >
      <template #body>
        <div class="grid gap-5 text-sm sm:grid-cols-2">
          <div class="space-y-3">
            <div class="font-semibold text-highlighted">Playback</div>
            <div class="flex items-center justify-between gap-4">
              <span>Play or pause</span>
              <span class="text-muted">Space, K</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Back 10 seconds</span>
              <span class="text-muted">J</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Forward 10 seconds</span>
              <span class="text-muted">L</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Mute</span>
              <span class="text-muted">M</span>
            </div>
          </div>
          <div class="space-y-3">
            <div class="font-semibold text-highlighted">Navigation</div>
            <div class="flex items-center justify-between gap-4">
              <span>Back 5 seconds</span>
              <span class="text-muted">Left</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Forward 5 seconds</span>
              <span class="text-muted">Right</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Go to start or end</span>
              <span class="text-muted">Home, End</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Jump through the timeline</span>
              <span class="text-muted">0-9</span>
            </div>
          </div>
          <div class="space-y-3">
            <div class="font-semibold text-highlighted">Volume & Speed</div>
            <div class="flex items-center justify-between gap-4">
              <span>Volume up or down</span>
              <span class="text-muted">Up, Down</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Faster</span>
              <span class="text-muted">'</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Slower</span>
              <span class="text-muted">;</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Step frame by frame</span>
              <span class="text-muted">, .</span>
            </div>
          </div>
          <div class="space-y-3">
            <div class="font-semibold text-highlighted">Display</div>
            <div class="flex items-center justify-between gap-4">
              <span>Fullscreen</span>
              <span class="text-muted">F</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Show or hide subtitles</span>
              <span class="text-muted">C</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Open this help</span>
              <span class="text-muted">?, /</span>
            </div>
            <div class="flex items-center justify-between gap-4">
              <span>Close help or player</span>
              <span class="text-muted">Esc</span>
            </div>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import Hls from 'hls.js';
import {
  disableOpacity,
  enableOpacity,
  encodePath,
  formatPageTitle,
  makeDownload,
  request,
  uri,
} from '~/utils';
import { usePlayerMediaVolume } from '~/composables/usePlayerMediaVolume';
import { usePlayerShortcutHelp } from '~/composables/usePlayerShortcutHelp';
import { usePlayerShortcuts } from '~/composables/usePlayerShortcuts';
import { usePlayerSubtitles } from '~/composables/usePlayerSubtitles';
import {
  canRequestFullscreen,
  exitDocumentFullscreen,
  getFullscreenElement,
  requestElementFullscreen,
} from '~/utils/fullscreen';

import type { StoreItem } from '~/types/store';
import type { FileInfo, PlayerSourceElement } from '~/types/video';

const config = useYtpConfig();

const props = defineProps<{ item: StoreItem }>();
const emitter = defineEmits<{
  (e: 'closeModel'): void;
  (e: 'error', message: string): void;
  (e: 'playback-state-change', isPlaying: boolean): void;
}>();

const {
  volume,
  muted,
  effectiveVolume,
  setVolume,
  changeVolume,
  toggleMute: toggleStoredMute,
} = usePlayerMediaVolume();
const showShortcutHelp = usePlayerShortcutHelp();

const playerContainer = ref<HTMLElement | null>(null);
const videoElement = ref<HTMLVideoElement | null>(null);
const assOverlayElement = ref<HTMLElement | null>(null);
const playerInfo = ref<FileInfo | null>(null);
const sources = ref<Array<PlayerSourceElement>>([]);
const loading = ref(true);
const loadingError = ref('');
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
const destroyed = ref(false);
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
let gainContext: AudioContext | null = null;
let gainSource: MediaElementAudioSourceNode | null = null;
let gainNode: GainNode | null = null;
let gainElement: HTMLMediaElement | null = null;
let unbindMediaSession: null | (() => void) = null;
let hls: Hls | null = null;

const isApple = /(iPhone|iPod|iPad).*AppleWebKit/i.test(navigator.userAgent);
const mediaFile = computed(() => props.item.filename || '');
const subtitleManifestUrl = computed(() => currentPlaybackUrl('api/player/subtitles/manifest'));
const canPlay = computed(() => Boolean(mediaFile.value && !loadingError.value));
const shouldRender = computed(() => active.value && !loading.value);
const isPlaying = computed(() => !paused.value);
const progress = computed(() => {
  if (!duration.value) return 0;
  return Math.round((currentTime.value / duration.value) * 1000);
});
const timeLabel = computed(() => {
  const currentLabel = formatDuration(Math.round(currentTime.value));
  const durationLabel = duration.value ? formatDuration(Math.round(duration.value)) : '--:--';
  return `${currentLabel} / ${durationLabel}`;
});
const showSeekZones = computed(() => {
  return Boolean(isTouchDevice.value && isPlaying.value);
});
const useGainFallback = computed(() => {
  return Boolean(isTouchDevice.value && getAudioContextCtor());
});

const {
  subtitleLoading,
  subtitleLoadError,
  subtitleEnabled,
  nativeSubtitleTrack,
  usesAssSubtitleTrack,
  hasSubtitles,
} = usePlayerSubtitles({
  manifestUrl: subtitleManifestUrl,
  isVideo: computed(() => !isAudio.value),
  canPlay,
  shouldRender,
  assLayoutVersion,
  video: videoElement,
  overlay: assOverlayElement,
});

useHead(() => (title.value ? { title: formatPageTitle(`Playing: ${title.value}`) } : {}));

watch(
  [volume, muted],
  ([nextVolume]) => {
    const normalizedVolume = normalizeMediaVolume(nextVolume);
    if (normalizedVolume !== nextVolume) {
      volume.value = normalizedVolume;
      return;
    }

    applyStoredMediaState(videoElement.value);
    syncVideoState();
  },
  { immediate: true },
);

watch(
  videoElement,
  (element, previousElement) => {
    if (previousElement && previousElement !== element) {
      disconnectGainController();
    }

    applyStoredMediaState(element);
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

function normalizeMediaVolume(volume: number): number {
  if (!Number.isFinite(volume)) return 1;
  return Math.min(1, Math.max(0, volume));
}

function getAudioContextCtor(): typeof AudioContext | null {
  if (!import.meta.client) return null;

  const maybeWindow = window as Window &
    typeof globalThis & {
      webkitAudioContext?: typeof AudioContext;
    };
  return maybeWindow.AudioContext || maybeWindow.webkitAudioContext || null;
}

function currentPlaybackUrl(base: string, playlist: boolean = false): string {
  if (!props.item.filename) {
    return '';
  }

  if (base === 'm3u8') {
    return makeDownload(config, props.item, base, true);
  }

  return makeDownload(config, props.item, base, playlist);
}

function activatePlayer() {
  active.value = true;
  void nextTick(async () => {
    applyStoredMediaState(videoElement.value);
    await resumeGainController();
    try {
      await videoElement.value?.play();
    } catch {}
    syncVideoState();
    showControls();
  });
}

function handleVideoLoadedData() {
  syncVideoState();
}

function handleVideoLoadedMetadata() {
  loadingError.value = '';
  syncVideoState();
  showControls();
  scheduleAssLayoutRefresh();
  if (videoElement.value) {
    updateMediaSessionPosition(videoElement.value);
  }
}

function handleVideoTimeUpdate() {
  syncVideoState();
  if (videoElement.value) {
    updateMediaSessionPosition(videoElement.value);
  }
}

function handleVideoPlay() {
  loadingError.value = '';
  void resumeGainController();
  syncVideoState();
  showControls();
  emitter('playback-state-change', true);
}

function handleVideoPause() {
  syncVideoState();
  clearControlsHideTimeout();
  controlsVisible.value = true;
  emitter('playback-state-change', false);
}

function handleVideoClick() {
  if (isTouchDevice.value) {
    return;
  }

  clearPendingVideoClickTimeout();
  pendingVideoClickTimeout = window.setTimeout(() => {
    pendingVideoClickTimeout = 0;
    toggleControls();
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

  if (!useGainFallback.value) {
    const normalizedVolume = normalizeMediaVolume(target.volume);
    if (Math.abs(volume.value - normalizedVolume) > 0.001) {
      volume.value = normalizedVolume;
    }
  }

  syncVideoState();
  updateMediaSessionPosition(target);
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
  const target = event.target as HTMLInputElement | null;
  if (!target || !videoElement.value || !duration.value) return;

  const sliderValue = Number(target.value);
  if (!Number.isFinite(sliderValue)) return;

  videoElement.value.currentTime = (sliderValue / 1000) * duration.value;
  syncVideoState();
  showControls();
}

function handleVolumeInput(event: Event) {
  const target = event.target as HTMLInputElement | null;
  if (!target || !videoElement.value) return;

  setVolume(Number(target.value) / 100);
  applyStoredMediaState(videoElement.value);
  syncVideoState();
  showControls();
  void resumeGainController();
}

async function togglePlayback() {
  if (!videoElement.value) return;

  try {
    if (videoElement.value.paused) {
      await resumeGainController();
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
  toggleStoredMute();
  applyStoredMediaState(videoElement.value);
  syncVideoState();
  showControls();
  void resumeGainController();
}

function seekBy(deltaSeconds: number) {
  if (!videoElement.value) return;

  if (!isPlaying.value) {
    showControls();
    return;
  }

  const duration = Number.isFinite(videoElement.value.duration) ? videoElement.value.duration : 0;
  const nextTime = Math.min(
    Math.max(videoElement.value.currentTime + deltaSeconds, 0),
    duration || Infinity,
  );
  videoElement.value.currentTime = nextTime;
  syncVideoState();
  showControls();
}

function applyStoredMediaState(element: HTMLMediaElement | null) {
  if (!element) return;

  if (useGainFallback.value) {
    ensureGainController(element);
    if (element.muted !== muted.value) {
      element.muted = muted.value;
    }
    if (gainNode) {
      gainNode.gain.value = effectiveVolume.value;
    }
    return;
  }

  const normalizedVolume = normalizeMediaVolume(volume.value);
  if (Math.abs(element.volume - normalizedVolume) > 0.001) {
    element.volume = normalizedVolume;
  }

  if (element.muted !== muted.value) {
    element.muted = muted.value;
  }
}

function ensureGainController(element: HTMLMediaElement | null) {
  if (!useGainFallback.value || !element) return;

  if (gainElement === element && gainNode) {
    gainNode.gain.value = effectiveVolume.value;
    return;
  }

  disconnectGainController();

  const AudioContextCtor = getAudioContextCtor();
  if (!AudioContextCtor) return;

  if (!gainContext || gainContext.state === 'closed') {
    try {
      gainContext = new AudioContextCtor();
    } catch {
      gainContext = null;
      return;
    }
  }

  try {
    gainSource = gainContext.createMediaElementSource(element);
    gainNode = gainContext.createGain();
    gainSource.connect(gainNode);
    gainNode.connect(gainContext.destination);
    gainNode.gain.value = effectiveVolume.value;
    gainElement = element;
  } catch {
    disconnectGainController();
  }
}

async function resumeGainController() {
  if (!useGainFallback.value) return;

  ensureGainController(videoElement.value);
  if (!gainContext || gainContext.state !== 'suspended') return;

  try {
    await gainContext.resume();
  } catch {}
}

function disconnectGainController() {
  try {
    gainSource?.disconnect();
  } catch {}

  try {
    gainNode?.disconnect();
  } catch {}

  gainSource = null;
  gainNode = null;
  gainElement = null;
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
  emitter('playback-state-change', !video.paused);
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
  if (!controlsVisible.value) {
    showControls();
    return;
  }

  if (videoElement.value?.paused) {
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
  const onPause = async (event: Event) => {
    const target = (event.currentTarget as HTMLVideoElement) ?? null;
    if (!target || destroyed.value) {
      return;
    }
    const dataUrl = await captureFrame(target);
    if (dataUrl) {
      poster.value = dataUrl;
      hasPoster.value = true;
      applyMediaSessionMetadata();
    }
  };

  el.addEventListener('loadedmetadata', onLoadedMetadata);
  el.addEventListener('timeupdate', onTimeUpdate);
  el.addEventListener('ratechange', onRateChange);
  el.addEventListener('seeked', onSeeked);
  el.addEventListener('pause', onPause);

  return () => {
    el.removeEventListener('loadedmetadata', onLoadedMetadata);
    el.removeEventListener('timeupdate', onTimeUpdate);
    el.removeEventListener('ratechange', onRateChange);
    el.removeEventListener('seeked', onSeeked);
    el.removeEventListener('pause', onPause);
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

async function captureFrame(el: HTMLVideoElement): Promise<string> {
  if (!el || destroyed.value) {
    return '';
  }
  if (el.videoWidth === 0 || el.videoHeight === 0) {
    return '';
  }

  const width = el.videoWidth;
  const height = el.videoHeight;

  try {
    if ('OffscreenCanvas' in window) {
      const canvas = new (window as any).OffscreenCanvas(width, height);
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        return '';
      }
      ctx.drawImage(el, 0, 0, width, height);
      const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.86 });
      return await new Promise<string>((resolve) => {
        const fileReader = new FileReader();
        fileReader.onload = () => resolve(String(fileReader.result));
        fileReader.readAsDataURL(blob);
      });
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      return '';
    }
    ctx.drawImage(el, 0, 0, width, height);
    return canvas.toDataURL('image/jpeg', 0.86);
  } catch {
    return '';
  }
}

async function captureFirstFramePoster(el: HTMLVideoElement): Promise<void> {
  if (!el || destroyed.value || hasPoster.value) {
    return;
  }
  if (el.videoWidth === 0 || el.videoHeight === 0) {
    return;
  }

  const dataUrl = await captureFrame(el);
  if (!dataUrl) {
    return;
  }

  poster.value = dataUrl;
  hasPoster.value = true;
  applyMediaSessionMetadata();
}

async function restoreDefaultTextTrack() {
  const el = videoElement.value;
  if (!el) {
    return;
  }

  try {
    const tracksList = el.textTracks;
    if (!tracksList || tracksList.length === 0) {
      return;
    }

    const firstTrack = tracksList[0] as TextTrack | undefined;
    const needsReload = firstTrack && (!firstTrack.cues || firstTrack.cues.length === 0);

    if (needsReload) {
      const trackElements = el.querySelectorAll('track');

      trackElements.forEach((trackEl, idx) => {
        const parent = trackEl.parentNode;
        const clone = trackEl.cloneNode(true) as HTMLTrackElement;
        trackEl.remove();
        setTimeout(() => {
          if (parent) {
            parent.appendChild(clone);
            clone.addEventListener(
              'load',
              () => {
                const trackObj = clone.track;
                if (trackObj) {
                  trackObj.mode = idx === 0 && subtitleEnabled.value ? 'showing' : 'disabled';
                }
              },
              { once: true },
            );
          }
        }, idx * 10);
      });

      return;
    }

    for (let i = 0; i < tracksList.length; i += 1) {
      const track = tracksList[i] as TextTrack | undefined;
      if (track) {
        track.mode = 'disabled';
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 50));

    for (let i = 0; i < tracksList.length; i += 1) {
      const track = tracksList[i] as TextTrack | undefined;
      if (!track) {
        continue;
      }
      track.mode = i === 0 && subtitleEnabled.value ? 'showing' : 'disabled';
    }
  } catch (error) {
    console.warn('Failed to restore subtitle track state', error);
  }
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
    loadingError.value = 'No media file is available for playback.';
    emitter('error', loadingError.value);
    emitter('closeModel');
    return;
  }

  loading.value = true;
  loadingError.value = '';

  const req = await request(currentPlaybackUrl('api/file/info'));
  const response: FileInfo = await req.json();

  if (!req.ok) {
    loading.value = false;
    loadingError.value = response?.error || 'Failed to fetch video info. Unknown error';
    emitter('error', loadingError.value);
    emitter('closeModel');
    return;
  }

  playerInfo.value = response;

  poster.value = '/images/placeholder.png';
  hasPoster.value = false;

  if (props.item.extras?.thumbnail) {
    poster.value = `/api/thumbnail?url=${encodePath(props.item.extras.thumbnail)}`;
    hasPoster.value = true;
  } else if (response.sidecar?.image?.[0]?.file) {
    poster.value = makeDownload(config, { filename: response.sidecar.image[0].file });
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
    const src = currentPlaybackUrl(allowedCodec ? 'api/download' : 'm3u8', !allowedCodec);
    sources.value.push({
      src,
      type: allowedCodec ? response.mimetype : 'application/x-mpegURL',
      onerror: (err: Event) => void src_error(err),
    });
    usingHls.value = !allowedCodec;
  } else {
    sources.value.push({
      src: currentPlaybackUrl('api/download'),
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

  if (isApple) {
    document.documentElement.style.setProperty('--webkit-text-track-display', 'block');
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

  applyStoredMediaState(videoElement.value);
  restoreDefaultTextTrack();

  if (hasVideo.value) {
    if ('requestVideoFrameCallback' in videoElement.value) {
      (videoElement.value as any).requestVideoFrameCallback(() =>
        captureFirstFramePoster(videoElement.value!),
      );
    } else {
      const tryOnce = () => captureFirstFramePoster(videoElement.value!);
      (videoElement.value as any).addEventListener('loadeddata', tryOnce, { once: true });
    }
  }
}

async function src_error(event: Event) {
  if (hls) {
    return;
  }

  await nextTick();
  if (destroyed.value) {
    return;
  }

  if (videoElement.value?.paused && !active.value) {
    return;
  }

  console.warn('Source failed to load, attempting HLS fallback via hls.js...', event);
  attach_hls(currentPlaybackUrl('m3u8', true));
}

function attach_hls(link: string) {
  if (!videoElement.value) {
    return;
  }

  if (hls) {
    hls.destroy();
  }

  hls = new Hls({
    debug: false,
    enableWorker: true,
    lowLatencyMode: true,
    backBufferLength: 120,
    fragLoadingTimeOut: 200000,
  });

  hls.on(Hls.Events.MANIFEST_PARSED, () => applyMediaSessionMetadata());
  hls.on(Hls.Events.MANIFEST_PARSED, async () => {
    await new Promise((resolve) => setTimeout(resolve, 100));
    await restoreDefaultTextTrack();
  });

  hls.on(Hls.Events.MEDIA_ATTACHED, async () => {
    await new Promise((resolve) => setTimeout(resolve, 200));
    await restoreDefaultTextTrack();
  });

  hls.on(Hls.Events.LEVEL_LOADED, () => {
    if (videoElement.value) {
      if ('requestVideoFrameCallback' in videoElement.value) {
        (videoElement.value as any).requestVideoFrameCallback(() =>
          captureFirstFramePoster(videoElement.value!),
        );
      } else {
        const once = () => captureFirstFramePoster(videoElement.value!);
        (videoElement.value as any).addEventListener('loadeddata', once, { once: true });
      }
    }
  });

  hls.loadSource(link);
  hls.attachMedia(videoElement.value);
  usingHls.value = true;
}

function forceSwitchToHls() {
  if (usingHls.value) {
    return;
  }

  if (!hasVideo.value) {
    useNotification().error('Cannot switch to HLS: stream has no video track.');
    return;
  }

  attach_hls(currentPlaybackUrl('m3u8', true));
}

usePlayerShortcuts({
  enabled: computed(() => active.value && Boolean(videoElement.value)),
  media: videoElement,
  video: videoElement,
  adjustVolume: (delta) => {
    changeVolume(delta);
    applyStoredMediaState(videoElement.value);
    syncVideoState();
    showControls();
    void resumeGainController();
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

onMounted(async () => {
  disableOpacity();
  isTouchDevice.value = window.matchMedia('(pointer: coarse)').matches;
  document.addEventListener('fullscreenchange', syncFullscreenState);
  document.addEventListener('webkitfullscreenchange', syncFullscreenState as EventListener);
  window.addEventListener('resize', scheduleAssLayoutRefresh);
  window.addEventListener('orientationchange', scheduleAssLayoutRefresh);
  syncFullscreenState();
  await loadPlayerInfo();
});

onBeforeUnmount(() => {
  enableOpacity();
  document.removeEventListener('fullscreenchange', syncFullscreenState);
  document.removeEventListener('webkitfullscreenchange', syncFullscreenState as EventListener);
  window.removeEventListener('resize', scheduleAssLayoutRefresh);
  window.removeEventListener('orientationchange', scheduleAssLayoutRefresh);

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

  disconnectGainController();
  if (gainContext && gainContext.state !== 'closed') {
    void gainContext.close().catch(() => {});
  }
  gainContext = null;

  if (videoElement.value) {
    destroyed.value = true;
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
});
</script>

<style scoped>
.share-video-element::-webkit-media-controls {
  display: none;
}

.share-video-element::-webkit-media-controls-fullscreen-button {
  display: none;
}
</style>
