<template>
  <div class="space-y-6">
    <UAlert
      v-if="validationError && hasEditorContent"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="validationError"
      class="sticky top-0 z-10 shadow-sm"
    />

    <div class="flex flex-wrap items-center gap-2">
      <UButton
        type="button"
        color="neutral"
        variant="ghost"
        size="sm"
        :icon="showImport ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        :disabled="isBusy"
        @click="
          () => {
            showImport = !showImport;
          }
        "
      >
        {{ showImport ? t('common.hideImport') : t('common.showImport') }}
      </UButton>
    </div>

    <div
      v-if="showImport"
      class="grid gap-4 rounded-lg border border-default bg-muted/10 p-4 lg:grid-cols-2"
    >
      <UFormField
        v-if="availableDefinitions.length"
        :ui="fieldUi"
        :description="t('common.prefillFromDef')"
      >
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-copy" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.importFromExisting') }}</span>
          </div>
        </template>

        <USelectMenu
          v-model="selectedExistingValue"
          :items="existingDefinitionItems"
          :placeholder="t('common.selectDefinition')"
          value-key="value"
          label-key="label"
          color="neutral"
          class="w-full"
          :ui="{ content: 'min-w-[13rem]', item: 'ps-6' }"
          :search-input="{ placeholder: t('common.searchPresets') }"
          :disabled="isBusy"
          @update:model-value="importExisting"
        />
      </UFormField>

      <UFormField :ui="fieldUi" :description="t('common.importStringDesc')">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-import" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.importString') }}</span>
          </div>
        </template>

        <div class="flex flex-col gap-2 sm:flex-row">
          <UInput
            v-model="importString"
            type="text"
            autocomplete="off"
            class="w-full"
            :ui="inputUi"
            :disabled="isBusy"
            dir="ltr"
          />

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            icon="i-lucide-import"
            class="justify-center sm:min-w-28"
            :disabled="isBusy || !importString.trim()"
            @click="importFromString"
          >
            {{ t('common.import') }}
          </UButton>
        </div>
      </UFormField>
    </div>

    <UAlert
      v-if="loading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('common.loadingData')"
    />

    <UAlert
      v-if="!guiSupported"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('common.advancedModeRequired')"
      :description="t('common.advancedModeRequiredDesc')"
    />

    <UAlert
      v-else-if="mode === 'gui'"
      color="info"
      variant="soft"
      icon="i-lucide-info"
      :title="t('common.guiLimitations')"
      :description="guiLimitations"
    />

    <template v-if="mode === 'gui'">
      <div class="grid gap-4 md:grid-cols-12">
        <UFormField
          class="md:col-span-6"
          :ui="fieldUi"
          :description="t('common.definitionNameDesc')"
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-type" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.name') }}</span>
            </div>
          </template>

          <UInput
            v-model="guiState.name"
            type="text"
            class="w-full"
            :ui="inputUi"
            :disabled="isBusy"
          />
        </UFormField>

        <UFormField
          class="md:col-span-3"
          :ui="fieldUi"
          :description="t('common.definitionPriorityDesc')"
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.priority') }}</span>
            </div>
          </template>

          <UInput
            v-model.number="guiState.priority"
            type="number"
            min="0"
            class="w-full"
            :ui="inputUi"
            :disabled="isBusy"
          />
        </UFormField>

        <UFormField class="md:col-span-3" :ui="fieldUi">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-power" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.status') }}</span>
            </div>
          </template>
          <template #description>
            <span>&nbsp;</span>
          </template>

          <div
            class="flex min-h-11 items-center rounded-md border border-default bg-elevated/40 px-3"
          >
            <USwitch v-model="guiState.enabled" :disabled="isBusy" />
            <span class="ms-3 text-sm text-default">{{
              guiState.enabled ? t('common.enabled') : t('common.disabled')
            }}</span>
          </div>
        </UFormField>

        <UFormField
          class="md:col-span-12"
          :ui="fieldUi"
          :description="t('common.matchPatternsDesc')"
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-link" class="size-4 text-toned" />
              <span class="font-semibold text-default">{{ t('common.matchPatterns') }}</span>
            </div>
          </template>

          <UTextarea
            v-model="guiState.matchText"
            :rows="4"
            placeholder="https://example.com/*&#10;https://example.org/channel/*"
            class="w-full"
            :ui="textareaUi"
            :disabled="isBusy"
            dir="ltr"
          />
        </UFormField>
      </div>

      <div class="grid gap-5 border-t border-default pt-5 lg:grid-cols-2">
        <div class="space-y-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-settings-2" class="size-4 text-toned" />
              <span>{{ t('common.requestSetup') }}</span>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <UFormField :ui="fieldUi" :description="t('common.engineDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-cpu" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.engine') }}</span>
                </div>
              </template>

              <USelect
                v-model="guiState.engineType"
                :items="engineItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField :ui="fieldUi" :description="t('common.requestMethodDesc')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-arrow-right-left" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.requestMethod') }}</span>
                </div>
              </template>

              <USelect
                v-model="guiState.requestMethod"
                :items="requestMethodItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField
              v-if="guiState.engineType === 'selenium'"
              class="md:col-span-2"
              :ui="fieldUi"
              :description="t('common.seleniumHubUrlDesc')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-server" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.seleniumHubUrl') }}</span>
                </div>
              </template>

              <UInput
                v-model="guiState.engineUrl"
                type="url"
                placeholder="http://selenium:4444/wd/hub"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField
              class="md:col-span-2"
              :ui="fieldUi"
              :description="t('common.requestUrlDesc')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-link" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.requestUrl') }}</span>
                </div>
              </template>

              <UInput
                v-model="guiState.requestUrl"
                type="url"
                placeholder="https://example.com/feed"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>
          </div>
        </div>

        <div class="space-y-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-list-tree" class="size-4 text-toned" />
              <span>{{ t('common.containerSelector') }}</span>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-12">
            <UFormField class="md:col-span-4" :ui="fieldUi" :description="t('common.selectorType')">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-shapes" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{ t('common.type') }}</span>
                </div>
              </template>

              <USelect
                v-model="guiState.containerType"
                :items="containerTypeItems"
                value-key="value"
                label-key="label"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>

            <UFormField
              class="md:col-span-8"
              :ui="fieldUi"
              :description="t('common.matchExpression')"
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-crosshair" class="size-4 text-toned" />
                  <span class="font-semibold text-default">{{
                    t('common.selectorExpression')
                  }}</span>
                </div>
              </template>

              <UInput
                v-model="guiState.containerSelector"
                type="text"
                placeholder="div.card"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
                dir="ltr"
              />
            </UFormField>
          </div>
        </div>
      </div>

      <div class="space-y-4 border-t border-default pt-5">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-braces" class="size-4 text-toned" />
              <span>{{ t('common.extractedFields') }}</span>
            </div>
          </div>

          <UButton
            type="button"
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-plus"
            :disabled="isBusy"
            @click="addField"
          >
            {{ t('common.addField') }}
          </UButton>
        </div>

        <div class="w-full min-w-0 overflow-x-auto overscroll-x-contain ytp-table-surface">
          <table class="table-fixed w-full text-sm" dir="ltr">
            <thead class="bg-elevated/60 text-xs uppercase tracking-wide text-toned">
              <tr
                class="text-start [&>th]:border-e [&>th]:border-default/60 [&>th]:px-2 [&>th]:py-2.5 [&>th]:font-semibold [&>th:last-child]:border-e-0"
              >
                <th class="w-28">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-key" class="size-3.5 text-toned" />
                    <span>{{ t('common.keyLabel') }}</span>
                  </span>
                </th>
                <th class="w-28">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-shapes" class="size-3.5 text-toned" />
                    <span>{{ t('common.fieldType') }}</span>
                  </span>
                </th>
                <th class="w-auto">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-code" class="size-3.5 text-toned" />
                    <span>{{ t('common.fieldExpression') }}</span>
                  </span>
                </th>
                <th class="w-28">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-at-sign" class="size-3.5 text-toned" />
                    <span>{{ t('common.fieldAttribute') }}</span>
                  </span>
                </th>
                <th class="w-12">
                  <span class="inline-flex items-center gap-1.5">
                    <UIcon name="i-lucide-trash-2" class="size-3.5 text-toned" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-default">
              <tr v-if="!guiState.fields.length">
                <td colspan="5" class="px-2 py-6 text-center text-sm text-toned">
                  {{ t('common.noExtractorFields') }}
                </td>
              </tr>
              <tr
                v-for="(field, index) in guiState.fields"
                :key="`${index}-${field.key}`"
                class="align-top [&>td]:border-e [&>td]:border-default/60 [&>td:last-child]:border-e-0"
              >
                <td class="px-2 py-2">
                  <UInput
                    v-model="field.key"
                    type="text"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <USelect
                    v-model="field.type"
                    :items="fieldTypeItems"
                    value-key="value"
                    label-key="label"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <UInput
                    v-model="field.expression"
                    type="text"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2">
                  <UInput
                    v-model="field.attribute"
                    type="text"
                    :placeholder="t('common.optional')"
                    class="w-full"
                    :ui="inputUi"
                    :disabled="isBusy"
                    dir="ltr"
                  />
                </td>
                <td class="px-2 py-2 text-end">
                  <UButton
                    type="button"
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-trash"
                    square
                    :disabled="isBusy"
                    @click="removeField(index)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <UAlert
        v-if="guiError"
        color="error"
        variant="soft"
        icon="i-lucide-circle-alert"
        :title="t('common.unableToBuildDef')"
        :description="guiError"
      />
    </template>

    <template v-else>
      <UFormField :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-file-code-2" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.rawJson') }}</span>
          </div>
        </template>

        <UTextarea
          v-model="jsonText"
          :rows="22"
          spellcheck="false"
          :readonly="submitting"
          class="w-full font-mono text-sm"
          :ui="advancedTextareaUi"
          dir="ltr"
        />
      </UFormField>

      <UAlert
        v-if="errorMessage"
        color="error"
        variant="soft"
        icon="i-lucide-circle-alert"
        :title="t('common.invalidJson')"
        :description="errorMessage"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import { prettyName, decode } from '~/utils';
