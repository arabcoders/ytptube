import { afterEach, beforeEach, describe, expect, it, mock } from 'bun:test';
import { effectScope, nextTick, ref } from 'vue';
import type { SubtitleTrack } from '~/types/subtitles';

async function flushPromises(times = 4) {
  for (let index = 0; index < times; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
}

describe('usePlayerSubtitles', () => {
  const originalEvent = globalThis.Event;
  const assShowMock = mock(() => {});
  const assDestroyMock = mock(() => {});
  const assConstructorMock = mock(() => {});
  const styled: SubtitleTrack = {
    id: 'e8',
    lang: 'en',
    name: 'Styled',
    source_format: 'ass',
    delivery_format: 'ass',
    renderer: 'assjs',
    url: '/api/player/media/resource/subtitles/e8',
  };

  class AssRenderer {
    constructor() {
      assConstructorMock();
    }

    show() {
      assShowMock();
    }

    destroy() {
      assDestroyMock();
    }
  }

  beforeEach(() => {
    globalThis.Event = window.Event;
    assShowMock.mockClear();
    assDestroyMock.mockClear();
    assConstructorMock.mockClear();
  });

  afterEach(() => {
    globalThis.Event = originalEvent;
  });

  it('ignore_stale_ass_error', async () => {
    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const scope = effectScope();
    let rejectFirst: (error: Error) => void = () => {};
    const first = new Promise<string>((_resolve, reject) => {
      rejectFirst = reject;
    });
    let firstSignal: AbortSignal | undefined;
    const subtitles = scope.run(() =>
      usePlayerSubtitles({
        canPlay: true,
        shouldRender: true,
        tracks: [styled, { ...styled, id: 'e9', url: '/second.ass' }],
        video: ref(document.createElement('video')),
        overlay: ref(document.createElement('div')),
        fetchText: (url, signal) => {
          if (url === styled.url) {
            firstSignal = signal;
            return first;
          }
          return Promise.resolve('[Script Info]\nTitle: Second\n');
        },
        loadRenderer: async () => AssRenderer,
      }),
    )!;
    try {
      await flushPromises();
      subtitles.selectedSubtitleTrackId.value = 'e9';
      await flushPromises(8);
      expect(firstSignal?.aborted).toBe(true);
      expect(assShowMock).toHaveBeenCalledTimes(1);
      const destroyed = assDestroyMock.mock.calls.length;
      rejectFirst(new Error('stale request'));
      await flushPromises();
      expect(assDestroyMock.mock.calls.length).toBe(destroyed);
      expect(subtitles.subtitleLoadError.value).toBe('');
    } finally {
      rejectFirst(new Error('cleanup'));
      scope.stop();
      await flushPromises();
    }
  });

  it('load_native_track', async () => {
    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const scope = effectScope();
    const native: SubtitleTrack = {
      id: 'x0',
      lang: 'en',
      name: 'English',
      source_format: 'vtt',
      delivery_format: 'vtt',
      renderer: 'native',
      url: '/api/player/media/resource/subtitles/x0',
    };
    const tracks = ref<SubtitleTrack[]>([]);
    const subtitles = scope.run(() =>
      usePlayerSubtitles({
        tracks,
        canPlay: true,
        shouldRender: false,
        video: ref(document.createElement('video')),
        overlay: ref(document.createElement('div')),
      }),
    )!;
    try {
      expect(subtitles.hasSubtitles.value).toBe(false);
      tracks.value = [native, styled];
      await flushPromises();
      expect(subtitles.hasSubtitles.value).toBe(true);
      expect(subtitles.selectedSubtitleTrack.value?.source_format).toBe('vtt');
      expect(subtitles.nativeSubtitleTrack.value?.url).toBe(native.url);
      expect(subtitles.usesAssSubtitleTrack.value).toBe(false);
    } finally {
      scope.stop();
    }
  });

  it('mount_ass_renderer', async () => {
    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const scope = effectScope();
    const tracks = ref<SubtitleTrack[]>([styled]);
    const shouldRender = ref(false);
    const fetchText = mock(async () => '[Script Info]\nTitle: Demo\n');
    const loadRenderer = mock(async () => AssRenderer);
    const subtitles = scope.run(() =>
      usePlayerSubtitles({
        tracks,
        canPlay: true,
        shouldRender,
        video: ref(document.createElement('video')),
        overlay: ref(document.createElement('div')),
        fetchText,
        loadRenderer,
      }),
    )!;
    try {
      await flushPromises();
      expect(subtitles.usesAssSubtitleTrack.value).toBe(true);
      expect(assConstructorMock).not.toHaveBeenCalled();
      shouldRender.value = true;
      await flushPromises(5);
      expect(fetchText).toHaveBeenCalledWith(styled.url, expect.any(AbortSignal));
      expect(loadRenderer).toHaveBeenCalledTimes(1);
      expect(assConstructorMock).toHaveBeenCalledTimes(1);
      expect(assShowMock).toHaveBeenCalledTimes(1);
      tracks.value = [];
      await flushPromises();
      expect(assDestroyMock.mock.calls.length).toBeGreaterThanOrEqual(1);
      expect(subtitles.hasSubtitles.value).toBe(false);
    } finally {
      scope.stop();
    }
  });

  it('remount_on_layout_change', async () => {
    const { usePlayerSubtitles } = await import('~/composables/usePlayerSubtitles');
    const scope = effectScope();
    const fetchText = mock(async () => '[Script Info]\nTitle: Demo\n');
    const loadRenderer = mock(async () => AssRenderer);
    const assLayoutVersion = ref(0);
    scope.run(() =>
      usePlayerSubtitles({
        tracks: [styled],
        canPlay: true,
        shouldRender: true,
        assLayoutVersion,
        video: ref(document.createElement('video')),
        overlay: ref(document.createElement('div')),
        fetchText,
        loadRenderer,
      }),
    );
    try {
      await flushPromises(5);
      expect(fetchText).toHaveBeenCalledTimes(1);
      expect(assConstructorMock).toHaveBeenCalledTimes(1);
      assLayoutVersion.value += 1;
      await flushPromises(5);
      expect(fetchText).toHaveBeenCalledTimes(1);
      expect(assDestroyMock.mock.calls.length).toBeGreaterThanOrEqual(1);
      expect(assConstructorMock).toHaveBeenCalledTimes(2);
    } finally {
      scope.stop();
    }
  });
});
