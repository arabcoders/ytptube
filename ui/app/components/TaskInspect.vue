<template>
  <div class="space-y-5">
    <form id="taskInspectForm" class="space-y-5" @submit.prevent="onSubmit">
      <div class="grid gap-4 lg:grid-cols-2">
        <UFormField
          :label="t('common.url')"
          :ui="fieldUi"
          :error="urlError || undefined"
          class="lg:col-span-2"
        >
          <UInput
            id="url"
            v-model="url"
            type="url"
            :placeholder="t('common.urlPlaceholder')"
            class="w-full"
            :ui="inputUi"
            :disabled="loading"
            dir="ltr"
          >
            <template #leading>
              <UIcon name="i-lucide-link" class="size-4 text-toned" />
            </template>
          </UInput>
        </UFormField>

        <UFormField
          :label="t('common.presetLabel')"
          :ui="fieldUi"
          :description="t('common.inspectPresetDesc')"
        >
          <USelectMenu
            id="preset"
            v-model="preset"
            :items="presetItems"
            :placeholder="t('common.selectPreset')"
            value-key="value"
            label-key="label"
            color="neutral"
            class="w-full"
            size="lg"
            :ui="{ content: 'min-w-[13rem]', item: 'ps-6' }"
            :search-input="{ placeholder: t('common.searchPresets') }"
            :disabled="loading"
          />
        </UFormField>

        <UFormField
          :label="t('common.inspectHandler')"
          :ui="fieldUi"
          :description="t('common.inspectHandlerDesc')"
        >
          <UInput
            id="handler"
            v-model="handler"
            type="text"
            :placeholder="t('tasks.handlerPlaceholder')"
            class="w-full"
            :ui="inputUi"
            :disabled="loading"
            dir="ltr"
          >
            <template #leading>
              <UIcon name="i-lucide-rss" class="size-4 text-toned" />
            </template>
          </UInput>
        </UFormField>
      </div>
    </form>

    <UAlert
      v-if="loading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.inspecting')"
      :description="t('common.inspectingDesc')"
    />

    <UAlert
      v-else-if="response && 'error' in response"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('common.errorPrefix', { msg: '' })"
      :description="errorDescription"
    />

    <div v-else-if="response" class="space-y-3">
      <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
        <UIcon name="i-lucide-braces" class="size-4 text-toned" />
        <span>{{ t('common.result') }}</span>
      </div>

      <div class="overflow-hidden ytp-frame">
        <div class="w-full max-w-full overflow-x-auto overscroll-x-contain">
          <pre
            class="min-w-0 max-w-full overflow-x-auto p-4 text-xs leading-6 text-default"
            dir="ltr"
          ><code>{{ formattedResponse }}</code></pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { request } from '~/utils';
import type { TaskInspectRequest, TaskInspectResponse } from '~/types/task_inspect';

const { t } = useI18n();

const props = defineProps<{
  url?: string;
  preset?: string;
  handler?: string;
}>();

const { selectItems } = usePresetOptions();

const config = useYtpConfig();
const url = ref(props.url ?? '');
const preset = ref(props.preset || config.app.default_preset || '');
const handler = ref(props.handler ?? '');
const loading = ref(false);
const response = ref<TaskInspectResponse | null>(null);
const urlError = ref('');

const fieldUi = {
  label: 'font-semibold text-default',
  container: 'space-y-2',
  description: 'text-sm text-toned',
  error: 'text-sm text-error',
};

const inputUi = {
  root: 'w-full',
  base: 'w-full bg-elevated/60 ring-default focus-visible:ring-primary',
};

const presetItems = computed(
  () => selectItems.value as Array<{ type?: 'label' | 'item'; label: string; value?: string }>,
);

const formattedResponse = computed(() => {
  return response.value ? JSON.stringify(response.value, null, 2) : '';
});

const errorDescription = computed(() => {
  if (!response.value || !('error' in response.value)) {
    return undefined;
  }

  const error =
    typeof response.value.error === 'string'
      ? response.value.error
      : String(response.value.error ?? '');
  const message =
    typeof response.value.message === 'string'
      ? response.value.message
      : String(response.value.message ?? '');

  return message ? `${error} ${message}` : error;
});

watch(
  () => props.url,
  (val) => {
    if (val !== undefined) {
      url.value = val;
    }
  },
);

watch(
  () => props.preset,
  (val) => {
    if (val !== undefined) {
      preset.value = val;
    }
  },
);

watch(
  () => props.handler,
  (val) => {
    if (val !== undefined) {
      handler.value = val;
    }
  },
);

const validateUrl = (val: string): boolean => {
  try {
    const parsed = new URL(val);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
};

async function onSubmit() {
  urlError.value = '';
  response.value = null;

  if (!url.value || !validateUrl(url.value)) {
    urlError.value = t('common.enterValidUrl');
    return;
  }

  loading.value = true;

  const payload: TaskInspectRequest = {
    url: url.value.trim(),
    preset: preset.value.trim() || undefined,
    handler: handler.value.trim() || undefined,
  };

  try {
    const res = await request('/api/tasks/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    response.value = await res.json();
  } catch (err: any) {
    response.value = { error: err?.message || t('common.unknownError') };
  } finally {
    loading.value = false;
  }
}

const onReset = () => {
  url.value = props.url || '';
  preset.value = props.preset || config.app.default_preset || '';
  handler.value = props.handler || '';
  response.value = null;
  urlError.value = '';
};

defineExpose({ loading, onReset, onSubmit });
</script>