import type { TaskDefinitionDocument, TaskDefinitionSummary } from '~/types/task_definitions';

const { t } = useI18n();

type EditorMode = 'gui' | 'advanced';

type GuiField = {
  key: string;
  type: string;
  expression: string;
  attribute: string;
};

type GuiState = {
  name: string;
  priority: number;
  enabled: boolean;
  matchText: string;
  engineType: 'httpx' | 'selenium';
  engineUrl: string;
  requestMethod: string;
  requestUrl: string;
  containerType: 'css' | 'xpath' | 'jsonpath';
  containerSelector: string;
  fields: GuiField[];
};

const props = defineProps<{
  title?: string;
  document: TaskDefinitionDocument | null;
  loading?: boolean;
  submitting?: boolean;
  availableDefinitions?: readonly TaskDefinitionSummary[];
  initialShowImport?: boolean;
}>();

const emit = defineEmits<{
  (e: 'submit', payload: TaskDefinitionDocument): void;
  (e: 'dirty-change' | 'valid-change', value: boolean): void;
  (e: 'import-existing', id: number): void;
}>();

const jsonText = ref('');
const errorMessage = ref<string | null>(null);
const guiError = ref<string | null>(null);
const guiSupported = ref(true);
const mode = ref<EditorMode>('gui');
const showImport = ref(false);
const importString = ref('');
const selectedExisting = ref<number | null>(null);
const selectedExistingValue = computed<number | undefined>({
  get: () => selectedExisting.value ?? undefined,
  set: (value) => {
    selectedExisting.value = value ?? null;
  },
});

