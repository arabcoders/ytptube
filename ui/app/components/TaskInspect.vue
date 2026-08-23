<template>
  <div class="space-y-5">
    <form :id="formId" class="space-y-5" @submit.prevent="onSubmit">
      <div class="grid gap-4 lg:grid-cols-2">
        <UFormField :ui="fieldUi" :error="urlError || undefined">
          <template #label>
            <span class="inline-flex items-center gap-2 font-semibold">
              <UIcon name="i-lucide-link" class="size-4 text-toned" />
              <span>{{ t('common.url') }}</span>
            </span>
          </template>

          <UInput
            id="url"
            v-model="url"
            type="url"
            :placeholder="t('common.urlPlaceholder')"
            class="w-full"
            :ui="inputUi"
            :disabled="loading"
            dir="ltr"
          />
        </UFormField>

        <UFormField :ui="fieldUi">
          <template #label>
            <span class="inline-flex items-center gap-2 font-semibold">
              <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
              <span>{{ t('common.presetLabel') }}</span>
            </span>
          </template>

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
      </div>
    </form>

    <UAlert
      v-if="loading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('common.loadingData')"
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

      <UInput
        v-model="query"
        type="search"
        :placeholder="t('common.filterText')"
        icon="i-lucide-filter"
        size="sm"
        class="w-full"
      />

      <UAlert
        v-if="query && 0 === filteredLineCount"
        color="warning"
        variant="soft"
        icon="i-lucide-filter"
        :title="t('common.noMatchingLines')"
      />

      <pre
        v-else
        ref="contentView"
        class="ytp-terminal max-h-[50vh] overflow-auto"
        dir="ltr"
        :class="wrap ? 'whitespace-pre-wrap wrap-break-word' : 'whitespace-pre'"
      ><code v-text="displayedResponse" /></pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { computed, ref, watch } from 'vue';
import { copyText, request } from '~/utils';
import { filterLogTextLines } from '~/utils/logs';
import type { TaskDefinitionDocument } from '~/types/task_definitions';
import type { TaskInspectRequest, TaskInspectResponse } from '~/types/task_inspect';

const { t } = useI18n();

const props = defineProps<{
  url?: string;
  preset?: string;
  definitionId?: number;
  definitionDocument?: TaskDefinitionDocument;
  formId?: string;
}>();

const { selectItems } = usePresetOptions();

const config = useYtpConfig();
const url = ref(props.url ?? '');
const preset = ref(props.preset || config.app.default_preset || '');
const definitionMode = computed(
  () => props.definitionId !== undefined || props.definitionDocument !== undefined,
);
const formId = computed(() => props.formId ?? 'taskInspectForm');
const loading = ref(false);
const response = ref<TaskInspectResponse | null>(null);
const urlError = ref('');
const query = ref('');
const wrap = useStorage<boolean>('task_inspect_wrap', false);
const contentView = ref<HTMLElement | null>(null);

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
const filteredLines = computed<Array<string>>(() =>
  filterLogTextLines(formattedResponse.value, query.value),
);
const filteredLineCount = computed(() => filteredLines.value.length);
const displayedResponse = computed(() =>
  query.value ? filteredLines.value.join('\n') : formattedResponse.value,
);
const hasResult = computed(() => Boolean(response.value && !('error' in response.value)));
const hasVisibleResponse = computed(() => displayedResponse.value.length > 0);

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
  () => props.definitionId,
  () => {
    response.value = null;
    query.value = '';
  },
);

watch(
  () => props.definitionDocument,
  () => {
    response.value = null;
    query.value = '';
  },
);

watch(query, () => {
  contentView.value?.scrollTo({ top: 0 });
});

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
  query.value = '';

  if (!url.value || !validateUrl(url.value)) {
    urlError.value = t('common.enterValidUrl');
    return;
  }

  loading.value = true;

  const payload: TaskInspectRequest = {
    url: url.value.trim(),
    preset: preset.value.trim() || undefined,
    ...(definitionMode.value
      ? props.definitionId !== undefined
        ? { definition_id: props.definitionId }
        : { document: props.definitionDocument }
      : {}),
  };

  try {
    const res = await request(
      definitionMode.value ? '/api/tasks/definitions/inspect' : '/api/tasks/inspect',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
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
  response.value = null;
  urlError.value = '';
  query.value = '';
};

const copyResponse = (): void => {
  if (displayedResponse.value) {
    copyText(displayedResponse.value, false);
  }
};

const toggleWrap = (): void => {
  wrap.value = !wrap.value;
};

const scrollResponse = (dir: 'start' | 'end'): void => {
  contentView.value?.scrollTo({
    top: dir === 'start' ? 0 : contentView.value.scrollHeight,
    behavior: 'smooth',
  });
};

defineExpose({
  loading,
  wrap,
  hasResult,
  hasVisibleResponse,
  onReset,
  onSubmit,
  copyResponse,
  toggleWrap,
  scrollResponse,
});
</script>
