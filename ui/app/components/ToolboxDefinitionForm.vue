<template>
  <form id="toolboxDefinitionForm" autocomplete="off" class="space-y-4" @submit.prevent="submit">
    <FormSubmitError
      v-if="action.message.value"
      :message="action.message.value"
      @dismiss="action.clear"
    />

    <details v-if="!definition" open class="ytp-card-padded-lg">
      <summary class="w-fit cursor-pointer text-sm font-semibold text-highlighted">
        {{ t('common.import') }}
      </summary>
      <div class="mt-4 grid gap-4 sm:grid-cols-2">
        <UFormField class="min-w-0" :label="t('common.importFromExisting')">
          <USelectMenu
            v-model="selected"
            :items="importItems"
            :placeholder="t('common.selectDefinition')"
            value-key="value"
            label-key="label"
            color="neutral"
            size="lg"
            class="w-full"
            :ui="{ content: 'min-w-[13rem]', item: 'ps-6' }"
            :search-input="{ placeholder: t('common.search') }"
            :loading="loadingOptions || importingExisting"
            :disabled="busy || loadingOptions"
            @update:model-value="importExisting"
          />
        </UFormField>

        <UFormField
          class="min-w-0"
          :label="t('common.importString')"
          :help="t('common.importStringDesc')"
        >
          <UFieldGroup size="lg" class="w-full">
            <UInput
              v-model="importString"
              type="text"
              dir="ltr"
              autocomplete="off"
              class="w-full min-w-0 flex-1"
              :disabled="busy"
              @keydown.enter.prevent="importItem"
            />
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-import"
              class="justify-center"
              :loading="importingString"
              :disabled="!importString.trim() || busy"
              @click="importItem"
            >
              {{ t('common.import') }}
            </UButton>
          </UFieldGroup>
        </UFormField>
      </div>
    </details>

    <div class="ytp-card-padded-lg grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
      <UFormField class="w-full" :label="t('common.name')" :error="errors.name" required>
        <UInput v-model="form.name" size="lg" :disabled="busy" class="w-full" />
      </UFormField>
      <UFormField
        class="w-full"
        :label="t('toolbox.outputExtension')"
        :error="errors.output_extension"
        required
      >
        <UInput
          v-model="form.output_extension"
          dir="ltr"
          placeholder=".mp4"
          size="lg"
          :disabled="busy"
          class="w-full"
        />
      </UFormField>
      <UFormField
        class="w-full sm:col-span-2"
        :label="t('common.description')"
        :error="errors.description"
      >
        <UTextarea
          v-model="form.description"
          :rows="3"
          size="lg"
          variant="outline"
          color="neutral"
          :disabled="busy"
          class="w-full"
        />
      </UFormField>
      <USwitch
        v-model="form.supports_overwrite"
        :label="t('toolbox.allowOverwrite')"
        :disabled="busy"
        class="sm:col-span-2"
      />
    </div>

    <div class="ytp-card-padded-lg space-y-4">
      <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
        <UIcon name="i-lucide-terminal" class="size-4 text-toned" />
        <span>{{ t('api.fields.command') }}</span>
      </div>
      <UFormField class="w-full" :label="t('toolbox.executable')" :error="errors.command" required>
        <template #hint>
          <NuxtLink
            to="/docs/toolbox"
            target="_blank"
            class="font-medium text-primary hover:underline"
          >
            {{ t('common.help') }}
          </NuxtLink>
        </template>
        <UInput
          v-model="form.executable"
          placeholder="ffmpeg"
          dir="ltr"
          size="lg"
          :disabled="busy"
          class="w-full"
        />
      </UFormField>

      <div class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
            <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
            <span>{{ t('api.fields.args') }}</span>
          </div>
          <UButton
            type="button"
            color="neutral"
            variant="outline"
            size="sm"
            icon="i-lucide-plus"
            :aria-label="`${t('common.add')}: ${t('api.fields.args')}`"
            :disabled="busy"
            @click="form.args.push('')"
          >
            {{ t('common.add') }}
          </UButton>
        </div>
        <div
          v-for="(_arg, index) in form.args"
          :key="index"
          class="ytp-form-group grid gap-2 p-3 md:grid-cols-[minmax(0,1fr)_auto]"
        >
          <UTextarea
            v-model="form.args[index]"
            :rows="1"
            :aria-label="`${t('api.fields.args')} ${index + 1}`"
            :disabled="busy"
            class="w-full"
            dir="ltr"
          />
          <div class="flex items-start gap-2">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-arrow-up"
              :aria-label="`${t('common.goUp')}: ${index + 1}`"
              :disabled="busy || index === 0"
              @click="moveArgument(index, -1)"
            />
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-arrow-down"
              :aria-label="`${t('common.goDown')}: ${index + 1}`"
              :disabled="busy || index === form.args.length - 1"
              @click="moveArgument(index, 1)"
            />
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-trash"
              :aria-label="`${t('common.remove')}: ${t('api.fields.args')} ${index + 1}`"
              :disabled="busy"
              @click="form.args.splice(index, 1)"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="ytp-card-padded-lg space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-key-round" class="size-4 text-toned" />
          <span>{{ t('toolbox.environment') }}</span>
        </div>
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          :aria-label="`${t('common.add')}: ${t('toolbox.environment')}`"
          :disabled="busy"
          @click="form.env.push({ key: '', value: '' })"
        >
          {{ t('common.add') }}
        </UButton>
      </div>
      <div
        v-for="(pair, index) in form.env"
        :key="index"
        class="ytp-form-group grid gap-2 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
      >
        <UFormField
          :label="t('common.keyLabel')"
          :error="duplicateError(`env.${index}.key`, t('common.keyLabel'))"
          required
        >
          <UInput v-model="pair.key" :disabled="busy" class="w-full" dir="ltr" />
        </UFormField>
        <UFormField :label="t('common.valueLabel')">
          <UTextarea v-model="pair.value" :rows="1" :disabled="busy" class="w-full" dir="ltr" />
        </UFormField>
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          icon="i-lucide-trash"
          :aria-label="t('common.remove')"
          :disabled="busy"
          class="self-end"
          @click="form.env.splice(index, 1)"
        />
      </div>
    </div>

    <div class="ytp-card-padded-lg space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-list-plus" class="size-4 text-toned" />
          <span>{{ t('toolbox.parameters') }}</span>
        </div>
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          :aria-label="`${t('common.add')}: ${t('toolbox.parameters')}`"
          :disabled="busy"
          @click="form.params.push(newToolboxParam())"
        >
          {{ t('common.add') }}
        </UButton>
      </div>

      <div
        v-for="(param, index) in form.params"
        :key="index"
        class="ytp-form-group grid gap-2 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
      >
        <UFormField
          :label="t('common.name')"
          :error="duplicateError(`params.${index}.name`, t('common.name'))"
          required
        >
          <UInput v-model="param.name" :disabled="busy" class="w-full" dir="ltr" />
        </UFormField>
        <UFormField :label="t('common.type')">
          <USelect v-model="param.kind" :items="paramKinds" :disabled="busy" class="w-full" />
        </UFormField>
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          icon="i-lucide-trash"
          :aria-label="t('common.remove')"
          :disabled="busy"
          class="self-end"
          @click="form.params.splice(index, 1)"
        />

        <USwitch
          v-if="param.kind === 'boolean'"
          v-model="param.checked"
          :label="t('common.defaultSource')"
          :disabled="busy"
          class="md:col-span-3"
        />
        <div v-else-if="param.kind === 'number'" class="grid gap-2 md:col-span-3 md:grid-cols-3">
          <UFormField :label="t('common.defaultSource')" required>
            <UInput
              v-model.number.optional="param.number"
              type="number"
              step="any"
              :disabled="busy"
              class="w-full"
              dir="ltr"
            />
          </UFormField>
          <UFormField :label="t('toolbox.minimum')">
            <UInput
              v-model.number.optional="param.min"
              type="number"
              step="any"
              :placeholder="t('common.optional')"
              :disabled="busy"
              class="w-full"
              dir="ltr"
            />
          </UFormField>
          <UFormField :label="t('toolbox.maximum')">
            <UInput
              v-model.number.optional="param.max"
              type="number"
              step="any"
              :placeholder="t('common.optional')"
              :disabled="busy"
              class="w-full"
              dir="ltr"
            />
          </UFormField>
        </div>
        <div v-else class="space-y-3 md:col-span-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon name="i-lucide-list" class="size-4 text-toned" />
              <span>{{ t('toolbox.choices') }}</span>
            </div>
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-plus"
              :aria-label="`${t('common.add')}: ${t('toolbox.choices')}`"
              :disabled="busy"
              @click="param.choices.push('')"
            >
              {{ t('common.add') }}
            </UButton>
          </div>
          <div
            v-for="(_choice, choiceIndex) in param.choices"
            :key="choiceIndex"
            class="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]"
          >
            <UTextarea
              v-model="param.choices[choiceIndex]"
              :rows="1"
              :placeholder="t('common.valueLabel')"
              :aria-label="`${t('common.valueLabel')} ${choiceIndex + 1}`"
              :disabled="busy"
              class="w-full"
              dir="ltr"
            />
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-trash"
              :aria-label="t('common.remove')"
              :disabled="busy"
              class="self-start"
              @click="removeChoice(param, choiceIndex)"
            />
          </div>
          <UFormField :label="t('common.defaultSource')" required>
            <USelect
              v-model="param.choice"
              :items="choiceItems(param.choices)"
              :placeholder="t('common.selectOption')"
              :disabled="busy || !param.choices.length"
              class="w-full"
            />
          </UFormField>
        </div>
      </div>
    </div>
  </form>