const availableDefinitions = computed(() => props.availableDefinitions ?? []);

const guiState = reactive<GuiState>({
  name: '',
  priority: 0,
  enabled: true,
  matchText: '',
  engineType: 'httpx',
  engineUrl: '',
  requestMethod: 'GET',
  requestUrl: '',
  containerType: 'css',
  containerSelector: '',
  fields: [],
});

const loading = computed(() => props.loading ?? false);
const submitting = computed(() => props.submitting ?? false);
const isBusy = computed(() => loading.value || submitting.value);
const advancedMode = computed(() => mode.value === 'advanced');

const guiLimitations = computed(() => t('common.editorInfo'));

const fieldUi = {
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
  base: 'min-h-[8rem] w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const advancedTextareaUi = {
  root: 'w-full',
  base: 'min-h-[24rem] w-full bg-elevated/60 font-mono text-sm ring-default focus-visible:ring-primary',
};

const engineItems = [
  { label: 'HTTPX', value: 'httpx' },
  { label: 'Selenium', value: 'selenium' },
];

const requestMethodItems = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
];

const containerTypeItems = [
  { label: 'CSS', value: 'css' },
  { label: 'XPath', value: 'xpath' },
  { label: 'JSONPath', value: 'jsonpath' },
];

const fieldTypeItems = [
  { label: 'CSS', value: 'css' },
  { label: 'XPath', value: 'xpath' },
  { label: 'Regex', value: 'regex' },
  { label: 'JSONPath', value: 'jsonpath' },
];

