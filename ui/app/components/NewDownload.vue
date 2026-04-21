<template>
  <main class="space-y-4">
    <form autocomplete="off" class="space-y-4" @submit.prevent="addDownload">
      <UPageCard variant="outline" :ui="downloadCardUi">
        <template #body>
          <div class="space-y-4">
            <UFormField class="w-full" :ui="downloadFieldUi">
              <template #label>
                <span class="inline-flex items-center gap-2 font-semibold">
                  <UTooltip text="Use Shift+Enter to switch to multiline input mode.">
                    <UIcon name="i-lucide-link" class="size-4 text-toned" />
                  </UTooltip>
                  <span>
                    URLs separated by newlines or
                    <span class="font-semibold lowercase">{{ getSeparatorsName(separator) }}</span>
                  </span>
                </span>
              </template>

              <div class="flex flex-col gap-2 sm:flex-row sm:items-start">
                <div class="min-w-0 flex-1">
                  <UTextarea
                    v-if="isMultiLineInput"
                    ref="urlTextarea"
                    id="url"
                    v-model="form.url"
                    :disabled="addInProgress"
                    size="lg"
                    variant="outline"
                    color="neutral"
                    class="w-full"
                    :rows="3"
                    :maxrows="12"
                    autoresize
                    :ui="{
                      root: 'w-full',
                      base: 'min-h-[7.25rem] bg-elevated/60 ring-default focus-visible:ring-primary',
                    }"
                    @keydown="handleKeyDown"
                    @input="() => void adjustTextareaHeight()"
                  />
                  <UInput
                    v-else
                    id="url"
                    v-model="form.url"
                    type="text"
                    placeholder="URLs to download"
                    :disabled="addInProgress"
                    size="lg"
                    variant="outline"
                    color="neutral"
                    class="w-full"
                    :ui="{
                      root: 'w-full',
                      base: 'bg-elevated/60 ring-default focus-visible:ring-primary',
                    }"
                    @keydown="handleKeyDown"
                    @paste="handlePaste"
                  />
                </div>

                <UButton
                  type="submit"
                  color="primary"
                  icon="i-lucide-plus"
                  :loading="addInProgress"
                  :disabled="addInProgress || !hasValidUrl"
                  size="lg"
                  class="justify-center sm:min-w-28"
                >
                  Add
                </UButton>
              </div>
            </UFormField>

            <div
              class="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.95fr)_11rem] xl:items-end"
            >
              <UFormField
                class="min-w-0 w-full"
                label="Preset"
                :ui="downloadFieldUi"
                :description="
                  hasFormatInConfig
                    ? 'Presets are disabled. Format key is present in the command options for yt-dlp.'
                    : 'Prefill saved yt-dlp command options.'
                "
              >
                <template #label>
                  <span class="inline-flex items-center gap-2 font-semibold">
                    <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
                    <span>Preset</span>
                  </span>
                </template>

                <div class="flex w-full gap-2">
                  <UButton
                    color="neutral"
                    variant="outline"
                    icon="i-lucide-info"
                    square
                    class="shrink-0"
                    @click="show_description = !show_description"
                  />

                  <div class="min-w-0 flex-1">
                    <USelect
                      id="preset"
                      v-model="form.preset"
                      :items="presetItems"
                      value-key="value"
                      label-key="label"
                      class="w-full"
                      size="lg"
                      :ui="{ base: 'w-full', content: 'min-w-[13rem]' }"
                      :disabled="addInProgress || hasFormatInConfig"
                      placeholder="Select preset"
                    />
                  </div>
                </div>
              </UFormField>

              <UFormField
                class="min-w-0 w-full"
                label="Download path"
                :ui="downloadFieldUi"
                :description="`Relative to ${config.app.download_path}`"
              >
                <template #label>
                  <span class="inline-flex items-center gap-2 font-semibold">
                    <UIcon name="i-lucide-folder-output" class="size-4 text-toned" />
                    <span>Download path</span>
                  </span>
                </template>

                <div class="flex items-center gap-2">
                  <span
                    class="max-w-44 shrink-0 truncate rounded-md border border-default bg-muted/40 px-3 py-2 text-xs text-toned"
                    :title="config.app.download_path"
                  >
                    {{ shortPath(config.app.download_path) }}
                  </span>

                  <UInput
                    id="folder"
                    v-model="form.folder"
                    :placeholder="getDefault('folder', '/')"
                    :disabled="addInProgress"
                    list="folders"
                    class="w-full"
                    size="lg"
                    :ui="{ root: 'w-full', base: 'bg-default/90' }"
                  />
                </div>
              </UFormField>

              <div class="flex w-full items-end xl:col-span-1">
                <UButton
                  type="button"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-settings-2"
                  size="lg"
                  class="w-full justify-center"
                  @click="showAdvanced = !showAdvanced"
                >
                  {{ showAdvanced ? 'Hide Options' : 'Show Options' }}
                </UButton>
              </div>
            </div>
          </div>

          <div
            v-if="show_description && !hasFormatInConfig && get_preset(form.preset)?.description"
            class="max-h-36 overflow-auto rounded-md border border-default bg-muted/30 px-3 py-2 text-sm text-toned"
          >
            <button
              type="button"
              class="block w-full cursor-pointer text-left"
              @click="expand_description"
            >
              <span class="inline-flex items-start gap-2">
                <UIcon name="i-lucide-info" class="mt-0.5 size-4 shrink-0 text-info" />
                <span class="is-ellipsis">{{ get_preset(form.preset)?.description }}</span>
              </span>
            </button>
          </div>
        </template>
      </UPageCard>

      <UPageCard v-if="showAdvanced" variant="outline" :ui="downloadCardUi">
        <template #body>
          <div class="space-y-4">
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-12">
              <div class="xl:col-span-2">
                <DLInput
                  id="force_download"
                  v-model="dlFields['--no-download-archive']"
                  type="bool"
                  label="Force download"
                  icon="i-lucide-download"
                  :disabled="addInProgress"
                  description="Ignore archive."
                  compact
                />
              </div>

              <div class="xl:col-span-2">
                <DLInput
                  id="auto_start"
                  v-model="auto_start"
                  type="bool"
                  label="Auto start"
                  icon="i-lucide-play"
                  :disabled="addInProgress"
                  description="Download automatically."
                  compact
                />
              </div>

              <div class="xl:col-span-2">
                <DLInput
                  id="no_cache"
                  v-model="dlFields['--no-continue']"
                  type="bool"
                  label="Bypass cache"
                  icon="i-lucide-eraser"
                  :disabled="addInProgress"
                  description="Remove temporary files."
                  compact
                />
              </div>

              <div class="md:col-span-2 xl:col-span-6">
                <DLInput
                  id="output_template"
                  v-model="form.template"
                  type="string"
                  label="Output template"
                  icon="i-lucide-file-code-2"
                  :disabled="addInProgress"
                  :placeholder="
                    getDefault('template', config.app.output_template || '%(title)s.%(ext)s')
                  "
                >
                  <template #description>
                    <span>
                      All output template naming options can be found on
                      <NuxtLink
                        target="_blank"
                        class="font-medium text-primary hover:underline"
                        to="https://github.com/yt-dlp/yt-dlp#output-template"
                      >
                        the yt-dlp output template page.
                      </NuxtLink>
                    </span>
                  </template>
                </DLInput>
              </div>
            </div>

            <div class="grid gap-4 xl:grid-cols-2">
              <UFormField
                label="Command options for yt-dlp"
                class="w-full"
                :ui="advancedEditorFieldUi"
              >
                <template #label>
                  <span class="inline-flex items-center gap-2 font-semibold">
                    <UIcon name="i-lucide-terminal" class="size-4 text-toned" />
                    <span>Command options for yt-dlp</span>
                  </span>
                </template>

                <template #description>
                  <span>
                    <button
                      type="button"
                      class="font-medium text-primary hover:underline"
                      @click="showOptions = true"
                    >
                      View all options
                    </button>
                    . Not all options are supported;
                    <a
                      target="_blank"
                      href="https://github.com/arabcoders/ytptube/blob/master/app/features/ytdlp/utils.py#L29"
                    >
                      some are ignored
                    </a>
                  </span>
                </template>

                <TextareaAutocomplete
                  id="cli_options"
                  v-model="form.cli"
                  :options="ytDlpOpt"
                  :placeholder="getDefault('cli', '')"
                  :disabled="addInProgress"
                  :rows="5"
                  class="w-full"
                />
              </UFormField>

              <UFormField label="Cookies" class="w-full" :ui="advancedEditorFieldUi">
                <template #label>
                  <span class="inline-flex items-center gap-2 font-semibold">
                    <UIcon name="i-lucide-cookie" class="size-4 text-toned" />
                    <span> Cookies </span>
                  </span>
                </template>

                <template #hint>
                  <button
                    type="button"
                    class="font-medium text-primary hover:underline"
                    @click="cookiesDropzoneRef?.triggerFileSelect()"
                  >
                    Upload file
                  </button>
                </template>
                <template #description>
                  <span>
                    Use the
                    <NuxtLink
                      target="_blank"
                      to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp"
                    >
                      recommended addon
                    </NuxtLink>
                    to export cookies.
                    <span class="text-error"
                      >The cookies MUST be in Netscape HTTP Cookie format.</span
                    >
                  </span>
                </template>

                <TextDropzone
                  ref="cookiesDropzoneRef"
                  id="ytdlpCookies"
                  v-model="form.cookies"
                  :disabled="addInProgress"
                  :rows="5"
                  :placeholder="
                    getDefault(
                      'cookies',
                      'Leave empty to use default cookies. Or drag & drop a cookie file here.',
                    )
                  "
                  class="w-full"
                  @error="(msg: string) => toast.error(msg)"
                />
              </UFormField>
            </div>

            <div
              v-if="config.dl_fields.length > 0"
              class="grid gap-4 md:grid-cols-2 xl:grid-cols-2"
            >
              <DLInput
                v-for="(fi, index) in sortedDLFields"
                :id="fi?.id || `dlf-${index}`"
                :key="fi.id || `dlf-${index}`"
                v-model="dlFields[fi.field]"
                :type="fi.kind"
                :description="fi.description"
                :label="fi.name"
                :icon="fi.icon"
                :field="fi.field"
                :disabled="addInProgress"
              />
            </div>
          </div>

          <div
            class="flex flex-wrap items-center justify-between gap-2 border-t border-default pt-4"
          >
            <UDropdownMenu class="sm:hidden" :items="mobileActionGroups" :modal="false">
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-ellipsis"
                trailing-icon="i-lucide-chevron-down"
              >
                Actions
              </UButton>
            </UDropdownMenu>

            <div class="hidden flex-wrap items-center gap-2 sm:flex">
              <UButton
                type="button"
                color="info"
                variant="outline"
                icon="i-lucide-info"
                :disabled="addInProgress || !hasValidUrl"
                @click="
                  emitter('getInfo', splitUrls(form.url || '')[0] || '', form.preset, form.cli)
                "
              >
                yt-dlp Information
              </UButton>

              <UButton
                v-if="config.app.console_enabled"
                type="button"
                color="warning"
                variant="outline"
                icon="i-lucide-terminal"
                :disabled="!hasValidUrl"
                @click="runCliCommand"
              >
                Run CLI
              </UButton>

              <UButton
                v-if="config.app.console_enabled"
                type="button"
                color="success"
                variant="outline"
                icon="i-lucide-flask-conical"
                :disabled="!hasValidUrl"
                @click="testDownloadOptions"
              >
                Show compiled yt-dlp options
              </UButton>
            </div>

            <UButton
              type="button"
              color="error"
              variant="outline"
              icon="i-lucide-rotate-ccw"
              :disabled="!!form?.id"
              @click="resetConfig"
            >
              Reset local settings
            </UButton>
          </div>
        </template>
      </UPageCard>
    </form>

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

    <UModal
      v-model:open="showTestResults"
      title="Test results"
      :dismissible="true"
      :ui="{ content: 'sm:max-w-5xl', body: 'p-0' }"
      @update:open="(open) => !open && closeTestResults()"
    >
      <template #body>
        <div class="relative min-h-[40vh] p-4 sm:p-5">
          <div v-if="!testResultsData" class="flex min-h-[40vh] items-center justify-center">
            <UIcon
              name="i-lucide-loader-circle"
              class="size-16 animate-spin text-toned sm:size-20"
            />
          </div>

          <div v-else class="relative">
            <div class="pointer-events-none absolute right-3 top-3 z-10 flex items-center gap-2">
              <button
                type="button"
                class="pointer-events-auto inline-flex size-9 items-center justify-center rounded-md border border-default bg-default/90 text-toned shadow-sm transition-colors hover:text-default"
                aria-label="Toggle wrapped text"
                @click="toggleTestResultsWrap"
              >
                <UIcon name="i-lucide-wrap-text" class="size-4" />
              </button>
              <button
                type="button"
                class="pointer-events-auto inline-flex size-9 items-center justify-center rounded-md border border-default bg-default/90 text-toned shadow-sm transition-colors hover:text-default"
                aria-label="Copy text"
                @click="copyTestResults"
              >
                <UIcon name="i-lucide-copy" class="size-4" />
              </button>
            </div>

            <pre
              :class="testResultsPreClasses"
            ><code class="block p-4" v-text="testResultsText" /></pre>
          </div>
        </div>
      </template>
    </UModal>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import TextDropzone from '~/components/TextDropzone.vue';
