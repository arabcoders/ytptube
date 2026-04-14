<template>
  <form id="dlFieldForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
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
              color="neutral"
              variant="outline"
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

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-type" class="size-4 text-toned" />
            <span class="font-semibold text-default">Field Name</span>
          </div>
        </template>

        <template #description>
          <span>The name of the field, it will be shown in the UI.</span>
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
            <span class="font-semibold text-default">Field Description</span>
          </div>
        </template>

        <template #description>
          <span>A short description of the field, it will be shown in the UI.</span>
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
            <span class="font-semibold text-default">Field Type</span>
          </div>
        </template>

        <template #description>
          <span>
            Field Type. String is a single line, Text is a multi-line, Bool is a checkbox.
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
            <span class="font-semibold text-default">Associated yt-dlp option</span>
          </div>
        </template>
        <template #description>
          <span>
            The long form of yt-dlp option name, e.g. <code>--no-overwrites</code> not
            <code>-w</code>.
          </span>
        </template>

        <InputAutocomplete
          v-model="form.field"
          :options="ytDlpOptions"
          :disabled="addInProgress"
          placeholder="Type or select a yt-dlp option"
          :multiple="false"
          :openOnFocus="true"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-list-ordered" class="size-4 text-toned" />
            <span class="font-semibold text-default">Field Order</span>
          </div>
        </template>

        <template #description>
          <span>
            The order of the field, used to sort the fields in the UI. Lower numbers will appear
            first.
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
            <span class="font-semibold text-default">Field Icon</span>
          </div>
        </template>
        <template #description>
          <span>
            The icon of the field must use a
            <a
              href="https://icones.js.org/collection/lucide"
              target="_blank"
              rel="noreferrer"
              class="text-primary hover:underline"
            >
              Lucide icon
            </a>
            name in the <code>i-lucide-*</code> format, e.g. <code>i-lucide-image</code>. Leave
            empty for no icon.
          </span>
        </template>

        <UInput
          v-model="form.icon"
          type="text"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
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
  </form>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import InputAutocomplete from '~/components/InputAutocomplete.vue';
import { useConfirm } from '~/composables/useConfirm';
import type { ImportedItem } from '~/types';
import type { AutoCompleteOptions } from '~/types/autocomplete';
import type { DLField } from '~/types/dl_fields';
import { decode } from '~/utils';

const emitter = defineEmits<{
  (e: 'cancel'): void;
  (e: 'submit', payload: { reference: number | null | undefined; item: DLField }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  item: DLField;
  addInProgress?: boolean;
}>();

const toast = useNotification();
const box = useConfirm();
const config = useConfigStore();

const fieldTypes = ['string', 'text', 'bool'] as const;
const fieldTypeItems = [...fieldTypes];
const form = reactive<DLField>(normalizeField(props.item));
const ytDlpOptions = ref<AutoCompleteOptions>([]);
const showImport = useStorage('showDlFieldsImport', false);
const importString = ref('');

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
  },
  { deep: true },
);

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

const importItem = async (): Promise<void> => {
  const value = importString.value.trim();
  if (!value) {
    toast.error('The import string is required.');
    return;
  }

  try {
    const item = decode(value) as DLField & ImportedItem;

    if (!item._type || item._type !== 'dl_field') {
      toast.error(
        `Invalid import string. Expected type 'dl_field', got '${item._type ?? 'unknown'}'.`,
      );
      return;
    }

    if (
      (form.name || form.field || form.description) &&
      !(await box.confirm('Overwrite the current form fields?'))
    ) {
      return;
    }

    Object.assign(form, normalizeField(item));
    importString.value = '';
    showImport.value = false;
  } catch (error: any) {
    toast.error(`Failed to parse import string. ${error.message}`);
  }
};

const checkInfo = (): void => {
  for (const key of ['name', 'field', 'kind', 'description'] as const) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`);
      return;
    }
  }

  if (!form.order || form.order < 1) {
    toast.error('Order must be a positive number.');
    return;
  }

  if (!fieldTypes.includes(form.kind)) {
    toast.error(`Invalid field type: ${form.kind}`);
    return;
  }

  if (!/^--[a-zA-Z0-9-]+$/.test(form.field)) {
    toast.error('Invalid field format, it must start with "--" and contain no spaces.');
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
</script>
