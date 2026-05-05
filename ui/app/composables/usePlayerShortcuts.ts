import {
  getCurrentScope,
  onScopeDispose,
  ref,
  watch,
  type MaybeRefOrGetter,
  type Ref,
  toValue,
} from 'vue';
import {
  clampMediaTime,
  clampMediaVolume,
  hasModifierKey,
  shouldHandleKeyboardShortcut,
} from '~/utils/keyboard';

type UsePlayerShortcutsOptions = {
  enabled: MaybeRefOrGetter<boolean>;
  media: MaybeRefOrGetter<HTMLMediaElement | null>;
  video: MaybeRefOrGetter<HTMLVideoElement | null>;
  adjustVolume?: (delta: number) => void;
  canToggleSubs: MaybeRefOrGetter<boolean>;
  helpOpen?: Ref<boolean>;
  toggleSubtitles: () => void;
  toggleFullscreen: () => Promise<void> | void;
  toggleMute?: () => void;
  closePlayer?: () => void;
};

export function usePlayerShortcuts(options: UsePlayerShortcutsOptions) {
  const showHelp = options.helpOpen || ref(false);

  function togglePlayPause(media: HTMLMediaElement) {
    if (media.paused) {
      void media.play().catch(() => {});
      return;
    }

    media.pause();
  }

  function stepFrame(media: HTMLMediaElement, direction: 'forward' | 'backward') {
    if (!media.paused) {
      media.pause();
    }

    const frameStep = direction === 'forward' ? 0.033 : -0.033;
    clampMediaTime(media, media.currentTime + frameStep);
  }

  function toggleNativeSubtitles(video: HTMLVideoElement) {
    const tracks = Array.from(video.textTracks);
    const subtitleTrack = tracks.find(
      (track) => track.kind === 'subtitles' || track.kind === 'captions',
    );
    if (!subtitleTrack) {
      return;
    }

    subtitleTrack.mode = subtitleTrack.mode === 'showing' ? 'hidden' : 'showing';
  }

  async function handleKeyDown(event: KeyboardEvent) {
    if (!toValue(options.enabled) || !shouldHandleKeyboardShortcut(event)) {
      return;
    }

    const media = toValue(options.media);
    if (!media) {
      return;
    }

    const key = event.key.toLowerCase();
    if (hasModifierKey(event) && !['f', '?', '/'].includes(key)) {
      return;
    }

    switch (key) {
      case ' ':
      case 'k':
        event.preventDefault();
        event.stopPropagation();
        togglePlayPause(media);
        break;
      case 'j':
        event.preventDefault();
        event.stopPropagation();
        clampMediaTime(media, media.currentTime - 10);
        break;
      case 'l':
        event.preventDefault();
        event.stopPropagation();
        clampMediaTime(media, media.currentTime + 10);
        break;
      case 'arrowleft':
        event.preventDefault();
        event.stopPropagation();
        clampMediaTime(media, media.currentTime - 5);
        break;
      case 'arrowright':
        event.preventDefault();
        event.stopPropagation();
        clampMediaTime(media, media.currentTime + 5);
        break;
      case 'home':
        event.preventDefault();
        event.stopPropagation();
        media.currentTime = 0;
        break;
      case 'end':
        event.preventDefault();
        event.stopPropagation();
        if (Number.isFinite(media.duration)) {
          media.currentTime = media.duration;
        }
        break;
      case '0':
      case '1':
      case '2':
      case '3':
      case '4':
      case '5':
      case '6':
      case '7':
      case '8':
      case '9': {
        event.preventDefault();
        event.stopPropagation();
        if (Number.isFinite(media.duration) && media.duration > 0) {
          media.currentTime = (parseInt(key, 10) / 10) * media.duration;
        }
        break;
      }
      case 'arrowup':
        event.preventDefault();
        event.stopPropagation();
        if (options.adjustVolume) {
          options.adjustVolume(0.1);
          break;
        }

        media.volume = clampMediaVolume(media.volume + 0.1);
        media.muted = false;
        break;
      case 'arrowdown':
        event.preventDefault();
        event.stopPropagation();
        if (options.adjustVolume) {
          options.adjustVolume(-0.1);
          break;
        }

        media.volume = clampMediaVolume(media.volume - 0.1);
        if (media.volume <= 0) {
          media.muted = true;
        }
        break;
      case 'm':
        event.preventDefault();
        event.stopPropagation();
        if (options.toggleMute) {
          options.toggleMute();
          break;
        }

        media.muted = !media.muted;
        break;
      case ';':
        event.preventDefault();
        event.stopPropagation();
        media.playbackRate = Math.max(0.25, media.playbackRate - 0.25);
        break;
      case "'":
        event.preventDefault();
        event.stopPropagation();
        media.playbackRate = Math.min(2, media.playbackRate + 0.25);
        break;
      case ',':
        event.preventDefault();
        event.stopPropagation();
        stepFrame(media, 'backward');
        break;
      case '.':
        event.preventDefault();
        event.stopPropagation();
        stepFrame(media, 'forward');
        break;
      case 'f':
        event.preventDefault();
        event.stopPropagation();
        await options.toggleFullscreen();
        break;
      case 'c': {
        if (!toValue(options.canToggleSubs)) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();
        const video = toValue(options.video);
        if (video?.textTracks.length) {
          toggleNativeSubtitles(video);
        }
        options.toggleSubtitles();
        break;
      }
      case '?':
      case '/':
        event.preventDefault();
        event.stopPropagation();
        showHelp.value = !showHelp.value;
        break;
      case 'escape':
        event.preventDefault();
        event.stopPropagation();
        if (showHelp.value) {
          showHelp.value = false;
          break;
        }
        options.closePlayer?.();
        break;
      default:
        break;
    }
  }

  document.addEventListener('keydown', handleKeyDown, { capture: true });

  watch(
    () => toValue(options.enabled),
    (enabled) => {
      if (!enabled) {
        showHelp.value = false;
      }
    },
  );

  if (getCurrentScope()) {
    onScopeDispose(() => {
      document.removeEventListener('keydown', handleKeyDown, { capture: true });
    });
  }

  return {
    showHelp,
  };
}
