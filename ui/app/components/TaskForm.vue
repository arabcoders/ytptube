<template>
  <form id="taskForm" autocomplete="off" class="space-y-4" @submit.prevent="checkInfo">
    <FormSubmitError :message="action.message.value" @dismiss="action.clear" />
    <UAlert
      v-if="displayError && hasFormContent"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="displayError"
      class="sticky top-0 z-10 shadow-sm"
    />

    <UAlert
      v-if="!isMultiLineInput && form.url && is_yt_handle(form.url)"
      color="warning"
      variant="soft"
      icon="i-lucide-info"
      :title="t('common.warning')"
    >
      <template #description>
        <div class="space-y-2 text-sm text-default">
          <p v-html="t('common.handleWarningDesc')" />

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            size="sm"
            :loading="convertInProgress"
            :disabled="addInProgress || convertInProgress"
            @click="() => void convertCurrentUrl()"
          >
            {{ t('common.convertUrl') }}
          </UButton>
        </div>
      </template>
    </UAlert>

    <UAlert
      v-if="form.url && is_generic_rss(form.url) && !isMultiLineInput"
      color="warning"
      variant="soft"
      icon="i-lucide-info"
      :title="t('common.information')"
      :description="t('common.rssWarningDesc')"
    />

    <UAlert
      v-if="isMultiLineInput"
      color="info"
      variant="soft"
      icon="i-lucide-files"
      :title="t('common.multipleUrls')"
    >
      <template #description>
        <ul class="list-disc space-y-1 ps-5 text-sm text-default">
          <li>{{ t('common.multipleUrlsDesc1') }}</li>
          <li>{{ t('common.multipleUrlsDesc2') }}</li>
          <li v-if="form.timer">{{ t('common.multipleUrlsDesc3') }}</li>
        </ul>
      </template>
    </UAlert>

    <div class="space-y-6 border-b border-default pb-5 last:border-b-0 last:pb-0">
      <div v-if="reference" class="flex justify-end">
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

      <div v-if="showImport || !reference" class="space-y-3 border-b border-default pb-5">
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
              v-model="import_string"
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
              :disabled="!import_string"
              class="justify-center sm:min-w-28"
              @click="() => void importItem()"
            >
              {{ t('common.import') }}
            </UButton>
          </div>
        </UFormField>
      </div>

      <div class="space-y-5">
        <div class="grid gap-4 xl:grid-cols-2">
          <UFormField class="w-full" :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-type" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.name') }}</span>
              </div>
            </template>
            <template #description>
              <span>&nbsp;</span>
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
                <UIcon name="i-lucide-link" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.url') }}</span>
                <UBadge v-if="canUseMultiUrl && urlCount > 1" color="info" variant="soft" size="sm">
                  {{ t('common.urlCount', { count: urlCount }) }}
                </UBadge>
              </div>
            </template>

            <template #description>
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-toned">
                <span v-if="canUseMultiUrl">{{ t('common.urlDesc') }}</span>
                <span v-else>&nbsp;</span>
                <button
                  v-if="!isMultiLineInput && is_yt_handle(form.url)"
                  type="button"
                  class="text-primary hover:underline"
                  :disabled="addInProgress || convertInProgress"
                  @click="() => void convertCurrentUrl()"
                >
                  {{ t('common.convertUrl') }}
                </button>
              </div>
            </template>

            <div class="w-full">
              <UTextarea
                v-if="isMultiLineInput"
                id="url"
                dir="ltr"
                ref="urlFieldRef"
                v-model="form.url"
                :disabled="addInProgress || convertInProgress"
                :rows="3"
                :maxrows="10"
                autoresize
                size="lg"
                class="w-full"
                :ui="textareaUi"
                placeholder="https://www.youtube.com/channel/UCUi3_cffYenmMTuWEsLHzqg"
                @keydown="handleKeyDown"
              />

              <UInput
                v-else
                id="url"
                dir="ltr"
                ref="urlFieldRef"
                v-model="form.url"
                type="url"
                :disabled="addInProgress || convertInProgress"
                size="lg"
                class="w-full"
                :ui="inputUi"
                placeholder="https://www.youtube.com/channel/UCUi3_cffYenmMTuWEsLHzqg"
                @keydown="handleKeyDown"
                @paste="handlePaste"
              />
            </div>
          </UFormField>
        </div>
      </div>

      <div class="space-y-5">
        <div class="grid gap-4 xl:grid-cols-2">
          <UFormField class="w-full" :ui="fieldUi" :error="timerError || undefined">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-clock-3" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.cronTimer') }}</span>
              </div>
            </template>
            <template #description>
              <span>
                {{ t('common.cronTimerDesc') }}
                <NuxtLink
                  to="https://crontab.guru/"
                  target="_blank"
                  class="text-primary hover:underline"
                >
                  crontab.guru
                </NuxtLink>
                .
              </span>
            </template>

            <UInput
              id="timer"
              dir="ltr"
              v-model="form.timer"
              type="text"
              :disabled="addInProgress"
              placeholder="0 12 * * 5"
              size="lg"
              class="w-full"
              :ui="inputUi"
            />
          </UFormField>

          <UFormField class="w-full" :ui="fieldUi" :description="presetDescription">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.presetLabel') }}</span>
              </div>
            </template>

            <UTooltip
              side="bottom"
              :text="hasFormatInConfig ? t('common.presetDisabled') : undefined"
            >
              <USelectMenu
                id="preset"
                v-model="form.preset"
                :items="presetItems"
                value-key="value"
                label-key="label"
                color="neutral"
                :disabled="addInProgress || hasFormatInConfig"
                :placeholder="t('common.selectPreset')"
                size="lg"
                class="w-full"
                :ui="{ content: 'min-w-[13rem]', item: 'ps-6' }"
                :search-input="{ placeholder: t('common.searchPresets') }"
              />
            </UTooltip>
          </UFormField>
        </div>
      </div>

      <div class="space-y-5">
        <div class="grid gap-4 xl:grid-cols-2">
          <UFormField class="w-full" :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-folder-output" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.downloadPath') }}</span>
              </div>
            </template>

            <template #description>
              {{ t('common.downloadPathDesc') }}
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
                :placeholder="getDefault('folder', '/')"
                :disabled="addInProgress"
                :ui="inputUi"
              />
            </div>
          </UFormField>

          <UFormField class="w-full" :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-file-code-2" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.outputTemplate') }}</span>
              </div>
            </template>

            <template #description>
              {{ t('common.outputTemplateDesc') }}
            </template>

            <UInput
              id="output_template"
              dir="ltr"
              v-model="form.template"
              type="text"
              :disabled="addInProgress"
              :placeholder="
                getDefault('template', config.app.output_template || '%(title)s.%(ext)s')
              "
              size="lg"
              class="w-full"
              :ui="inputUi"
            />
          </UFormField>
        </div>
      </div>

      <div class="space-y-5">
        <div class="flex flex-wrap gap-2 *:min-w-32 *:flex-1">
          <div class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex h-full items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-power" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">{{ t('common.enabled') }}</p>
                </div>
              </div>
              <USwitch v-model="form.enabled" :disabled="addInProgress" />
            </div>
          </div>

          <div class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex h-full items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-play" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">{{ t('common.autoStart') }}</p>
                </div>
              </div>
              <USwitch v-model="form.auto_start" :disabled="addInProgress" />
            </div>
          </div>

          <div class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex h-full items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-rss" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">{{ t('common.enableHandler') }}</p>
                </div>
                <p class="text-xs text-toned">
                  {{ t('common.enableHandlerDesc') }}
                </p>
              </div>
              <USwitch v-model="form.handler_enabled" :disabled="addInProgress" />
            </div>
          </div>

          <div v-if="!reference" class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex h-full items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-archive" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">{{ t('common.archiveAll') }}</p>
                </div>
                <p class="text-xs text-toned">{{ t('common.archiveAllDesc') }}</p>
              </div>
              <USwitch v-model="archiveAllAfterAdd" :disabled="addInProgress" />
            </div>
          </div>
        </div>
      </div>

      <div class="space-y-5 border-t border-default pt-5">
        <UFormField class="w-full" :ui="editorFieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-terminal" class="size-4 text-toned" />
              <span>{{ t('common.cliOptions') }}</span>
            </div>
          </template>
          <template #description>
            <NuxtLink class="text-primary hover:underline" @click="showOptions = true">
              {{ t('common.cliOptionsViewAll') }}
            </NuxtLink>
            {{ t('common.cliOptionsDescPrefix') }}
            <a
              target="_blank"
              href="https://github.com/arabcoders/ytptube/blob/master/app/features/ytdlp/utils.py#L29"
              class="text-primary hover:underline"
            >
              {{ t('common.cliOptionsDescIgnored') }}
            </a>
          </template>
          <TextareaAutocomplete
            id="cli_options"
            v-model="form.cli"
            :options="ytDlpOpt"
            :placeholder="getDefault('cli', '')"
            :disabled="addInProgress"
          />
        </UFormField>
      </div>
    </div>

    <UAlert color="info" variant="soft">
      <template #description>
        <ul class="list-disc space-y-2 ps-5 text-sm text-default">
          <li v-html="t('common.tasksInfo1')" />
          <li v-html="t('common.tasksInfo2')" />
          <li v-html="t('common.tasksInfo3')" />
          <li v-html="t('common.tasksInfo4')" />
          <li v-html="t('common.tasksInfo5')" />
        </ul>
      </template>
    </UAlert>

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

