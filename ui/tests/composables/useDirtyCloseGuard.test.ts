import { beforeAll, beforeEach, afterEach, describe, expect, it, mock } from 'bun:test';
import { ref } from 'vue';

type DialogResult = { status: boolean; value: null };
type RouteGuard = () => Promise<boolean> | boolean;

let beforeRouteLeaveHandler: RouteGuard | null = null;
let beforeRouteUpdateHandler: RouteGuard | null = null;
let unmountHandlers: Array<() => void> = [];

const confirmDialogMock = mock<() => Promise<DialogResult>>(() =>
  Promise.resolve({ status: true, value: null }),
);

mock.module('#imports', () => ({
  onBeforeRouteLeave: (handler: RouteGuard) => {
    beforeRouteLeaveHandler = handler;
  },
  onBeforeRouteUpdate: (handler: RouteGuard) => {
    beforeRouteUpdateHandler = handler;
  },
  onBeforeUnmount: (handler: () => void) => {
    unmountHandlers.push(handler);
  },
}));

mock.module('~/composables/useDialog', () => ({
  useDialog: () => ({
    confirmDialog: confirmDialogMock,
  }),
}));

let useDirtyCloseGuard: typeof import('~/composables/useDirtyCloseGuard').useDirtyCloseGuard;

beforeAll(async () => {
  ({ useDirtyCloseGuard } = await import('~/composables/useDirtyCloseGuard'));
});

beforeEach(() => {
  beforeRouteLeaveHandler = null;
  beforeRouteUpdateHandler = null;
  unmountHandlers = [];
  confirmDialogMock.mockReset();
  confirmDialogMock.mockImplementation(() => Promise.resolve({ status: true, value: null }));
});

afterEach(() => {
  for (const handler of unmountHandlers) {
    handler();
  }

  beforeRouteLeaveHandler = null;
  beforeRouteUpdateHandler = null;
  unmountHandlers = [];
});

describe('useDirtyCloseGuard', () => {
  it('confirms discard on route leave when the editor is open and dirty', async () => {
    const open = ref(true);
    const dirty = ref(true);
    const onDiscard = mock(() => {});

    useDirtyCloseGuard(open, {
      dirty,
      onDiscard,
    });

    expect(beforeRouteLeaveHandler).not.toBeNull();

    const allowed = await beforeRouteLeaveHandler?.();

    expect(allowed).toBe(true);
    expect(confirmDialogMock).toHaveBeenCalledTimes(1);
    expect(onDiscard).toHaveBeenCalledTimes(1);
    expect(open.value).toBe(false);
  });

  it('blocks route updates when the user keeps editing', async () => {
    const open = ref(true);
    const dirty = ref(true);

    confirmDialogMock.mockImplementationOnce(() => Promise.resolve({ status: false, value: null }));

    useDirtyCloseGuard(open, {
      dirty,
    });

    expect(beforeRouteUpdateHandler).not.toBeNull();

    const allowed = await beforeRouteUpdateHandler?.();

    expect(allowed).toBe(false);
    expect(confirmDialogMock).toHaveBeenCalledTimes(1);
    expect(open.value).toBe(true);
  });

  it('only prevents browser unload while the editor is open and dirty, then removes the listener on unmount', () => {
    const open = ref(true);
    const dirty = ref(true);

    useDirtyCloseGuard(open, {
      dirty,
    });

    const guardedEvent = new window.Event('beforeunload', { cancelable: true });
    const guardedResult = window.dispatchEvent(guardedEvent);

    expect(guardedResult).toBe(false);
    expect(guardedEvent.defaultPrevented).toBe(true);

    dirty.value = false;

    const cleanEvent = new window.Event('beforeunload', { cancelable: true });
    const cleanResult = window.dispatchEvent(cleanEvent);

    expect(cleanResult).toBe(true);
    expect(cleanEvent.defaultPrevented).toBe(false);

    for (const handler of unmountHandlers) {
      handler();
    }
    unmountHandlers = [];

    dirty.value = true;

    const afterUnmountEvent = new window.Event('beforeunload', { cancelable: true });
    const afterUnmountResult = window.dispatchEvent(afterUnmountEvent);

    expect(afterUnmountResult).toBe(true);
    expect(afterUnmountEvent.defaultPrevented).toBe(false);
  });

  it('dedupes concurrent close requests into one discard dialog', async () => {
    const open = ref(true);
    const dirty = ref(true);
    const onDiscard = mock(() => {});

    let resolveDialog: (result: DialogResult | PromiseLike<DialogResult>) => void = () => {
      throw new Error('Expected the discard dialog promise to be pending.');
    };
    confirmDialogMock.mockImplementationOnce(
      () =>
        new Promise<DialogResult>((resolve) => {
          resolveDialog = resolve;
        }),
    );

    const guard = useDirtyCloseGuard(open, {
      dirty,
      onDiscard,
    });

    const first = guard.requestClose();
    const second = guard.requestClose();

    expect(confirmDialogMock).toHaveBeenCalledTimes(1);
    resolveDialog({ status: true, value: null });

    expect(await first).toBe(true);
    expect(await second).toBe(true);
    expect(onDiscard).toHaveBeenCalledTimes(1);
    expect(open.value).toBe(false);
  });

  it('does not guard route changes when the editor is clean', async () => {
    const open = ref(true);
    const dirty = ref(false);

    useDirtyCloseGuard(open, {
      dirty,
    });

    expect(await beforeRouteLeaveHandler?.()).toBe(true);
    expect(await beforeRouteUpdateHandler?.()).toBe(true);
    expect(confirmDialogMock).not.toHaveBeenCalled();
    expect(open.value).toBe(true);
  });
});
