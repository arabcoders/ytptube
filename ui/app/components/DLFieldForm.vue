<template>
  <form id="dlFieldForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
    <UAlert
      v-if="
        formError &&
        (String(form.name).trim() ||
          String(form.description).trim() ||
          String(form.field).trim() ||
          String(form.icon || '').trim() ||
          form.order !== 1)
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
              class="justify-center sm:min-w-28"
              :disabled="!importString"
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
            <span class="font-semibold text-default">{{ t('common.fieldName') }}</span>
          </div>
        </template>

        <UInput
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
            <UIcon name="i-lucide-message-square-text" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.fieldDescription') }}</span>
          </div>
        </template>

        <UInput
          v-model="form.description"
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
            <UIcon name="i-lucide-shapes" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.fieldType') }}</span>
          </div>
        </template>

        <template #description>
          <span>
            {{ t('common.fieldTypeDesc') }}
          </span>
        </template>

        <USelect
          v-model="form.kind"
          :items="fieldTypeItems"
          size="lg"
          class="w-full"
          :disabled="addInProgress"
          :ui="selectUi"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-terminal" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.associatedYtdlpOption') }}</span>
          </div>
        </template>
        <template #description>
          <span v-html="t('common.associatedYtdlpOptionDesc')" />
        </template>

        <InputAutocomplete
          v-model="form.field"
          :options="ytDlpOptions"
          :disabled="addInProgress"
          :placeholder="t('common.selectYtdlpOption')"
          :multiple="false"
          :openOnFocus="true"
          :preferUp="true"
          dir="ltr"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.fieldOrder') }}</span>
          </div>
        </template>

        <template #description>
          <span>
            {{ t('common.fieldOrderDesc') }}
          </span>
        </template>

        <UInput
          v-model.number="form.order"
          type="number"
          min="1"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-image" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.fieldIcon') }}</span>
          </div>
        </template>
        <template #description>
          <span v-html="t('common.fieldIconDesc')" />
        </template>

        <IconAutocomplete
          id="field_icon"
          v-model="form.icon"
          :options="iconOptions"
          :disabled="addInProgress"
          :placeholder="t('common.fieldIconPlaceholder')"
          :preferUp="true"
        />
      </UFormField>
    </div>
  </form>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import IconAutocomplete from '~/components/IconAutocomplete.vue';
import InputAutocomplete from '~/components/InputAutocomplete.vue';
import { useConfirm } from '~/composables/useConfirm';
import type { ImportedItem } from '~/types';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { DLField } from '~/types/dl_fields';
import { decode } from '~/utils';
import { bundledUiIconNames, isBundledUiIcon } from '~/utils/generatedIconCatalog';

const emitter = defineEmits<{
  (e: 'dirty-change' | 'valid-change', value: boolean): void;
  (e: 'submit', payload: { reference: number | null | undefined; item: DLField }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  item: DLField;
  addInProgress?: boolean;
}>();

const toast = useNotification();
const box = useConfirm();
const config = useYtpConfig();
const { t } = useI18n();

const fieldTypes = ['string', 'text', 'bool'] as const;
const fieldTypeItems = computed(() => [
  { label: t('common.fieldTypeString'), value: 'string' },
  { label: t('common.fieldTypeText'), value: 'text' },
  { label: t('common.fieldTypeBool'), value: 'bool' },
]);
const form = reactive<DLField>(normalizeField(props.item));
const ytDlpOptions = ref<AutoCompleteOptions>([]);
const iconOptions: AutoCompleteOptions = bundledUiIconNames.map((name) => ({
  value: name,
  description: name.replace('i-lucide-', '').replaceAll('-', ' '),
}));
const showImport = useStorage('showDlFieldsImport', false);
const importString = ref('');

const dirtySource = computed(() => ({
  reference: props.reference ?? null,
  form: normalizeField(form),
  importString: importString.value,
  showImport: showImport.value,
}));
const { isDirty, markClean } = useDirtyState(dirtySource);

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

const selectUi = {
  base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

watch(
  () => props.item,
  (value) => {
    Object.assign(form, normalizeField(value));

    importString.value = '';
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
    (ytDlpOptions.value = newOptions
      .filter((opt) => !opt.ignored)
      .flatMap((opt) =>
        opt.flags
          .filter((flag) => flag.startsWith('--'))
          .map((flag) => ({ value: flag, description: opt.description || '' })),
      )),
  { immediate: true },
);

function normalizeField(value?: Partial<DLField> | null): DLField {
  const item = JSON.parse(JSON.stringify(value || {})) as Partial<DLField>;
  const normalized: Partial<DLField> = {
    ...item,
    description: item.description ?? '',
    kind: item.kind ?? 'string',
    value: item.value ?? '',
    icon: item.icon ?? '',
    order: item.order ?? 1,
    extras: item.extras ? { ...item.extras } : {},
  };

  return Object.assign(
    {
      name: '',
      description: '',
      kind: 'string',
      field: '',
      value: '',
      icon: '',
      order: 1,
      extras: {},
    },
    normalized,
  ) as DLField;
}

const formError = computed(() => {
  for (const key of ['name', 'field', 'kind', 'description'] as const) {
    if (!String(form[key]).trim()) {
      return t('common.fieldRequired', { field: key });
    }
  }

  if (!form.order || form.order < 1) {
    return t('common.validationOrderPositive');
  }

  if (!fieldTypes.includes(form.kind)) {
    return t('common.validationInvalidFieldType', { kind: form.kind });
  }

  if (!/^--[a-zA-Z0-9-]+$/.test(form.field)) {
    return t('common.validationInvalidFieldFormat');
  }

  if (form.icon && !isBundledUiIcon(form.icon)) {
    return t('common.validationInvalidIcon');
  }

  return '';
});
watch(formError, (value) => emitter('valid-change', !value), { immediate: true });

const importItem = async (): Promise<void> => {
  const value = importString.value.trim();
  if (!value) {
    toast.error(t('common.validationImportRequired'));
    return;
  }

  try {
    const item = decode(value) as DLField & ImportedItem;

    if (!item._type || item._type !== 'dl_field') {
      toast.error(
        t('common.validationInvalidImport', {
          expected: 'dl_field',
          type: item._type ?? 'unknown',
        }),
      );
      return;
    }

    if (
      (form.name || form.field || form.description) &&
      !(await box.confirm(t('common.overwriteForm')))
    ) {
      return;
    }

    Object.assign(form, normalizeField(item));
    importString.value = '';
    showImport.value = false;
  } catch (error: any) {
    toast.error(t('common.validationImportParseFailed', { error: error.message }));
  }
};

const checkInfo = (): void => {
  if (formError.value) {
    return;
  }

  const copy: DLField = JSON.parse(JSON.stringify(form));
  const entries = copy as Record<string, unknown>;

  for (const key in entries) {
    if ('string' !== typeof entries[key]) {
      continue;
    }

    entries[key] = String(entries[key]).trim();
  }

  emitter('submit', { reference: toRaw(props.reference), item: toRaw(copy) });
};

onMounted(() => {
  markClean();
  emitter('dirty-change', false);
});
</script>
