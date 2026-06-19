<template>
  <UModal v-model:open="modalOpen" :title="resolvedTitle" :ui="modalUi">
    <template #description>
      <span class="sr-only">{{ modalDescription }}</span>
    </template>

    <template #body>
      <div class="space-y-4">
        <div v-if="isLoading" class="flex min-h-80 items-center justify-center">
          <UIcon name="i-lucide-loader-circle" class="size-16 animate-spin text-primary" />
        </div>

        <UAlert
          v-else-if="errorMessage"
          color="error"
          variant="soft"
          icon="i-lucide-triangle-alert"
          title="Unable to load information"
          :description="errorMessage"
        />

        <div v-else class="space-y-3">
          <UInput
            v-model="query"
            type="search"
            placeholder="Filter text"
            icon="i-lucide-filter"
            size="sm"
            class="w-full"
          />

          <UAlert
            v-if="query && 0 === filteredLineCount"
            color="warning"
            variant="soft"
            icon="i-lucide-filter"
            title="No matching lines"
          />

          <UAlert
            v-else-if="!hasDisplayText"
            color="neutral"
            variant="soft"
            icon="i-lucide-info"
            title="No content returned"
            description="The request completed successfully but did not return any visible content."
          />

          <pre
            v-else-if="!query || filteredLineCount > 0"
            ref="contentView"
            class="ytp-terminal max-h-[55vh] overflow-auto"
            :class="wrap ? 'whitespace-pre-wrap wrap-break-word' : 'whitespace-pre'"
          ><code v-text="displayedText" /></pre>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full flex-wrap items-center justify-end gap-2">
        <UButton
          type="button"
          color="neutral"
          :variant="wrap ? 'soft' : 'outline'"
          size="sm"
          icon="i-lucide-wrap-text"
          :disabled="isLoading || !hasVisibleText"
          @click="wrap = !wrap"
        >
          <span class="hidden sm:inline">Wrap</span>
        </UButton>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-copy"
          :disabled="isLoading || !hasVisibleText"
          @click="copyData"
        >
          Copy
        </UButton>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-arrow-down"
          :disabled="isLoading || !hasVisibleText"
          @click="scrollContent('end')"
        >
          Go down
        </UButton>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :disabled="!link"
          :loading="isLoading"
          @click="() => void loadInfo()"
        >
          Reload
        </UButton>

        <UButton
          type="button"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-arrow-up"
          :disabled="isLoading || !hasVisibleText"
          @click="scrollContent('start')"
        >
          Go up
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import { filterLogTextLines } from '~/utils/logs';
const emitter = defineEmits<{ (e: 'closeModel'): void }>();

const props = withDefaults(
  defineProps<{
    link?: string;
    preset?: string;
    cli?: string;
    useUrl?: boolean;
  }>(),
  {
    link: '',
    preset: '',
    cli: '',
    useUrl: false,
  },
);

const isLoading = ref(true);
const data = ref<unknown>(null);
const errorMessage = ref('');
const query = ref('');
const wrap = useStorage<boolean>('getinfo_wrap', false);
const contentView = ref<HTMLElement | null>(null);
let latestRequestId = 0;

const toast = useNotification();

const modalUi = {
  content: 'w-full sm:max-w-5xl',
  body: 'p-4 sm:p-5',
  footer: 'px-4 pb-4 sm:px-5 sm:pb-5',
} as const;

const modalOpen = computed({
  get: () => true,
  set: (value: boolean) => {
    if (!value) {
      emitter('closeModel');
    }
  },
});

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

const filteredLines = computed<Array<string>>(() =>
  filterLogTextLines(displayText.value, query.value),
);

const filteredLineCount = computed(() => filteredLines.value.length);
const displayedText = computed(() =>
  query.value ? filteredLines.value.join('\n') : displayText.value,
);
const hasDisplayText = computed(() => displayText.value.length > 0);
const hasVisibleText = computed(() => displayedText.value.length > 0);

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

  query.value = '';
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
  if (!displayedText.value) {
    return;
  }

  copyText(displayedText.value, false);
};

const scrollContent = (dir: 'start' | 'end'): void => {
  if (!contentView.value) {
    return;
  }

  contentView.value.scrollTo({
    top: 'start' === dir ? 0 : contentView.value.scrollHeight,
    behavior: 'smooth',
  });
};

watch(query, () => {
  if (!contentView.value) {
    return;
  }

  contentView.value.scrollTo({ top: 0 });
});

watch(
  () => [props.link, props.preset, props.cli, props.useUrl],
  () => {
    void loadInfo();
  },
  { immediate: true },
);
</script>