import type { item_request } from '~/types/item';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import { navigateTo } from '#app';
import { useDialog } from '~/composables/useDialog';

const props = defineProps<{ item?: Partial<item_request> }>();
const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string | undefined, cli: string | undefined): void;
  (e: 'clear_form'): void;
}>();
const config = useYtpConfig();
const toast = useNotification();
const dialog = useDialog();
const { findPreset, hasPreset, selectItems, getPresetDefault } = usePresetOptions();

const showAdvanced = useStorage<boolean>('show_advanced', false);
const separator = useStorage<string>('url_separator', separators[0]?.value ?? ',');
const auto_start = useStorage<boolean>('auto_start', true);
const show_description = useStorage<boolean>('show_description', true);
const dlFields = useStorage<Record<string, any>>('dl_fields', {});
const storedCommand = useStorage<string>('console_command', '');
const testResultsClasses = useStorage<string>('modal_text_classes', '');

const addInProgress = ref<boolean>(false);
const showOptions = ref<boolean>(false);
const showTestResults = ref<boolean>(false);
const testResultsData = ref<any>(null);
const dlFieldsExtra = ['--no-download-archive', '--no-continue'];
const ytDlpOpt = ref<AutoCompleteOptions>([]);
const cookiesDropzoneRef = ref<InstanceType<typeof TextDropzone> | null>(null);
const urlTextarea = ref<{ textareaRef?: HTMLTextAreaElement | null } | null>(null);

