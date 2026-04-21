import { disableOpacity, enableOpacity, syncOpacity } from '~/utils';

const OVERLAY_SELECTOR = '[data-slot="overlay"]';
const SETTINGS_PANEL_SELECTOR = '.yt-settings-panel';

export default defineNuxtPlugin(() => {
  if (import.meta.server) {
    return;
  }

  let observer: MutationObserver | null = null;
  let isLocked = false;

  const syncOverlayOpacity = (): void => {
    const overlays = Array.from(document.querySelectorAll(OVERLAY_SELECTOR));
    const hasOverlay = overlays.length > 0;
    const isSettingsOnlyOverlay =
      overlays.length === 1 && document.querySelector(SETTINGS_PANEL_SELECTOR) !== null;

    if (isSettingsOnlyOverlay) {
      if (isLocked) {
        enableOpacity();
        isLocked = false;
      }

      return;
    }

    if (hasOverlay && !isLocked) {
      disableOpacity();
      isLocked = true;
      return;
    }

    if (hasOverlay) {
      syncOpacity();
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
});
