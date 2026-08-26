<template>
  <form id="notificationForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
    <FormSubmitError :message="action.message.value" @dismiss="action.clear" />
    <UAlert
      v-if="formError && hasFormContent"
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
              dir="ltr"
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

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-type" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.targetName') }}</span>
          </div>
        </template>

        <UInput
          id="name"
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
            <UIcon name="i-lucide-link" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.targetUrl') }}</span>
          </div>
        </template>

        <UInput
          id="url"
          dir="ltr"
          v-model="form.request.url"
          type="url"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>
    </div>

    <UAlert
      v-if="isAppriseTarget"
      color="info"
      variant="soft"
      icon="i-lucide-bell-ring"
      :title="t('common.appriseDetected')"
      :description="t('common.appriseDetectedDesc')"
    />

    <div v-if="!isAppriseTarget" class="grid gap-4 border-t border-default pt-5 md:grid-cols-2">
      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-arrow-right-left" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.requestMethod') }}</span>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.requestMethodDesc') }}</span>
        </template>

        <USelect
          id="method"
          dir="ltr"
          v-model="form.request.method"
          :items="requestMethods"
          size="lg"
          class="w-full"
          :disabled="addInProgress"
          :ui="selectUi"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-braces" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.requestType') }}</span>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.requestTypeDesc') }}</span>
        </template>

        <USelect
          id="type"
          dir="ltr"
          v-model="form.request.type"
          :items="requestTypeItems"
          value-key="value"
          label-key="label"
          size="lg"
          class="w-full"
          :disabled="addInProgress"
          :ui="selectUi"
        />
      </UFormField>
    </div>

    <div class="grid gap-5 border-t border-default pt-5 md:grid-cols-2">
      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <span class="inline-flex items-center gap-2 font-semibold text-default">
              <UIcon name="i-lucide-bell-ring" class="size-4 text-toned" />
              <span>{{ t('common.selectEvents') }}</span>
            </span>
            <button
              v-if="form.on.length > 0"
              type="button"
              class="text-primary hover:underline"
              @click="form.on = []"
            >
              {{ t('common.clearSelection') }}
            </button>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.selectEventsDesc') }}</span>
        </template>

        <USelectMenu
          id="on"
          dir="ltr"
          v-model="form.on"
          :items="eventItems"
          multiple
          color="neutral"
          size="lg"
          class="w-full"
          :disabled="addInProgress"
          :search-input="{ placeholder: t('common.search') }"
          :ui="selectUi"
        />
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <span class="inline-flex items-center gap-2 font-semibold text-default">
              <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
              <span>{{ t('common.selectPresets') }}</span>
            </span>
            <button
              v-if="form.presets.length > 0"
              type="button"
              class="text-primary hover:underline"
              @click="form.presets = []"
            >
              {{ t('common.clearSelection') }}
            </button>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.selectPresetsDesc') }}</span>
        </template>

        <USelectMenu
          id="presets"
          v-model="form.presets"
          :items="selectItems"
          value-key="value"
          label-key="label"
          multiple
          color="neutral"
          size="lg"
          class="w-full"
          :disabled="addInProgress"
          :search-input="{ placeholder: t('common.searchPresets') }"
          :ui="selectUi"
        />
      </UFormField>
    </div>

    <div class="grid gap-4 border-t border-default pt-5 md:grid-cols-2">
      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-power" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.enabled') }}</span>
          </div>
        </template>
        <template #description>
          <span>&nbsp;</span>
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

      <UFormField v-if="!isAppriseTarget" class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-braces" class="size-4 text-toned" />
            <span class="font-semibold text-default">{{ t('common.dataField') }}</span>
          </div>
        </template>

        <template #description>
          <span>{{ t('common.dataFieldDesc') }}</span>
        </template>

        <UInput
          id="data_key"
          dir="ltr"
          v-model="form.request.data_key"
          type="text"
          size="lg"
          :disabled="addInProgress"
          class="w-full"
          :ui="inputUi"
        />
      </UFormField>
    </div>

    <div v-if="!isAppriseTarget" class="space-y-4 border-t border-default pt-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="space-y-1">
          <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
            <UIcon name="i-lucide-key" class="size-4 text-toned" />
            <span>{{ t('common.optionalHeaders') }}</span>
          </div>
        </div>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          :disabled="addInProgress"
          @click="addHeader"
        >
          {{ t('common.add') }}
        </UButton>
      </div>

      <div v-if="form.request.headers.length > 0" class="space-y-3">
        <div
          v-for="(header, index) in form.request.headers"
          :key="`header-${index}`"
          class="grid gap-3 rounded-lg border border-default bg-muted/20 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
          dir="ltr"
        >
          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-key" class="size-4 text-toned" />
                <span class="font-semibold text-default">{{ t('common.keyLabel') }}</span>
              </div>
            </template>

            <UInput
              v-model="header.key"
              dir="ltr"
              type="text"
              size="lg"
              :disabled="addInProgress"
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

            <UInput
              v-model="header.value"
              dir="ltr"
              type="text"
              size="lg"
              :disabled="addInProgress"
              class="w-full"
              :ui="inputUi"
            />
          </UFormField>

          <div class="flex items-end">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              icon="i-lucide-trash"
              :disabled="addInProgress"
              @click="
                () => {
                  form.request.headers.splice(index, 1);
                }
              "
            >
              {{ t('common.remove') }}
            </UButton>
          </div>
        </div>
      </div>

      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        :description="t('common.headerEmptyWarning')"
      />
    </div>
  </form>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { useConfirm } from '~/composables/useConfirm';
import { useNotifications } from '~/composables/useNotifications';
import type { ImportedItem } from '~/types';
import type { notification, notificationRequestHeaderItem } from '~/types/notification';

