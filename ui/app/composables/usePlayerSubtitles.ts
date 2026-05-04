import {
  computed,
  getCurrentScope,
  onScopeDispose,
  ref,
  watch,
  type MaybeRefOrGetter,
  toValue,
} from 'vue';
import type { SubtitleManifestResponse, SubtitleTrack } from '~/types/subtitles';
import { parse_api_error, request } from '~/utils';

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
  manifestUrl: MaybeRefOrGetter<string>;
  isVideo: MaybeRefOrGetter<boolean>;
  canPlay: MaybeRefOrGetter<boolean>;
  shouldRender: MaybeRefOrGetter<boolean>;
  assLayoutVersion?: MaybeRefOrGetter<number>;
  video: MaybeRefOrGetter<HTMLVideoElement | null>;
  overlay: MaybeRefOrGetter<HTMLElement | null>;
  fetchText?: (url: string) => Promise<string>;
  loadRenderer?: () => Promise<AssRendererConstructor>;
};

async function defaultFetchSubtitleText(url: string): Promise<string> {
  const res = await request(url, { headers: { Accept: 'text/plain, text/vtt, text/x-ssa' } });
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
  const subtitleLoading = ref(false);
  const subtitleLoadError = ref('');
  const subtitleEnabled = ref(true);
  const selectedTrack = computed(() => tracks.value[0] || null);
  const nativeSubtitleTrack = computed(() => {
    const track = selectedTrack.value;
    return subtitleEnabled.value && track?.renderer === 'native' ? track : null;
  });
  const usesAssTrack = computed(() => selectedTrack.value?.renderer === 'assjs');
  const hasSubtitles = computed(() => tracks.value.length > 0);

  let assRenderer: AssRendererInstance | null = null;
  let subtitleRequestId = 0;
  let assRequestId = 0;
  let cachedAssSubtitleUrl = '';
  let cachedAssSubtitleContent = '';

  function destroyAssRenderer() {
    assRenderer?.destroy();
    assRenderer = null;
  }

  async function loadTracks() {
    const manifestUrl = toValue(options.manifestUrl);
    const isVideo = toValue(options.isVideo);
    const canPlay = toValue(options.canPlay);
    const requestId = ++subtitleRequestId;

    assRequestId += 1;
    destroyAssRenderer();
    tracks.value = [];
    subtitleLoadError.value = '';

    if (!manifestUrl || !isVideo || !canPlay) {
      subtitleLoading.value = false;
      return;
    }

    subtitleLoading.value = true;

    try {
      const res = await request(manifestUrl);
      const payload = (await res.json()) as SubtitleManifestResponse | { error?: string };
      if (!res.ok) {
        throw new Error(await parse_api_error(payload));
      }

      if (requestId !== subtitleRequestId) {
        return;
      }

      tracks.value = (payload as SubtitleManifestResponse).subtitles || [];
      if (tracks.value.length > 0) {
        subtitleEnabled.value = true;
      }
    } catch {
      if (requestId !== subtitleRequestId) {
        return;
      }

      subtitleLoadError.value = 'Failed to load subtitles for this video.';
    } finally {
      if (requestId === subtitleRequestId) {
        subtitleLoading.value = false;
      }
    }
  }

  async function syncAssRenderer() {
    const track = selectedTrack.value;
    const shouldRender = toValue(options.shouldRender);
    const video = toValue(options.video);
    const overlay = toValue(options.overlay);
    const requestId = ++assRequestId;

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
        cachedAssSubtitleUrl === track.url ? cachedAssSubtitleContent : await fetchText(track.url);
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
        subtitleLoadError.value = 'Failed to render ASS subtitles in the browser.';
      }

      destroyAssRenderer();
    }
  }

  watch(
    () => [toValue(options.manifestUrl), toValue(options.isVideo), toValue(options.canPlay)],
    () => {
      void loadTracks();
    },
    { immediate: true },
  );

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
      destroyAssRenderer();
    });
  }

  return {
    subtitleTracks: tracks,
    subtitleLoading,
    subtitleLoadError,
    subtitleEnabled,
    selectedSubtitleTrack: selectedTrack,
    nativeSubtitleTrack,
    usesAssSubtitleTrack: usesAssTrack,
    hasSubtitles,
    loadSelectedSubtitles: loadTracks,
  };
}
