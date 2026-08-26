<template>
  <form id="conditionForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
    <FormSubmitError :message="action.message.value" @dismiss="action.clear" />
    <UAlert
      v-if="
        formError &&
        (String(form.name).trim() ||
          String(form.filter).trim() ||
          String(form.cli).trim() ||
          String(form.description).trim() ||
          Object.keys(form.extras).length ||
          form.priority !== 0 ||
          !form.enabled ||
          newExtraValue.trim())
      "
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="formError"
      class="sticky top-0 z-10 shadow-sm"
    />

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
        <UFormField class="w-full md:col-span-2" :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-import" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.importString') }}</span>
            </div>
          </template>

          <template #description>
            <span>{{ t('common.importStringDesc') }}</span>
          </template>

          <UFieldGroup size="lg" class="w-full">
            <UInput
              id="import_string"
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
              class="justify-center sm:min-w-28"
              :loading="importInProgress"
              :disabled="!importString || importInProgress"
              @click="() => void importItem()"
            >
              {{ t('common.import') }}
            </UButton>
          </UFieldGroup>
        </UFormField>
      </template>

      <UFormField class="w-full md:col-span-2" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-type" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.name') }}</span>
          </div>
        </template>

        <UInput
          id="name"
          v-model="form.name"
          type="text"
          :placeholder="t('common.conditionNamePlaceholder')"
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
            <span class="font-semibold text-default">{{ t('common.enabled') }}</span>
          </div>
        </template>

        <div
          class="flex min-h-11 items-center justify-between rounded-md border border-default bg-elevated/40 px-3"
        >
          <span class="text-sm text-default">{{
            form.enabled ? t('common.yesLabel') : t('common.noLabel')
          }}</span>
          <USwitch v-model="form.enabled" :disabled="addInProgress" />
        </div>
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.priority') }}</span>
          </div>
        </template>

        <UInput
          id="priority"
          v-model.number="form.priority"
          type="number"
          min="0"
          :placeholder="t('conditions.priorityPlaceholder')"
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
            <span class="font-semibold text-default">{{ t('common.conditionFilter') }}</span>
            <button
              v-if="!addInProgress || form.filter"
              type="button"
              class="text-primary hover:underline"
              @click="testData.show = true"
            >
              {{ t('common.testFilter') }}
            </button>
          </div>
        </template>
        <template #description>
          <span v-html="t('common.filterSyntaxDesc')"></span>
        </template>

        <UInput
          id="filter"
          dir="ltr"
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
          <span>{{ t('common.cliOptions') }}</span>
        </div>
        <p class="text-sm text-toned">
          <button type="button" class="text-primary hover:underline" @click="showOptions = true">
            {{ t('common.cliOptionsViewAll') }}
          </button>
          {{ t('common.cliOptionsDescPrefix') }}
          <a
            target="_blank"
            rel="noreferrer"
            href="https://github.com/arabcoders/ytptube/blob/master/app/features/ytdlp/utils.py#L29"
            class="text-primary hover:underline"
          >
            {{ t('common.cliOptionsDescIgnored') }}</a
          >.
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
          <span>{{ t('common.extraOptions') }}</span>
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
                <span class="font-semibold text-default">{{ t('common.keyLabel') }}</span>
              </div>
            </template>

            <USelect
              :model-value="entry[0]"
              :items="extraOptionItems"
              value-key="value"
              size="lg"
              disabled
              class="w-full"
              :ui="inputUi"
            />
          </UFormField>

          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-pen-line" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.valueLabel') }}</span>
              </div>
            </template>

            <div
              v-if="booleanExtraKeys.includes(entry[0])"
              class="flex h-10 items-center justify-between rounded-md border border-default bg-elevated/40 px-3"
            >
              <span class="text-sm text-default">{{
                entry[1] === true ? t('common.yesLabel') : t('common.noLabel')
              }}</span>
              <USwitch
                :model-value="entry[1] === true"
                :disabled="addInProgress"
                @update:model-value="(value) => updateExtraValue(entry[0], Boolean(value))"
              />
            </div>
            <UTextarea
              v-else-if="entry[0] === 'set_cookies'"
              :model-value="String(entry[1] ?? '')"
              placeholder="value"
              :disabled="addInProgress"
              class="w-full"
              :ui="textareaUi"
              dir="ltr"
              :rows="8"
              @update:model-value="(value) => updateExtraValue(entry[0], String(value))"
            />
            <UInput
              v-else
              :model-value="String(entry[1] ?? '')"
              type="text"
              placeholder="value"
              size="lg"
              :disabled="addInProgress"
              class="w-full"
              dir="ltr"
              :ui="inputUi"
              @update:model-value="(value) => updateExtraValue(entry[0], String(value))"
            />
          </UFormField>

          <div class="flex items-end">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-trash"
              :disabled="addInProgress"
              @click="removeExtra(entry[0])"
            >
              {{ t('common.remove') }}
            </UButton>
          </div>
        </div>
      </div>

      <div class="grid gap-3 ytp-card-padded md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <UFormField :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-key" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.newKey') }}</span>
            </div>
          </template>

          <USelect
            v-model="newExtraKey"
            :items="extraOptionItems.filter((item) => form.extras[item.value] === undefined)"
            value-key="value"
            :placeholder="t('common.selectOption')"
            size="lg"
            :disabled="addInProgress"
            class="w-full"
            :ui="inputUi"
            @update:model-value="(value) => selectNewExtra(String(value))"
          />
        </UFormField>

        <UFormField :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-pen-line" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.newValue') }}</span>
            </div>
          </template>

          <div
            v-if="booleanExtraKeys.includes(newExtraKey)"
            class="flex h-10 items-center justify-between rounded-md border border-default bg-elevated/40 px-3"
          >
            <span class="text-sm text-default">{{
              newExtraValue === 'true' ? t('common.yesLabel') : t('common.noLabel')
            }}</span>
            <USwitch
              :model-value="newExtraValue === 'true'"
              :disabled="addInProgress"
              @update:model-value="(value) => (newExtraValue = String(Boolean(value)))"
            />
          </div>
          <UTextarea
            v-else-if="newExtraKey.trim() === 'set_cookies'"
            v-model="newExtraValue"
            placeholder="value"
            :disabled="addInProgress"
            class="w-full"
            :ui="textareaUi"
            dir="ltr"
            :rows="8"
          />
          <UInput
            v-else
            v-model="newExtraValue"
            type="text"
            placeholder="new_value"
            size="lg"
            :disabled="addInProgress"
            class="w-full"
            :ui="inputUi"
            dir="ltr"
            @keyup.enter="addExtra"
          />
        </UFormField>

        <div class="flex items-end gap-2">
          <UButton
            v-if="newExtraKey"
            type="button"
            color="neutral"
            variant="outline"
            icon="i-lucide-rotate-ccw"
            class="justify-center"
            :disabled="addInProgress"
            @click="
              () => {
                newExtraKey = '';
                newExtraValue = '';
              }
            "
          >
            {{ t('common.reset') }}
          </UButton>

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            icon="i-lucide-plus"
            class="justify-center"
            :disabled="addInProgress || !newExtraKey || !newExtraValue"
            @click="addExtra"
          >
            {{ t('common.add') }}
          </UButton>
        </div>
      </div>
    </div>

    <div class="space-y-4 border-t border-default pt-5">
      <div class="space-y-1">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-message-square-text" class="size-4 text-toned" />
          <span>{{ t('common.description') }}</span>
        </div>
      </div>

      <UFormField class="w-full" :ui="editorFieldUi">
        <UTextarea
          id="description"
          v-model="form.description"
          :disabled="addInProgress"
          :placeholder="t('common.conditionDescPlaceholder')"
          :rows="6"
          size="lg"
          variant="outline"
          color="neutral"
          class="w-full"
          :ui="textareaUi"
        />
      </UFormField>
    </div>

    <UModal
      v-if="testData.show"
      :open="testData.show"
      :title="t('common.testCondition')"
      :dismissible="!testData.in_progress"
      :ui="{ content: 'w-full sm:max-w-5xl', body: 'max-h-[85vh] overflow-y-auto p-4 sm:p-6' }"
      @update:open="handleTestOpen"
    >
      <template #body>
        <form id="conditionTestForm" autocomplete="off" class="space-y-5" @submit.prevent="runTest">
          <FormSubmitError :message="testAction.message.value" @dismiss="testAction.clear" />
          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-link" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.url') }}</span>
              </div>
            </template>

            <template #description>
              <span>{{ t('common.testUrlDesc') }}</span>
            </template>

            <UInput
              id="test_url"
              dir="ltr"
              v-model="testData.url"
              type="url"
              placeholder="https://..."
              size="lg"
              :disabled="testData.in_progress"
              class="w-full"
              :ui="inputUi"
            />
          </UFormField>

          <UFormField :ui="fieldUi" :description="t('common.testFilterDesc')">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-filter" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.conditionFilter') }}</span>
              </div>
            </template>

            <UInput
              id="test_filter"
              dir="ltr"
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
            :title="t('common.filterStatus')"
            :description="
              testData.data.status === null
                ? t('common.notTested')
                : logicTest
                  ? t('common.matched')
                  : t('common.notMatched')
            "
          />

          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-braces" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.returnedData') }}</span>
              </div>
            </template>

            <pre
              class="max-h-[60vh] overflow-auto rounded-lg border border-default bg-elevated/40 p-4 text-xs text-default"
              dir="ltr"
            ><code>{{ showData() }}</code></pre>
          </UFormField>
        </form>
      </template>

      <template #footer>
        <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <UButton
            type="submit"
            form="conditionTestForm"
            color="primary"
            icon="i-lucide-play"
            class="justify-center"
            :disabled="testData.in_progress"
            :loading="testData.in_progress"
          >
            {{ t('common.test') }}
          </UButton>
        </div>
      </template>
    </UModal>

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
import { useConfirm } from '~/composables/useConfirm';
import type { ImportedItem } from '~/types';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { Condition, ConditionTestResponse } from '~/types/conditions';
import { match_str } from '~/utils/ytdlp';