const testResultsText = computed(() => {
  if (typeof testResultsData.value === 'string') {
    return testResultsData.value;
  }

  if (testResultsData.value === undefined || testResultsData.value === null) {
    return '';
  }

  try {
    return JSON.stringify(testResultsData.value, null, 2) ?? '';
  } catch {
    return String(testResultsData.value ?? '');
  }
});

const testResultsPreClasses = computed(() => [
  'max-h-[calc(100vh-10rem)] overflow-auto rounded-xl border border-default bg-elevated/40 text-sm text-default',
  'font-mono leading-6 whitespace-pre',
  testResultsClasses.value,
]);

const downloadCardUi = {
  root: 'w-full',
  container: 'w-full p-4 sm:p-6',
  wrapper: 'w-full items-stretch',
  body: 'w-full space-y-4',
};

const downloadFieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
};

const advancedEditorFieldUi = {
  root: 'w-full',
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
  help: 'mt-2 text-sm text-toned',
};

const form = useStorage<item_request>('local_config_v1', {
  id: null,
  url: '',
  preset: config.app.default_preset,
  cookies: '',
  cli: '',
  template: '',
  folder: '',
  extras: {},
}) as Ref<item_request>;

const presetItems = computed(() => selectItems.value);

const mobileActionGroups = computed(() => {
  const groups = [
    [
      {
        label: 'Custom Fields',
        icon: 'i-lucide-plus',
        onSelect: () => navigateTo('/dl_fields'),
      },
      {
        label: 'yt-dlp Information',
        icon: 'i-lucide-info',
        disabled: addInProgress.value || !hasValidUrl.value,
        onSelect: () =>
          emitter(
            'getInfo',
            splitUrls(form.value.url || '')[0] || '',
            form.value.preset,
            form.value.cli,
          ),
      },
    ],
  ] as Array<Array<Record<string, unknown>>>;

  if (config.app.console_enabled) {
    groups[0]?.push(
      {
        label: 'Run CLI',
        icon: 'i-lucide-terminal',
        disabled: !hasValidUrl.value,
        onSelect: () => void runCliCommand(),
      },
      {
        label: 'Show compiled yt-dlp options',
        icon: 'i-lucide-flask-conical',
        disabled: !hasValidUrl.value,
        onSelect: () => void testDownloadOptions(),
      },
    );
  }

  groups.push([
    {
      label: 'Reset local settings',
      icon: 'i-lucide-rotate-ccw',
      color: 'error',
      disabled: Boolean(form.value?.id),
      onSelect: () => void resetConfig(),
    },
  ]);

  return groups;
});