<script lang="ts" setup>
import { useStorage } from '@vueuse/core';
import { CronExpressionParser } from 'cron-parser';
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { ExportedTask, Task } from '~/types/tasks';
import { ensure_api_success, shortPath } from '~/utils';

const props = defineProps<{
  reference?: number | null | undefined;
  task: Task;
  addInProgress?: boolean;
}>();

const emitter = defineEmits<{
  (e: 'dirty-change' | 'valid-change', value: boolean): void;
  (
    e: 'submit',
    payload: { reference: number | null | undefined; task: Task | Task[]; archive_all?: boolean },
  ): void;
}>();

const toast = useNotification();
const config = useYtpConfig();
const dialog = useDialog();
const { t } = useI18n();
const tasksComposable = useTasks();
const { findPreset, getPresetDefault, selectItems } = usePresetOptions();
const showImport = useStorage('showTaskImport', false);

const createDefaultTask = (source?: Partial<Task>): Task => ({
  name: '',
  url: '',
  folder: '',
  preset: '',
  timer: '',
  template: '',
  cli: '',
  auto_start: true,
  handler_enabled: true,
  enabled: true,
  ...(JSON.parse(JSON.stringify(source || {})) as Partial<Task>),
});

const convertInProgress = ref(false);
const import_string = ref('');
const showOptions = ref(false);
const ytDlpOpt = ref<AutoCompleteOptions>([]);
const archiveAllAfterAdd = ref(false);
const urlFieldRef = ref<{
  inputRef?: HTMLInputElement | null;
  textareaRef?: HTMLTextAreaElement | null;
} | null>(null);