const { t } = useI18n();

const emitter = defineEmits<{
  (e: 'dirty-change' | 'valid-change', value: boolean): void;
  (e: 'submit', payload: { reference: number | null | undefined; item: Condition }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  item: Condition;
  addInProgress?: boolean;
}>();

const showImport = useStorage('showImport', false);
const box = useConfirm();
const config = useYtpConfig();

const form = reactive<Condition>(normalizeCondition(props.item));
const action = useFormSubmit();
const testAction = useFormSubmit();
const importString = ref('');
const importInProgress = ref(false);
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

const dirtySource = computed(() => ({
  reference: props.reference ?? null,
  form: normalizeCondition(form),
  importString: importString.value,
  showImport: showImport.value,
  newExtraKey: newExtraKey.value,
  newExtraValue: newExtraValue.value,
}));
const { isDirty, markClean } = useDirtyState(dirtySource);

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
    action.clear();
    testAction.clear();
    Object.assign(form, normalizeCondition(value));

    importString.value = '';
    newExtraKey.value = '';
    newExtraValue.value = '';
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
const booleanExtraKeys = ['ignore_download', 'no_archive'];
const extraOptionItems = computed(() => [
  {
    label: 'ignore_download',
    value: 'ignore_download',
    description: t('common.conditionExtraIgnoreDownload'),
  },
  {
    label: 'no_archive',
    value: 'no_archive',
    description: t('common.conditionExtraNoArchive'),
  },
  {
    label: 'set_preset',
    value: 'set_preset',
    description: t('common.conditionExtraSetPreset'),
  },
  {
    label: 'set_cookies',
    value: 'set_cookies',
    description: t('common.conditionExtraSetCookies'),
  },
]);
const formError = computed(() => {
  if (!newExtraKey.value.trim() && newExtraValue.value.trim()) {
    return t('common.bothKeyValueRequired');
  }

  if (newExtraKey.value.trim() && newExtraValue.value.trim()) {
    return t('common.conditionActionNotAdded');
  }

  if (!String(form.name).trim()) {
    return t('common.fieldRequired', { field: t('common.name') });
  }

  if (!String(form.filter).trim()) {
    return t('common.fieldRequired', { field: t('common.conditionFilter') });
  }

  if (!Number.isInteger(form.priority) || form.priority < 0) {
    return t('common.validationNonNegativeInteger', { field: t('common.priority') });
  }

  if (!String(form.cli).trim() && Object.keys(form.extras).length < 1) {
    return t('common.optionsOrExtraRequired');
  }

  return '';
});
watch(formError, (value) => emitter('valid-change', !value), { immediate: true });

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

const checkInfo = async (): Promise<void> => {
  action.clear();
  if (formError.value) {
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
  } catch (error) {
    action.setError(error);
    return null;
  }
};

const runTest = async (): Promise<void> => {
  testAction.clear();
  if (!testData.value.url) {
    testAction.setError(new Error(t('common.urlRequiredForTest')));
    return;
  }

  try {
    new URL(testData.value.url);
  } catch {
    testAction.setError(new Error(t('common.invalidUrl')));
    return;
  }

  testData.value.in_progress = true;
  testData.value.data.status = false;

  try {
    const response = await request('/api/conditions/test', {
      method: 'POST',
      body: JSON.stringify({ url: testData.value.url, condition: form.filter }),
    });

    await ensure_api_success(response);
    const json = await response.json();

    testData.value.data = json as ConditionTestResponse;
    testData.value.changed = false;
  } catch (error) {
    testAction.setError(error);
  } finally {
    testData.value.in_progress = false;
  }
};

const handleTestOpen = (open: boolean): void => {
  testData.value.show = open;
  if (!open) {
    testAction.clear();
  }
};

const importItem = async (): Promise<void> => {
  if (importInProgress.value) {
    return;
  }

  action.clear();
  const value = importString.value.trim();
  if (!value) {
    action.setError(new Error(t('common.validationImportRequired')));
    return;
  }

  importInProgress.value = true;
  try {
    const item = decode(value) as Condition & ImportedItem;

    if (!item._type || item._type !== 'condition') {
      action.setError(
        new Error(
          t('common.validationInvalidImport', {
            expected: 'condition',
            type: item._type ?? 'unknown',
          }),
        ),
      );
      return;
    }

    if (
      (form.filter || form.cli || Object.keys(form.extras).length > 0) &&
      !(await box.confirm(t('common.overwriteFormDesc')))
    ) {
      return;
    }

    Object.assign(form, normalizeCondition(item));
    importString.value = '';
    showImport.value = false;
    action.clear();
  } catch (error) {
    action.setError(
      new Error(
        t('common.validationImportParseFailed', {
          error: error instanceof Error ? error.message : t('common.unknownError'),
        }),
      ),
    );
  } finally {
    importInProgress.value = false;
  }
};

const showData = (): string => {
  if (!testData.value.data?.data || Object.keys(testData.value.data.data).length === 0) {
    return t('common.noDataToShow');
  }

  return JSON.stringify(testData.value.data.data, null, 2);
};

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
  const value = newExtraValue.value;

  if (!key || !value.trim()) {
    action.setError(new Error(t('common.bothKeyValueRequired')));
    return;
  }

  if (form.extras[key] !== undefined) {
    action.setError(new Error(t('common.keyAlreadyExists', { key })));
    return;
  }

  form.extras = { ...form.extras, [key]: key === 'set_cookies' ? value : parseValue(value.trim()) };
  action.clear();
  newExtraKey.value = '';
  newExtraValue.value = '';
};

const selectNewExtra = (key: string): void => {
  newExtraKey.value = key;
  newExtraValue.value = booleanExtraKeys.includes(key) ? 'true' : '';
};

const removeExtra = (key: string): void => {
  const { [key]: _, ...rest } = form.extras;
  form.extras = rest;
};

const updateExtraValue = (key: string, rawValue: string | boolean): void => {
  form.extras = {
    ...form.extras,
    [key]:
      typeof rawValue === 'boolean'
        ? rawValue
        : key === 'set_cookies'
          ? rawValue
          : rawValue.trim()
            ? parseValue(rawValue.trim())
            : '',
  };
};

onMounted(() => {
  markClean();
  emitter('dirty-change', false);
});
</script>
