import { describe, expect, it } from 'bun:test';

(
  globalThis as typeof globalThis & { defineNuxtPlugin?: (setup: () => void) => () => void }
).defineNuxtPlugin = (setup) => setup;

const { overlayOpacityAction } = await import('../../app/plugins/modal-opacity.client.ts');

describe('modal opacity plugin', () => {
  it('ignores settings overlay', () => {
    expect(overlayOpacityAction(1, true, false)).toEqual({ action: null, locked: false });
  });

  it('unlocks for settings', () => {
    expect(overlayOpacityAction(1, true, true)).toEqual({ action: 'enable', locked: false });
  });

  it('locks for overlay', () => {
    expect(overlayOpacityAction(1, false, false)).toEqual({ action: 'disable', locked: true });
  });

  it('syncs existing lock', () => {
    expect(overlayOpacityAction(2, false, true)).toEqual({ action: 'sync', locked: true });
  });

  it('unlocks without overlays', () => {
    expect(overlayOpacityAction(0, false, true)).toEqual({ action: 'enable', locked: false });
  });
});
