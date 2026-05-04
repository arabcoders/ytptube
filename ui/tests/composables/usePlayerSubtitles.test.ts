import { afterEach, beforeEach, describe, expect, it, mock } from 'bun:test';
import { nextTick, ref } from 'vue';

type MockResponseInput = {
  ok: boolean;
  status: number;
  jsonData?: unknown;
  textData?: string;
};

const runtimeConfig = {
  app: {
    baseURL: '/',
  },
};

const testGlobals = globalThis as typeof globalThis & {
  useRuntimeConfig?: () => typeof runtimeConfig;
  useNotification?: () => { error: ReturnType<typeof mock> };
};

const notificationErrorMock = mock(() => {});

testGlobals.useRuntimeConfig = () => runtimeConfig;
testGlobals.useNotification = () => ({ error: notificationErrorMock });

mock.module('#imports', () => ({
  useRuntimeConfig: () => runtimeConfig,
  useNotification: () => ({ error: notificationErrorMock }),
}));

function createMockResponse({ ok, status, jsonData, textData }: MockResponseInput): Response {
  return {
    ok,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    redirected: false,
    statusText: ok ? 'OK' : 'Error',
    type: 'basic',
    url: '',
    body: null,
    bodyUsed: false,
    clone() {
      return this;
    },
    async json() {
      return jsonData;
    },
    async text() {
      return textData ?? JSON.stringify(jsonData ?? {});
    },
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
  } as Response;
}