const existingDefinitionItems = computed(() => {
  return availableDefinitions.value.map((item) => ({
    label: prettyName(item.name || String(item.id)),
    value: item.id,
  }));
});

const dirtySource = computed(() => ({
  mode: mode.value,
  showImport: showImport.value,
  importString: importString.value,
  selectedExisting: selectedExisting.value,
  jsonText: jsonText.value,
  guiState: JSON.parse(JSON.stringify(guiState)),
}));
const { isDirty, markClean } = useDirtyState(dirtySource);

const resetGuiState = (state: GuiState): void => {
  guiState.name = state.name;
  guiState.priority = state.priority;
  guiState.enabled = state.enabled;
  guiState.matchText = state.matchText;
  guiState.engineType = state.engineType;
  guiState.engineUrl = state.engineUrl;
  guiState.requestMethod = state.requestMethod;
  guiState.requestUrl = state.requestUrl;
  guiState.containerType = state.containerType;
  guiState.containerSelector = state.containerSelector;
  guiState.fields = state.fields.map((field) => ({ ...field }));
};

const defaultField = (): GuiField => ({ key: '', type: 'css', expression: '', attribute: '' });

const addField = (): void => {
  guiState.fields.push(defaultField());
};

const removeField = (index: number): void => {
  guiState.fields.splice(index, 1);
};

const splitMatches = (text: string): string[] => {
  return text
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
};

