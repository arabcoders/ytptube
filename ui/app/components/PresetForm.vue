<template>
  <form id="presetForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
    <div class="grid gap-4 md:grid-cols-2">
      <div v-if="reference" class="md:col-span-2 flex justify-end">
        <UButton
          type="button"
          color="neutral"
          variant="ghost"
          size="sm"
          :icon="showImport ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          @click="
            () => {
              showImport = !showImport;
            }
          "
        >
          {{ showImport ? t('common.hideImport') : t('common.showImport') }}
        </UButton>
      </div>

      <template v-if="showImport || !reference">
        <UFormField class="w-full" :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-copy" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.importPreset') }}</span>
            </div>
          </template>

          <template #description>
            <span>{{ t('common.importPresetDesc') }}</span>
          </template>

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
            @update:model-value="() => void importExistingPreset()"
          />
        </UFormField>

        <UFormField class="w-full" :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-import" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.importString') }}</span>
            </div>
          </template>

          <template #description>
            <span>{{ t('common.importStringDesc') }}</span>
          </template>

          <div class="flex flex-col gap-2 sm:flex-row">
            <UInput
              id="import_string"
              dir="ltr"
              v-model="importString"
              type="text"
              autocomplete="off"
              size="lg"
              class="w-full"
              :ui="inputUi"
            />

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-import"
              size="lg"
              :disabled="!importString"
              class="justify-center sm:min-w-28"
              @click="() => void importItem()"
            >
              {{ t('common.import') }}
            </UButton>
          </div>
        </UFormField>
      </template>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-type" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.name') }}</span>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.presetNameDesc') }}</span>
        </template>

        <UInput
          id="name"
          v-model="form.name"
          type="text"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.priority') }}</span>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.presetPriorityDesc') }}</span>
        </template>

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

      <UFormField class="w-full" :ui="fieldUi" :description="t('common.presetPathDesc')">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-folder-output" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.downloadPath') }}</span>
          </div>
        </template>

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
            :placeholder="t('common.leaveEmptyDefault')"
            :disabled="addInProgress"
            :ui="inputUi"
          />
        </div>
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi" :description="t('common.presetTemplateDesc')">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-file-code-2" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.outputTemplate') }}</span>
          </div>
        </template>

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

    <div class="space-y-5 border-t border-default pt-5">
      <UFormField class="w-full" :ui="editorFieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-terminal" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.cliOptions') }}</span>
          </div>
        </template>

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

    <div class="grid gap-5 border-t border-default pt-5 md:grid-cols-2">
      <div class="space-y-3">
        <UFormField class="h-full w-full" :ui="editorFieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-cookie" class="size-4 text-toned" />
              <span>{{ t('common.cookiesLabel') }}</span>
            </div>
          </template>
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
            @error="(msg: string) => toast.error(msg)"
            :placeholder="t('common.cookiesPlaceholder')"
          />
        </UFormField>
      </div>

      <div class="space-y-3">
        <UFormField class="h-full w-full" :ui="editorFieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-message-square-text" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.description') }}</span>
            </div>
          </template>
          <template #description>
            <span>&nbsp;</span>
          </template>

          <UTextarea
            id="description"
            v-model="form.description"
            :disabled="addInProgress"
            :placeholder="t('common.extrasInstructions')"
            :rows="7"
            size="lg"
            variant="outline"
            color="neutral"
            class="w-full"
            :ui="textareaUi"
          />
        </UFormField>
      </div>
    </div>

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
import { useStorage } from '@vueuse/core';
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import TextDropzone from '~/components/TextDropzone.vue';
import type { ImportedItem } from '~/types';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { Preset } from '~/types/presets';
import { normalizePresetName, shortPath } from '~/utils';

const { t } = useI18n();

const emitter = defineEmits<{
  (event: 'dirty-change', dirty: boolean): void;
  (event: 'submit', payload: { reference: number | null; preset: Preset }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  preset: Partial<Preset>;
  addInProgress?: boolean;
}>();

const config = useYtpConfig();
const toast = useNotification();
const dialog = useDialog();
const { presets, findPreset, selectItems } = usePresetOptions();

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
const showImport = useStorage<boolean>('showImport', false);
const selectedPreset = ref<string>('');
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
  base: 'min-h-[10rem] w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const importPresetItems = computed(() => selectItems.value);

const dirtySource = computed(() => ({
  reference: props.reference ?? null,
  form: JSON.parse(JSON.stringify(form)),
  importString: importString.value,
  selectedPreset: selectedPreset.value,
  showImport: showImport.value,
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

const hasFormContent = computed(() => {
  return Boolean(
    form.name ||
    form.cli ||
    form.template ||
    form.folder ||
    form.cookies ||
    form.description ||
    (form.priority ?? 0) > 0,
  );
});

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
  try {
    const response = await convertCliOptions(args);

    if (response.output_template) {
      form.template = response.output_template;
    }

    if (response.download_path) {
      form.folder = response.download_path;
    }

    return response.opts as Record<string, any>;
  } catch (error: any) {
    toast.error(error.message);
    return null;
  }
};

const checkInfo = async (): Promise<void> => {
  for (const key of ['name']) {
    if (!form[key as keyof Preset]) {
      toast.error(t('common.fieldRequired', { field: key }));
      return;
    }
  }

  const normalizedName = normalizePresetName(String(form.name));
  if (!normalizedName) {
    toast.error(t('common.validationNameRequired'));
    return;
  }

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
  const usedName = presets.value.some(
    (item) => item.id !== props.reference && item.name === normalizedName,
  );

  if (usedName) {
    toast.error(t('common.presetNameAlreadyInUse'));
    return;
  }

  for (const key in copy) {
    const value = copy[key as keyof Preset];
    if (typeof value === 'string') {
      (copy as any)[key] = value.trim();
    }
  }

  emitter('submit', { reference: toRaw(props.reference ?? null), preset: toRaw(copy) });
};

const importItem = async (): Promise<void> => {
  const value = importString.value.trim();
  if (!value) {
    toast.error(t('common.validationImportRequired'));
    return;
  }

  if (!(await confirmImportOverwrite())) {
    return;
  }

  try {
    const item = decode(value) as Preset & ImportedItem;

    if (!item?._type || 'preset' !== item._type) {
      toast.error(
        t('common.validationInvalidImport', { expected: 'preset', type: item._type ?? 'unknown' }),
      );
      return;
    }

    if (item.name) {
      form.name = item.name;
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
    showImport.value = false;
  } catch (error: any) {
    console.error(error);
    toast.error(t('common.validationImportParseFailed', { error: error.message }));
  }
};

const importExistingPreset = async (): Promise<void> => {
  if (!selectedPreset.value) {
    return;
  }

  if (!(await confirmImportOverwrite())) {
    selectedPreset.value = '';
    return;
  }

  const preset = findPreset(selectedPreset.value);
  if (!preset) {
    toast.error(t('common.presetNotFoundShort'));
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
};

onMounted(() => {
  markClean();
  emitter('dirty-change', false);
});
</script>
