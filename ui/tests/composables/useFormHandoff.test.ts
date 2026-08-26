import { afterAll, beforeEach, describe, expect, it } from 'bun:test';

import { useFormHandoff } from '~/composables/useFormHandoff';

const state = new Map<string, { value: unknown }>();
const originalUseState = globalThis.useState;

beforeEach(() => state.clear());

afterAll(() => {
  if (originalUseState) {
    globalThis.useState = originalUseState;
    return;
  }

  Reflect.deleteProperty(globalThis, 'useState');
});

globalThis.useState = <T>(key: string, init: () => T) => {
  if (!state.has(key)) {
    state.set(key, { value: init() });
  }
  return state.get(key) as { value: T };
};

describe('useFormHandoff', () => {
  it('takes once', () => {
    const handoff = useFormHandoff<{ url: string }>('test');
    handoff.set({ url: 'https://example.com' });

    expect(handoff.take()).toEqual({ url: 'https://example.com' });
    expect(handoff.take()).toBeNull();
  });
});
