<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="ytp-page-header">
      <div class="ytp-page-heading items-start">
        <span class="ytp-page-icon">
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div class="ytp-page-kicker">
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex w-full flex-wrap items-center gap-2 xl:w-auto xl:justify-end">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-copy"
          :disabled="isLoading || !report"
          @click="copyDiagnostics"
        >
          {{ t('common.copy') }}
        </UButton>

        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="isLoading"
          :disabled="isLoading"
          @click="void load(true)"
        >
          {{ t('common.refresh') }}
        </UButton>
      </div>
    </div>

    <UAlert
      v-if="!report && isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('diagnostics.loadingDesc')"
    />

    <UAlert
      v-else-if="!report && lastError"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('diagnostics.failed')"
      :description="lastError"
    />

    <template v-else-if="report">
      <UAlert
        v-if="showRequiredAlert"
        color="error"
        variant="soft"
        icon="i-lucide-octagon-alert"
        :title="t('diagnostics.requiredMissing')"
        :description="requiredAlertDescription"
      />

      <section class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-gauge" class="size-4 text-toned" />
          <span>{{ t('diagnostics.overview') }}</span>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            v-for="item in summaryCards"
            :key="item.label"
            :label="item.label"
            :value="item.value"
            :hint="item.description"
            :icon="item.icon"
            :color="item.color"
          />
        </div>
      </section>

      <section class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-server" class="size-4 text-toned" />
          <span>{{ t('diagnostics.runtime') }}</span>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <StatCard
            v-for="row in runtimeRows"
            :key="row.label"
            :label="row.label"
            :value="row.value"
            :hint="row.description"
            :icon="row.icon"
            color="neutral"
            value-wrap
          />
        </div>
      </section>

      <section v-for="section in featureSections" :key="section.id" class="space-y-3">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div class="space-y-1">
            <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
              <UIcon :name="section.icon" class="size-4 text-toned" />
              <span>{{ section.label }}</span>
            </div>
            <p class="text-sm text-toned">{{ section.description }}</p>
          </div>
        </div>

        <div class="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          <article
            v-for="item in section.items"
            :key="item.id"
            class="ytp-card-padded shadow-sm"
            dir="ltr"
          >
            <div class="min-w-0 space-y-3">
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <span :class="tagDotClass(item.status)"></span>
                  <p class="text-base font-semibold text-default" dir="auto">{{ item.label }}</p>
                  <span
                    class="inline-flex items-center rounded-md border border-default px-2 py-1 text-xs text-toned"
                  >
                    {{ item.required ? t('diagnostics.required') : t('common.optional') }}
                  </span>
                </div>

                <p v-if="item.description" class="text-sm text-toned" dir="auto">
                  {{ item.description }}
                </p>
                <p v-if="showMessage(item)" class="text-sm leading-6 text-default" dir="auto">
                  {{ item.message }}
                </p>
              </div>

              <div v-if="Object.keys(item.details || {}).length > 0" class="flex flex-wrap gap-2">
                <span
                  v-for="(value, key) in item.details"
                  :key="`${item.id}-${key}`"
                  class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 text-xs text-toned"
                >
                  <span class="font-medium text-default" dir="auto">{{ keyLabel(key) }}:</span>
                  <span dir="auto">{{ formatValue(value) }}</span>
                </span>
              </div>
            </div>
          </article>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import moment from 'moment';
import StatCard from '~/components/StatCard.vue';
import type { DiagnosticCheck, DiagnosticStatus } from '~/types/diagnostics';
import { usePageShell } from '~/composables/usePageShell';
import { copyText } from '~/utils';

const { t } = useI18n();
type SummaryCard = {
  label: string;
  description: string;
  value: number;
  icon: string;
  color: 'success' | 'error' | 'warning' | 'neutral';
};

type DetailRow = {
  label: string;
  description: string;
  value: string;
  icon: string;
};

type FeatureMeta = {
  icon: string;
};

type FeatureSection = FeatureMeta & {
  id: string;
  label: string;
  description: string;
  items: Array<DiagnosticCheck>;
};

const FEATURE_META: Record<string, FeatureMeta> = {
  core: {
    icon: 'i-lucide-wrench',
  },
  youtube: {
    icon: 'i-lucide-video',
  },
  notifications: {
    icon: 'i-lucide-bell',
  },
  advanced: {
    icon: 'i-lucide-plug-zap',
  },
  custom: {
    icon: 'i-lucide-package-plus',
  },
};

const FEATURE_ORDER = ['core', 'youtube', 'notifications', 'advanced', 'custom'];

const pageShell = usePageShell('diagnostics');
const diagnosticsState = useDiagnostics();

const report = diagnosticsState.diagnostics;
const isLoading = diagnosticsState.isLoading;
const lastError = diagnosticsState.lastError;
const groupedChecks = diagnosticsState.groupedChecks;

const showRequiredAlert = computed(() => {
  return (report.value?.summary.required_failed ?? 0) > 0;
});

