<template>
  <form id="notificationForm" autocomplete="off" class="space-y-6" @submit.prevent="checkInfo">
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
            <span class="font-semibold text-default">Target name</span>
          </div>
        </template>

        <template #description>
          <span>
            The notification target name, this is used to identify the target in the logs and
            notifications.
          </span>
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
            <span class="font-semibold text-default">Target URL</span>
          </div>
        </template>

        <template #description>
          <span>
            The URL to send the notification to. It can be regular http/https endpoint. or
            <a
              target="_blank"
              rel="noreferrer"
              href="https://github.com/caronc/apprise?tab=readme-ov-file#readme"
              class="text-primary hover:underline"
            >
              Apprise
            </a>
            URL.
          </span>
        </template>

        <UInput
          id="url"
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
      title="Apprise target detected"
      description="Apprise URLs only require the target name and URL. Request method, request type, headers, and data field are not used."
    />

    <div v-if="!isAppriseTarget" class="grid gap-4 border-t border-default pt-5 md:grid-cols-2">
      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-arrow-right-left" class="size-4 text-toned" />
            <span class="font-semibold text-default">Request method</span>
          </div>
        </template>

        <template #description>
          <span>
            The request method to use when sending the notification. This can be any of the standard
            HTTP methods.
          </span>
        </template>

        <USelect
          id="method"
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
            <span class="font-semibold text-default">Request Type</span>
          </div>
        </template>

        <template #description>
          <span>
            The request type to use when sending the notification. This can be JSON or FORM request.
          </span>
        </template>

        <USelect
          id="type"
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
              <span>Select Events</span>
            </span>
            <button
              v-if="form.on.length > 0"
              type="button"
              class="text-primary hover:underline"
              @click="form.on = []"
            >
              Clear selection
            </button>
          </div>
        </template>

        <template #description>
          <span>
            Subscribe to the events you want to listen for. When the event is triggered, the
            notification will be sent to the target URL. If no events are selected, the notification
            will be sent for all events.
          </span>
        </template>

        <select
          id="on"
          v-model="form.on"
          multiple
          :disabled="addInProgress"
          class="min-h-40 w-full rounded-md border border-default bg-elevated/60 px-3 py-2 text-sm text-default outline-none transition focus:border-primary"
        >
          <option v-for="aEvent in allowedEvents" :key="aEvent" :value="aEvent">
            {{ aEvent }}
          </option>
        </select>
      </UFormField>

      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <span class="inline-flex items-center gap-2 font-semibold text-default">
              <UIcon name="i-lucide-sliders-horizontal" class="size-4 text-toned" />
              <span>Select Presets</span>
            </span>
            <button
              v-if="form.presets.length > 0"
              type="button"
              class="text-primary hover:underline"
              @click="form.presets = []"
            >
              Clear selection
            </button>
          </div>
        </template>

        <template #description>
          <span>
            Select the presets you want to listen for. If you select presets, only events that
            reference those presets will trigger the notification. If no presets are selected, the
            notification will be sent for all presets.
          </span>
        </template>

        <select
          id="presets"
          v-model="form.presets"
          multiple
          :disabled="addInProgress"
          class="min-h-40 w-full rounded-md border border-default bg-elevated/60 px-3 py-2 text-sm text-default outline-none transition focus:border-primary"
        >
          <optgroup v-if="filterPresets(false).length > 0" label="Custom presets">
            <option v-for="preset in filterPresets(false)" :key="preset.id" :value="preset.name">
              {{ preset.name }}
            </option>
          </optgroup>

          <optgroup label="Default presets">
            <option v-for="preset in filterPresets(true)" :key="preset.id" :value="preset.name">
              {{ preset.name }}
            </option>
          </optgroup>
        </select>
      </UFormField>
    </div>

    <div class="grid gap-4 border-t border-default pt-5 md:grid-cols-2">
      <UFormField class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-power" class="size-4 text-toned" />
            <span class="font-semibold text-default">Enabled</span>
          </div>
        </template>

        <template #description>
          <span>Whether the notification target is enabled.</span>
        </template>

        <div
          class="flex min-h-11 items-center justify-between rounded-md border border-default bg-elevated/40 px-3"
        >
          <span class="text-sm text-default">{{ form.enabled ? 'Yes' : 'No' }}</span>
          <USwitch v-model="form.enabled" :disabled="addInProgress" />
        </div>
      </UFormField>

      <UFormField v-if="!isAppriseTarget" class="w-full" :ui="fieldUi">
        <template #label>
          <div class="flex flex-wrap items-center gap-2">
            <UIcon name="i-lucide-braces" class="size-4 text-toned" />
            <span class="font-semibold text-default">Data field</span>
          </div>
        </template>

        <template #description>
          <span>
            The field name to use when sending the notification. This is used to identify the data
            in the request. The default is data.
          </span>
        </template>

        <UInput
          id="data_key"
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
            <span>Optional Headers</span>
          </div>
          <p class="text-sm text-toned">The header key/value to send with the notification.</p>
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
          Add Header
        </UButton>
      </div>

      <div v-if="form.request.headers.length > 0" class="space-y-3">
        <div
          v-for="(header, index) in form.request.headers"
          :key="`header-${index}`"
          class="grid gap-3 rounded-lg border border-default bg-muted/20 p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
        >
          <UFormField :ui="fieldUi">
            <template #label>
              <div class="flex flex-wrap items-center gap-2">
                <UIcon name="i-lucide-key" class="size-4 text-toned" />
                <span class="font-semibold text-default">Header key</span>
              </div>
            </template>

            <UInput
              v-model="header.key"
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
                <span class="font-semibold text-default">Header value</span>
              </div>
            </template>

            <UInput
              v-model="header.value"
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
              @click="form.request.headers.splice(index, 1)"
            >
              Remove
            </UButton>
          </div>
        </div>
      </div>

      <UAlert
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        description="If header key or value is empty, the header will not be sent."
      />
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
import { useConfirm } from '~/composables/useConfirm';
import { useNotifications } from '~/composables/useNotifications';
import type { ImportedItem } from '~/types';
import type { notification, notificationRequestHeaderItem } from '~/types/notification';

