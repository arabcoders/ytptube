import { onScopeDispose, toValue, watch, type MaybeRefOrGetter } from 'vue';
import { guardPlayerRequests, type PlayerRequestGuard } from '~/utils/playerRequests';

export function usePlayerStartup(options: {
  video: MaybeRefOrGetter<HTMLVideoElement | null>;
  enabled: MaybeRefOrGetter<boolean>;
  onFallback: (reason: 'startup-timeout' | 'request-limit') => void;
}) {
  let finished = false;
  let guard: PlayerRequestGuard | null = null;
  const stop = () => {
    guard?.stop();
    guard = null;
  };
  const fallback = (reason: 'startup-timeout' | 'request-limit') => {
    if (finished) return;
    finished = true;
    options.onFallback(reason);
  };
  onScopeDispose(stop);
  watch(
    [() => toValue(options.video), () => toValue(options.enabled)],
    ([video, enabled], _previous, onCleanup) => {
      if (!video || !enabled || finished) return;
      let timer = 0;
      const clear = () => window.clearTimeout(timer);
      const complete = () => {
        if (video.readyState < 2) return;
        finished = true;
        guard?.ready();
        guard = null;
        clear();
      };
      complete();
      if (finished) return;
      // Network activity and metadata alone do not mean the browser can play the media.
      timer = window.setTimeout(() => {
        if (video.readyState < 2) fallback('startup-timeout');
        else complete();
      }, 10000);
      video.addEventListener('loadeddata', complete);
      video.addEventListener('canplay', complete);
      video.addEventListener('playing', complete);
      onCleanup(() => {
        clear();
        stop();
        video.removeEventListener('loadeddata', complete);
        video.removeEventListener('canplay', complete);
        video.removeEventListener('playing', complete);
      });
    },
    { immediate: true, flush: 'sync' },
  );

  return {
    prepare: async (mediaUrl: string, scriptUrl: string, signal: AbortSignal) => {
      guard = await guardPlayerRequests(
        mediaUrl,
        scriptUrl,
        () => fallback('request-limit'),
        signal,
      );
      return guard !== null && !finished && !signal.aborted;
    },
  };
}
