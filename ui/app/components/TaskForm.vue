<template>
  <form id="taskForm" autocomplete="off" class="space-y-4" @submit.prevent="checkInfo">
    <UAlert
      v-if="!isMultiLineInput && form.url && is_yt_handle(form.url)"
      color="warning"
      variant="soft"
      icon="i-lucide-info"
      title="Warning"
    >
      <template #description>
        <div class="space-y-2 text-sm text-default">
          <p>
            You are using a YouTube link with <code>@handle</code> instead of
            <code>channel_id</code>. To activate RSS feed support for URL click on the
            <b>Convert URL</b> link.
          </p>

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            size="sm"
            :loading="convertInProgress"
            :disabled="addInProgress || convertInProgress"
            @click="() => void convertCurrentUrl()"
          >
            Convert URL
          </UButton>
        </div>
      </template>
    </UAlert>

    <UAlert
      v-if="form.url && is_generic_rss(form.url) && !isMultiLineInput"
      color="warning"
      variant="soft"
      icon="i-lucide-info"
      title="Information"
      description="You are using a generic RSS/Atom feed URL. The task handler will automatically download new items found in this feed."
    />

    <UAlert
      v-if="isMultiLineInput"
      color="info"
      variant="soft"
      icon="i-lucide-files"
      title="Multiple URLs"
    >
      <template #description>
        <ul class="list-disc space-y-1 pl-5 text-sm text-default">
          <li>First URL uses the <b>Name</b> provided above with full settings.</li>
          <li>Other URLs infer names from metadata and inherit settings from the first URL.</li>
          <li v-if="form.timer">Timers are offset by 5-minute increments for each URL.</li>
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
          @click="showImport = !showImport"
        >
          {{ showImport ? 'Hide' : 'Show' }} import
        </UButton>
      </div>

      <div v-if="showImport || !reference" class="space-y-3 border-b border-default pb-5">
        <UFormField class="w-full" :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-import" class="size-4 text-toned" />
              <span class="font-semibold text-default">Import string</span>
            </div>
          </template>
          <template #description>
            <span>You can use this field to populate the data, using shared string.</span>
          </template>

          <div class="flex flex-col gap-2 sm:flex-row">
            <UInput
              id="import_string"
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
              Import
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
                <span class="font-semibold text-default">Name</span>
              </div>
            </template>
            <template #description>
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-toned">
                <p class="text-sm text-toned">The name is used to identify this specific task.</p>
              </div>
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
                <span class="font-semibold text-default">URL</span>
                <UBadge v-if="urlCount > 1" color="info" variant="soft" size="sm">
                  {{ urlCount }} URLs
                </UBadge>
              </div>
            </template>

            <template #description>
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-toned">
                <span>The channel or playlist URL. Use Shift+Enter for multiple URLs.</span>
                <button
                  v-if="!isMultiLineInput && is_yt_handle(form.url)"
                  type="button"
                  class="text-primary hover:underline"
                  :disabled="addInProgress || convertInProgress"
                  @click="() => void convertCurrentUrl()"
                >
                  Convert URL
                </button>
              </div>
            </template>

            <div class="w-full">
              <UTextarea
                v-if="isMultiLineInput"
                id="url"
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
          <UFormField class="w-full" :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-clock-3" class="size-4 text-toned" />
                <span class="font-semibold text-default">CRON Timer</span>
              </div>
            </template>
            <template #description>
              <span>
                The CRON timer expression to use for this task. If not set, the task runner will be
                disabled. For more information on CRON expressions, see
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
                <span class="font-semibold text-default">Preset</span>
              </div>
            </template>

            <UTooltip
              side="bottom"
              :text="
                hasFormatInConfig
                  ? 'Presets are disabled. Format key is present in the command options for yt-dlp.'
                  : undefined
              "
            >
              <USelect
                id="preset"
                v-model="form.preset"
                :items="presetItems"
                value-key="value"
                label-key="label"
                :disabled="addInProgress || hasFormatInConfig"
                placeholder="Select preset"
                size="lg"
                class="w-full"
                :ui="{ base: 'w-full' }"
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
                <span class="font-semibold text-default">Download path</span>
              </div>
            </template>

            <template #description>
              Path relative to the download path, leave empty to use preset or default download
              path.
            </template>

            <div class="flex flex-col gap-2 sm:flex-row">
              <UTooltip :text="`Full Path: ${config.app.download_path}`">
                <div
                  class="inline-flex min-h-11 items-center rounded-md border border-default bg-muted/30 px-3 text-sm text-toned"
                >
                  {{ shortPath(config.app.download_path) }}
                </div>
              </UTooltip>

              <UInput
                id="folder"
                v-model="form.folder"
                type="text"
                list="folders"
                :placeholder="getDefault('folder', '/')"
                :disabled="addInProgress"
                size="lg"
                class="w-full"
                :ui="inputUi"
              />
            </div>
          </UFormField>

          <UFormField class="w-full" :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-file-code-2" class="size-4 text-toned" />
                <span class="font-semibold text-default">Output template</span>
              </div>
            </template>

            <template #description>
              The template to use. Leave empty to use preset or default template.
            </template>

            <UInput
              id="output_template"
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
        <div class="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-power" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">Enabled</p>
                </div>
                <p class="text-xs text-toned">Whether the task is enabled.</p>
              </div>
              <USwitch v-model="form.enabled" :disabled="addInProgress" />
            </div>
          </div>

          <div class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-play" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">Auto Start</p>
                </div>
                <p class="text-xs text-toned">
                  Whether to automatically queue and start the download task.
                </p>
              </div>
              <USwitch v-model="form.auto_start" :disabled="addInProgress" />
            </div>
          </div>

          <div class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-rss" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">Enable Handler</p>
                </div>
                <p class="text-xs text-toned">Handlers run regardless of task timer.</p>
              </div>
              <USwitch v-model="form.handler_enabled" :disabled="addInProgress" />
            </div>
          </div>

          <div v-if="!reference" class="rounded-lg border border-default bg-muted/20 p-3">
            <div class="flex items-center justify-between gap-3">
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-archive" class="size-4 text-toned" />
                  <p class="text-sm font-semibold text-default">Archive All</p>
                </div>
                <p class="text-xs text-toned">Mark all existing items as downloaded after add.</p>
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
              <span>Command options for yt-dlp</span>
            </div>
          </template>
          <template #description>
            <NuxtLink class="text-primary hover:underline" @click="showOptions = true">
              View all options
            </NuxtLink>
            . Not all options are supported;
            <a
              target="_blank"
              href="https://github.com/arabcoders/ytptube/blob/master/app/features/ytdlp/utils.py#L29"
              class="text-primary hover:underline"
            >
              some are ignored
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
        <ul class="list-disc space-y-2 pl-5 text-sm text-default">
          <li>
            <strong>Tasks:</strong> requires <code>--download-archive</code> in
            <code>Command options for yt-dlp</code> can be set via presets or manually. Default
            presets already include this option.
          </li>
          <li>
            <strong>YouTube RSS:</strong> Use <code>channel_id</code> or
            <code>playlist_id</code> URLs. Other link types (custom names, handles, user profiles)
            are not supported.
          </li>
          <li>
            <strong>Generic RSS/Atom:</strong> URL must end with <code>.rss</code> or
            <code>.atom</code>. If not possible, append <code>&handler=rss</code> to existing query
            parameters, or add <code>#handler=rss</code> as a fragment.
          </li>
          <li>
            <strong>RSS Monitoring Basics:</strong> Runs hourly independently. Timer controls
            scheduled downloads to yt-dlp. Disable <code>Enable Handler</code> to disable RSS
            monitoring.
          </li>
        </ul>
      </template>
    </UAlert>

    <div
      class="flex flex-col-reverse gap-2 border-t border-default pt-5 sm:flex-row sm:justify-end"
    >
      <UButton
        type="button"
        color="neutral"
        variant="outline"
        size="lg"
        icon="i-lucide-x"
        :disabled="addInProgress"
        class="justify-center"
        @click="emitter('cancel')"
      >
        Cancel
      </UButton>

      <UButton
        type="submit"
        color="primary"
        size="lg"
        icon="i-lucide-save"
        :disabled="addInProgress"
        :loading="addInProgress"
        class="justify-center"
      >
        Save
      </UButton>
    </div>

    <datalist v-if="config?.folders" id="folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>

    <UModal
      v-if="showOptions"
      v-model:open="showOptions"
      title="yt-dlp options"
      :dismissible="true"
      :ui="{ content: 'sm:max-w-6xl', body: 'p-0' }"
    >
      <template #description>
        <span class="sr-only">Browse available yt-dlp flags and descriptions.</span>
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

