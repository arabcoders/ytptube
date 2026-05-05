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
  changeSpeed,
  changeVolume,
  forward,
  frameStep,
  hasModifierKey,
  playPause,
  rewind,
  seekBackward,
  seekEnd,
  seekForward,
  seekStart,
  seekToPercent,
  shouldHandleKeyboardShortcut,
  toggleCaptions,
} from '~/utils/keyboard';

import type { KeyboardShortcutContext } from '~/types/video';

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

  async function handleKeyDown(event: KeyboardEvent) {
    if (!toValue(options.enabled) || !shouldHandleKeyboardShortcut(event)) {
      return;
    }

    const media = toValue(options.media);
    if (!media) {
      return;
    }

    const ctx: KeyboardShortcutContext = { video: media };

    const key = event.key.toLowerCase();
    if (hasModifierKey(event) && !['f', '?', '/'].includes(key)) {
      return;
    }

    switch (key) {
      case ' ':
      case 'k':
        event.preventDefault();
        event.stopPropagation();
        playPause(ctx);
        break;
      case 'j':
        event.preventDefault();
        event.stopPropagation();
        rewind(ctx, 10);
        break;
      case 'l':
        event.preventDefault();
        event.stopPropagation();
        forward(ctx, 10);
        break;
      case 'arrowleft':
        event.preventDefault();
        event.stopPropagation();
        seekBackward(ctx, 5);
        break;
      case 'arrowright':
        event.preventDefault();
        event.stopPropagation();
        seekForward(ctx, 5);
        break;
      case 'home':
        event.preventDefault();
        event.stopPropagation();
        seekStart(ctx);
        break;
      case 'end':
        event.preventDefault();
        event.stopPropagation();
        seekEnd(ctx);
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
        seekToPercent(ctx, parseInt(key, 10) * 10);
        break;
      }
      case 'arrowup':
        event.preventDefault();
        event.stopPropagation();
        if (options.adjustVolume) {
          options.adjustVolume(0.1);
          break;
        }

        changeVolume(ctx, 0.1);
        break;
      case 'arrowdown':
        event.preventDefault();
        event.stopPropagation();
        if (options.adjustVolume) {
          options.adjustVolume(-0.1);
          break;
        }

        changeVolume(ctx, -0.1);
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
        changeSpeed(ctx, -0.25);
        break;
      case "'":
        event.preventDefault();
        event.stopPropagation();
        changeSpeed(ctx, 0.25);
        break;
      case ',':
        event.preventDefault();
        event.stopPropagation();
        frameStep(ctx, 'backward');
        break;
      case '.':
        event.preventDefault();
        event.stopPropagation();
        frameStep(ctx, 'forward');
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
          toggleCaptions(video);
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