</template>

<script setup lang="ts">
import type { SelectMenuItem } from '@nuxt/ui';
import type {
  ToolboxDefinition,
  ToolboxDefinitionPayload,
  ToolboxDefinitionSummary,
} from '~/types/toolbox';
import {
  buildToolboxDefinition,
  importToolboxDefinition,
  makeToolboxDraft,
  newToolboxParam,
} from '~/utils/toolboxDefinitions';

const props = defineProps<{
  definition: ToolboxDefinition | null;
  submitting: boolean;
  errors: Record<string, string>;
}>();
const emit = defineEmits<{
  'dirty-change': [dirty: boolean];
  'valid-change': [valid: boolean];
  submit: [definition: ToolboxDefinitionPayload];
}>();
const { t } = useI18n();
const { confirmDialog } = useDialog();
const { get, listForImport } = useToolboxDefinitions();
const action = useFormSubmit();
const form = ref(makeToolboxDraft(props.definition));
const initial = JSON.stringify(form.value);
const importString = ref('');
const selected = ref<number>();
const options = ref<ToolboxDefinitionSummary[]>([]);
const loadingOptions = ref(false);
const importingExisting = ref(false);
const importingString = ref(false);
const busy = computed(() => props.submitting || importingExisting.value || importingString.value);
const changed = computed(() => JSON.stringify(form.value) !== initial);
const dirty = computed(() => changed.value || Boolean(importString.value));
const parsed = computed(() => buildToolboxDefinition(form.value));
const valid = computed(() => Boolean(parsed.value.value) && !busy.value);
const duplicateError = (field: string, label: string): string | undefined => {
  const duplicate = parsed.value.duplicate;
  return duplicate?.field === field
    ? t('errors.ALREADY_EXISTS', { resource: duplicate.key || label })
    : undefined;
};
const paramKinds = computed(() => [
  { label: t('common.valueBoolean'), value: 'boolean' as const },
  { label: t('common.valueNumber'), value: 'number' as const },
  { label: t('toolbox.choices'), value: 'choices' as const },
]);
const choiceItems = (choices: string[]) =>
  choices.map((label, value) => ({ label: label || '""', value }));