const toGui = (document: TaskDefinitionDocument): GuiState | null => {
  if (!document || Array.isArray(document) || typeof document !== 'object') {
    return null;
  }

  const entry = document;
  const match = entry.match_url;
  if (!Array.isArray(match) || match.some((item) => typeof item !== 'string')) {
    return null;
  }

  const definition = entry.definition;
  if (!definition || Array.isArray(definition) || typeof definition !== 'object') {
    return null;
  }

  const parse = definition.parse;
  if (!parse || Array.isArray(parse) || typeof parse !== 'object') {
    return null;
  }

  const parseRecord = parse as Record<string, unknown>;
  const items = parseRecord.items;
  if (!items || Array.isArray(items) || typeof items !== 'object') {
    return null;
  }

  const itemRecord = items as Record<string, unknown>;
  const fields = itemRecord.fields;
  if (!fields || Array.isArray(fields) || typeof fields !== 'object') {
    return null;
  }

  const fieldRecord = fields as Record<string, unknown>;
  const guiFields: GuiField[] = [];
  for (const [key, value] of Object.entries(fieldRecord)) {
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      return null;
    }

    const rule = value as Record<string, unknown>;
    if (typeof rule.type !== 'string' || typeof rule.expression !== 'string') {
      return null;
    }

    if (
      Object.keys(rule).some(
        (prop) => !['type', 'expression', 'attribute', 'post_filter'].includes(prop),
      )
    ) {
      return null;
    }

    guiFields.push({
      key,
      type: String(rule.type),
      expression: String(rule.expression),
      attribute: typeof rule.attribute === 'string' ? String(rule.attribute) : '',
    });
  }

  const engine = definition.engine as Record<string, unknown> | undefined;
  const engineType = engine?.type === 'selenium' ? 'selenium' : 'httpx';
  const engineUrl =
    typeof engine?.options === 'string' && engineType === 'selenium'
      ? ''
      : ((engine?.options as Record<string, unknown> | undefined)?.url as string | undefined);

  if (engineUrl && engineType === 'selenium' && typeof engineUrl !== 'string') {
    return null;
  }

  const request = definition.request as Record<string, unknown> | undefined;
  const selectorType = String(itemRecord.type ?? 'css') as GuiState['containerType'];
  const selectorSource = (itemRecord.selector ?? itemRecord.expression) as string | undefined;
  if (!selectorSource || typeof selectorSource !== 'string') {
    return null;
  }

  return {
    name: typeof entry.name === 'string' ? entry.name : '',
    priority: Number(entry.priority ?? 0) || 0,
    enabled: typeof entry.enabled === 'boolean' ? entry.enabled : true,
    matchText: match.join('\n'),
    engineType,
    engineUrl: engineType === 'selenium' ? String(engineUrl ?? '') : '',
    requestMethod: typeof request?.method === 'string' ? String(request.method) : 'GET',
    requestUrl: typeof request?.url === 'string' ? String(request.url) : '',
    containerType: selectorType,
    containerSelector: selectorSource,
    fields: guiFields.length ? guiFields : [defaultField()],
  };
};

const fromGui = (state: GuiState): TaskDefinitionDocument => {
  if (!state.name.trim()) {
    throw new Error(t('common.validationNameRequired'));
  }

  const matches = splitMatches(state.matchText);
  if (!matches.length) {
    throw new Error(t('common.validationMatchRequired'));
  }

  if (!state.containerSelector.trim()) {
    throw new Error(t('common.validationSelectorRequired'));
  }

  const formattedFields: Record<string, Record<string, string>> = {};
  state.fields.forEach((field) => {
    if (!field.key.trim()) {
      return;
    }

    if (!field.expression.trim()) {
      throw new Error(t('common.validationExpressionRequired', { key: field.key }));
    }

    formattedFields[field.key.trim()] = {
      type: field.type || 'css',
      expression: field.expression,
      ...(field.attribute ? { attribute: field.attribute } : {}),
    };
  });

  if (!Object.keys(formattedFields).length) {
    throw new Error(t('common.validationFieldsRequired'));
  }

  const definition: Record<string, unknown> = {
    parse: {
      items: {
        type: state.containerType,
        selector: state.containerType === 'jsonpath' ? undefined : state.containerSelector,
        expression: state.containerType === 'jsonpath' ? state.containerSelector : undefined,
        fields: formattedFields,
      },
    },
  };

  if (state.engineType !== 'httpx' || state.engineUrl) {
    definition.engine = {
      type: state.engineType,
      ...(state.engineType === 'selenium' && state.engineUrl
        ? { options: { url: state.engineUrl } }
        : {}),
    };
  }

  const request: Record<string, string> = {};
  if (state.requestMethod && state.requestMethod !== 'GET') {
    request.method = state.requestMethod;
  }
  if (state.requestUrl) {
    request.url = state.requestUrl;
  }
  if (Object.keys(request).length) {
    definition.request = request;
  }

  return {
    name: state.name.trim(),
    priority: Number(state.priority) || 0,
    enabled: state.enabled,
    match_url: matches,
    definition: definition as unknown as TaskDefinitionDocument['definition'],
  };
};

