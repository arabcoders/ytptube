import { computed, ref } from 'vue';

import type { Preset } from '~/types/presets';
import { cleanObject, prettyName } from '~/utils';

type EditablePreset = Partial<Preset> & {
  raw?: boolean;
  toggle_description?: boolean;
};

const REMOVE_KEYS = ['raw', 'toggle_description'];

const makeEmptyPreset = (): Partial<Preset> => ({
  name: '',
  description: '',
  folder: '',
  template: '',
  cookies: '',
  cli: '',
  priority: 0,
});

const sanitizePreset = (item: Preset | EditablePreset): Partial<Preset> => {
  const cleaned = cleanObject(JSON.parse(JSON.stringify(item)), REMOVE_KEYS) as Partial<Preset> & {
    default?: boolean;
  };

  if ('default' in cleaned) {
    delete cleaned.default;
  }

  return cleaned;
};

export const usePresetEditor = () => {
  const presetsStore = usePresets();
  const dialog = useDialog();

  const isOpen = ref(false);
  const reference = ref<number | null>(null);
  const preset = ref<Partial<Preset>>(makeEmptyPreset());
  const initialSnapshot = ref('');
  const sessionId = ref(0);

  const modalTitle = computed(() => {
    return reference.value ? `Edit - ${prettyName(preset.value.name || '')}` : 'Add';
  });

  const modalDescription = computed(() => {
    return reference.value ? 'Update an existing preset.' : 'Create a preset.';
  });

  const modalKey = computed(() => `${reference.value ?? 'create'}:${sessionId.value}`);

  const reset = (): void => {
    reference.value = null;
    preset.value = makeEmptyPreset();
    initialSnapshot.value = '';
  };

  const close = (): void => {
    isOpen.value = false;
    reset();
  };

  const snapshot = (item: Partial<Preset>): string =>
    JSON.stringify(sanitizePreset(item as Preset));

  const isDirty = computed(() => {
    if (!isOpen.value) {
      return false;
    }

    return snapshot(preset.value) !== initialSnapshot.value;
  });

  const openCreate = (): void => {
    reset();
    sessionId.value += 1;
    initialSnapshot.value = snapshot(preset.value);
    isOpen.value = true;
  };

  const openEdit = (item: Preset | EditablePreset): void => {
    reference.value = item.id ?? null;
    preset.value = sanitizePreset(item);
    sessionId.value += 1;
    initialSnapshot.value = snapshot(preset.value);
    isOpen.value = true;
  };

  const requestClose = async (): Promise<void> => {
    if (presetsStore.addInProgress.value) {
      return;
    }

    if (!isDirty.value) {
      close();
      return;
    }

    const { status } = await dialog.confirmDialog({
      title: 'Discard changes?',
      message: 'You have unsaved changes. Close the preset editor and discard them?',
      confirmText: 'Discard',
      cancelText: 'Keep editing',
      confirmColor: 'warning',
    });

    if (status === true) {
      close();
    }
  };

  const submit = async ({
    reference: currentReference,
    preset: currentPreset,
  }: {
    reference: number | null;
    preset: Preset;
  }) => {
    const cleaned = sanitizePreset(currentPreset) as Preset;

    if (currentReference) {
      const updated = await presetsStore.updatePreset(currentReference, cleaned);
      if (updated) {
        close();
      }
      return updated;
    }

    const created = await presetsStore.createPreset(cleaned);
    if (created) {
      close();
    }
    return created;
  };

  return {
    isOpen,
    reference,
    preset,
    modalKey,
    modalTitle,
    modalDescription,
    isDirty,
    addInProgress: presetsStore.addInProgress,
    openCreate,
    openEdit,
    close,
    requestClose,
    reset,
    submit,
  };
};
