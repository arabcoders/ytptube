import { onBeforeRouteLeave, onBeforeRouteUpdate, onBeforeUnmount } from '#imports';
import { computed, toValue, type MaybeRefOrGetter, type Ref } from 'vue';
import { useStorage } from '@vueuse/core';

import { useDialog } from '~/composables/useDialog';

type DirtyCloseGuardOptions = {
  dirty: MaybeRefOrGetter<boolean>;
  preferenceKey: string;
  title?: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: 'primary' | 'secondary' | 'success' | 'info' | 'warning' | 'error' | 'neutral';
  onDiscard?: () => void | Promise<void>;
};

let dirtyCloseSkips: ReturnType<typeof useStorage<Record<string, boolean>>> | null = null;

const LEGACY_PLAYER_KEYS = ['history-player', 'simple-player', 'browser-player'];

export const useDirtyCloseGuardPreferences = () => {
  dirtyCloseSkips ??= useStorage<Record<string, boolean>>('dirty_close_guard_skips', {});
  const current = dirtyCloseSkips.value;
  if (true !== current.player && LEGACY_PLAYER_KEYS.some((key) => true === current[key])) {
    dirtyCloseSkips.value = Object.fromEntries(
      Object.entries(current)
        .filter(([key]) => false === LEGACY_PLAYER_KEYS.includes(key))
        .concat([['player', true]]),
    );
  }
  return dirtyCloseSkips;
};

export const useDirtyCloseGuard = (open: Ref<boolean>, options: DirtyCloseGuardOptions) => {
  const dialog = useDialog();
  const { t } = useI18n();
  const skipped = useDirtyCloseGuardPreferences();
  let pendingCloseRequest: Promise<boolean> | null = null;

  const isDirty = computed<boolean>(() => Boolean(toValue(options.dirty)));
  const skipConfirmation = computed<boolean>(() => true === skipped.value[options.preferenceKey]);
  const shouldGuard = computed<boolean>(
    () => Boolean(open.value) && true === isDirty.value && false === skipConfirmation.value,
  );

  const confirmClose = async (): Promise<boolean> => {
    if (false === isDirty.value) {
      open.value = false;
      return true;
    }

    if (true === skipConfirmation.value) {
      await options.onDiscard?.();
      open.value = false;
      return true;
    }

    const { status, value } = await dialog.confirmDialog({
      title: options.title ?? t('common.pleaseConfirm'),
      message: options.message ?? t('common.discardChanges'),
      confirmText: options.confirmText ?? t('common.discardChangesConfirm'),
      cancelText: options.cancelText ?? t('common.keepEditing'),
      confirmColor: options.confirmColor ?? 'warning',
      options: [{ key: 'skip', label: t('common.dontAskAgain') }],
    });

    if (true !== status) {
      return false;
    }

    await options.onDiscard?.();
    if (true === value?.skip) {
      skipped.value = { ...skipped.value, [options.preferenceKey]: true };
    }
    open.value = false;
    return true;
  };

  const requestClose = async (): Promise<boolean> => {
    if (pendingCloseRequest) {
      return pendingCloseRequest;
    }

    pendingCloseRequest = confirmClose().finally(() => {
      pendingCloseRequest = null;
    });

    return pendingCloseRequest;
  };

  const handleOpenChange = async (value: boolean): Promise<void> => {
    if (true === value) {
      open.value = true;
      return;
    }

    await requestClose();
  };

  onBeforeRouteLeave(async () => {
    if (false === shouldGuard.value) {
      return true;
    }

    return await requestClose();
  });

  onBeforeRouteUpdate(async () => {
    if (false === shouldGuard.value) {
      return true;
    }

    return await requestClose();
  });

  if ('undefined' !== typeof window) {
    const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
      if (false === shouldGuard.value) {
        return;
      }

      event.preventDefault();
      event.returnValue = '';
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    onBeforeUnmount(() => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    });
  }

  return {
    isDirty,
    requestClose,
    handleOpenChange,
  };
};
