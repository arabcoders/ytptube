import { afterEach, beforeEach, describe, expect, it, mock } from 'bun:test';
import { effectScope, ref } from 'vue';

describe('usePlayerShortcuts', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('toggle_subs_c', async () => {
    const { usePlayerShortcuts } = await import('~/composables/usePlayerShortcuts');
    const scope = effectScope();

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

    scope.run(() =>
      usePlayerShortcuts({
        enabled: ref(true),
        media: ref(videoElement),
        video: ref(videoElement),
        canToggleSubs: ref(true),
        toggleSubtitles: () => {
          subtitleEnabled.value = !subtitleEnabled.value;
        },
        toggleFullscreen: () => {},
      }),
    );

    document.body.dispatchEvent(new window.KeyboardEvent('keydown', { key: 'c', bubbles: true }));

    expect(subtitleTrack.mode).toBe('hidden');
    expect(subtitleEnabled.value).toBe(false);

    scope.stop();
  });

  it('volume_up_unmute', async () => {
    const { usePlayerShortcuts } = await import('~/composables/usePlayerShortcuts');
    const scope = effectScope();

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

    scope.run(() =>
      usePlayerShortcuts({
        enabled: ref(true),
        media: ref(media),
        video: ref(null),
        canToggleSubs: ref(false),
        toggleSubtitles: () => {},
        toggleFullscreen: () => {},
      }),
    );

    document.body.dispatchEvent(
      new window.KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true }),
    );

    expect(media.volume).toBe(0.1);
    expect(media.muted).toBe(false);

    scope.stop();
  });

  it('close_help_first', async () => {
    const { usePlayerShortcuts } = await import('~/composables/usePlayerShortcuts');
    const scope = effectScope();

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

    scope.run(() =>
      usePlayerShortcuts({
        enabled: ref(true),
        media: ref(media),
        video: ref(null),
        canToggleSubs: ref(false),
        helpOpen: showHelp,
        toggleSubtitles: () => {},
        toggleFullscreen: () => {},
        closePlayer,
      }),
    );

    document.body.dispatchEvent(
      new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    );
    expect(showHelp.value).toBe(false);
    expect(closePlayer).toHaveBeenCalledTimes(0);

    document.body.dispatchEvent(
      new window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    );
    expect(closePlayer).toHaveBeenCalledTimes(1);

    scope.stop();
  });
});
