import { disableOpacity, enableOpacity, syncOpacity } from '~/utils';

const OVERLAY_SELECTOR = '[data-slot="overlay"]';
const SETTINGS_PANEL_SELECTOR = '.yt-settings-panel';

type OpacityAction = 'disable' | 'enable' | 'sync' | null;

export const overlayOpacityAction = (
  overlayCount: number,
  hasSettingsPanel: boolean,
  isLocked: boolean,
): { action: OpacityAction; locked: boolean } => {
  if (overlayCount === 1 && hasSettingsPanel) {
    return { action: isLocked ? 'enable' : null, locked: false };
  }
  if (overlayCount > 0 && !isLocked) {
    return { action: 'disable', locked: true };
  }
  if (overlayCount > 0) {
    return { action: 'sync', locked: true };
  }
  return { action: isLocked ? 'enable' : null, locked: false };
};

export default defineNuxtPlugin(() => {
  if (import.meta.server) {
    return;
  }

  let observer: MutationObserver | null = null;
  let isLocked = false;

  const syncOverlayOpacity = (): void => {
    const overlays = Array.from(document.querySelectorAll(OVERLAY_SELECTOR));
    const state = overlayOpacityAction(
      overlays.length,
      document.querySelector(SETTINGS_PANEL_SELECTOR) !== null,
      isLocked,
    );
    isLocked = state.locked;

    if (state.action === 'disable') {
      disableOpacity();
    } else if (state.action === 'enable') {
      enableOpacity();
    } else if (state.action === 'sync') {
      syncOpacity();
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