async function flushPromises(times = 4) {
  for (let index = 0; index < times; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
}

describe('usePlayerSubtitles', () => {
  const fetchMock = mock(async (_input: RequestInfo | URL) => createMockResponse({ ok: true, status: 200, jsonData: {} }));
  const assShowMock = mock(() => {});
  const assDestroyMock = mock(() => {});
  const assConstructorMock = mock(() => ({
    show: assShowMock,
    destroy: assDestroyMock,
  }));

  beforeEach(() => {
    runtimeConfig.app.baseURL = '/';
    fetchMock.mockClear();
    assShowMock.mockClear();
    assDestroyMock.mockClear();
    assConstructorMock.mockClear();
    notificationErrorMock.mockClear();
    globalThis.fetch = fetchMock as typeof fetch;
  });

  afterEach(() => {
    delete (globalThis as { fetch?: typeof fetch }).fetch;
  });

  it('loads subtitle manifest and exposes the preferred native track', async () => {
    fetchMock.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          subtitles: [
            {
              lang: 'en',
              name: 'English',
              source_format: 'vtt',
              delivery_format: 'vtt',
              renderer: 'native',
              url: '/api/player/subtitles/vtt/video.vtt',
            },
            {
              lang: 'en',
              name: 'Styled',
              source_format: 'ass',
              delivery_format: 'ass',
              renderer: 'assjs',
              url: '/api/player/subtitles/ass/video.ass',
            },
          ],
        },
      }),
    );

    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const manifestUrl = ref('/api/player/subtitles/manifest/video%20file.mkv');
    const isVideo = ref(true);
    const canPlay = ref(true);
    const shouldRender = ref(false);
    const video = ref<HTMLVideoElement | null>(document.createElement('video'));
    const overlay = ref<HTMLElement | null>(document.createElement('div'));

    const { hasSubtitles, nativeSubtitleTrack, selectedSubtitleTrack, usesAssSubtitleTrack } =
      usePlayerSubtitles({
        manifestUrl,
        isVideo,
        canPlay,
        shouldRender,
        video,
        overlay,
      });

    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith('/api/player/subtitles/manifest/video%20file.mkv', expect.anything());
    expect(hasSubtitles.value).toBe(true);
    expect(selectedSubtitleTrack.value?.source_format).toBe('vtt');
    expect(nativeSubtitleTrack.value?.url).toBe('/api/player/subtitles/vtt/video.vtt');
    expect(usesAssSubtitleTrack.value).toBe(false);
  });

  it('uses the provided full manifest path including folders', async () => {
    fetchMock.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { subtitles: [] },
      }),
    );

    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');

    usePlayerSubtitles({
      manifestUrl: ref(
        '/api/player/subtitles/manifest/youtube/Channel%20Name/Season%202026/video%20file.mkv',
      ),
      isVideo: ref(true),
      canPlay: ref(true),
      shouldRender: ref(false),
      video: ref<HTMLVideoElement | null>(document.createElement('video')),
      overlay: ref<HTMLElement | null>(document.createElement('div')),
    });

    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/player/subtitles/manifest/youtube/Channel%20Name/Season%202026/video%20file.mkv',
      expect.anything(),
    );
  });

  it('creates and destroys an ASS renderer for ASS subtitles when playback becomes active', async () => {
    fetchMock.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          subtitles: [
            {
              lang: 'en',
              name: 'Styled',
              source_format: 'ass',
              delivery_format: 'ass',
              renderer: 'assjs',
              url: '/api/player/subtitles/ass/video.ass',
            },
          ],
        },
      }),
    );

    const fetchText = mock(async () => '[Script Info]\nTitle: Demo\n');
    const loadRenderer = mock(async () => assConstructorMock as any);

    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const manifestUrl = ref('/api/player/subtitles/manifest/video.mkv');
    const isVideo = ref(true);
    const canPlay = ref(true);
    const shouldRender = ref(false);
    const video = ref<HTMLVideoElement | null>(document.createElement('video'));
    const overlay = ref<HTMLElement | null>(document.createElement('div'));

    const { usesAssSubtitleTrack } = usePlayerSubtitles({
      manifestUrl,
      isVideo,
      canPlay,
      shouldRender,
      video,
      overlay,
      fetchText,
      loadRenderer,
    });

    await flushPromises();

    expect(usesAssSubtitleTrack.value).toBe(true);
    expect(assConstructorMock).not.toHaveBeenCalled();

    shouldRender.value = true;
    await flushPromises(5);

    expect(fetchText).toHaveBeenCalledWith('/api/player/subtitles/ass/video.ass');
    expect(loadRenderer).toHaveBeenCalledTimes(1);
    expect(assConstructorMock).toHaveBeenCalledTimes(1);
    expect(assShowMock).toHaveBeenCalledTimes(1);

    manifestUrl.value = '/api/player/subtitles/manifest/second.mkv';
    fetchMock.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { subtitles: [] },
      }),
    );
    await flushPromises();

    expect(assDestroyMock.mock.calls.length).toBeGreaterThanOrEqual(1);
  });

  it('recreates an ASS renderer when the layout version changes without refetching subtitles', async () => {
    fetchMock.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          subtitles: [
            {
              lang: 'en',
              name: 'Styled',
              source_format: 'ass',
              delivery_format: 'ass',
              renderer: 'assjs',
              url: '/api/player/subtitles/ass/video.ass',
            },
          ],
        },
      }),
    );

    const fetchText = mock(async () => '[Script Info]\nTitle: Demo\n');
    const loadRenderer = mock(async () => assConstructorMock as any);

    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const assLayoutVersion = ref(0);

    usePlayerSubtitles({
      manifestUrl: ref('/api/player/subtitles/manifest/video.mkv'),
      isVideo: ref(true),
      canPlay: ref(true),
      shouldRender: ref(true),
      assLayoutVersion,
      video: ref<HTMLVideoElement | null>(document.createElement('video')),
      overlay: ref<HTMLElement | null>(document.createElement('div')),
      fetchText,
      loadRenderer,
    });

    await flushPromises(5);

    expect(fetchText).toHaveBeenCalledTimes(1);
    expect(assConstructorMock).toHaveBeenCalledTimes(1);

    assLayoutVersion.value += 1;
    await flushPromises(5);

    expect(fetchText).toHaveBeenCalledTimes(1);
    expect(assDestroyMock.mock.calls.length).toBeGreaterThanOrEqual(1);
    expect(assConstructorMock).toHaveBeenCalledTimes(2);
  });
});