const hasEditorContent = computed(() => {
  if (mode.value === 'advanced') {
    return Boolean(jsonText.value.trim());
  }

  return Boolean(
    guiState.name.trim() ||
    guiState.matchText.trim() ||
    guiState.containerSelector.trim() ||
    guiState.engineUrl.trim() ||
    guiState.requestUrl.trim() ||
    guiState.fields.some((field) => field.key.trim() || field.expression.trim()),
  );
});

const validationError = computed(() => {
  if (mode.value === 'gui') {
    try {
      fromGui(guiState);
      return '';
    } catch (error) {
      return error instanceof Error ? error.message : t('common.unableToBuildDef');
    }
  }

  if (!jsonText.value.trim()) {
    return t('common.validationDefinitionEmpty');
  }

  try {
    const parsed = JSON.parse(jsonText.value) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      return t('common.validationDefinitionObject');
    }
  } catch (error) {
    return error instanceof Error ? error.message : t('common.invalidJsonDocument');
  }

  return '';
});
watch(
  validationError,
  (value) => {
    emit('valid-change', !value);
    if (!value) {
      if (mode.value === 'gui') {
        guiError.value = null;
      } else {
        errorMessage.value = null;
      }
    }
  },
  { immediate: true },
);

const normalizeRequestConfig = (request: any): any => {
  if (!request || typeof request !== 'object') {
    return request;
  }

  if ('json' in request) {
    const normalized = { ...request };
    normalized.json_data = normalized.json;
    delete normalized.json;
    return normalized;
  }

  return request;
};

const parseImportedDocument = (payload: unknown): TaskDefinitionDocument => {
  if (!payload || Array.isArray(payload) || typeof payload !== 'object') {
    throw new Error(t('common.validationImportPayload'));
  }

  const record = payload as Record<string, unknown>;
  if ('_type' in record && record._type !== undefined && record._type !== 'task_definition') {
    throw new Error(t('common.invalidImportDefinition'));
  }

  const version = record._version as string | undefined;
  if (!['1.0', '2.0'].includes(version ?? '')) {
    throw new Error(t('common.unsupportedVersion'));
  }

  let base: TaskDefinitionDocument;

  if (version === '1.0') {
    const oldDef = record.definition as Record<string, unknown>;
    const oldMatch = Array.isArray(oldDef.match) ? oldDef.match : [];
    const normalizedMatch: string[] = [];

    for (const item of oldMatch) {
      if (typeof item === 'string') {
        normalizedMatch.push(item);
      } else if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>;
        if (typeof obj.regex === 'string') {
          normalizedMatch.push(`/${obj.regex}/`);
        } else if (typeof obj.glob === 'string') {
          normalizedMatch.push(obj.glob);
        }
      }
    }

    base = {
      name:
        typeof oldDef.name === 'string'
          ? oldDef.name
          : typeof record.name === 'string'
            ? record.name
            : '',
      priority: Number(oldDef.priority ?? record.priority ?? 0) || 0,
      enabled: true,
      match_url: normalizedMatch,
      definition: {
        parse: oldDef.parse as any,
        engine: oldDef.engine as any,
        request: normalizeRequestConfig(oldDef.request),
        response: oldDef.response as any,
      },
    };
  } else {
    base = record as unknown as TaskDefinitionDocument;
  }

  return JSON.parse(JSON.stringify(base)) as TaskDefinitionDocument;
};

const parseDocument = (): TaskDefinitionDocument | null => {
  try {
    if (!jsonText.value.trim()) {
      throw new Error(t('common.validationDefinitionEmpty'));
    }

    const parsed = JSON.parse(jsonText.value) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error(t('common.validationDefinitionObject'));
    }

    errorMessage.value = null;
    return parsed as TaskDefinitionDocument;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t('common.invalidJsonDocument');
    return null;
  }
};

