import { afterEach, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';
import { ref } from 'vue';

function getKeydownHandler(addEventListenerSpy: ReturnType<typeof spyOn>) {
  const handler = addEventListenerSpy.mock.calls.find((call) => call[0] === 'keydown')?.[1];
  if (!handler || typeof handler !== 'function') {
    throw new Error('Expected keydown handler to be registered');
  }

  return handler;
}

describe('usePlayerShortcuts', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('toggle_subs_c', async () => {
    const { usePlayerShortcuts } = await import('~/composables/usePlayerShortcuts');
    const addEventListenerSpy = spyOn(document, 'addEventListener');

    const subtitleTrack = { kind: 'subtitles', mode: 'showing' } as TextTrack;
    const videoElement = {
      paused: true,
      currentTime: 0,
      duration: 100,
      playbackRate: 1,
      volume: 1,
      muted: false,
      play: async () => {},
      pause: () => {},
      textTracks: [subtitleTrack],
    } as unknown as HTMLVideoElement;

    const subtitleEnabled = ref(true);

    usePlayerShortcuts({
      enabled: ref(true),
      media: ref(videoElement),
      video: ref(videoElement),
      canToggleSubs: ref(true),
      toggleSubtitles: () => {
        subtitleEnabled.value = !subtitleEnabled.value;
      },
      toggleFullscreen: () => {},
    });

    const handler = getKeydownHandler(addEventListenerSpy);

    const preventDefault = mock(() => {});
    const stopPropagation = mock(() => {});
    handler({
      key: 'c',
      target: document.body,
      preventDefault,
      stopPropagation,
      ctrlKey: false,
      metaKey: false,
      altKey: false,
    } as unknown as KeyboardEvent);

    expect(subtitleTrack.mode).toBe('hidden');
    expect(subtitleEnabled.value).toBe(false);

    addEventListenerSpy.mockRestore();
  });

  it('volume_up_unmute', async () => {
    const { usePlayerShortcuts } = await import('~/composables/usePlayerShortcuts');
    const addEventListenerSpy = spyOn(document, 'addEventListener');

    const media = {
      paused: true,
      currentTime: 0,
      duration: 100,
      playbackRate: 1,
      volume: 0,
      muted: true,
      play: async () => {},
      pause: () => {},
      textTracks: [],
    } as unknown as HTMLMediaElement;

    usePlayerShortcuts({
      enabled: ref(true),
      media: ref(media),
      video: ref(null),
      canToggleSubs: ref(false),
      toggleSubtitles: () => {},
      toggleFullscreen: () => {},
    });

    const handler = getKeydownHandler(addEventListenerSpy);
    const preventDefault = mock(() => {});
    const stopPropagation = mock(() => {});

    handler({
      key: 'ArrowUp',
      target: document.body,
      preventDefault,
      stopPropagation,
      ctrlKey: false,
      metaKey: false,
      altKey: false,
    } as unknown as KeyboardEvent);

    expect(media.volume).toBe(0.1);
    expect(media.muted).toBe(false);

    addEventListenerSpy.mockRestore();
  });

  it('close_help_first', async () => {
    const { usePlayerShortcuts } = await import('~/composables/usePlayerShortcuts');

    const media = {
      paused: true,
      currentTime: 0,
      duration: 100,
      playbackRate: 1,
      volume: 1,
      muted: false,
      play: async () => {},
      pause: () => {},
      textTracks: [],
    } as unknown as HTMLMediaElement;

    const showHelp = ref(true);
    const closePlayer = mock(() => {});

    usePlayerShortcuts({
      enabled: ref(true),
      media: ref(media),
      video: ref(null),
      canToggleSubs: ref(false),
      helpOpen: showHelp,
      toggleSubtitles: () => {},
      toggleFullscreen: () => {},
      closePlayer,
    });

    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(showHelp.value).toBe(false);
    expect(closePlayer).toHaveBeenCalledTimes(0);

    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(closePlayer).toHaveBeenCalledTimes(1);
  });
});
