<template>
  <form id="conditionForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
    <div class="grid gap-4 md:grid-cols-2">
      <div v-if="reference" class="md:col-span-2 flex justify-end">
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

      <template v-if="showImport || !reference">
        <UFormField class="w-full md:col-span-2" :ui="fieldUi">
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
              v-model="importString"
              type="text"
              autocomplete="off"
              size="lg"
              class="w-full"
              :ui="inputUi"
            />

            <UButton
              type="button"
              color="primary"
              icon="i-lucide-import"
              size="lg"
              class="justify-center sm:min-w-28"
              :disabled="!importString"
              @click="() => void importItem()"
            >
              Import
            </UButton>
          </div>
        </UFormField>
      </template>

      <UFormField class="w-full md:col-span-2" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-type" class="size-4 text-toned" />
            <span class="font-semibold text-default">Name</span>
          </div>
        </template>

        <template #description>
          <span>The name that refers to this condition.</span>
        </template>

        <UInput
          id="name"
          v-model="form.name"
          type="text"
          placeholder="For the problematic channel or video name."
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-power" class="size-4 text-toned" />
            <span class="font-semibold text-default">Enabled</span>
          </div>
        </template>

        <template #description>
          <span>Whether the condition is enabled.</span>
        </template>

        <div
          class="flex min-h-11 items-center justify-between rounded-md border border-default bg-elevated/40 px-3"
        >
          <span class="text-sm text-default">{{ form.enabled ? 'Yes' : 'No' }}</span>
          <USwitch v-model="form.enabled" :disabled="addInProgress" />
        </div>
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
            <span class="font-semibold text-default">Priority</span>
          </div>
        </template>

        <template #description>
          <span>Higher priority conditions are checked first.</span>
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
    </div>

    <div class="space-y-5 border-t border-default pt-5">
      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-filter" class="size-4 text-toned" />
            <span class="font-semibold text-default">Condition Filter</span>
            <button
              v-if="!addInProgress || form.filter"
              type="button"
              class="text-primary hover:underline"
              @click="testData.show = true"
            >
              Test filter logic
            </button>
          </div>
        </template>
        <template #description>
          <span>
            This filter determines when the condition applies. It uses the same syntax as yt-dlp's
            <code>--match-filters</code> with <code>OR</code> and <code>||</code> support.
          </span>
        </template>

        <UInput
          id="filter"
          v-model="form.filter"
          type="text"
          placeholder="availability = 'needs_auth' & channel_id = 'channel_id'"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>
    </div>

    <div class="space-y-5 border-t border-default pt-5">
      <div class="space-y-1">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-terminal" class="size-4 text-toned" />
          <span>Command options for yt-dlp</span>
        </div>
        <p class="text-sm text-toned">
          <button type="button" class="text-primary hover:underline" @click="showOptions = true">
            View all options
          </button>
          . Not all options are supported;
          <a
            target="_blank"
            rel="noreferrer"
            href="https://github.com/arabcoders/ytptube/blob/master/app/features/ytdlp/utils.py#L29"
            class="text-primary hover:underline"
          >
            some are ignored.
          </a>
        </p>
      </div>

      <UFormField class="w-full" :ui="editorFieldUi">
        <TextareaAutocomplete
          id="cli_options"
          v-model="form.cli"
          :options="ytDlpOpt"
          :disabled="addInProgress"
        />
      </UFormField>
    </div>

    <div class="space-y-5 border-t border-default pt-5">
      <div class="space-y-1">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-list-plus" class="size-4 text-toned" />
          <span>Extra/Custom Options</span>
        </div>
      </div>

      <div v-if="extrasEntries.length > 0" class="space-y-3">
        <div
          v-for="(entry, index) in extrasEntries"
          :key="`${entry[0]}-${index}`"
          class="grid gap-3 rounded-lg border border-default bg-muted/20 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-key" class="size-4 text-toned" />
                <span class="font-semibold text-default">Key</span>
              </div>
            </template>

            <UInput
              :model-value="entry[0]"
              type="text"
              placeholder="key_name"
              size="lg"
              :disabled="addInProgress"
              class="w-full"
              :ui="inputUi"
              @update:model-value="(value) => updateExtraKey(String(value), entry[0])"
            />
          </UFormField>

          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-pen-line" class="size-4 text-toned" />
                <span class="font-semibold text-default">Value</span>
              </div>
            </template>

            <UInput
              :model-value="String(entry[1] ?? '')"
              type="text"
              placeholder="value"
              size="lg"
              :disabled="addInProgress"
              class="w-full"
              :ui="inputUi"
              @update:model-value="(value) => updateExtraValue(entry[0], String(value))"
            />
          </UFormField>

          <div class="flex items-end">
            <UButton
              type="button"
              color="error"
              variant="outline"
              icon="i-lucide-trash"
              :disabled="addInProgress"
              @click="removeExtra(entry[0])"
            >
              Remove
            </UButton>
          </div>
        </div>
      </div>

      <div
        class="grid gap-3 rounded-lg border border-default bg-default p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
      >
        <UFormField :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-key" class="size-4 text-toned" />
              <span class="font-semibold text-default">New key</span>
            </div>
          </template>

          <UInput
            v-model="newExtraKey"
            type="text"
            placeholder="new_key"
            size="lg"
            :disabled="addInProgress"
            class="w-full"
            :ui="inputUi"
            @keyup.enter="addExtra"
          />
        </UFormField>

        <UFormField :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-pen-line" class="size-4 text-toned" />
              <span class="font-semibold text-default">New value</span>
            </div>
          </template>

          <UInput
            v-model="newExtraValue"
            type="text"
            placeholder="new_value"
            size="lg"
            :disabled="addInProgress"
            class="w-full"
            :ui="inputUi"
            @keyup.enter="addExtra"
          />
        </UFormField>

        <div class="flex items-end">
          <UButton
            type="button"
            color="primary"
            icon="i-lucide-plus"
            class="justify-center"
            :disabled="addInProgress || !newExtraKey || !newExtraValue"
            @click="addExtra"
          >
            Add
          </UButton>
        </div>
      </div>

      <div class="rounded-lg border border-info/30 bg-info/10 p-4 text-sm text-default">
        <ul class="list-disc space-y-2 pl-5 text-sm text-default">
          <li>For advanced users only. This feature is meant to be expanded later.</li>
          <li>Keys must be lowercase with underscores (e.g., custom_field).</li>
          <li class="font-semibold text-error">
            You must click on Add to actually add the option.
          </li>
          <li>
            The key <code>ignore_download</code> with value of <code>true</code> will instruct
            <b>YTPTube</b> to ignore the download and directly mark the item as archived. this is
            useful to skip certain kind of downloads.
          </li>
          <li>
            The key <code>set_preset</code> with the name of an existing preset will instruct
            <b>YTPTube</b> to switch the download to use the specified preset. This is useful to
            apply different download settings based on content type or source.
          </li>
        </ul>
      </div>
    </div>

    <div class="space-y-4 border-t border-default pt-5">
      <div class="space-y-1">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-message-square-text" class="size-4 text-toned" />
          <span>Description</span>
        </div>
        <p class="text-sm text-toned">
          Use this field to help understand the purpose of this condition.
        </p>
      </div>

      <UFormField class="w-full" :ui="editorFieldUi">
        <UTextarea
          id="description"
          v-model="form.description"
          :disabled="addInProgress"
          placeholder="Describe what this condition does"
          :rows="6"
          size="lg"
          variant="outline"
          color="neutral"
          class="w-full"
          :ui="textareaUi"
        />
      </UFormField>
    </div>

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

    <UModal
      v-if="testData.show"
      :open="testData.show"
      title="Test condition"
      :dismissible="!testData.in_progress"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="(open) => !open && (testData.show = false)"
    >
      <template #body>
        <form autocomplete="off" class="space-y-5" @submit.prevent="runTest">
          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-link" class="size-4 text-toned" />
                <span class="font-semibold text-default">URL</span>
              </div>
            </template>

            <template #description>
              <span>The url to test the filter against.</span>
            </template>

            <div class="flex flex-col gap-2 sm:flex-row">
              <UInput
                id="test_url"
                v-model="testData.url"
                type="url"
                placeholder="https://..."
                size="lg"
                :disabled="testData.in_progress"
                class="w-full"
                :ui="inputUi"
              />

              <UButton
                type="submit"
                color="primary"
                icon="i-lucide-play"
                size="lg"
                class="justify-center sm:min-w-24"
                :disabled="testData.in_progress"
                :loading="testData.in_progress"
              >
                Test
              </UButton>
            </div>
          </UFormField>

          <UFormField :ui="fieldUi" description="yt-dlp --match-filters logic with OR, || support.">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-filter" class="size-4 text-toned" />
                <span class="font-semibold text-default">Condition Filter</span>
              </div>
            </template>

            <UInput
              id="test_filter"
              v-model="form.filter"
              type="text"
              placeholder="availability = 'needs_auth' & channel_id = 'channel_id'"
              size="lg"
              :disabled="testData.in_progress"
              class="w-full"
              :ui="inputUi"
            />
          </UFormField>

          <UAlert
            :color="logicTest === true ? 'success' : logicTest === false ? 'error' : 'neutral'"
            variant="soft"
            :icon="
              logicTest === true
                ? 'i-lucide-check'
                : logicTest === false
                  ? 'i-lucide-x'
                  : 'i-lucide-circle-help'
            "
            title="Filter Status"
            :description="logicStatusText"
          />

          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-braces" class="size-4 text-toned" />
                <span class="font-semibold text-default">Returned data</span>
              </div>
            </template>

            <pre
              class="max-h-[60vh] overflow-auto rounded-lg border border-default bg-elevated/40 p-4 text-xs text-default"
            ><code>{{ showData() }}</code></pre>
          </UFormField>
        </form>
      </template>
    </UModal>

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

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue';
import { useConfirm } from '~/composables/useConfirm';
import type { ImportedItem } from '~/types';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { Condition, ConditionTestResponse } from '~/types/conditions';
import { match_str } from '~/utils/ytdlp';

