<template>
  <UModal
    :open="open"
    :title="t('toolbox.title')"
    :dismissible="!submitting"
    :ui="{ content: 'w-full sm:max-w-2xl', body: 'max-h-[75vh] overflow-y-auto p-4 sm:p-6' }"
    @update:open="close"
  >
    <template #body>
      <FormSubmitError
        :message="submission.message.value || toolsError"
        @dismiss="submission.clear"
      />
      <form id="toolboxForm" class="space-y-5" @submit.prevent="submit">
        <UAlert
          v-if="toolWarning && !submission.message.value && !toolsError"
          color="warning"
          variant="soft"
          icon="i-lucide-triangle-alert"
          :title="toolWarning"
        />
        <p v-if="isToolsLoading" role="status" class="text-sm text-toned">
          {{ t('common.loading') }}
        </p>
        <UFormField :label="t('common.operation')">
          <USelectMenu
            v-model="tool"
            :items="[...tools]"
            value-key="id"
            label-key="name"
            :search-input="{ placeholder: t('common.search') }"
            :disabled="submitting || isToolsLoading"
            class="w-full"
          />
        </UFormField>
        <p v-if="selectedTool" class="text-sm text-toned">{{ selectedTool.description }}</p>
        <UFormField :label="t('common.file')">
          <p class="break-all text-sm" dir="auto">{{ file }}</p>
        </UFormField>
        <DLInput
          v-for="field in optionSchema.fields"
          :id="field.name"
          :key="`${tool}-${field.name}`"
          v-model="options[field.name]"
          :type="field.type"
          :label="field.label"
          :description="field.description"
          :required="field.required"
          :nullable="field.nullable"
          :min="field.min"
          :max="field.max"
          :step="field.step"
          :items="field.items"
          :error="submission.fields.value[field.name]"
          :disabled="submitting"
        />
        <UFormField
          v-if="selectedTool?.supports_overwrite"
          :label="t('common.overwriteSource')"
          :help="t('common.overwriteSourceDesc')"
        >
          <USwitch
            v-model="overwriteSource"
            :disabled="submitting"
            :aria-label="t('common.overwriteSource')"
          />
        </UFormField>
      </form>
    </template>
    <template #footer>
      <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          icon="i-lucide-x"
          :disabled="submitting"
          class="justify-center"
          @click="close(false)"
          >{{ t('common.cancel') }}</UButton
        >
        <UButton
          type="submit"
          form="toolboxForm"
          icon="i-lucide-play"
          :loading="submitting"
          :disabled="!canSubmit"
          class="justify-center"
          >{{ t('common.start') }}</UButton
        >
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { useFormSubmit } from '~/composables/useFormSubmit';
import { useToolbox } from '~/composables/useToolbox';
import type { ToolboxJob, ToolboxOptions } from '~/types/toolbox';
import { sTrim } from '~/utils';
import { toolboxOptionDefaults, toolboxOptionFields } from '~/utils/toolbox';

const props = defineProps<{ file: string }>();
const emit = defineEmits<{ close: []; created: [job: ToolboxJob] }>();
const { t } = useI18n();
const { tools, isToolsLoading, toolsError, loadTools, createJob } = useToolbox();
const submission = useFormSubmit();
const submitting = ref(false);
const open = ref(true);
const file = computed(() => sTrim(props.file, '/'));
const tool = ref<number>();
const initialTool = ref<number>();
const overwriteSource = useStorage('toolbox_overwrite_source', true);
const options = ref<ToolboxOptions>({});
const initialOptions = ref('{}');
const dirty = computed(
  () => tool.value !== initialTool.value || JSON.stringify(options.value) !== initialOptions.value,
);
const selectedTool = computed(() => tools.value.find((item) => item.id === tool.value));
const optionSchema = computed(() => toolboxOptionFields(selectedTool.value?.options_schema ?? {}));
const toolWarning = computed(() => {
  if (selectedTool.value && !selectedTool.value.available) {
    return selectedTool.value.reason || 'This operation is unavailable.';
  }
  const unsupported = optionSchema.value.unsupported;
  return unsupported.length
    ? t('toolbox.unsupportedOptions', { fields: unsupported.join(', ') })
    : '';
});
watch(
  tool,
  () => {
    options.value = toolboxOptionDefaults(optionSchema.value.fields);
    initialOptions.value = JSON.stringify(options.value);
    submission.clear();
  },
  { flush: 'sync' },
);
const canSubmit = computed(
  () =>
    !submitting.value &&
    Boolean(file.value) &&
    Boolean(selectedTool.value?.available) &&
    !optionSchema.value.unsupported.length,
);
let disposed = false;
const guard = useDirtyCloseGuard(open, { dirty, preferenceKey: 'toolbox', routeGuards: false });
const requestClose = async (): Promise<boolean> =>
  !submitting.value && (await guard.requestClose());
const close = async (value: boolean): Promise<void> => {
  if (!value && (await requestClose()) && !disposed) emit('close');
};
const submit = async (): Promise<void> => {
  const selected = selectedTool.value;
  if (!canSubmit.value || !selected) return;
  submitting.value = true;
  try {
    const job = await submission.run(() =>
      createJob(
        selected.id,
        file.value,
        selected.supports_overwrite && overwriteSource.value,
        options.value,
      ),
    );
    if (job && !disposed) emit('created', job);
  } finally {
    submitting.value = false;
  }
};
onBeforeRouteLeave(requestClose);
onMounted(async () => {
  await loadTools();
  if (disposed) return;
  tool.value = tools.value.find((item) => item.available)?.id ?? tools.value[0]?.id;
  initialTool.value = tool.value;
});
onScopeDispose(() => {
  disposed = true;
});
</script>
