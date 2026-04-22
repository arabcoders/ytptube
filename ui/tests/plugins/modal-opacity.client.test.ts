import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, mock, spyOn } from 'bun:test';

const disableOpacityMock = mock(() => {});
const enableOpacityMock = mock(() => {});
const syncOpacityMock = mock(() => {});

(globalThis as typeof globalThis & { defineNuxtPlugin?: (setup: () => void) => () => void }).defineNuxtPlugin =
  (setup) => setup;

let utils: Awaited<typeof import('~/utils/index')>;
let plugin: Awaited<typeof import('../../app/plugins/modal-opacity.client.ts')>['default'];
let started = false;
let disableOpacitySpy: ReturnType<typeof spyOn>;
let enableOpacitySpy: ReturnType<typeof spyOn>;
let syncOpacitySpy: ReturnType<typeof spyOn>;

const flushMutations = async (): Promise<void> => {
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
};

const createOverlay = (): HTMLDivElement => {
  const overlay = document.createElement('div');
  overlay.setAttribute('data-slot', 'overlay');
  return overlay;
};

const startPlugin = (): void => {
  if (started) {
    return;
  }

  plugin();
  document.dispatchEvent(new window.Event('DOMContentLoaded'));
  started = true;
};

beforeAll(async () => {
  utils = await import('~/utils/index');
  disableOpacitySpy = spyOn(utils, 'disableOpacity').mockImplementation(disableOpacityMock);
  enableOpacitySpy = spyOn(utils, 'enableOpacity').mockImplementation(enableOpacityMock);
  syncOpacitySpy = spyOn(utils, 'syncOpacity').mockImplementation(syncOpacityMock);
  plugin = (await import('../../app/plugins/modal-opacity.client.ts')).default;
});

afterAll(() => {
  disableOpacitySpy.mockRestore();
  enableOpacitySpy.mockRestore();
  syncOpacitySpy.mockRestore();
});

beforeEach(() => {
  globalThis.MutationObserver = window.MutationObserver;
  document.body.innerHTML = '';
  disableOpacityMock.mockClear();
  enableOpacityMock.mockClear();
  syncOpacityMock.mockClear();
});

afterEach(async () => {
  document.body.innerHTML = '';
  await flushMutations();
});

describe('modal opacity plugin', () => {
  it('ignores a settings-only overlay', async () => {
    startPlugin();

    const settingsPanel = document.createElement('div');
    settingsPanel.className = 'yt-settings-panel';

    document.body.append(settingsPanel, createOverlay());
    await flushMutations();

    expect(disableOpacityMock).not.toHaveBeenCalled();
    expect(enableOpacityMock).not.toHaveBeenCalled();
    expect(syncOpacityMock).not.toHaveBeenCalled();
  });

  it('restores opacity when a normal overlay closes back to settings-only', async () => {
    startPlugin();

    const settingsPanel = document.createElement('div');
    settingsPanel.className = 'yt-settings-panel';
    const settingsOverlay = createOverlay();
    const modalOverlay = createOverlay();

    document.body.append(settingsPanel, settingsOverlay);
    await flushMutations();

    document.body.append(modalOverlay);
    await flushMutations();

    expect(disableOpacityMock).toHaveBeenCalledTimes(1);

    modalOverlay.remove();
    await flushMutations();

    expect(enableOpacityMock).toHaveBeenCalledTimes(1);
  });

  it('resyncs opacity when overlays change while already locked', async () => {
    startPlugin();

    document.body.append(createOverlay());
    await flushMutations();

    document.body.append(createOverlay());
    await flushMutations();

    expect(disableOpacityMock).toHaveBeenCalledTimes(1);
    expect(syncOpacityMock).toHaveBeenCalledTimes(1);
  });

  it('does not unlock opacity on beforeunload when reload is canceled', async () => {
    startPlugin();

    document.body.append(createOverlay());
    await flushMutations();

    expect(disableOpacityMock).toHaveBeenCalledTimes(1);

    window.dispatchEvent(new window.Event('beforeunload'));
    await flushMutations();

    expect(enableOpacityMock).not.toHaveBeenCalled();
  });
});
