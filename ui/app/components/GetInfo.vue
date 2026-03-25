<template>
  <UModal
    v-if="!externalModel"
    :open="true"
    :title="resolvedTitle"
    :dismissible="true"
    :ui="{ content: 'w-full sm:max-w-5xl', body: 'p-0 overflow-hidden' }"
    @update:open="(open) => !open && emitter('closeModel')"
  >
    <template #description>
      <span class="sr-only">{{ modalDescription }}</span>
    </template>

    <template #body>
      <div class="flex h-[75vh] min-h-96 min-w-0 flex-col">
        <div
          class="flex flex-wrap items-center justify-between gap-3 border-b border-default bg-muted/20 px-4 py-3"
        >
          <div class="min-w-0 space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon :name="contentIcon" class="size-4 text-toned" />
              <span>{{ contentLabel }}</span>
              <UBadge color="neutral" variant="soft" size="sm">
                {{ isStructuredData ? 'JSON' : 'Text' }}
              </UBadge>
            </div>
            <p class="truncate text-xs text-toned">{{ sourceSummary }}</p>
          </div>

          <div class="flex items-center gap-2">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              :disabled="isLoading || !hasDisplayText"
              @click="wrapText = !wrapText"
            >
              {{ wrapText ? 'No wrap' : 'Wrap text' }}
            </UButton>

            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-copy"
              :disabled="isLoading || !hasDisplayText"
              @click="copyData"
            >
              Copy
            </UButton>
          </div>
        </div>

        <div class="flex-1 min-h-0 p-4 sm:p-5">
          <div v-if="isLoading" class="flex h-full min-h-64 items-center justify-center">
            <div class="flex flex-col items-center gap-3 text-center text-toned">
              <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin text-info" />
              <span class="text-sm">Loading information...</span>
            </div>
          </div>

          <div v-else-if="errorMessage" class="flex h-full min-h-64 items-center justify-center">
            <div class="w-full max-w-2xl space-y-4">
              <UAlert
                color="error"
                variant="soft"
                icon="i-lucide-triangle-alert"
                title="Unable to load information"
                :description="errorMessage"
              />

              <div class="flex justify-end">
                <UButton
                  type="button"
                  color="neutral"
                  variant="outline"
                  size="sm"
                  icon="i-lucide-rotate-ccw"
                  @click="() => void loadInfo()"
                >
                  Retry
                </UButton>
              </div>
            </div>
          </div>

          <div v-else-if="!hasDisplayText" class="flex h-full min-h-64 items-center justify-center">
            <UAlert
              color="neutral"
              variant="soft"
              icon="i-lucide-info"
              title="No content returned"
              description="The request completed successfully but did not return any visible content."
              class="w-full max-w-2xl"
            />
          </div>

          <pre :class="preClasses"><code class="block min-w-full" v-text="displayText" /></pre>
        </div>
      </div>
    </template>
  </UModal>

  <div v-else class="flex h-[75vh] min-h-96 min-w-0 flex-col">
    <div
      class="flex flex-wrap items-center justify-between gap-3 border-b border-default bg-muted/20 px-4 py-3"
    >
      <div class="min-w-0 space-y-1">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon :name="contentIcon" class="size-4 text-toned" />
          <span>{{ contentLabel }}</span>
          <UBadge color="neutral" variant="soft" size="sm">
            {{ isStructuredData ? 'JSON' : 'Text' }}
          </UBadge>
        </div>
        <p class="truncate text-xs text-toned">{{ sourceSummary }}</p>
      </div>

      <div class="flex items-center gap-2">
        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          :disabled="isLoading || !hasDisplayText"
          @click="wrapText = !wrapText"
        >
          {{ wrapText ? 'No wrap' : 'Wrap text' }}
        </UButton>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-copy"
          :disabled="isLoading || !hasDisplayText"
          @click="copyData"
        >
          Copy
        </UButton>
      </div>
    </div>

    <div class="flex-1 min-h-0 p-4 sm:p-5">
      <div v-if="isLoading" class="flex h-full min-h-64 items-center justify-center">
        <div class="flex flex-col items-center gap-3 text-center text-toned">
          <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin text-info" />
          <span class="text-sm">Loading information...</span>
        </div>
      </div>

      <div v-else-if="errorMessage" class="flex h-full min-h-64 items-center justify-center">
        <div class="w-full max-w-2xl space-y-4">
          <UAlert
            color="error"
            variant="soft"
            icon="i-lucide-triangle-alert"
            title="Unable to load information"
            :description="errorMessage"
          />

          <div class="flex justify-end">
            <UButton
              type="button"
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-rotate-ccw"
              @click="() => void loadInfo()"
            >
              Retry
            </UButton>
          </div>
        </div>
      </div>

      <div v-else-if="!hasDisplayText" class="flex h-full min-h-64 items-center justify-center">
        <UAlert
          color="neutral"
          variant="soft"
          icon="i-lucide-info"
          title="No content returned"
          description="The request completed successfully but did not return any visible content."
          class="w-full max-w-2xl"
        />
      </div>

      <pre :class="preClasses"><code class="block min-w-full" v-text="displayText" /></pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';

