<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          type="button"
          color="neutral"
          variant="ghost"
          size="sm"
          :icon="showImport ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          :disabled="isBusy"
          @click="showImport = !showImport"
        >
          {{ showImport ? 'Hide import' : 'Show import' }}
        </UButton>

        <div class="inline-flex rounded-md border border-default bg-muted/20 p-1">
          <UButton
            type="button"
            size="sm"
            icon="i-lucide-sliders-horizontal"
            :color="mode === 'gui' ? 'primary' : 'neutral'"
            :variant="mode === 'gui' ? 'solid' : 'ghost'"
            :disabled="!guiSupported || isBusy"
            @click="switchMode('gui')"
          >
            GUI
          </UButton>
          <UButton
            type="button"
            size="sm"
            icon="i-lucide-code"
            :color="mode === 'advanced' ? 'primary' : 'neutral'"
            :variant="mode === 'advanced' ? 'solid' : 'ghost'"
            :disabled="isBusy"
            @click="switchMode('advanced')"
          >
            Advanced
          </UButton>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-2">
        <UButton
          v-if="mode === 'advanced'"
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-wand-sparkles"
          :disabled="isBusy"
          @click="beautify"
        >
          Format
        </UButton>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-x"
          :disabled="submitting"
          @click="cancel"
        >
          Cancel
        </UButton>

        <UButton
          type="button"
          color="primary"
          size="sm"
          icon="i-lucide-save"
          :loading="submitting"
          :disabled="isBusy"
          @click="submit"
        >
          Save
        </UButton>
      </div>
    </div>

    <div
      v-if="showImport"
      class="grid gap-4 rounded-lg border border-default bg-muted/10 p-4 lg:grid-cols-2"
    >
      <UFormField
        v-if="availableDefinitions.length"
        :ui="fieldUi"
        description="Pre-fill from an existing task definition."
      >
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-copy" class="size-4 text-toned" />
            <span class="font-semibold text-default">Import from existing</span>
          </div>
        </template>

        <USelect
          v-model="selectedExistingValue"
          :items="existingDefinitionItems"
          placeholder="Select a definition"
          value-key="value"
          label-key="label"
          class="w-full"
          :ui="inputUi"
          :disabled="isBusy"
          @update:model-value="importExisting"
        />
      </UFormField>

      <UFormField
        :ui="fieldUi"
        description="Paste shared task definition string here to import it."
      >
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-import" class="size-4 text-toned" />
            <span class="font-semibold text-default">Import string</span>
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
          />

          <UButton
            type="button"
            color="primary"
            icon="i-lucide-import"
            class="justify-center sm:min-w-28"
            :disabled="isBusy || !importString.trim()"
            @click="importFromString"
          >
            Import
          </UButton>
        </div>
      </UFormField>
    </div>

    <UAlert
      v-if="loading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      title="Loading"
      description="Loading full definition before editing."
    />

    <UAlert
      v-if="!guiSupported"
      color="warning"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="Advanced mode required"
      description="This task definition uses features that cannot be represented with the visual editor. You can still update it via the advanced view."
    />

    <UAlert
      v-else-if="mode === 'gui'"
      color="info"
      variant="soft"
      icon="i-lucide-info"
      title="GUI limitations"
      :description="guiLimitations"
    />

    <template v-if="mode === 'gui'">
      <div class="grid gap-4 md:grid-cols-12">
        <UFormField
          class="md:col-span-6"
          :ui="fieldUi"
          description="Human readable label for this definition."
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-type" class="size-4 text-toned" />
              <span class="font-semibold text-default">Name</span>
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
          description="Lower values are evaluated first."
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
              <span class="font-semibold text-default">Priority</span>
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

        <UFormField
          class="md:col-span-3"
          :ui="fieldUi"
          description="Disabled definitions won't match tasks."
        >
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-power" class="size-4 text-toned" />
              <span class="font-semibold text-default">Status</span>
            </div>
          </template>

          <div
            class="flex min-h-11 items-center rounded-md border border-default bg-elevated/40 px-3"
          >
            <USwitch v-model="guiState.enabled" :disabled="isBusy" />
            <span class="ml-3 text-sm text-default">{{
              guiState.enabled ? 'Enabled' : 'Disabled'
            }}</span>
          </div>
        </UFormField>

        <UFormField class="md:col-span-12" :ui="fieldUi" description="One glob/regex url per line">
          <template #label>
            <div class="flex flex-wrap items-center gap-2">
              <UIcon name="i-lucide-link" class="size-4 text-toned" />
              <span class="font-semibold text-default">Match patterns</span>
            </div>
          </template>

          <UTextarea
            v-model="guiState.matchText"
            :rows="4"
            placeholder="https://example.com/*&#10;https://example.org/channel/*"
            class="w-full"
            :ui="textareaUi"
            :disabled="isBusy"
          />
        </UFormField>
      </div>

      <div class="grid gap-5 border-t border-default pt-5 lg:grid-cols-2">
        <div class="space-y-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-settings-2" class="size-4 text-toned" />
              <span>Request setup</span>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-2">
            <UFormField
              :ui="fieldUi"
              description="Choose the fetch engine. You should use HTTPX when possible."
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-cpu" class="size-4 text-toned" />
                  <span class="font-semibold text-default">Engine</span>
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
              />
            </UFormField>

            <UFormField :ui="fieldUi" description="HTTP method to use when fetching the page.">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-arrow-right-left" class="size-4 text-toned" />
                  <span class="font-semibold text-default">Request Method</span>
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
              />
            </UFormField>

            <UFormField
              v-if="guiState.engineType === 'selenium'"
              class="md:col-span-2"
              :ui="fieldUi"
              description="Remote webdriver endpoint."
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-server" class="size-4 text-toned" />
                  <span class="font-semibold text-default">Selenium Hub URL (Required)</span>
                </div>
              </template>

              <UInput
                v-model="guiState.engineUrl"
                type="url"
                placeholder="http://selenium:4444/wd/hub"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
              />
            </UFormField>

            <UFormField
              class="md:col-span-2"
              :ui="fieldUi"
              description="Overrides the URL used to fetch the page. Useful for sites with separate feed URLs."
            >
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-link" class="size-4 text-toned" />
                  <span class="font-semibold text-default">Request URL (optional)</span>
                </div>
              </template>

              <UInput
                v-model="guiState.requestUrl"
                type="url"
                placeholder="https://example.com/feed"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
              />
            </UFormField>
          </div>
        </div>

        <div class="space-y-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-list-tree" class="size-4 text-toned" />
              <span>Container selector</span>
            </div>
          </div>

          <div class="grid gap-4 md:grid-cols-12">
            <UFormField class="md:col-span-4" :ui="fieldUi">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-shapes" class="size-4 text-toned" />
                  <span class="font-semibold text-default">Type</span>
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
              />
            </UFormField>

            <UFormField class="md:col-span-8" :ui="fieldUi">
              <template #label>
                <div class="flex flex-wrap items-center gap-2">
                  <UIcon name="i-lucide-crosshair" class="size-4 text-toned" />
                  <span class="font-semibold text-default">Selector / Expression</span>
                </div>
              </template>

              <UInput
                v-model="guiState.containerSelector"
                type="text"
                placeholder="div.card"
                class="w-full"
                :ui="inputUi"
                :disabled="isBusy"
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
              <span>Extracted fields</span>
            </div>
          </div>

          <UButton
            type="button"
            color="primary"
            size="sm"
            icon="i-lucide-plus"
            :disabled="isBusy"
            @click="addField"
          >
            Add field
          </UButton>
        </div>

        <div
          class="w-full min-w-0 max-w-full overflow-hidden rounded-lg border border-default bg-default"
        >
          <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
            <table class="min-w-215 table-fixed w-full text-sm">
              <thead class="bg-muted/40 text-xs uppercase tracking-wide text-toned">
                <tr class="text-left [&>th]:px-3 [&>th]:py-3 [&>th]:font-semibold">
                  <th class="w-40">
                    <span class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-key" class="size-3.5 text-toned" />
                      <span>Key</span>
                    </span>
                  </th>
                  <th class="w-36">
                    <span class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-shapes" class="size-3.5 text-toned" />
                      <span>Type</span>
                    </span>
                  </th>
                  <th class="w-auto">
                    <span class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-code" class="size-3.5 text-toned" />
                      <span>Expression</span>
                    </span>
                  </th>
                  <th class="w-44">
                    <span class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-at-sign" class="size-3.5 text-toned" />
                      <span>Attribute</span>
                    </span>
                  </th>
                  <th class="w-20">
                    <span class="inline-flex items-center gap-1.5">
                      <UIcon name="i-lucide-trash-2" class="size-3.5 text-toned" />
                      <span>Action</span>
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-default">
                <tr v-if="!guiState.fields.length">
                  <td colspan="5" class="px-3 py-6 text-center text-sm text-toned">
                    No extractor fields configured.
                  </td>
                </tr>
                <tr
                  v-for="(field, index) in guiState.fields"
                  :key="`${index}-${field.key}`"
                  class="align-top"
                >
                  <td class="px-3 py-3">
                    <UInput
                      v-model="field.key"
                      type="text"
                      class="w-full"
                      :ui="inputUi"
                      :disabled="isBusy"
                    />
                  </td>
                  <td class="px-3 py-3">
                    <USelect
                      v-model="field.type"
                      :items="fieldTypeItems"
                      value-key="value"
                      label-key="label"
                      class="w-full"
                      :ui="inputUi"
                      :disabled="isBusy"
                    />
                  </td>
                  <td class="px-3 py-3">
                    <UInput
                      v-model="field.expression"
                      type="text"
                      class="w-full"
                      :ui="inputUi"
                      :disabled="isBusy"
                    />
                  </td>
                  <td class="px-3 py-3">
                    <UInput
                      v-model="field.attribute"
                      type="text"
                      placeholder="Optional"
                      class="w-full"
                      :ui="inputUi"
                      :disabled="isBusy"
                    />
                  </td>
                  <td class="px-3 py-3 text-right">
                    <UButton
                      type="button"
                      color="error"
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
      </div>

      <UAlert
        v-if="guiError"
        color="error"
        variant="soft"
        icon="i-lucide-circle-alert"
        title="Unable to build definition"
        :description="guiError"
      />
    </template>

    <template v-else>
      <UFormField :ui="fieldUi" description="Edit the full task definition JSON directly.">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-file-code-2" class="size-4 text-toned" />
            <span class="font-semibold text-default">Raw JSON definition</span>
          </div>
        </template>

        <UTextarea
          v-model="jsonText"
          :rows="22"
          spellcheck="false"
          :readonly="submitting"
          class="w-full font-mono text-sm"
          :ui="advancedTextareaUi"
        />
      </UFormField>

      <UAlert
        v-if="errorMessage"
        color="error"
        variant="soft"
        icon="i-lucide-circle-alert"
        title="Invalid JSON"
        :description="errorMessage"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import { prettyName, decode } from '~/utils';
