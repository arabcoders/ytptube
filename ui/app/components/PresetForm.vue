<template>
  <form id="presetForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
    <FormSubmitError :message="action.message.value" @dismiss="action.clear" />
    <UAlert
      v-if="formError && hasFormContent"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="formError"
      class="sticky top-0 z-10 shadow-sm"
    />

    <details :open="!reference" class="border-b border-default pb-5">
      <summary class="w-fit cursor-pointer text-sm font-semibold text-highlighted">
        {{ t('common.import') }}
      </summary>
      <div class="mt-4 grid gap-4 sm:grid-cols-2">
        <UFormField
          class="min-w-0"
          :ui="fieldUi"
          :label="t('common.importPreset')"
          :help="t('common.importPresetDesc')"
        >
          <USelectMenu
            v-model="selectedPreset"
            :items="importPresetItems"
            :placeholder="t('common.selectPreset')"
            value-key="value"
            label-key="label"
            color="neutral"
            size="lg"
            class="w-full"
            :ui="{ content: 'min-w-[13rem]', item: 'ps-6' }"
            :search-input="{ placeholder: t('common.searchPresets') }"
            :disabled="importInProgress"
            @update:model-value="() => void importExistingPreset()"
          />
        </UFormField>

        <UFormField
          class="min-w-0"
          :ui="fieldUi"
          :label="t('common.importString')"
          :help="t('common.importStringDesc')"
        >
          <UFieldGroup size="lg" class="w-full">
            <UInput
              id="import_string"
              dir="ltr"
              v-model="importString"
              type="text"
              autocomplete="off"
              class="min-w-0 flex-1"
              :ui="inputUi"
              :disabled="importInProgress"
              @keydown.enter.prevent="() => void importItem()"
            />

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-import"
              :loading="importInProgress"
              :disabled="!importString || importInProgress"
              class="justify-center"
              @click="() => void importItem()"
            >
              {{ t('common.import') }}
            </UButton>
          </UFieldGroup>
        </UFormField>
      </div>
    </details>

    <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
      <UFormField
        class="w-full"
        :ui="fieldUi"
        :label="t('common.name')"
        :help="t('common.presetNameDesc')"
      >
        <UInput
          id="name"
          v-model="form.name"
          type="text"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
          @update:model-value="normalizeName"
        />
      </UFormField>

      <UFormField
        class="w-full"
        :ui="fieldUi"
        :label="t('common.priority')"
        :help="t('common.presetPriorityDesc')"
      >
        <UInput
          id="priority"
          v-model.number="form.priority"
          type="number"
          min="0"
          placeholder="0"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField class="w-full sm:col-span-2" :ui="fieldUi" :label="t('common.description')">
        <UTextarea
          id="description"
          v-model="form.description"
          :disabled="addInProgress"
          :placeholder="t('common.extrasInstructions')"
          :rows="3"
          size="lg"
          variant="outline"
          color="neutral"
          class="w-full"
          :ui="textareaUi"
        />
      </UFormField>
    </div>

    <div class="space-y-4 border-t border-default pt-5">
      <UFormField
        class="w-full"
        :ui="fieldUi"
        :label="t('common.downloadPath')"
        :description="t('common.presetPathDesc')"
      >
        <div class="flex flex-col gap-2 sm:flex-row" dir="ltr">
          <UTooltip :text="t('common.fullPath', { path: config.app.download_path })">
            <div
              class="inline-flex min-h-11 items-center rounded-md border border-default bg-muted/30 px-3 text-sm text-toned"
            >
              {{ shortPath(config.app.download_path) }}
            </div>
          </UTooltip>

          <FolderInput
            id="folder"
            v-model="form.folder"
            class="min-w-0 flex-1"
            :placeholder="t('common.leaveEmptyDefault')"
            :disabled="addInProgress"
            :ui="inputUi"
          />
        </div>
      </UFormField>

      <UFormField
        class="w-full"
        :ui="fieldUi"
        :label="t('common.outputTemplate')"
        :description="t('common.presetTemplateDesc')"
      >
        <UInput
          id="output_template"
          dir="ltr"
          v-model="form.template"
          type="text"
          :placeholder="t('common.leaveEmptyDefaultTemplate')"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>
    </div>

    <div class="border-t border-default pt-5">
      <UFormField class="w-full" :ui="editorFieldUi" :label="t('common.cliOptions')">
        <template #description>
          <p class="text-sm text-toned">
            <button type="button" class="text-primary hover:underline" @click="showOptions = true">
              {{ t('common.cliOptionsViewAll') }}</button
            >{{ t('common.cliOptionsDescPrefix') }}
            <a
              target="_blank"
              class="text-primary hover:underline"
              href="https://github.com/arabcoders/ytptube/blob/master/app/features/ytdlp/utils.py#L29"
            >
              {{ t('common.cliOptionsDescIgnored') }}</a
            >.
          </p>
        </template>
        <TextareaAutocomplete
          id="cli_options"
          v-model="form.cli"
          :options="ytDlpOpt"
          :disabled="addInProgress"
        />
      </UFormField>
    </div>

    <details :open="Boolean(preset.cookies)" class="border-t border-default pt-5">
      <summary class="w-fit cursor-pointer text-sm font-semibold text-highlighted">
        {{ t('common.cookiesLabel') }}
      </summary>
      <UFormField
        class="mt-4 w-full"
        :ui="{ ...editorFieldUi, label: 'sr-only' }"
        :label="t('common.cookiesLabel')"
      >
        <template #description>
          <p class="text-sm text-toned">
            {{ t('common.cookiesDesc') }}
            <NuxtLink
              target="_blank"
              to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp"
              class="text-sm text-primary hover:underline"
              >{{ t('common.recommendedAddon') }}</NuxtLink
            >
          </p>
        </template>
        <template #hint>
          <button
            type="button"
            class="text-sm font-medium text-primary hover:underline"
            @click="triggerCookieUpload"
          >
            {{ t('common.uploadFile') }}
          </button>
        </template>
        <TextDropzone
          ref="cookiesDropzoneRef"
          id="cookies"
          :rows="7"
          v-model="form.cookies"
          :disabled="addInProgress"
          dir="ltr"
          @error="showActionError"
          :placeholder="t('common.cookiesPlaceholder')"
        />
      </UFormField>
    </details>

    <UModal
      v-if="showOptions"
      v-model:open="showOptions"
      :title="t('common.cliOptions')"
      :dismissible="true"
      :ui="{ content: 'sm:max-w-6xl', body: 'p-0' }"
    >
      <template #description>
        <span class="sr-only">{{ t('common.browseYtdlpFlags') }}</span>
      </template>

      <template #body>
        <YTDLPOptions />
      </template>
    </UModal>
  </form>
