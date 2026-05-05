import type { KeyboardShortcutContext } from '~/types/video';

export const clampMediaTime = (media: HTMLMediaElement, nextTime: number) => {
  const duration =
    Number.isFinite(media.duration) && media.duration > 0 ? media.duration : Infinity;
  media.currentTime = Math.min(Math.max(nextTime, 0), duration);
};

export const clampMediaVolume = (volume: number) => {
  return Math.min(1, Math.max(0, volume));
};

export const hasModifierKey = (event: KeyboardEvent): boolean =>
  event.ctrlKey || event.metaKey || event.altKey;

export const playPause = (ctx: KeyboardShortcutContext) => {
  if (ctx.video.paused) {
    ctx.video.play();
  } else {
    ctx.video.pause();
  }
};

export const rewind = (ctx: KeyboardShortcutContext, seconds: number = 10) => {
  ctx.video.currentTime = Math.max(0, ctx.video.currentTime - seconds);
};

export const forward = (ctx: KeyboardShortcutContext, seconds: number = 10) => {
  ctx.video.currentTime = Math.min(ctx.video.duration, ctx.video.currentTime + seconds);
};

export const mute = (ctx: KeyboardShortcutContext) => {
  ctx.video.muted = !ctx.video.muted;
};

export const changeVolume = (ctx: KeyboardShortcutContext, delta: number) => {
  const volume = clampMediaVolume(ctx.video.volume + delta);
  ctx.video.volume = volume;
};

export const changeSpeed = (ctx: KeyboardShortcutContext, delta: number) => {
  const speed = ctx.video.playbackRate;
  ctx.video.playbackRate = Math.max(0.25, Math.min(2, speed + delta));
};

export const frameStep = (
  ctx: KeyboardShortcutContext,
  direction: 'forward' | 'backward' = 'forward',
) => {
  if (!ctx.video.paused) {
    ctx.video.pause();
  }

  // Frame step by ~33ms (approximately 1 frame at 30fps, ~16.7ms at 60fps)
  const frameStep = 'forward' === direction ? 0.033 : -0.033;
  ctx.video.currentTime = Math.max(
    0,
    Math.min(ctx.video.duration, ctx.video.currentTime + frameStep),
  );
};

export const seekToPercent = (ctx: KeyboardShortcutContext, percent: number) => {
  ctx.video.currentTime = (percent / 100) * ctx.video.duration;
};

export const seekBackward = (ctx: KeyboardShortcutContext, seconds: number = 5) => {
  clampMediaTime(ctx.video, ctx.video.currentTime - seconds);
};

export const seekForward = (ctx: KeyboardShortcutContext, seconds: number = 5) => {
  clampMediaTime(ctx.video, ctx.video.currentTime + seconds);
};

export const fullscreen = (video: HTMLVideoElement) => {
  if (!document.fullscreenElement) {
    video.requestFullscreen().catch((err) => {
      console.error(`Error attempting to enable fullscreen: ${err.message}`);
    });
  } else {
    document.exitFullscreen();
  }
};

export const pictureInPicture = async (video: HTMLVideoElement) => {
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture();
    } else if (document.pictureInPictureEnabled) {
      await video.requestPictureInPicture();
    }
  } catch (error) {
    console.error(`Picture-in-Picture error: ${error}`);
  }
};

export const toggleCaptions = (video: HTMLVideoElement) => {
  const textTracks = video.textTracks;

  if (0 === textTracks.length) {
    return;
  }

  for (let i = 0; i < textTracks.length; i++) {
    const track = textTracks[i] as TextTrack | null;
    if (track && ('captions' === track.kind || 'subtitles' === track.kind)) {
      track.mode = 'showing' === track.mode ? 'hidden' : 'showing';
      break;
    }
  }
};

export const shouldHandleKeyboardShortcut = (event: KeyboardEvent): boolean => {
  const target = event.target as HTMLElement;
  const tagName = target?.tagName?.toLowerCase();
  if (
    'input' === tagName ||
    'textarea' === tagName ||
    'true' === target?.contentEditable ||
    'true' === target?.getAttribute('contenteditable')
  ) {
    return false;
  }

  return true;
};

export const modifierKey = (event: KeyboardEvent): boolean => hasModifierKey(event);