import type { TaskDefinitionDocument, TaskDefinitionSummary } from '~/types/task_definitions';

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
  (e: 'cancel'): void;
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

const guiLimitations =
  'Only a single container selector and per-field extractors are exposed. More advanced constructs require raw view mode.';

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
    throw new Error('Name is required.');
  }

  const matches = splitMatches(state.matchText);
  if (!matches.length) {
    throw new Error('At least one match pattern is required.');
  }

  if (!state.containerSelector.trim()) {
    throw new Error('Container selector is required.');
  }

  const formattedFields: Record<string, Record<string, string>> = {};
  state.fields.forEach((field) => {
    if (!field.key.trim()) {
      return;
    }

    if (!field.expression.trim()) {
      throw new Error(`Expression is required for field "${field.key}".`);
    }

    formattedFields[field.key.trim()] = {
      type: field.type || 'css',
      expression: field.expression,
      ...(field.attribute ? { attribute: field.attribute } : {}),
    };
  });

  if (!Object.keys(formattedFields).length) {
    throw new Error('Configure at least one extractor field.');
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
    throw new Error('Import payload is not a task definition object.');
  }

  const record = payload as Record<string, unknown>;
  if ('_type' in record && record._type !== undefined && record._type !== 'task_definition') {
    throw new Error('Import string is not a task definition export.');
  }

  const version = record._version as string | undefined;
  if (!['1.0', '2.0'].includes(version ?? '')) {
    throw new Error(
      `Unsupported or missing _version field. Expected "1.0" or "2.0", got: ${version ?? 'undefined'}`,
    );
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
      throw new Error('Definition cannot be empty.');
    }

    const parsed = JSON.parse(jsonText.value) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('Definition must be a JSON object.');
    }

    errorMessage.value = null;
    return parsed as TaskDefinitionDocument;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Invalid JSON document.';
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
    errorMessage.value = 'Failed to prepare definition for editing.';
  }
};

const importFromString = (): void => {
  if (isBusy.value) {
    return;
  }

  if (!importString.value.trim()) {
    guiError.value = 'Import string cannot be empty.';
    return;
  }

  try {
    const decoded = decode(importString.value.trim());
    const document = parseImportedDocument(decoded);
    applyDocument(document);
    importString.value = '';
    showImport.value = false;
  } catch (error) {
    guiError.value = error instanceof Error ? error.message : 'Unable to import definition.';
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
      guiError.value = error instanceof Error ? error.message : 'Failed to serialize GUI changes.';
      return;
    }
  }

  mode.value = next;
};

const submit = (): void => {
  if (isBusy.value) {
    return;
  }

  if (mode.value === 'gui') {
    try {
      const doc = fromGui(guiState);
      emit('submit', doc);
      guiError.value = null;
    } catch (error) {
      guiError.value = error instanceof Error ? error.message : 'Unable to build definition.';
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

const cancel = (): void => {
  if (submitting.value) {
    return;
  }

  emit('cancel');
};

defineExpose({ submit, beautify });
</script>
