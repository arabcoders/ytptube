import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  watch,
  type MaybeRefOrGetter,
  toValue,
} from 'vue';
import type { SubtitleTrack } from '~/types/subtitles';
import { request } from '~/utils';
import { loadPlayerFonts, type PlayerFont } from '~/utils/playback';

type AssRendererInstance = {
  destroy(): unknown;
  show(): unknown;
};

type AssRendererConstructor = new (
  content: string,
  video: HTMLVideoElement,
  options: { container: HTMLElement; resampling: 'video_height' },
) => AssRendererInstance;

type UsePlayerSubtitlesOptions = {
  canPlay: MaybeRefOrGetter<boolean>;
  shouldRender: MaybeRefOrGetter<boolean>;
  assLayoutVersion?: MaybeRefOrGetter<number>;
  video: MaybeRefOrGetter<HTMLVideoElement | null>;
  overlay: MaybeRefOrGetter<HTMLElement | null>;
  tracks: MaybeRefOrGetter<SubtitleTrack[]>;
  fonts?: MaybeRefOrGetter<PlayerFont[]>;
  fetchText?: (url: string, signal?: AbortSignal) => Promise<string>;
  loadRenderer?: () => Promise<AssRendererConstructor>;
};

async function defaultFetchSubtitleText(url: string, signal?: AbortSignal): Promise<string> {
  const res = await request(url, {
    signal,
    headers: { Accept: 'text/plain, text/vtt, text/x-ssa' },
  });
  if (!res.ok) {
    throw new Error('Subtitle fetch failed');
  }

  return res.text();
}

async function defaultLoadAssRenderer(): Promise<AssRendererConstructor> {
  const mod = await import('assjs');
  return mod.default as AssRendererConstructor;
}

export function usePlayerSubtitles(options: UsePlayerSubtitlesOptions) {
  const fetchText = options.fetchText || defaultFetchSubtitleText;
  const loadRenderer = options.loadRenderer || defaultLoadAssRenderer;
  const tracks = ref<SubtitleTrack[]>([]);
  const subtitleLoadError = ref('');
  const subtitleEnabled = ref(true);
  const selectedTrackId = ref<string | null>(null);
  const selectedTrack = computed(
    () => tracks.value.find((track) => track.id === selectedTrackId.value) || null,
  );
  const nativeSubtitleTrack = computed(() => {
    const track = selectedTrack.value;
    return subtitleEnabled.value && track?.renderer === 'native' ? track : null;
  });
  const usesAssTrack = computed(() => selectedTrack.value?.renderer === 'assjs');
  const hasSubtitles = computed(() => tracks.value.length > 0);

  let assRenderer: AssRendererInstance | null = null;
  let assRequestId = 0;
  let cachedAssSubtitleUrl = '';
  let cachedAssSubtitleContent = '';
  let assAbort: AbortController | null = null;
  let releaseFonts: (() => void) | null = null;

  function destroyAssRenderer() {
    assRenderer?.destroy();
    assRenderer = null;
    releaseFonts?.();
    releaseFonts = null;
  }

  function syncTracks() {
    assRequestId += 1;
    assAbort?.abort();
    destroyAssRenderer();
    tracks.value = toValue(options.canPlay) ? toValue(options.tracks) : [];
    selectedTrackId.value =
      tracks.value.find((track) => track.renderer !== 'unsupported')?.id || null;
    subtitleLoadError.value = '';
  }

  async function syncAssRenderer() {
    const track = selectedTrack.value;
    const shouldRender = toValue(options.shouldRender);
    const video = toValue(options.video);
    const overlay = toValue(options.overlay);
    const requestId = ++assRequestId;
    assAbort?.abort();
    const abort = new AbortController();
    assAbort = abort;

    destroyAssRenderer();

    if (
      !track ||
      track.renderer !== 'assjs' ||
      !subtitleEnabled.value ||
      !shouldRender ||
      !video ||
      !overlay
    ) {
      return;
    }

    try {
      const subtitleContent =
        cachedAssSubtitleUrl === track.url
          ? cachedAssSubtitleContent
          : await fetchText(track.url, abort.signal);
      if (requestId !== assRequestId) {
        return;
      }

      if (cachedAssSubtitleUrl !== track.url) {
        cachedAssSubtitleUrl = track.url;
        cachedAssSubtitleContent = subtitleContent;
      }

      const Ass = await loadRenderer();
      if (requestId !== assRequestId) {
        return;
      }
      const release = await loadPlayerFonts(
        options.fonts ? toValue(options.fonts) : [],
        abort.signal,
      );
      if (requestId !== assRequestId) {
        release();
        return;
      }
      releaseFonts = release;

      assRenderer = new Ass(subtitleContent, video, {
        container: overlay,
        resampling: 'video_height',
      }) as AssRendererInstance;
      assRenderer.show();
      video.dispatchEvent(new Event('seeking'));
      if (!video.paused) {
        video.dispatchEvent(new Event('playing'));
      }
      subtitleLoadError.value = '';
    } catch {
      if (requestId === assRequestId) {
        subtitleLoadError.value =
          useNuxtApp().$i18n?.t('player.subtitleRenderFailed') ?? 'player.subtitleRenderFailed';
        destroyAssRenderer();
      }
    }
  }

  watch(() => [toValue(options.canPlay), toValue(options.tracks)], syncTracks, { immediate: true });

  watch(
    () => [
      selectedTrack.value?.url || '',
      selectedTrack.value?.renderer || '',
      subtitleEnabled.value,
      toValue(options.shouldRender),
      toValue(options.assLayoutVersion) || 0,
      toValue(options.video),
      toValue(options.overlay),
    ],
    () => {
      void syncAssRenderer();
    },
    { immediate: true },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      assRequestId += 1;
      assAbort?.abort();
      destroyAssRenderer();
    });
  }

  return {
    subtitleTracks: tracks,
    subtitleLoadError,
    subtitleEnabled,
    selectedSubtitleTrack: selectedTrack,
    selectedSubtitleTrackId: selectedTrackId,
    nativeSubtitleTrack,
    usesAssSubtitleTrack: usesAssTrack,
    hasSubtitles,
  };
}
