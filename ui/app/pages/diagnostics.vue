<template>
  <main class="w-full min-w-0 max-w-full space-y-6">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div class="flex min-w-0 items-start gap-3">
        <span
          class="inline-flex size-11 shrink-0 items-center justify-center rounded-md border border-default bg-elevated/70 text-primary"
        >
          <UIcon :name="pageShell.icon" class="size-5" />
        </span>

        <div class="min-w-0 space-y-2">
          <div
            class="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-toned"
          >
            <span>{{ pageShell.sectionLabel }}</span>
            <span>/</span>
            <span>{{ pageShell.pageLabel }}</span>
          </div>

          <p class="max-w-3xl text-sm text-toned">{{ pageShell.description }}</p>
        </div>
      </div>

      <div class="flex min-w-0 flex-wrap items-center justify-end gap-2 xl:justify-end">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-copy"
          :disabled="isLoading || !report"
          @click="copyDiagnostics"
        >
          Copy
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
          Refresh
        </UButton>
      </div>
    </div>

    <div
      v-if="!report && isLoading"
      class="flex min-h-72 items-center justify-center rounded-md border border-default bg-default/90"
    >
      <div class="flex flex-col items-center gap-3 text-center text-toned">
        <UIcon name="i-lucide-loader-circle" class="size-10 animate-spin text-info" />
        <div class="space-y-1">
          <p class="text-sm font-medium text-default">Loading</p>
          <p class="text-xs">Reading tools, paths, and configured extras.</p>
        </div>
      </div>
    </div>

    <UAlert
      v-else-if="!report && lastError"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      title="Diagnostics failed"
      :description="lastError"
    />

    <template v-else-if="report">
      <UAlert
        v-if="showRequiredAlert"
        color="error"
        variant="soft"
        icon="i-lucide-octagon-alert"
        title="Required items missing"
        :description="requiredAlertDescription"
      />

      <section class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-gauge" class="size-4 text-toned" />
          <span>Overview</span>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article
            v-for="item in summaryCards"
            :key="item.label"
            class="rounded-md border border-default bg-default px-3 py-3 shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs font-medium uppercase tracking-wide text-toned">
                  {{ item.label }}
                </p>
                <p class="mt-1 text-xs text-toned">{{ item.description }}</p>
              </div>

              <span
                class="inline-flex size-8 shrink-0 items-center justify-center rounded-md border border-default bg-default"
              >
                <UIcon :name="item.icon" class="size-4 text-toned" />
              </span>
            </div>

            <p :class="['mt-4 text-2xl font-semibold', item.valueClass]">{{ item.value }}</p>
          </article>
        </div>
      </section>

      <section class="space-y-3">
        <div class="flex items-center gap-2 text-sm font-semibold text-highlighted">
          <UIcon name="i-lucide-server" class="size-4 text-toned" />
          <span>Runtime</span>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="row in runtimeRows"
            :key="row.label"
            class="rounded-md border border-default bg-default px-3 py-3 shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs font-medium uppercase tracking-wide text-toned">
                  {{ row.label }}
                </p>
                <p class="mt-1 text-xs text-toned">{{ row.description }}</p>
              </div>

              <span
                class="inline-flex size-8 shrink-0 items-center justify-center rounded-md border border-default bg-default"
              >
                <UIcon :name="row.icon" class="size-4 text-toned" />
              </span>
            </div>

            <p class="mt-4 wrap-break-word text-sm font-semibold text-default">{{ row.value }}</p>
          </article>
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
            class="rounded-md border border-default bg-default px-4 py-4 shadow-sm"
          >
            <div class="min-w-0 space-y-3">
              <div class="space-y-2">
                <div class="flex flex-wrap items-center gap-2">
                  <span :class="tagDotClass(item.status)"></span>
                  <p class="text-base font-semibold text-default">{{ item.label }}</p>
                  <span
                    class="inline-flex items-center rounded-md border border-default px-2 py-1 text-xs text-toned"
                  >
                    {{ item.required ? 'Required' : 'Optional' }}
                  </span>
                </div>

                <p v-if="item.description" class="text-sm text-toned">{{ item.description }}</p>
                <p v-if="showMessage(item)" class="text-sm leading-6 text-default">
                  {{ item.message }}
                </p>
              </div>

              <div v-if="Object.keys(item.details || {}).length > 0" class="flex flex-wrap gap-2">
                <span
                  v-for="(value, key) in item.details"
                  :key="`${item.id}-${key}`"
                  class="inline-flex items-center gap-1 rounded-md border border-default px-2 py-1 text-xs text-toned"
                >
                  <span class="font-medium text-default">{{ keyLabel(key) }}:</span>
                  <span>{{ formatValue(value) }}</span>
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
import type { DiagnosticCheck, DiagnosticStatus } from '~/types/diagnostics';
import { requirePageShell } from '~/utils/topLevelNavigation';
import { copyText } from '~/utils';