const is_valid_dl_field = (dl_field: string): boolean => {
  if (dlFieldsExtra.includes(dl_field)) {
    return true;
  }

  if (config.dl_fields && config.dl_fields.length > 0) {
    return config.dl_fields.some((f) => f.field === dl_field);
  }

  return false;
};

const adjustTextareaHeight = async (): Promise<void> => {
  await nextTick();
  urlTextarea.value?.textareaRef?.dispatchEvent(new Event('input', { bubbles: true }));
};

const handleKeyDown = async (event: KeyboardEvent): Promise<void> => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  const isTextarea = target.tagName === 'TEXTAREA';
  if (event.key !== 'Enter') {
    return;
  }

  if (event.ctrlKey && isTextarea && !hasValidUrl.value) {
    event.preventDefault();
    addDownload();
    return;
  }

  if (event.shiftKey && !isTextarea) {
    event.preventDefault();
    const cursorPos = target.selectionStart || form.value.url.length;
    form.value.url =
      form.value.url.substring(0, cursorPos) +
      '\n' +
      form.value.url.substring(target.selectionEnd || cursorPos);

    await nextTick();

    if (urlTextarea.value) {
      await adjustTextareaHeight();
      urlTextarea.value.textareaRef?.setSelectionRange(cursorPos + 1, cursorPos + 1);
      urlTextarea.value.textareaRef?.focus();
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
  const currentValue = form.value.url || '';
  const start = target.selectionStart || currentValue.length;
  const end = target.selectionEnd || currentValue.length;
  form.value.url = currentValue.substring(0, start) + pastedText + currentValue.substring(end);

  await nextTick();

  if (urlTextarea.value) {
    await adjustTextareaHeight();
    const newPos = start + pastedText.length;
    urlTextarea.value.textareaRef?.setSelectionRange(newPos, newPos);
    urlTextarea.value.textareaRef?.focus();
  }
};

const splitUrls = (urlString: string): Array<string> => {
  const lines = urlString.split('\n');
  const urls: string[] = [];

  lines.forEach((line) =>
    line.split(separator.value).forEach((url) => {
      const trimmed = url.trim();
      if (trimmed) {
        urls.push(trimmed);
      }
    }),
  );

  return urls;
};

const addDownload = async () => {
  if (form.value.folder) {
    form.value.folder = form.value.folder.trim();
  }

  let form_cli = (form.value?.cli || '').trim();

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = [];
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid_dl_field(key)) {
        continue;
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue;
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (form_cli && keyRegex.test(form_cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`);
    }

    if (joined.length > 0) {
      form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ');
    }
  }

  if (form_cli && form_cli.trim()) {
    const options = await convertOptions(form_cli);
    if (null === options) {
      return;
    }
  }

  const request_data = [] as Array<item_request>;

  splitUrls(form.value.url).forEach(async (url: string) => {
    const data = {
      url: url,
      preset: form.value.preset || config.app.default_preset,
      folder: form.value.folder,
      template: form.value.template,
      cookies: form.value.cookies,
      cli: form_cli,
      auto_start: auto_start.value,
    } as item_request;

    if (form.value?.extras && Object.keys(form.value.extras).length > 0) {
      data.extras = form.value.extras;
    }

    request_data.push(data);
  });

  try {
    addInProgress.value = true;
    const response = await request('/api/history', {
      method: 'POST',
      body: JSON.stringify(request_data),
    });

    const data = await response.json();
    if (!response.ok) {
      toast.error(`Error: ${data.error || 'Failed to add download.'}`);
      return;
    }

    let had_errors = false;

    if (200 === response.status) {
      data.forEach((item: Record<string, any>) => {
        if (false !== item.status) {
          return;
        }

        had_errors = true;

        if (item?.hidden) {
          return;
        }

        toast.error(`Error: ${item.msg || 'Failed to add download.'}`);
      });
    }

    if (202 === response.status) {
      toast.success(data.message, { timeout: 2000 });
    }

    if (false === had_errors) {
      form.value.url = '';
      emitter('clear_form');
    }
  } catch (e: any) {
    console.error(e);
    toast.error(`Error: ${e.message}`);
  } finally {
    addInProgress.value = false;
  }
};

const resetConfig = async () => {
  const { status } = await dialog.confirmDialog({
    title: 'Confirm Action',
    message: `Reset local configuration?`,
    confirmColor: 'error',
  });
  if (!status) {
    return;
  }

  form.value = {
    url: '',
    preset: config.app.default_preset,
    cookies: '',
    cli: '',
    template: '',
    folder: '',
    extras: {},
  } as item_request;
  dlFields.value = {};
  showAdvanced.value = false;
  toast.success('Local configuration has been reset.');
};

const convertOptions = async (args: string) => {
  try {
    const response = await convertCliOptions(args);

    if (response.output_template) {
      form.value.template = response.output_template;
    }

    if (response.download_path) {
      form.value.folder = response.download_path;
    }

    return response.opts;
  } catch (e: any) {
    toast.error(e.message);
  }

  return null;
};

onUpdated(async () => {
  await nextTick();

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset;
  }

  if (config.isLoaded() && form.value?.preset && !hasPreset(form.value.preset)) {
    form.value.preset = config.app.default_preset;
  }
});

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

onMounted(async () => {
  await nextTick();

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset;
  }

  if (form.value?.folder) {
    form.value.folder = form.value.folder.trim();
    await nextTick();
  }

  if (config.isLoaded() && form.value?.preset && !hasPreset(form.value.preset)) {
    form.value.preset = config.app.default_preset;
  }

  if (props?.item) {
    const updates: Partial<item_request> = {};
    const keys = Object.keys(props.item) as (keyof item_request)[];
    for (const key of keys) {
      const value = props.item[key];
      updates[key] = key === 'extras' ? JSON.parse(JSON.stringify(value)) : value!;
    }
    form.value = { ...form.value, ...updates };
    emitter('clear_form');
  }

  await nextTick();

  if (!separators.some((s) => s.value === separator.value)) {
    separator.value = separators[0]?.value ?? ',';
  }

  if (isMultiLineInput.value && urlTextarea.value) {
    await adjustTextareaHeight();
  }
});

const runCliCommand = async (): Promise<void> => {
  if (!form.value.url) {
    toast.warning('Please enter a URL first');
    return;
  }

  if (form.value?.folder) {
    form.value.folder = form.value.folder.trim();
    await nextTick();
  }

  const { status } = await dialog.confirmDialog({
    title: 'Run CLI Command',
    message: `This will generate a yt-dlp command and run it in the console. Continue?`,
  });

  if (!status) {
    return;
  }

  let form_cli = (form.value?.cli || '').trim();

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = [];
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid_dl_field(key)) {
        continue;
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue;
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (form_cli && keyRegex.test(form_cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`);
    }

    if (joined.length > 0) {
      form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ');
    }
  }

  if (form_cli && form_cli.trim()) {
    const options = await convertOptions(form_cli);
    if (null === options) {
      return;
    }
  }

  try {
    const resp = await request('/api/yt-dlp/command', {
      method: 'POST',
      body: JSON.stringify({
        url: splitUrls(form.value.url).join(' '),
        preset: form.value.preset,
        folder: form.value.folder,
        cookies: form.value.cookies,
        template: form.value.template,
        cli: form_cli,
      }),
    });

    const json = (await resp.json()) as { command?: string; error?: string };

    if (!resp.ok) {
      toast.error(`Error: ${json.error || 'Failed to generate command.'}`);
      return;
    }

    storedCommand.value = json.command;

    await nextTick();
    await navigateTo('/console');
  } catch (error) {
    toast.error(
      error instanceof Error ? error.message : 'Failed to create and navigate to command',
    );
  }
};