</template>

<script setup lang="ts">
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import TextDropzone from '~/components/TextDropzone.vue';
import type { ImportedItem } from '~/types';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { Preset } from '~/types/presets';
import { normalizePresetName, shortPath } from '~/utils';

const { t } = useI18n();

const emitter = defineEmits<{
  (event: 'dirty-change' | 'valid-change', value: boolean): void;
  (event: 'submit', payload: { reference: number | null; preset: Preset }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  preset: Partial<Preset>;
  addInProgress?: boolean;
}>();

const config = useYtpConfig();
const dialog = useDialog();
const { presets, findPreset, selectItems } = usePresetOptions();
const action = useFormSubmit();

const form = reactive<Preset>({
  name: '',
  description: '',
  folder: '',
  template: '',
  cookies: '',
  cli: '',
  default: false,
  priority: 0,
  ...JSON.parse(JSON.stringify(props.preset || {})),
});

const importString = ref('');
const selectedPreset = ref<string>('');
const importInProgress = ref(false);
const showOptions = ref(false);
const ytDlpOpt = ref<AutoCompleteOptions>([]);
const cookiesDropzoneRef = ref<InstanceType<typeof TextDropzone> | null>(null);

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
  hint: 'text-sm text-toned',
};

const editorFieldUi = {
  root: 'w-full',
  label: 'font-semibold text-default',
  container: 'flex flex-col space-y-2',
  description: 'text-sm text-toned',
  hint: 'text-sm text-toned',
};