const emitter = defineEmits<{
  (event: 'cancel'): void;
  (event: 'submit', payload: { reference: number | undefined; item: notification }): void;
}>();

const props = defineProps<{
  reference?: number | null;
  allowedEvents: readonly string[];
  item: notification;
  addInProgress?: boolean;
}>();

const toast = useNotification();
const box = useConfirm();
const { isApprise } = useNotifications();
const { filterPresets, hasPreset } = usePresetOptions();

const requestMethods = ['POST', 'PUT'];
const requestTypeItems = [
  { label: 'Json', value: 'json' },
  { label: 'Form', value: 'form' },
];

const showImport = useStorage('showImport', false);
const importString = ref('');

const requestType = computed(() => form.request.type);

const form = reactive<notification>(normalizeNotification(props.item));

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

watch(
  () => props.item,
  (value) => {
    Object.assign(form, normalizeNotification(value));
  },
  { deep: true },
);

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
    (requestType.value === 'form' ? form.request.data_key : '') ||
    form.on.length > 0 ||
    form.presets.length > 0 ||
    form.request.headers.some((header) => header.key || header.value),
  );
});

const addHeader = (): void => {
  form.request.headers.push({ key: '', value: '' });
};

const checkInfo = async (): Promise<void> => {
  const required = !isAppriseTarget.value
    ? [
        'name',
        'request.url',
        'request.method',
        'request.type',
        ...(requestType.value === 'form' ? ['request.data_key'] : []),
      ]
    : ['name', 'request.url'];

  for (const key of required) {
    if (key.includes('.')) {
      const [parent, child] = key.split('.') as ['request', keyof notification['request'] & string];
      const parentObject = form[parent] as Record<string, unknown> | undefined;

      if (!parentObject || !parentObject[child]) {
        toast.error(`The field ${parent}.${child} is required.`);
        return;
      }
    } else if (!(form as Record<string, unknown>)[key]) {
      toast.error(`The field ${key} is required.`);
      return;
    }
  }

  if (!isAppriseTarget.value) {
    try {
      new URL(form.request.url);
    } catch {
      toast.error('Invalid URL');
      return;
    }
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
  const value = importString.value.trim();
  if (!value) {
    toast.error('The import string is required.');
    return;
  }

  try {
    const item = decode(value) as notification & ImportedItem;

    if ('notification' !== item._type) {
      toast.error(`Invalid import string. Expected type 'notification', got '${item._type}'.`);
      importString.value = '';
      return;
    }

    if (
      hasFormContent.value &&
      false === (await box.confirm('Overwrite the current form fields?'))
    ) {
      return;
    }

    const nextValue = normalizeNotification(item);
    nextValue.presets = nextValue.presets.filter((preset) => hasPreset(preset));
    Object.assign(form, nextValue);

    importString.value = '';
    showImport.value = false;
  } catch (error: any) {
    toast.error(`Failed to import task. ${error.message}`);
  }
};
</script>