const props = defineProps<{
  reference?: number | null | undefined;
  task: Task;
  addInProgress?: boolean;
}>();

const emitter = defineEmits<{
  (e: 'cancel'): void;
  (
    e: 'submit',
    payload: { reference: number | null | undefined; task: Task | Task[]; archive_all?: boolean },
  ): void;
}>();

const toast = useNotification();
const config = useConfigStore();
const dialog = useDialog();
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

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
  hint: 'text-sm text-toned',
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

const isMultiLineInput = computed(() => Boolean(form.url && form.url.includes('\n')));
const urlCount = computed(() => splitUrls(form.url || '').length);
const presetItems = computed(() => selectItems.value);
const presetDescription = computed(() => {
  return hasFormatInConfig.value
    ? 'Presets are disabled. Format key is present in the command options for yt-dlp.'
    : "Select the preset to use for this URL. If the -f, --format argument is present in the command line options, the preset and all it's options will be ignored.";
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
    Object.assign(form, createDefaultTask(value));
    if (!value?.preset) {
      form.preset = toRaw(config.app.default_preset);
    }
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

  if (event.shiftKey && !isTextarea) {
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
  if (!pastedText.includes('\n')) {
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

const confirmImportOverwrite = async (): Promise<boolean> => {
  if (!hasFormContent.value) {
    return true;
  }

  const { status } = await dialog.confirmDialog({
    title: 'Overwrite current form?',
    message: 'Importing will overwrite the current task form fields.',
    confirmText: 'Overwrite',
    cancelText: 'Cancel',
    confirmColor: 'warning',
  });

  return status === true;
};

const checkInfo = async (): Promise<void> => {
  const urls = splitUrls(form.url || '');

  if (urls.length === 0) {
    toast.error('At least one URL is required.');
    return;
  }

  if (!form.name) {
    toast.error('The name field is required.');
    return;
  }

  if (form.folder) {
    form.folder = form.folder.trim();
    await nextTick();
  }

  if (form.timer) {
    try {
      CronExpressionParser.parse(form.timer);
    } catch (error: any) {
      console.error(error);
      toast.error(`Invalid CRON expression. ${error.message}`);
      return;
    }
  }

  try {
    new URL(urls[0] || '');
  } catch {
    toast.error('Invalid URL');
    return;
  }

  if (form.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli);
    if (null === options) {
      return;
    }
    form.cli = form.cli.trim();
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

    return { url } as Task;
  });

  emitter('submit', {
    reference: toRaw(props.reference),
    task: tasks,
    archive_all: archiveAllAfterAdd.value,
  });
};

const importItem = async (): Promise<void> => {
  const val = import_string.value.trim();
  if (!val) {
    toast.error('The import string is required.');
    return;
  }

  if (!(await confirmImportOverwrite())) {
    return;
  }

  try {
    const item = decode(val) as ExportedTask;

    if ('task' !== item._type) {
      toast.error(`Invalid import string. Expected type 'task', got '${item._type}'.`);
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
        toast.warning(`Preset '${item.preset}' not found. Preset will be set to default.`);
        form.preset = 'default';
      } else {
        form.preset = item.preset;
      }
    }

    import_string.value = '';
    showImport.value = false;
  } catch (error: any) {
    console.error(error);
    toast.error(`Failed to import string. ${error.message}`);
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
  } catch (error: any) {
    toast.error(error.message);
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
    const body = await resp.json();
    const channel_id = ag(body, 'channel_id', null);

    if (channel_id) {
      return url.replace(`/@${m.groups.handle}`, `/channel/${channel_id}`);
    }
  } catch (error: any) {
    console.error(error);
    toast.error(`Error: ${error.message}`);
  } finally {
    convertInProgress.value = false;
  }

  return url;
};

const convertCurrentUrl = async (): Promise<void> => {
  form.url = await convert_url(form.url);
};

const getDefault = (type: 'cookies' | 'cli' | 'template' | 'folder', ret: string = '') => {
  if (false !== hasFormatInConfig.value || !form.preset) {
    return ret;
  }

  return getPresetDefault(form.preset, type, ret);
};
</script>
