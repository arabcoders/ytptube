import { disableOpacity, enableOpacity } from '~/utils';

const OVERLAY_SELECTOR = '[data-slot="overlay"]';

export default defineNuxtPlugin(() => {
  if (import.meta.server) {
    return;
  }

  let observer: MutationObserver | null = null;
  let isLocked = false;

  const syncOverlayOpacity = (): void => {
    const hasOverlay = document.querySelector(OVERLAY_SELECTOR) !== null;

    if (hasOverlay && !isLocked) {
      disableOpacity();
      isLocked = true;
      return;
    }

    if (!hasOverlay && isLocked) {
      enableOpacity();
      isLocked = false;
    }
  };

  const startObserver = (): void => {
    if (observer || !document.body) {
      return;
    }

    observer = new MutationObserver(() => syncOverlayOpacity());
    observer.observe(document.body, { childList: true, subtree: true });
    syncOverlayOpacity();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserver, { once: true });
  } else {
    startObserver();
  }

  window.addEventListener(
    'beforeunload',
    () => {
      observer?.disconnect();
      observer = null;

      if (isLocked) {
        enableOpacity();
        isLocked = false;
      }
    },
    { once: true },
  );
});