const requiredAlertDescription = computed(() => {
  const count = report.value?.summary.required_failed ?? 0;
  return `${count} required fail${count === 1 ? '' : 's'}.`;
});

const featureSections = computed<Array<FeatureSection>>(() => {
  return FEATURE_ORDER.filter((id) => (groupedChecks.value[id] ?? []).length > 0).map((id) => {
    const meta = FEATURE_META[id]!;
    return {
      id,
      label: t(`diagnostics.feature.${id}.label`),
      description: t(`diagnostics.feature.${id}.description`),
      icon: meta.icon,
      items: groupedChecks.value[id] ?? [],
    };
  });
});

const summaryCards = computed<Array<SummaryCard>>(() => {
  const current = report.value;
  if (!current) {
    return [];
  }

  return [
    {
      label: t('diagnostics.passing'),
      description: t('diagnostics.passingDesc'),
      value: current.summary.pass,
      icon: 'i-lucide-badge-check',
      color: current.summary.pass > 0 ? 'success' : 'neutral',
    },
    {
      label: t('diagnostics.requiredFails'),
      description: t('diagnostics.requiredFailsDesc'),
      value: current.summary.required_failed,
      icon: 'i-lucide-octagon-alert',
      color: current.summary.required_failed > 0 ? 'error' : 'neutral',
    },
    {
      label: t('diagnostics.warnings'),
      description: t('diagnostics.warningsDesc'),
      value: current.summary.warn,
      icon: 'i-lucide-triangle-alert',
      color: current.summary.warn > 0 ? 'warning' : 'neutral',
    },
    {
      label: t('common.skipped'),
      description: t('diagnostics.skippedDesc'),
      value: current.summary.skip,
      icon: 'i-lucide-minus',
      color: 'neutral',
    },
  ];
});

const runtimeRows = computed<Array<DetailRow>>(() => {
  const runtime = report.value?.runtime;
  const python = report.value?.requirements.python;

  if (!runtime || !python) {
    return [];
  }

  return [
    {
      label: t('diagnostics.app'),
      description: t('diagnostics.appDesc'),
      value: runtime.app_version || 'Unknown',
      icon: 'i-lucide-package',
    },
    {
      label: t('diagnostics.host'),
      description: t('diagnostics.hostDesc'),
      value: `${runtime.platform} ${runtime.platform_release} (${runtime.platform_machine})`,
      icon: 'i-lucide-server',
    },
    {
      label: t('diagnostics.python'),
      description: `${python.note} Minimum ${python.required}+`,
      value: python.current,
      icon: 'i-lucide-square-terminal',
    },
  ];
});

const SHARE_STATUS: Record<DiagnosticStatus, string> = {
  pass: 'PASS',
  fail: 'FAIL',
  warn: 'WARN',
  skip: 'SKIP',
};

const SHARE_SECTION_LABELS: Record<string, string> = {
  core: 'Core',
  youtube: 'YouTube',
  notifications: 'Notifications',
  advanced: 'Advanced',
  custom: 'Custom',
};

