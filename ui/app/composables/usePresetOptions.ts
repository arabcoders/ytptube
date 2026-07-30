import { computed, toValue, type MaybeRefOrGetter } from 'vue';

import { useYtpConfig } from '~/composables/useYtpConfig';
import type { Preset } from '~/types/presets';

type PresetSelectItem = {
  type?: 'label' | 'item';
  label: string;
  value?: string;
};

type PresetDefaultField = 'cookies' | 'cli' | 'template' | 'folder';

type UsePresetOptionsOptions = {
  order?: 'custom-first' | 'default-first';
};

export const usePresetOptions = (
  source?: MaybeRefOrGetter<Preset[] | readonly Preset[] | undefined>,
  options: UsePresetOptionsOptions = {},
) => {
  const { t } = useI18n();
  const config = useYtpConfig();

  const presets = computed<Preset[]>(() => {
    const items = source ? toValue(source) : config.presets;
    return Array.isArray(items) ? [...items] : [];
  });

  const defaultPresets = computed(() => presets.value.filter((item) => item.default));
  const customPresets = computed(() => presets.value.filter((item) => !item.default));

  const filterPresets = (flag: boolean = true): Preset[] =>
    presets.value.filter((item) => item.default === flag);

  const findPreset = (name?: string | null): Preset | undefined =>
    presets.value.find((item) => item.name === name);

  const hasPreset = (name?: string | null): boolean => Boolean(findPreset(name));

  const selectItems = computed<PresetSelectItem[]>(() => {
    const items: PresetSelectItem[] = [];

    const groups =
      options.order === 'default-first'
        ? [
            { label: t('common.defaultPresets'), list: defaultPresets.value },
            { label: t('common.customPresets'), list: customPresets.value },
          ]
        : [
            { label: t('common.customPresets'), list: customPresets.value },
            { label: t('common.defaultPresets'), list: defaultPresets.value },
          ];

    groups.forEach((group) => {
      if (group.list.length < 1) {
        return;
      }

      items.push({ type: 'label', label: group.label });
      group.list.forEach((preset) => {
        items.push({ label: preset.name, value: preset.name });
      });
    });

    return items;
  });

  const getPresetDefault = (
    presetName: string | undefined,
    type: PresetDefaultField,
    fallback: string = '',
    downloadPath: string = config.app.download_path || '',
  ): string => {
    const preset = findPreset(presetName);
    if (!preset) {
      return fallback;
    }

    if (type === 'folder' && preset.folder) {
      return preset.folder.replace(downloadPath, '') || fallback;
    }

    return preset[type] || fallback;
  };

  return {
    presets,
    defaultPresets,
    customPresets,
    filterPresets,
    findPreset,
    hasPreset,
    selectItems,
    getPresetDefault,
  };
};