type SummaryCard = {
  label: string;
  description: string;
  value: number;
  icon: string;
  valueClass: string;
};

type DetailRow = {
  label: string;
  description: string;
  value: string;
  icon: string;
};

type FeatureMeta = {
  label: string;
  description: string;
  icon: string;
};

type FeatureSection = FeatureMeta & {
  id: string;
  items: Array<DiagnosticCheck>;
};

const FEATURE_META: Record<string, FeatureMeta> = {
  core: {
    label: 'Core setup',
    description: 'Main tools and local paths.',
    icon: 'i-lucide-wrench',
  },
  youtube: {
    label: 'YouTube',
    description: 'Support needed for YouTube downloads.',
    icon: 'i-lucide-video',
  },
  notifications: {
    label: 'Notifications',
    description: 'Apprise support.',
    icon: 'i-lucide-bell',
  },
  advanced: {
    label: 'Advanced',
    description: 'Optional tools, transports, browser extractor, and plugins.',
    icon: 'i-lucide-plug-zap',
  },
  custom: {
    label: 'Custom pip packages',
    description: 'Packages requested through config.',
    icon: 'i-lucide-package-plus',
  },
};

const FEATURE_ORDER = ['core', 'youtube', 'notifications', 'advanced', 'custom'];

const pageShell = requirePageShell('diagnostics');
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
  return FEATURE_ORDER.filter((id) => (groupedChecks.value[id] ?? []).length > 0).map((id) => ({
    id,
    ...FEATURE_META[id]!,
    items: groupedChecks.value[id] ?? [],
  }));
});

const summaryCards = computed<Array<SummaryCard>>(() => {
  const current = report.value;
  if (!current) {
    return [];
  }

  return [
    {
      label: 'Passing',
      description: 'Checks that passed.',
      value: current.summary.pass,
      icon: 'i-lucide-badge-check',
      valueClass: current.summary.pass > 0 ? 'text-success' : 'text-default',
    },
    {
      label: 'Required fails',
      description: 'Items that block core use.',
      value: current.summary.required_failed,
      icon: 'i-lucide-octagon-alert',
      valueClass: current.summary.required_failed > 0 ? 'text-error' : 'text-default',
    },
    {
      label: 'Warnings',
      description: 'Optional or incomplete items.',
      value: current.summary.warn,
      icon: 'i-lucide-triangle-alert',
      valueClass: current.summary.warn > 0 ? 'text-warning' : 'text-default',
    },
    {
      label: 'Skipped',
      description: 'Not configured or not needed.',
      value: current.summary.skip,
      icon: 'i-lucide-minus',
      valueClass: current.summary.skip > 0 ? 'text-toned' : 'text-default',
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
      label: 'App',
      description: 'Current build.',
      value: runtime.app_version || 'Unknown',
      icon: 'i-lucide-package',
    },
    {
      label: 'Host',
      description: 'OS and machine.',
      value: `${runtime.platform} ${runtime.platform_release} (${runtime.platform_machine})`,
      icon: 'i-lucide-server',
    },
    {
      label: 'Python',
      description: `${python.note} Minimum ${python.required}+`,
      value: python.current,
      icon: 'i-lucide-square-terminal',
    },
  ];
});

const shareText = computed(() => {
  const current = report.value;
  if (!current) {
    return '';
  }

  const lines = [
    'YTPTube diagnostics',
    `Generated: ${formatIsoTimestamp(current.generated_at)}`,
    '',
  ];

  lines.push('Overview');
  for (const item of summaryCards.value) {
    lines.push(`- ${item.label}: ${item.value}`);
  }

  lines.push('', 'Runtime');
  lines.push(`- App: ${current.runtime.app_version || 'Unknown'}`);
  lines.push(
    `- Host: ${current.runtime.platform} ${current.runtime.platform_release} (${current.runtime.platform_machine})`,
  );
  lines.push(`- Python: ${current.requirements.python.current}`);
  lines.push(`- Started: ${formatIsoTimestamp(current.runtime.started)}`);

  for (const section of featureSections.value) {
    lines.push('', section.label);

    for (const item of section.items) {
      const versionSuffix = formatShareVersion(item);
      lines.push(
        `- [${statusLabel(item.status)}] ${item.label} (${item.required ? 'Required' : 'Optional'})${versionSuffix}`,
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

const statusLabel = (status: DiagnosticStatus): string => {
  switch (status) {
    case 'pass':
      return 'PASS';
    case 'fail':
      return 'FAIL';
    case 'warn':
      return 'WARN';
    case 'skip':
    default:
      return 'SKIP';
  }
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
