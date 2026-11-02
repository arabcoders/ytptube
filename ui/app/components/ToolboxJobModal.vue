<template>
  <UModal
    :open="true"
    :title="
      selectedJob ? `#${selectedJob.id} - ${toolLabel(selectedJob.tool)}` : t('toolbox.title')
    "
    :ui="{ content: 'w-full sm:max-w-3xl', body: 'max-h-[75vh] overflow-y-auto p-4 sm:p-6' }"
    @update:open="(open) => !open && close()"
  >
    <template #body>
      <div class="space-y-5">
        <p v-if="detailLoading" role="status" class="text-sm text-toned">
          {{ t('common.loading') }}
        </p>
        <UAlert v-if="detailError" color="error" variant="soft" :title="detailError" />
        <template v-if="selectedJob">
          <section class="space-y-3">
            <div class="grid gap-4 sm:grid-cols-2">
              <StatCard
                :label="t('common.status')"
                :value="toolboxStatusLabel(selectedJob.status, t)"
                icon="i-lucide-activity"
                :color="toolboxStatusColor(selectedJob.status)"
              />
              <StatCard
                :label="t('common.date')"
                :value="formatRelativeTime(selectedJob.created_at, locale)"
                icon="i-lucide-clock"
                :tooltip="formatDateTime(selectedJob.created_at, locale, { seconds: true })"
                color="neutral"
              />
            </div>
            <div v-if="selectedJob.status === 'running'" class="space-y-2">
              <div class="flex items-center justify-between gap-3 text-xs text-toned">
                <span>{{ t('queue.progress') }}</span>
                <span v-if="selectedJob.progress !== null"
                  >{{ Math.round(selectedJob.progress) }}%</span
                >
              </div>
              <UProgress :model-value="selectedJob.progress" :aria-label="t('queue.progress')" />
            </div>
            <p
              v-if="
                (isToolboxActive(selectedJob) || selectedJob.status === 'skipped') &&
                selectedJob.message
              "
              class="wrap-break-word text-sm text-toned"
            >
              {{ selectedJob.message }}
            </p>
          </section>
          <UAlert
            v-if="selectedJob.error"
            color="error"
            variant="soft"
            :title="selectedJob.error"
            :description="selectedJob.error_code || undefined"
          />
          <dl>
            <div class="rounded-sm border border-default bg-elevated/40 p-3">
              <dt class="text-[11px] font-semibold uppercase tracking-wide text-toned">
                {{ t('common.source') }}
              </dt>
              <dd class="mt-1">
                <UTooltip :text="selectedJob.file">
                  <p class="truncate font-mono text-xs text-default" dir="auto">
                    {{ selectedJob.file }}
                  </p>
                </UTooltip>
              </dd>
            </div>
          </dl>
          <section v-if="selectedJob.result?.outputs.length" class="space-y-3">
            <div class="flex items-center gap-3">
              <span class="ytp-detail-icon"
                ><UIcon name="i-lucide-file-output" class="size-4"
              /></span>
              <h3 class="text-base font-semibold text-highlighted">{{ t('common.result') }}</h3>
            </div>
            <div
              v-for="output in selectedJob.result.outputs"
              :key="output"
              class="flex items-center gap-3 rounded-sm border border-default bg-elevated/40 p-3"
            >
              <div class="min-w-0 flex-1">
                <UTooltip :text="output">
                  <a
                    :href="makeDownload({}, { filename: output })"
                    :download="basename(output)"
                    class="block truncate text-sm font-semibold text-highlighted hover:underline"
                    dir="auto"
                    >{{ basename(output) }}</a
                  >
                </UTooltip>
              </div>
              <UButton
                color="neutral"
                variant="outline"
                size="sm"
                icon="i-lucide-folder-open"
                :to="outputBrowserUrl(output)"
                >{{ t('app.nav.labels.files') }}</UButton
              >
            </div>
          </section>
          <section v-if="selectedJob.log" class="space-y-3">
            <div class="flex items-center justify-between gap-3">
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center justify-between gap-3 text-start"
                :aria-expanded="logOpen"
                @click="logOpen = !logOpen"
              >
                <span class="flex items-center gap-3">
                  <span class="ytp-detail-icon"
                    ><UIcon name="i-lucide-terminal" class="size-4"
                  /></span>
                  <span class="text-base font-semibold text-highlighted">{{
                    t('common.logDetails')
                  }}</span>
                </span>
                <UIcon
                  name="i-lucide-chevron-right"
                  :class="[
                    'size-4 shrink-0 text-toned transition-transform',
                    logOpen ? 'rotate-90' : '',
                  ]"
                />
              </button>
              <UButton
                v-if="logOpen"
                color="neutral"
                variant="outline"
                size="xs"
                icon="i-lucide-copy"
                @click="copyText(selectedJob.log, true)"
                >{{ t('common.copy') }}</UButton
              >
            </div>
            <pre
              v-if="logOpen"
              class="ytp-terminal max-h-96 overflow-auto whitespace-pre-wrap wrap-break-word"
              dir="ltr"
            ><code>{{ selectedJob.log }}</code></pre>
          </section>
        </template>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import StatCard from '~/components/StatCard.vue';