const testDownloadOptions = async (): Promise<void> => {
  if (!form.value.url) {
    toast.warning('Please enter a URL first');
    return;
  }

  if (form.value?.folder) {
    form.value.folder = form.value.folder.trim();
    await nextTick();
  }

  let form_cli = (form.value?.cli || '').trim();

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = [];
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid_dl_field(key)) {
        continue;
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue;
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`);
      if (form_cli && keyRegex.test(form_cli)) {
        continue;
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`);
    }

    if (joined.length > 0) {
      form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ');
    }
  }

  try {
    const resp = await request('/api/yt-dlp/command?full=true', {
      method: 'POST',
      body: JSON.stringify({
        url: form.value.url,
        preset: form.value.preset,
        folder: form.value.folder,
        cookies: form.value.cookies,
        template: form.value.template,
        cli: form_cli,
      }),
    });

    const json = await resp.json();

    if (!resp.ok) {
      toast.error(`Error: ${json.error || 'Failed to generate command.'}`);
      return;
    }

    testResultsData.value = {
      command: json.command,
      yt_dlp: json.ytdlp,
    };
    showTestResults.value = true;
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to test download options');
  }
};

const closeTestResults = () => {
  showTestResults.value = false;
  testResultsData.value = null;
};

const toggleTestResultsWrap = () => {
  if (testResultsClasses.value.includes('is-pre-wrap-force')) {
    testResultsClasses.value = testResultsClasses.value.replace('is-pre-wrap-force', '').trim();
    return;
  }

  testResultsClasses.value = `${testResultsClasses.value} is-pre-wrap-force`.trim();
};