const emitter = defineEmits<{
  (e: 'cancel'): void;
  (e: 'submit', payload: { reference: number | null | undefined; item: Condition }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  item: Condition;
  addInProgress?: boolean;
}>();

const toast = useNotification();
const showImport = useStorage('showImport', false);
const box = useConfirm();
const config = useConfigStore();

const form = reactive<Condition>(normalizeCondition(props.item));
const importString = ref('');
const newExtraKey = ref('');
const newExtraValue = ref('');
const testData = ref<{
  show: boolean;
  url: string;
  in_progress: boolean;
  changed: boolean;
  data: ConditionTestResponse | { status: null; condition?: string; data: Record<string, unknown> };
}>({
  show: false,
  url: '',
  in_progress: false,
  changed: false,
  data: { status: null, data: {} },
});
const showOptions = ref(false);
const ytDlpOpt = ref<AutoCompleteOptions>([]);

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
  base: 'min-h-[9rem] w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

watch(
  () => props.item,
  (value) => {
    Object.assign(form, normalizeCondition(value));
  },
  { deep: true },
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
  () => form.filter,
  () => {
    testData.value.changed = true;
  },
);

function normalizeCondition(value?: Partial<Condition> | null): Condition {
  const item = JSON.parse(JSON.stringify(value || {})) as Partial<Condition>;
  const normalized: Partial<Condition> = {
    ...item,
    extras: item.extras ? { ...item.extras } : {},
    enabled: item.enabled ?? true,
    priority: item.priority ?? 0,
    description: item.description ?? '',
  };

  return Object.assign(
    {
      name: '',
      filter: '',
      cli: '',
      extras: {},
      enabled: true,
      priority: 0,
      description: '',
    },
    normalized,
  ) as Condition;
}

const extrasEntries = computed(() => Object.entries(form.extras || {}));

const logicTest = computed(() => {
  if (Object.keys(testData.value.data?.data ?? {}).length < 1) {
    return null;
  }

  if (!testData.value.changed) {
    return testData.value.data.status;
  }

  try {
    return match_str(form.filter, testData.value.data.data);
  } catch {
    return false;
  }
});

const logicStatusText = computed(() => {
  if (testData.value.data.status === null) {
    return 'Not tested';
  }

  return logicTest.value ? 'Matched' : 'Not matched';
});

const checkInfo = async (): Promise<void> => {
  for (const key of ['name', 'filter'] as const) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`);
      return;
    }
  }

  if ((!form.cli || '' === form.cli.trim()) && Object.keys(form.extras).length < 1) {
    toast.error('Command options for yt-dlp or at least one extra option is required.');
    return;
  }

  if (form.cli && '' !== form.cli.trim()) {
    const options = await convertOptions(form.cli);
    if (options === null) {
      return;
    }
    form.cli = form.cli.trim();
  }

  const copy: Condition = JSON.parse(JSON.stringify(form));

  for (const key in copy) {
    if ('string' !== typeof copy[key as keyof Condition]) {
      continue;
    }

    (copy as unknown as Record<string, unknown>)[key] = String(copy[key as keyof Condition]).trim();
  }

  emitter('submit', { reference: toRaw(props.reference), item: toRaw(copy) });
};

const convertOptions = async (args: string): Promise<Record<string, unknown> | null> => {
  try {
    const response = await convertCliOptions(args);
    return response.opts as Record<string, unknown>;
  } catch (error: any) {
    toast.error(error.message);
    return null;
  }
};

const runTest = async (): Promise<void> => {
  if (!testData.value.url) {
    toast.error('The URL is required for testing.', { force: true });
    return;
  }

  try {
    new URL(testData.value.url);
  } catch {
    toast.error('The URL is invalid.', { force: true });
    return;
  }

  testData.value.in_progress = true;
  testData.value.data.status = false;

  try {
    const response = await request('/api/conditions/test', {
      method: 'POST',
      body: JSON.stringify({ url: testData.value.url, condition: form.filter }),
    });

    const json = await response.json();
    if (!response.ok) {
      toast.error(json.message || json.error || 'Unknown error', { force: true });
      return;
    }

    testData.value.data = json as ConditionTestResponse;
    testData.value.changed = false;
  } catch (error: any) {
    toast.error(`Failed to test condition. ${error.message}`);
  } finally {
    testData.value.in_progress = false;
  }
};

const importItem = async (): Promise<void> => {
  const value = importString.value.trim();
  if (!value) {
    toast.error('The import string is required.');
    return;
  }

  try {
    const item = decode(value) as Condition & ImportedItem;

    if (!item._type || item._type !== 'condition') {
      toast.error(
        `Invalid import string. Expected type 'condition', got '${item._type ?? 'unknown'}'.`,
      );
      return;
    }

    if (
      (form.filter || form.cli || Object.keys(form.extras).length > 0) &&
      !(await box.confirm('Overwrite the current form fields?'))
    ) {
      return;
    }

    Object.assign(form, normalizeCondition(item));
    importString.value = '';
    showImport.value = false;
  } catch (error: any) {
    toast.error(`Failed to parse import string. ${error.message}`);
  }
};

const showData = (): string => {
  if (!testData.value.data?.data || Object.keys(testData.value.data.data).length === 0) {
    return 'No data to show.';
  }

  return JSON.stringify(testData.value.data.data, null, 2);
};

const validateKey = (key: string): boolean => /^[a-z][a-z0-9_]*$/.test(key);

const parseValue = (value: string): string | number | boolean => {
  if (!isNaN(Number(value)) && !isNaN(parseFloat(value))) {
    return Number(value);
  }

  if ('true' === value.toLowerCase()) {
    return true;
  }

  if ('false' === value.toLowerCase()) {
    return false;
  }

  return value;
};

const addExtra = (): void => {
  const key = newExtraKey.value.trim();
  const value = newExtraValue.value.trim();

  if (!key || !value) {
    toast.error('Both key and value are required.');
    return;
  }

  if (!validateKey(key)) {
    toast.error('Key must be lower_case.');
    return;
  }

  if (form.extras[key] !== undefined) {
    toast.error(`Key '${key}' already exists.`);
    return;
  }

  form.extras = { ...form.extras, [key]: parseValue(value) };
  newExtraKey.value = '';
  newExtraValue.value = '';
};

const removeExtra = (key: string): void => {
  const { [key]: _, ...rest } = form.extras;
  form.extras = rest;
};

const updateExtraKey = (newKeyValue: string, oldKey: string): void => {
  const newKey = newKeyValue.trim();
  if (!newKey || newKey === oldKey) {
    return;
  }

  if (!validateKey(newKey)) {
    toast.error('Key must be lowercase and contain only letters, numbers, and underscores.');
    return;
  }

  if (form.extras[newKey] !== undefined) {
    toast.error(`Key '${newKey}' already exists.`);
    return;
  }

  const value = form.extras[oldKey];
  const { [oldKey]: _, ...rest } = form.extras;
  form.extras = { ...rest, [newKey]: value };
};

const updateExtraValue = (key: string, rawValue: string): void => {
  form.extras = {
    ...form.extras,
    [key]: rawValue.trim() ? parseValue(rawValue.trim()) : '',
  };
};
</script>