const applyDocument = (document: TaskDefinitionDocument | null): void => {
  const shouldShowImport = props.initialShowImport ?? !document;
  showImport.value = shouldShowImport;
  importString.value = '';
  selectedExisting.value = null;
  guiError.value = null;
  errorMessage.value = null;

  if (!document) {
    jsonText.value = '';
    guiSupported.value = true;
    resetGuiState({
      name: '',
      priority: 0,
      enabled: true,
      matchText: '',
      engineType: 'httpx',
      engineUrl: '',
      requestMethod: 'GET',
      requestUrl: '',
      containerType: 'css',
      containerSelector: '',
      fields: [defaultField()],
    });
    nextTick(() => {
      markClean();
      emit('dirty-change', false);
      emit('valid-change', !validationError.value);
    });
    return;
  }

  try {
    jsonText.value = JSON.stringify(document, null, 2);
    const gui = toGui(document);
    if (gui) {
      guiSupported.value = true;
      resetGuiState(gui);
      if (mode.value !== 'gui') {
        mode.value = 'gui';
      }
    } else {
      guiSupported.value = false;
      mode.value = 'advanced';
    }
  } catch (error) {
    console.error('Failed to prepare definition for editing.', error);
    jsonText.value = '';
    guiSupported.value = false;
    mode.value = 'advanced';
    errorMessage.value = t('common.failedPrepareDefinition');
  }

  nextTick(() => {
    markClean();
    emit('dirty-change', false);
    emit('valid-change', !validationError.value);
  });
};

const importFromString = (): void => {
  if (isBusy.value) {
    return;
  }

  if (!importString.value.trim()) {
    guiError.value = t('common.importStringEmpty');
    return;
  }

  try {
    const decoded = decode(importString.value.trim());
    const document = parseImportedDocument(decoded);
    applyDocument(document);
    importString.value = '';
    showImport.value = false;
  } catch (error) {
    guiError.value = error instanceof Error ? error.message : t('common.unableToImportDefinition');
  }
};

const importExisting = (): void => {
  if (!selectedExisting.value || isBusy.value) {
    return;
  }

  emit('import-existing', Number(selectedExisting.value));
  selectedExisting.value = null;
};

watch(
  () => props.document,
  (doc) => applyDocument(doc),
  { immediate: true },
);

watch(isDirty, (value: boolean) => emit('dirty-change', value));

const switchMode = (next: EditorMode): void => {
  if (isBusy.value || next === mode.value) {
    return;
  }

  if (next === 'gui') {
    if (!guiSupported.value) {
      return;
    }

    const parsed = parseDocument();
    if (!parsed) {
      return;
    }

    const gui = toGui(parsed);
    if (!gui) {
      guiSupported.value = false;
      return;
    }

    resetGuiState(gui);
    guiSupported.value = true;
  }

  if (next === 'advanced') {
    try {
      const doc = fromGui(guiState);
      jsonText.value = JSON.stringify(doc, null, 2);
      errorMessage.value = null;
      guiError.value = null;
    } catch (error) {
      guiError.value = error instanceof Error ? error.message : t('common.failedSerializeGui');
      return;
    }
  }

  mode.value = next;
};

const submit = (): void => {
  if (isBusy.value || validationError.value) {
    return;
  }

  if (mode.value === 'gui') {
    try {
      const doc = fromGui(guiState);
      emit('submit', doc);
      guiError.value = null;
    } catch (error) {
      guiError.value = error instanceof Error ? error.message : t('common.unableToBuildDef');
    }
    return;
  }

  const parsed = parseDocument();
  if (!parsed) {
    return;
  }

  emit('submit', parsed);
};

const beautify = (): void => {
  if (mode.value !== 'advanced') {
    return;
  }

  const parsed = parseDocument();
  if (!parsed) {
    return;
  }

  jsonText.value = JSON.stringify(parsed, null, 2);
  errorMessage.value = null;
};

defineExpose({
  submit,
  beautify,
  switchMode,
  advancedMode,
  guiSupported,
  isBusy,
  mode,
  submitting,
});
</script>