const inputUi = {
  root: 'w-full',
  base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const textareaUi = {
  root: 'w-full',
  base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const importPresetItems = computed(() => selectItems.value);

const dirtySource = computed(() => ({
  reference: props.reference ?? null,
  form: JSON.parse(JSON.stringify(form)),
  importString: importString.value,
  selectedPreset: selectedPreset.value,
}));
const { isDirty, markClean } = useDirtyState(dirtySource);

watch(
  () => props.preset,
  (value) => {
    Object.assign(form, {
      name: '',
      description: '',
      folder: '',
      template: '',
      cookies: '',
      cli: '',
      default: false,
      priority: 0,
      ...JSON.parse(JSON.stringify(value || {})),
    });

    importString.value = '';
    selectedPreset.value = '';
    action.clear();
    nextTick(() => {
      markClean();
      emitter('dirty-change', false);
    });
  },
  { deep: true },
);

watch(isDirty, (value: boolean) => emitter('dirty-change', value));

watch(
  () => config.ytdlp_options,
  (newOptions) =>
    (ytDlpOpt.value = newOptions
      .filter((opt) => !opt.ignored)
      .flatMap((opt) =>
        opt.flags
          .filter((flag) => flag.startsWith('--'))
          .map((flag) => ({ value: flag, description: opt.description || '' })),
      )),
  { immediate: true },
);

const triggerCookieUpload = (): void => {
  cookiesDropzoneRef.value?.triggerFileSelect();
};

const showActionError = (message: string): void => {
  action.setError(new Error(message));
};

const hasFormContent = computed(() => {
  return Boolean(
    form.name ||
    form.cli ||
    form.template ||
    form.folder ||
    form.cookies ||
    form.description ||
    form.priority !== 0,
  );
});

const normalizeName = (value: string): void => {
  form.name = normalizePresetName(value);
};

const formError = computed(() => {
  if (!String(form.name).trim() || !normalizePresetName(String(form.name))) {
    return t('common.validationNameRequired');
  }

  if (
    presets.value.some(
      (item) => item.id !== props.reference && item.name === normalizePresetName(String(form.name)),
    )
  ) {
    return t('common.presetNameAlreadyInUse');
  }

  if (!Number.isInteger(form.priority) || form.priority < 0) {
    return t('common.validationNonNegativeInteger', { field: t('common.priority') });
  }

  return '';
});
watch(formError, (value) => emitter('valid-change', !value), { immediate: true });

const confirmImportOverwrite = async (): Promise<boolean> => {
  if (!hasFormContent.value) {
    return true;
  }

  const { status } = await dialog.confirmDialog({
    title: t('common.overwriteForm'),
    message: t('common.overwriteFormDesc'),
    confirmText: t('common.overwrite'),
    cancelText: t('common.cancel'),
    confirmColor: 'warning',
  });

  return status === true;
};

const convertOptions = async (args: string): Promise<Record<string, any> | null> => {
  action.clear();
  try {
    const response = await convertCliOptions(args);

    if (response.output_template) {
      form.template = response.output_template;
    }

    if (response.download_path) {
      form.folder = response.download_path;
    }

    return response.opts as Record<string, any>;
  } catch (error) {
    showActionError(error instanceof Error ? error.message : t('common.unknownError'));
    return null;
  }
};

const checkInfo = async (): Promise<void> => {
  action.clear();
  if (formError.value) {
    return;
  }

  const normalizedName = normalizePresetName(String(form.name));
  form.name = normalizedName;

  if (form.folder) {
    form.folder = form.folder.trim();
    await nextTick();
  }

  if (form.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli);
    if (null === options) {
      return;
    }
    form.cli = form.cli.trim();
  }

  const copy: Preset = JSON.parse(JSON.stringify(form));
  for (const key in copy) {
    const value = copy[key as keyof Preset];
    if (typeof value === 'string') {
      (copy as any)[key] = value.trim();
    }
  }

  emitter('submit', { reference: toRaw(props.reference ?? null), preset: toRaw(copy) });
};

const importItem = async (): Promise<void> => {
  if (importInProgress.value) {
    return;
  }

  action.clear();
  const value = importString.value.trim();
  if (!value) {
    showActionError(t('common.validationImportRequired'));
    return;
  }

  importInProgress.value = true;
  try {
    if (!(await confirmImportOverwrite())) {
      return;
    }

    const item = decode(value) as Preset & ImportedItem;

    if (!item?._type || 'preset' !== item._type) {
      showActionError(
        t('common.validationInvalidImport', {
          expected: 'preset',
          type: item?._type ?? 'unknown',
        }),
      );
      return;
    }

    if (item.name) {
      form.name = normalizePresetName(item.name);
    }
    if (item.cli) {
      form.cli = item.cli;
    }
    if (item.template) {
      form.template = item.template;
    }
    if (item.folder) {
      form.folder = item.folder;
    }
    if (item.description) {
      form.description = item.description;
    }
    if (item.priority !== undefined) {
      form.priority = item.priority;
    }

    importString.value = '';
    action.clear();
  } catch (error) {
    console.error(error);
    showActionError(
      t('common.validationImportParseFailed', {
        error: error instanceof Error ? error.message : t('common.unknownError'),
      }),
    );
  } finally {
    importInProgress.value = false;
  }
};

const importExistingPreset = async (): Promise<void> => {
  if (importInProgress.value) {
    return;
  }

  action.clear();
  if (!selectedPreset.value) {
    return;
  }

  importInProgress.value = true;
  try {
    if (!(await confirmImportOverwrite())) {
      selectedPreset.value = '';
      return;
    }

    const preset = findPreset(selectedPreset.value);
    if (!preset) {
      showActionError(t('common.presetNotFoundShort'));
      return;
    }

    form.cli = preset.cli || '';
    form.folder = preset.folder || '';
    form.template = preset.template || '';
    form.cookies = preset.cookies || '';
    form.description = preset.description || '';
    form.priority = preset.priority ?? 0;

    await nextTick();
    selectedPreset.value = '';
    action.clear();
  } finally {
    importInProgress.value = false;
  }
};

onMounted(() => {
  markClean();
  emitter('dirty-change', false);
});
</script>