import { useAppSocket } from '~/composables/useAppSocket';
import { useToolbox } from '~/composables/useToolbox';
import type { WSEP } from '~/types/sockets';
import type { ToolboxJob } from '~/types/toolbox';
import { basename, copyText, dirname, encodePath, makeDownload } from '~/utils';
import { formatDateTime } from '~/utils/date';
import { formatRelativeTime } from '~/utils/relativeTime';
import { isToolboxActive, toolboxStatusColor, toolboxStatusLabel } from '~/utils/toolbox';

const props = defineProps<{ id: number }>();
const emit = defineEmits<{ close: [] }>();
const { t, locale } = useI18n();
const { tools, jobs, getJob } = useToolbox();
const socket = useAppSocket();
const selectedJob = ref<ToolboxJob | null>(null);
const detailLoading = ref(false);
const detailError = ref('');
let detailRequest = 0;
let disposed = false;
const close = (): void => {
  disposed = true;
  detailRequest++;
  emit('close');
};
const loadJob = async (): Promise<void> => {
  const id = props.id;
  const sequence = ++detailRequest;
  detailError.value = '';
  detailLoading.value = Boolean(id);
  if (!id) return;
  try {
    const job = await getJob(id);
    if (
      !disposed &&
      sequence === detailRequest &&
      !(selectedJob.value && !isToolboxActive(selectedJob.value) && isToolboxActive(job))
    )
      selectedJob.value = job;
  } catch (error) {
    if (!disposed && sequence === detailRequest)
      detailError.value = error instanceof Error ? error.message : t('common.unknownError');
  } finally {
    if (!disposed && sequence === detailRequest) detailLoading.value = false;
  }
};
const onJob = (event: WSEP['toolbox_job']): void => {
  if (disposed || event.data.id !== props.id) return;
  if (selectedJob.value && !isToolboxActive(selectedJob.value) && isToolboxActive(event.data))
    return;
  detailRequest++;
  selectedJob.value = event.data;
  detailLoading.value = false;
  detailError.value = '';
};
const toolLabel = (id: string): string => tools.value.find((item) => item.id === id)?.name ?? id;
const logOpen = ref(false);
const outputBrowserUrl = (output: string): string => {
  const folder = dirname(output);
  return `${folder === '.' ? '/browser' : `/browser/${encodePath(folder)}`}?${new URLSearchParams({ search: basename(output) })}`;
};
watch(
  () => props.id,
  (id) => {
    logOpen.value = false;
    selectedJob.value = jobs.value.find((job) => job.id === id) ?? null;
    void loadJob();
  },
  { immediate: true, flush: 'sync' },
);
socket.on('toolbox_job', onJob);
socket.on('connect', loadJob);
onScopeDispose(() => {
  disposed = true;
  detailRequest++;
  socket.off('toolbox_job', onJob);
  socket.off('connect', loadJob);
});
</script>
