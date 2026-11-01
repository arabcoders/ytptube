<template>
  <div v-if="'bool' === type && compact && !required && !error" class="w-full space-y-1.5">
    <div
      class="flex min-h-11 items-start justify-between gap-3 rounded-md border border-default bg-elevated/20 px-3 py-2"
    >
      <div class="min-w-0 flex-1">
        <div class="inline-flex min-w-0 items-center gap-2 text-sm font-semibold text-default">
          <UIcon v-if="iconName" :name="iconName" class="size-4 shrink-0 text-toned" />
          <UTooltip :text="field ? t('common.ytdlpOption', { field }) : undefined">
            <span class="truncate" :class="{ 'has-tooltip': field }">
              {{ label }}
            </span>
          </UTooltip>
        </div>

        <div v-if="$slots.description" class="mt-0.5 text-xs text-toned">
          <slot name="description" />
        </div>

        <p v-else-if="description" class="mt-0.5 text-xs text-toned">
          {{ description }}
        </p>
      </div>

      <USwitch
        :id="`dlf-${id}`"
        v-model="boolModel"
        :disabled="disabled"
        color="success"
        :aria-label="label"
        size="lg"
        class="shrink-0"
        :ui="{ root: 'items-center gap-2', wrapper: 'ms-0 text-sm' }"
      />
    </div>

    <div v-if="$slots.help" class="text-xs text-toned">
      <slot name="help" />
    </div>
  </div>

  <UFormField
    v-else
    :name="String(id)"
    :description="$slots.description ? undefined : description"
    :required="required"
    :error="error"
    class="w-full"
    :ui="fieldUi"
  >
    <template #label>
      <template v-if="$slots.title">
        <slot name="title" />
      </template>
      <template v-else>
        <span class="inline-flex items-center gap-2 font-semibold">
          <UIcon v-if="iconName" :name="iconName" class="size-4 text-toned" />
          <UTooltip :text="field ? t('common.ytdlpOption', { field }) : undefined">
            <span :class="{ 'has-tooltip': field }">
              {{ label }}
            </span>
          </UTooltip>
        </span>
      </template>
    </template>

    <UInput
      v-if="'string' === type"
      dir="ltr"
      :id="`dlf-${id}`"
      v-model="stringModel"
      :placeholder="placeholder"
      :disabled="disabled"
      size="lg"
      class="w-full"
      :ui="{ root: 'w-full', base: 'w-full bg-elevated/60' }"
    />

    <UTextarea
      v-else-if="'text' === type"
      dir="ltr"
      :id="`dlf-${id}`"
      v-model="stringModel"
      :placeholder="placeholder"
      :disabled="disabled"
      autoresize
      :rows="4"
      size="lg"
      class="w-full"
      :ui="{
        root: 'w-full',
        base: 'w-full bg-elevated/60 font-mono text-sm whitespace-pre-wrap ring-default',
      }"
    />

    <UInput
      v-else-if="'number' === type"
      :id="`dlf-${id}`"
      v-model.number.optional="numberModel"
      type="number"
      :min="min"
      :max="max"
      :step="step"
      :placeholder="placeholder"
      :disabled="disabled"
      size="lg"
      class="w-full"
      :ui="{ root: 'w-full', base: 'w-full bg-elevated/60' }"
    />

    <USelectMenu
      v-else-if="'select' === type"
      :id="`dlf-${id}`"
      v-model="selectModel"
      :items="items"
      value-key="value"
      label-key="label"
      :search-input="{ placeholder: t('common.search') }"
      :placeholder="placeholder"
      :disabled="disabled"
      clear
      size="lg"
      class="w-full"
      :ui="{ base: 'w-full bg-elevated/60' }"
    />

    <USwitch
      v-else-if="'bool' === type"
      :id="`dlf-${id}`"
      v-model="boolModel"
      :disabled="disabled"
      color="success"
      :label="boolModel ? t('common.yesLabel') : t('common.noLabel')"
      size="lg"
      class="w-full"
      :ui="{ root: 'w-full items-start justify-between gap-4', wrapper: 'ms-0 flex-1 text-sm' }"
    />

    <template v-if="$slots.description" #description>
      <slot name="description" />
    </template>

    <template v-if="$slots.help" #help>
      <slot name="help" />
    </template>
  </UFormField>
</template>

<script setup lang="ts">
import type { DLFieldType } from '~/types/dl_fields';
import { isBundledUiIcon } from '~/utils/generatedIconCatalog';

const { t } = useI18n();

const props = defineProps<{
  id: number | string;
  label: string;
  field?: string;
  type: DLFieldType | 'number' | 'select';
  description?: string;
  icon?: string;
  placeholder?: string;
  disabled?: boolean;
  compact?: boolean;
  required?: boolean;
  error?: string;
  nullable?: boolean;
  min?: number;
  max?: number;
  step?: number | 'any';
  items?: { label: string; value: string | number | boolean | null }[];
}>();

const model = defineModel<string | boolean | number | null>();

const iconName = computed(() => {
  if (!props.icon) {
    return '';
  }

  return isBundledUiIcon(props.icon) ? props.icon : 'i-lucide-circle-dot';
});

const stringModel = computed({
  get: () => (typeof model.value === 'string' ? model.value : ''),
  set: (value: string) => {
    model.value = value;
  },
});

const boolModel = computed({
  get: () => Boolean(model.value),
  set: (value: boolean) => {
    model.value = value;
  },
});

const numberModel = computed<number | undefined>({
  get: () => (typeof model.value === 'number' ? model.value : undefined),
  set: (value) => {
    model.value =
      value !== undefined && Number.isFinite(value) ? value : props.nullable ? null : undefined;
  },
});

const selectModel = computed({
  get: () => model.value,
  set: (value: string | number | boolean | null | undefined) => {
    model.value = value ?? (props.nullable ? null : undefined);
  },
});

const fieldUi = computed(() => ({
  container: props.compact ? 'space-y-1.5' : 'space-y-2',
  description: props.compact ? 'text-xs text-toned' : 'text-sm text-toned',
  help: props.compact ? 'mt-1 text-xs text-toned' : 'mt-2 text-sm text-toned',
}));
</script>