const CHANNEL_REGEX =
  /^https?:\/\/(?:www\.)?youtube\.com\/(?:(?:channel\/(?<channelId>UC[0-9A-Za-z_-]{22}))|(?:c\/(?<customName>[A-Za-z0-9_-]+))|(?:user\/(?<userName>[A-Za-z0-9_-]+))|(?:@(?<handle>[A-Za-z0-9_-]+)))(?<suffix>\/.*)?\/?$/;
const GENERIC_RSS_REGEX = /\.(rss|atom)(\?.*)?$|handler=rss/i;

const form = reactive<Task>(createDefaultTask(props.task));
const timerError = ref('');
const action = useFormSubmit();

const dirtySource = computed(() => ({
  reference: props.reference ?? null,
  form: JSON.parse(JSON.stringify(form)),
  import_string: import_string.value,
  showImport: showImport.value,
  archiveAllAfterAdd: archiveAllAfterAdd.value,
}));
const { isDirty, markClean } = useDirtyState(dirtySource);

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
  hint: 'text-sm text-toned',
  error: 'text-sm text-error',
};

const editorFieldUi = {
  root: 'w-full',
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
  hint: 'text-sm text-toned',
};

const inputUi = {
  root: 'w-full',
  base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const textareaUi = {
  root: 'w-full',
  base: 'min-h-[7rem] w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const canUseMultiUrl = computed(() => props.reference == null);
const isMultiLineInput = computed(
  () => canUseMultiUrl.value && Boolean(form.url && form.url.includes('\n')),
);
const urlCount = computed(() => splitUrls(form.url || '').length);
const presetItems = computed(() => selectItems.value);
const presetDescription = computed(() => {
  return hasFormatInConfig.value ? t('common.presetDisabled') : t('common.presetDescription');
});

const hasFormatInConfig = computed<boolean>(
  () => !!form.cli && /(?<!\S)(-f|--format)(=|\s)(\S+)/.test(form.cli),
);

const splitUrls = (urlString: string): string[] => {
  return urlString
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
};

const getUrlElement = (): HTMLInputElement | HTMLTextAreaElement | null => {
  return urlFieldRef.value?.textareaRef || urlFieldRef.value?.inputRef || null;
};

watch(
  () => props.task,
  (value) => {
    action.clear();
    Object.assign(form, createDefaultTask(value));
    if (!value?.preset) {
      form.preset = toRaw(config.app.default_preset);
    }

    import_string.value = '';
    archiveAllAfterAdd.value = false;
    nextTick(() => {
      markClean();
      emitter('dirty-change', false);
    });
  },
  { immediate: true, deep: true },
);

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

watch(
  () => form.cli,
  () => {
    if (!hasFormatInConfig.value && !form.preset) {
      form.preset = config.app.default_preset;
    }
  },
);

watch(isDirty, (value: boolean) => emitter('dirty-change', value));

const handleKeyDown = async (event: KeyboardEvent): Promise<void> => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  const isTextarea = target.tagName === 'TEXTAREA';

  if (event.key !== 'Enter') {
    return;
  }

  if (event.ctrlKey && isTextarea) {
    event.preventDefault();
    await checkInfo();
    return;
  }

  if (canUseMultiUrl.value && event.shiftKey && !isTextarea) {
    event.preventDefault();
    const cursorPos = target.selectionStart || form.url.length;
    form.url =
      form.url.substring(0, cursorPos) +
      '\n' +
      form.url.substring(target.selectionEnd || cursorPos);

    await nextTick();

    const field = getUrlElement();
    if (field instanceof HTMLTextAreaElement) {
      field.setSelectionRange(cursorPos + 1, cursorPos + 1);
      field.focus();
    }
  }
};

const handlePaste = async (event: ClipboardEvent): Promise<void> => {
  const pastedText = event.clipboardData?.getData('text') || '';
  if (!canUseMultiUrl.value || !pastedText.includes('\n')) {
    return;
  }

  event.preventDefault();

  const target = event.target as HTMLInputElement;
  const currentValue = form.url || '';
  const start = target.selectionStart || currentValue.length;
  const end = target.selectionEnd || currentValue.length;
  form.url = currentValue.substring(0, start) + pastedText + currentValue.substring(end);

  await nextTick();

  const field = getUrlElement();
  if (field instanceof HTMLTextAreaElement) {
    const newPos = start + pastedText.length;
    field.setSelectionRange(newPos, newPos);
    field.focus();
  }
};

const hasFormContent = computed(() => {
  return Boolean(
    form.name ||
    form.url ||
    form.timer ||
    form.template ||
    form.folder ||
    form.cli ||
    (form.preset && form.preset !== config.app.default_preset) ||
    form.auto_start === false ||
    form.handler_enabled === false ||
    form.enabled === false,
  );
});

const formError = computed(() => {
  const urls = splitUrls(form.url || '');
  if (urls.length === 0) {
    return t('common.validationUrlRequired');
  }

  if (!canUseMultiUrl.value && urls.length > 1) {
    return t('common.multipleUrlsAddOnly');
  }

  if (!String(form.name).trim()) {
    return t('common.validationNameRequired');
  }

  if (form.timer) {
    try {
      CronExpressionParser.parse(form.timer);
    } catch (error) {
      return t('common.validationInvalidCron', {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  try {
    new URL(urls[0] || '');
  } catch {
    return t('common.invalidUrl');
  }

  return '';
});
const displayError = computed(() => formError.value || timerError.value);
watch(displayError, (value) => emitter('valid-change', !value), { immediate: true });
watch([() => form.url, () => form.preset, () => form.timer, () => form.handler_enabled], () => {
  timerError.value = '';
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

const checkInfo = async (): Promise<void> => {
  const urls = splitUrls(form.url || '');
  action.clear();
  timerError.value = '';

  if (formError.value) {
    return;
  }

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

  try {
    await requireTimerForTask(form);
  } catch (error) {
    timerError.value = error instanceof Error ? error.message : t('common.unknownError');
    return;
  }

  if (urls.length === 1) {
    emitter('submit', {
      reference: toRaw(props.reference),
      task: toRaw({ ...form }),
      archive_all: archiveAllAfterAdd.value,
    });
    return;
  }

  const tasks: Task[] = urls.map((url, idx) => {
    if (idx === 0) {
      return {
        name: form.name,
        url,
        folder: form.folder,
        preset: form.preset,
        timer: form.timer,
        template: form.template,
        cli: form.cli,
        auto_start: form.auto_start,
        handler_enabled: form.handler_enabled,
        enabled: form.enabled,
      } as Task;
    }

    return {
      url,
      preset: form.preset,
      timer: form.timer,
      handler_enabled: form.handler_enabled,
    } as Task;
  });

  try {
    await Promise.all(tasks.map((item) => requireTimerForTask(item)));
  } catch (error) {
    timerError.value = error instanceof Error ? error.message : t('common.unknownError');
    return;
  }

  const submitTasks: Task[] = tasks.map((item, idx) => {
    if (idx === 0) {
      return item;
    }

    return { url: item.url } as Task;
  });

  emitter('submit', {
    reference: toRaw(props.reference),
    task: submitTasks,
    archive_all: archiveAllAfterAdd.value,
  });
};

const importItem = async (): Promise<void> => {
  action.clear();
  const val = import_string.value.trim();
  if (!val) {
    action.setError(new Error(t('common.validationImportRequired')));
    return;
  }

  if (!(await confirmImportOverwrite())) {
    return;
  }

  try {
    const item = decode(val) as ExportedTask;

    if ('task' !== item._type) {
      action.setError(
        new Error(t('common.validationInvalidImport', { expected: 'task', type: item._type })),
      );
      import_string.value = '';
      return;
    }

    form.name = item.name ?? form.name;
    form.url = item.url ?? form.url;
    form.template = item.template ?? form.template;
    form.timer = item.timer ?? form.timer;
    form.folder = item.folder ?? form.folder;
    form.cli = item.cli ?? form.cli;
    form.auto_start = item.auto_start ?? true;
    form.handler_enabled = item.handler_enabled ?? true;
    form.enabled = item.enabled ?? true;

    if (item.preset) {
      const preset = findPreset(item.preset);
      if (!preset) {
        toast.warning(t('common.presetNotFound', { preset: item.preset }));
        form.preset = 'default';
      } else {
        form.preset = item.preset;
      }
    }

    import_string.value = '';
    showImport.value = false;
    action.clear();
  } catch (error) {
    console.error(error);
    action.setError(
      new Error(
        t('common.validationImportParseFailed', {
          error: error instanceof Error ? error.message : t('common.unknownError'),
        }),
      ),
    );
  }
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
  } catch (error) {
    action.setError(error);
    return null;
  }
};

const is_yt_handle = (url: string): boolean => {
  if (!url || '' === url) {
    return false;
  }
  const m = url.match(CHANNEL_REGEX);
  if (m?.groups) {
    return !m.groups.channelId;
  }
  return false;
};

const is_generic_rss = (url: string): boolean => {
  if (!url || '' === url) {
    return false;
  }
  return GENERIC_RSS_REGEX.test(url);
};

const convert_url = async (url: string): Promise<string> => {
  action.clear();
  if (!url || '' === url) {
    return url;
  }

  const m = url.match(CHANNEL_REGEX);
  if (!m?.groups || !m.groups.handle) {
    return url;
  }

  const params = new URLSearchParams();
  params.append('url', url);
  params.append('args', '-I0');

  try {
    convertInProgress.value = true;
    const resp = await request('/api/yt-dlp/url/info?' + params.toString());
    await ensure_api_success(resp);
    const body = await resp.json();
    const channel_id = ag(body, 'channel_id', null);

    if (channel_id) {
      return url.replace(`/@${m.groups.handle}`, `/channel/${channel_id}`);
    }
  } catch (error) {
    console.error(error);
    action.setError(error);
  } finally {
    convertInProgress.value = false;
  }

  return url;
};

const convertCurrentUrl = async (): Promise<void> => {
  form.url = await convert_url(form.url);
};

const requireTimerForTask = async (
  item: Pick<Task, 'url' | 'preset' | 'timer' | 'handler_enabled'>,
): Promise<void> => {
  if (item.timer?.trim()) {
    return;
  }

  if (item.handler_enabled === false) {
    throw new Error(t('common.handlerDisabledCron'));
  }

  const result = await tasksComposable.inspectTaskHandler({
    url: item.url,
    preset: item.preset,
    static_only: true,
  });

  if (!result) {
    throw new Error(t('common.handlerVerifyFailed'));
  }

  if (result?.matched) {
    return;
  }

  throw new Error(t('common.handlerNoMatch'));
};

const getDefault = (type: 'cookies' | 'cli' | 'template' | 'folder', ret: string = '') => {
  if (false !== hasFormatInConfig.value || !form.preset) {
    return ret;
  }

  return getPresetDefault(form.preset, type, ret);
};

onMounted(() => {
  markClean();
  emitter('dirty-change', false);
});
</script>