const copyTestResults = () => {
  try {
    copyText(JSON.stringify(testResultsData.value, null, 2));
  } catch {
    copyText(testResultsText.value);
  }
};

const isMultiLineInput = computed(() => !!form.value.url && form.value.url.includes('\n'));
const hasFormatInConfig = computed(
  (): boolean => !!form.value.cli?.match(/(?<!\S)(-f|--format)(=|\s)(\S+)/),
);

const get_preset = (name: string | undefined) => findPreset(name);
const expand_description = (e: Event) =>
  toggleClass(e.target as HTMLElement, ['is-ellipsis', 'is-pre-wrap']);

const getDefault = (type: 'cookies' | 'cli' | 'template' | 'folder', ret: string = '') => {
  if (false !== hasFormatInConfig.value || !form.value.preset) {
    return ret;
  }

  return getPresetDefault(form.value.preset, type, ret);
};

const sortedDLFields = computed(() =>
  [...config.dl_fields].sort((a, b) => (a.order || 0) - (b.order || 0)),
);
const hasValidUrl = computed(() => form.value.url && form.value.url.trim().length > 0);

watch(isMultiLineInput, async (newValue) => {
  await nextTick();
  if (newValue) {
    await adjustTextareaHeight();
    urlTextarea.value?.textareaRef?.focus();
    return;
  }
  const inputElement = document.getElementById('url') as HTMLInputElement;
  inputElement?.focus();
});
</script>
