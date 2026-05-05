import { describe, expect, it } from 'bun:test';

describe('playerControls utils', () => {
  it('show_hidden_touch', async () => {
    const { nextTapVisible } = await import('~/utils/playerControls');

    expect(nextTapVisible({ touch: true, paused: false, visible: false })).toBe(true);
  });

  it('keep_hidden_desktop', async () => {
    const { nextTapVisible } = await import('~/utils/playerControls');

    expect(nextTapVisible({ touch: false, paused: false, visible: false })).toBe(false);
  });

  it('hide_visible_when_playing', async () => {
    const { nextTapVisible } = await import('~/utils/playerControls');

    expect(nextTapVisible({ touch: true, paused: false, visible: true })).toBe(false);
  });
});