const shareText = computed(() => {
  const current = report.value;
  if (!current) {
    return '';
  }

  const summary = current.summary;
  const lines: string[] = [
    'YTPTube Diagnostics',
    `Generated: ${formatIsoTimestamp(current.generated_at)}`,
    '',
    'Overview',
    `- Passing: ${summary.pass}`,
    `- Required fails: ${summary.required_failed}`,
    `- Warnings: ${summary.warn}`,
    `- Skipped: ${summary.skip}`,
    '',
    'Runtime',
    `- App: ${current.runtime.app_version || 'Unknown'}`,
    `- Host: ${current.runtime.platform} ${current.runtime.platform_release} (${current.runtime.platform_machine})`,
    `- Python: ${current.requirements.python.current}`,
    `- Started: ${formatIsoTimestamp(current.runtime.started)}`,
  ];

  if (current.stats?.enabled) {
    lines.push('', 'Resource Stats');

    if (current.stats.error) {
      lines.push(`- Error: ${current.stats.error}`);
    } else {
      const stats = current.stats.summary;
      const bottlenecks = current.stats.bottlenecks;

      lines.push(`- Window: ${formatDuration(current.stats.window_seconds)}`);
      lines.push(`- Samples: ${current.stats.sample_count ?? 0}`);

      if (stats) {
        lines.push(`- Avg app CPU: ${formatPercent(stats.averages.process_cpu_percent)}`);
        lines.push(`- Max app CPU: ${formatPercent(stats.max.process_cpu_percent)}`);
        lines.push(`- Avg system CPU: ${formatPercent(stats.averages.system_cpu_percent)}`);
        lines.push(`- Max system CPU: ${formatPercent(stats.max.system_cpu_percent)}`);
        lines.push(`- Avg memory: ${formatPercent(stats.averages.memory_percent)}`);
        lines.push(`- Max memory: ${formatPercent(stats.max.memory_percent)}`);
        lines.push(`- Avg RSS: ${formatMb(stats.averages.rss_mb)}`);
        lines.push(`- Max RSS: ${formatMb(stats.max.rss_mb)}`);
        lines.push(
          `- Avg jobs: ${formatOptionalNumber(stats.averages.active_jobs)} active, ${formatOptionalNumber(stats.averages.queued_jobs)} queued`,
        );
        lines.push(
          `- Max jobs: ${formatOptionalNumber(stats.max.active_jobs)} active, ${formatOptionalNumber(stats.max.queued_jobs)} queued`,
        );
        lines.push(`- Avg children: ${formatOptionalNumber(stats.averages.children_count)}`);
        lines.push(`- Max children: ${formatOptionalNumber(stats.max.children_count)}`);
        lines.push(`- Avg process write: ${formatBps(stats.averages.process_write_bps)}`);
        lines.push(`- Max process write: ${formatBps(stats.max.process_write_bps)}`);
        lines.push(`- Avg process read: ${formatBps(stats.averages.process_read_bps)}`);
        lines.push(`- Max process read: ${formatBps(stats.max.process_read_bps)}`);
        lines.push(`- Avg disk write: ${formatBps(stats.averages.disk_write_bps)}`);
        lines.push(`- Max disk write: ${formatBps(stats.max.disk_write_bps)}`);
        lines.push(`- Avg disk read: ${formatBps(stats.averages.disk_read_bps)}`);
        lines.push(`- Max disk read: ${formatBps(stats.max.disk_read_bps)}`);
        lines.push(`- Avg network down: ${formatBps(stats.averages.network_recv_bps)}`);
        lines.push(`- Max network down: ${formatBps(stats.max.network_recv_bps)}`);
        lines.push(`- Avg network up: ${formatBps(stats.averages.network_sent_bps)}`);
        lines.push(`- Max network up: ${formatBps(stats.max.network_sent_bps)}`);
      }

      if (bottlenecks) {
        lines.push(`- Bottleneck status: ${bottlenecks.status}`);
        lines.push(`- Bottleneck window: ${bottlenecks.window_samples} samples`);

        if (bottlenecks.bottlenecks.length > 0) {
          for (const item of bottlenecks.bottlenecks) {
            lines.push(`- [${item.level.toUpperCase()}] ${item.summary} ${item.details}`);
          }
        } else {
          lines.push('- Bottlenecks: none detected');
        }
      }
    }
  }

  for (const section of featureSections.value) {
    lines.push('', SHARE_SECTION_LABELS[section.id] ?? section.id);

    for (const item of section.items) {
      const versionSuffix = formatShareVersion(item);
      lines.push(
        `- [${SHARE_STATUS[item.status] ?? item.status}] ${item.label} (${item.required ? 'required' : 'optional'})${versionSuffix}`,
      );
    }
  }

  return lines.join('\n');
});

const load = async (force: boolean = false): Promise<void> => {
  await diagnosticsState.loadDiagnostics(force);
};

const copyDiagnostics = (): void => {
  if (!shareText.value) {
    return;
  }

  copyText(shareText.value);
};

const showMessage = (item: DiagnosticCheck): boolean => {
  if (item.status === 'pass') {
    return false;
  }

  return Boolean(item.message?.trim());
};

const tagDotClass = (status: DiagnosticStatus): string => {
  const base = 'inline-flex size-2.5 shrink-0 rounded-full';

  switch (status) {
    case 'pass':
      return `${base} bg-success`;
    case 'fail':
      return `${base} bg-error`;
    case 'warn':
      return `${base} bg-warning`;
    case 'skip':
    default:
      return `${base} bg-muted`;
  }
};

const formatValue = (value: DiagnosticCheck['details'][string]): string => {
  if (value === null || value === undefined || value === '') {
    return 'n/a';
  }

  return String(value);
};

const keyLabel = (value: string): string => {
  return value.replace(/_/g, ' ');
};

const formatIsoTimestamp = (value: number | undefined): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'Unknown';
  }

  return moment.unix(value).utc().format('YYYY-MM-DDTHH:mm:ss[Z]');
};

const formatDuration = (value: number | undefined): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'Unknown';
  }

  if (value % 3600 === 0) {
    return `${value / 3600}h`;
  }

  if (value % 60 === 0) {
    return `${value / 60}m`;
  }

  return `${value}s`;
};

const formatOptionalNumber = (value: number | null | undefined, digits: number = 2): string => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }

  return Number(value.toFixed(digits)).toString();
};

const formatPercent = (value: number | null | undefined): string => {
  const formatted = formatOptionalNumber(value);
  return formatted === 'n/a' ? formatted : `${formatted}%`;
};

const formatMb = (value: number | null | undefined): string => {
  const formatted = formatOptionalNumber(value);
  return formatted === 'n/a' ? formatted : `${formatted} MB`;
};

const formatBps = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a';
  }

  return `${formatOptionalNumber(value / 1024 / 1024)} MB/s`;
};

const formatShareVersion = (item: DiagnosticCheck): string => {
  const version = item.details?.version;
  if (version === null || version === undefined || version === '') {
    return '';
  }

  return ` [${String(version)}]`;
};

onMounted(() => {
  void load(true);
});
</script>