const importItems = computed<SelectMenuItem[][]>(() => {
  const custom: SelectMenuItem[] = [];
  const defaults: SelectMenuItem[] = [{ type: 'label', label: t('common.defaultSource') }];
  for (const item of options.value) {
    (item.default ? defaults : custom).push({ value: item.id, label: item.name });
  }
  return [custom, defaults.length > 1 ? defaults : []].filter((group) => group.length);
});
watch(dirty, (value) => emit('dirty-change', value), { immediate: true });
watch(valid, (value) => emit('valid-change', value), { immediate: true });

const moveArgument = (index: number, offset: number): void => {
  const args = form.value.args;
  const next = index + offset;
  const arg = args[index];
  const other = args[next];
  if (arg === undefined || other === undefined) return;
  args[index] = other;
  args[next] = arg;
};

const removeChoice = (param: ReturnType<typeof newToolboxParam>, index: number): void => {
  param.choices.splice(index, 1);
  if (param.choice === index) param.choice = undefined;
  else if (param.choice !== undefined && param.choice > index) param.choice--;
};

const confirmOverwrite = async (): Promise<boolean> => {
  if (!changed.value) return true;
  const { status } = await confirmDialog({
    title: t('common.overwriteForm'),
    message: t('common.overwriteFormDesc'),
    confirmText: t('common.overwrite'),
    confirmColor: 'warning',
  });
  return status === true;
};

const importItem = async (): Promise<void> => {
  if (!importString.value.trim() || props.definition || busy.value) return;
  action.clear();
  const value = importToolboxDefinition(importString.value);
  if (!value) {
    action.setError(new Error(t('common.unableToImportDefinition')));
    return;
  }
  importingString.value = true;
  try {
    if (!(await confirmOverwrite())) return;
    form.value = makeToolboxDraft(value);
    importString.value = '';
  } finally {
    importingString.value = false;
  }
};

const importExisting = async (id?: number): Promise<void> => {
  if (id === undefined || props.definition || busy.value) return;
  action.clear();
  importingExisting.value = true;
  try {
    if (!(await confirmOverwrite())) return;
    const value = await action.run(() => get(id));
    if (!value) return;
    form.value = { ...makeToolboxDraft(value), name: form.value.name };
  } finally {
    selected.value = undefined;
    importingExisting.value = false;
  }
};

const submit = (): void => {
  const value = parsed.value.value;
  if (valid.value && value) emit('submit', value);
};

onMounted(async () => {
  if (props.definition) return;
  loadingOptions.value = true;
  try {
    options.value = (await action.run(listForImport)) ?? [];
  } finally {
    loadingOptions.value = false;
  }
});
</script>
