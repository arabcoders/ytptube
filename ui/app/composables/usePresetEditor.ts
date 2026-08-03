import { computed, ref } from 'vue';

import type { Preset } from '~/types/presets';
import { useDirtyCloseGuard } from '~/composables/useDirtyCloseGuard';
import { cleanObject } from '~/utils';

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
  const { t } = useI18n();
  const presetsStore = usePresets();
  const submission = useFormSubmit();

  const isOpen = ref(false);
  const reference = ref<number | null>(null);
  const preset = ref<Partial<Preset>>(makeEmptyPreset());
  const dirty = ref(false);
  const sessionId = ref(0);

  const discardEditor = (): void => {
    submission.clear();
    dirty.value = false;
    reference.value = null;
    preset.value = makeEmptyPreset();
  };

  const {
    isDirty,
    requestClose: requestCloseGuard,
    handleOpenChange,
  } = useDirtyCloseGuard(isOpen, {
    dirty,
    message: t('common.discardChanges'),
    onDiscard: async () => {
      discardEditor();
    },
  });

  const modalTitle = computed(() =>
    reference.value ? t('common.editTitle', { name: preset.value.name || '' }) : t('common.add'),
  );

  const modalDescription = computed(() => {
    return reference.value ? t('common.updateDescription') : t('common.createDescription');
  });

  const modalKey = computed(() => `${reference.value ?? 'create'}:${sessionId.value}`);

  const reset = (): void => {
    discardEditor();
  };

  const close = (): void => {
    dirty.value = false;
    isOpen.value = false;
    reset();
  };

  const openCreate = (): void => {
    reset();
    dirty.value = false;
    sessionId.value += 1;
    isOpen.value = true;
  };

  const openEdit = (item: Preset | EditablePreset): void => {
    dirty.value = false;
    reference.value = item.id ?? null;
    preset.value = sanitizePreset(item);
    sessionId.value += 1;
    isOpen.value = true;
  };

  const requestClose = async (): Promise<void> => {
    if (presetsStore.addInProgress.value) {
      return;
    }

    await requestCloseGuard();
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
      const updated = await submission.run(() =>
        presetsStore.updatePreset(currentReference, cleaned as Preset),
      );
      if (updated) {
        close();
      }
      return updated;
    }

    const created = await submission.run(() => presetsStore.createPreset(cleaned));
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
    dirty,
    addInProgress: presetsStore.addInProgress,
    submitError: submission.message,
    clearSubmitError: submission.clear,
    openCreate,
    openEdit,
    close,
    handleOpenChange,
    requestClose,
    reset,
    submit,
  };
};