const toast = useNotification();
const emitter = defineEmits<{ (e: 'closeModel'): void }>();

const props = withDefaults(
  defineProps<{
    link?: string;
    preset?: string;
    cli?: string;
    useUrl?: boolean;
    externalModel?: boolean;
    code_classes?: string;
  }>(),
  {
    link: '',
    preset: '',
    cli: '',
    useUrl: false,
    externalModel: false,
    code_classes: '',
  },
);

const isLoading = ref(true);
const data = ref<unknown>(null);
const errorMessage = ref('');
const wrapText = useStorage<boolean>('get_info_wrap_text', false);
let latestRequestId = 0;

const resolvedTitle = computed(() => {
  if (props.useUrl && props.link.startsWith('/api/history/')) {
    return 'Local Information';
  }

  if (props.useUrl) {
    return 'File Contents';
  }

  return 'yt-dlp Information';
});

const modalDescription = computed(() => {
  if (props.useUrl && props.link.startsWith('/api/history/')) {
    return 'View the stored local information payload for this item.';
  }

  if (props.useUrl) {
    return 'Preview the fetched text response.';
  }

  return 'View the yt-dlp information payload for this URL.';
});

const displayText = computed(() => {
  if (typeof data.value === 'string') {
    return data.value;
  }

  if (data.value === null || data.value === undefined) {
    return '';
  }

  try {
    return JSON.stringify(data.value, null, 2) ?? '';
  } catch {
    return String(data.value ?? '');
  }
});

const hasDisplayText = computed(() => displayText.value.length > 0);

const isStructuredData = computed(() => {
  return data.value !== null && data.value !== undefined && typeof data.value !== 'string';
});

const contentIcon = computed(() => {
  return isStructuredData.value ? 'i-lucide-braces' : 'i-lucide-file-text';
});

const contentLabel = computed(() => {
  return isStructuredData.value ? 'Structured output' : 'Plain text output';
});

const sourceSummary = computed(() => {
  if (props.useUrl) {
    return props.link || 'Direct response source';
  }

  const details = [];

  if (props.preset) {
    details.push(`Preset: ${props.preset}`);
  }

  if (props.cli) {
    details.push('Custom yt-dlp args applied');
  }

  return details.join(' | ') || 'yt-dlp response payload';
});

const preClasses = computed(() => [
  'h-full max-h-full overflow-auto rounded-xl border border-default bg-elevated/40 p-4 text-sm text-default',
  'font-mono leading-6',
  wrapText.value ? 'whitespace-pre-wrap break-words' : 'whitespace-pre',
  props.code_classes,
]);

const buildRequestUrl = (): string => {
  if (props.useUrl) {
    return props.link;
  }

  const params = new URLSearchParams();

  if (props.preset) {
    params.append('preset', props.preset);
  }

  if (props.cli) {
    params.append('args', props.cli);
  }

  params.append('url', props.link);

  return `/api/yt-dlp/url/info?${params.toString()}`;
};

const parseResponseBody = (body: string): unknown => {
  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
};

const getErrorMessage = (body: string, status: number): string => {
  if (!body) {
    return `Request failed with status ${status}.`;
  }

  try {
    const parsed = JSON.parse(body) as { message?: string; error?: string };
    return parsed.message || parsed.error || body;
  } catch {
    return body;
  }
};

const loadInfo = async (): Promise<void> => {
  latestRequestId += 1;
  const requestId = latestRequestId;

  isLoading.value = true;
  errorMessage.value = '';
  data.value = null;

  if (!props.link) {
    errorMessage.value = 'No source URL was provided.';
    isLoading.value = false;
    return;
  }

  try {
    const response = await request(buildRequestUrl());
    const body = await response.text();

    if (requestId !== latestRequestId) {
      return;
    }

    if (!response.ok) {
      throw new Error(getErrorMessage(body, response.status));
    }

    data.value = parseResponseBody(body);
  } catch (error: unknown) {
    if (requestId !== latestRequestId) {
      return;
    }

    console.error(error);
    const message = error instanceof Error ? error.message : 'Failed to load information.';
    errorMessage.value = message;
    toast.error(`Error: ${message}`);
  } finally {
    if (requestId === latestRequestId) {
      isLoading.value = false;
    }
  }
};

const copyData = (): void => {
  if (!displayText.value) {
    return;
  }

  copyText(displayText.value);
};

watch(
  () => [props.link, props.preset, props.cli, props.useUrl],
  () => {
    void loadInfo();
  },
  { immediate: true },
);
</script>