const { t } = useI18n();

const emitter = defineEmits<{
  (event: 'dirty-change' | 'valid-change', value: boolean): void;
  (event: 'submit', payload: { reference: number | undefined; item: notification }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  allowedEvents: readonly string[];
  item: notification;
  addInProgress?: boolean;
}>();

const box = useConfirm();
const { isApprise } = useNotifications();
const { hasPreset, selectItems } = usePresetOptions();

const eventItems = computed(() => [...props.allowedEvents]);
const requestMethods = ['POST', 'PUT'];
const requestTypeItems = computed(() => [
  { label: t('common.requestTypeJson'), value: 'json' },
  { label: t('common.requestTypeForm'), value: 'form' },
]);

const showImport = useStorage('showImport', false);
const importString = ref('');
const importInProgress = ref(false);

const requestType = computed(() => form.request.type);

const form = reactive<notification>(normalizeNotification(props.item));
const action = useFormSubmit();

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

const isAppriseTarget = computed(() => Boolean(form.request.url) && isApprise(form.request.url));

const dirtySource = computed(() => ({
  reference: props.reference ?? null,
  form: normalizeNotification(form),
  importString: importString.value,
  showImport: showImport.value,
}));
const { isDirty, markClean } = useDirtyState(dirtySource);

watch(
  () => props.item,
  (value) => {
    action.clear();
    Object.assign(form, normalizeNotification(value));

    importString.value = '';
    nextTick(() => {
      markClean();
      emitter('dirty-change', false);
    });
  },
  { deep: true },
);

watch(isDirty, (value: boolean) => emitter('dirty-change', value));

function createDefaultNotification(): notification {
  return {
    name: '',
    on: [],
    presets: [],
    enabled: true,
    request: {
      method: 'POST',
      url: '',
      type: 'json',
      headers: [],
      data_key: 'data',
    },
  };
}

function normalizeNotification(value?: Partial<notification> | null): notification {
  const base = createDefaultNotification();
  const item = JSON.parse(JSON.stringify(value || {})) as Partial<notification>;

  return {
    ...base,
    ...item,
    on: Array.isArray(item.on) ? [...item.on] : [],
    presets: Array.isArray(item.presets) ? [...item.presets] : [],
    enabled: item.enabled ?? true,
    request: {
      ...base.request,
      ...(item.request || {}),
      headers: Array.isArray(item.request?.headers)
        ? item.request.headers.map((header) => ({ ...header }))
        : [],
    },
  };
}

const hasFormContent = computed(() => {
  return Boolean(
    form.name ||
    form.request.url ||
    form.request.method !== 'POST' ||
    form.request.type !== 'json' ||
    (requestType.value === 'form' ? form.request.data_key : '') ||
    form.on.length > 0 ||
    form.presets.length > 0 ||
    !form.enabled ||
    form.request.headers.some((header) => header.key || header.value),
  );
});

const formError = computed(() => {
  if (!String(form.name).trim()) {
    return t('common.fieldRequired', { field: 'name' });
  }

  if (!String(form.request.url).trim()) {
    return t('common.fieldRequired', { field: 'request.url' });
  }

  if (isAppriseTarget.value) {
    return '';
  }

  if (!form.request.method) {
    return t('common.fieldRequired', { field: 'request.method' });
  }

  if (!form.request.type) {
    return t('common.fieldRequired', { field: 'request.type' });
  }

  if (requestType.value === 'form' && !String(form.request.data_key).trim()) {
    return t('common.fieldRequired', { field: 'request.data_key' });
  }

  try {
    new URL(form.request.url);
  } catch {
    return t('common.invalidUrl');
  }

  return '';
});
watch(formError, (value) => emitter('valid-change', !value), { immediate: true });

const addHeader = (): void => {
  form.request.headers.push({ key: '', value: '' });
};

const checkInfo = async (): Promise<void> => {
  action.clear();
  if (formError.value) {
    return;
  }

  const copy = normalizeNotification(form);
  copy.name = copy.name.trim();
  copy.request.url = copy.request.url.trim();
  copy.request.method = copy.request.method.trim();
  copy.request.type = copy.request.type.trim();
  copy.request.data_key = copy.request.data_key.trim();
  copy.on = copy.on.map((entry) => entry.trim()).filter(Boolean);
  copy.presets = copy.presets.map((entry) => entry.trim()).filter(Boolean);
  copy.request.headers = copy.request.headers
    .map((header) => ({
      key: String(header.key || '').trim(),
      value: String(header.value || '').trim(),
    }))
    .filter((header) => header.key && header.value) as notificationRequestHeaderItem[];

  emitter('submit', { reference: toRaw(props.reference ?? undefined), item: toRaw(copy) });
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
    const item = decode(value) as notification & ImportedItem;

    if ('notification' !== item._type) {
      action.setError(
        new Error(
          t('common.validationInvalidImport', { expected: 'notification', type: item._type }),
        ),
      );
      importString.value = '';
      return;
    }

    if (hasFormContent.value && false === (await box.confirm(t('common.overwriteFormDesc')))) {
      return;
    }

    const nextValue = normalizeNotification(item);
    nextValue.presets = nextValue.presets.filter((preset) => hasPreset(preset));
    Object.assign(form, nextValue);

    importString.value = '';
    showImport.value = false;
    action.clear();
  } catch (error) {
    action.setError(
      new Error(
        t('common.failedImportNotification', {
          error: error instanceof Error ? error.message : t('common.unknownError'),
        }),
      ),
    );
  } finally {
    importInProgress.value = false;
  }
};

onMounted(() => {
  markClean();
  emitter('dirty-change', false);
});
</script>
