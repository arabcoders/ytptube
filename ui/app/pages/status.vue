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
        <UTooltip
          :text="connected ? t('status.clickToDisconnect') : t('status.clickToReconnect')"
          v-if="!monitorDisabled"
        >
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-toned transition-colors hover:bg-elevated/60 hover:text-default"
            @click="toggleStream"
          >
            <span
              :class="[
                'inline-flex size-2 shrink-0 rounded-full',
                connected ? 'bg-success' : 'bg-muted',
              ]"
            ></span>
            <span>{{ connected ? t('common.live') : t('common.offline') }}</span>
          </button>
        </UTooltip>
      </div>
    </div>

    <UAlert
      v-if="monitorDisabled"
      color="warning"
      variant="soft"
      icon="i-lucide-info"
      :title="t('status.monitoringDisabled')"
      :description="t('status.monitoringDisabledDesc')"
    />

    <UAlert
      v-else-if="!sample && isLoading"
      color="info"
      variant="soft"
      icon="i-lucide-loader-circle"
      :title="t('common.loading')"
      :description="t('status.loadingDesc')"
    />

    <UAlert
      v-else-if="!sample && lastError"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="t('status.failedLoad')"
      :description="lastError"
    />

    <template v-else-if="sample">
      <section class="space-y-3">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 text-start text-sm font-semibold text-highlighted"
          @click="toggleSection('resources')"
        >
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-activity" class="size-4 text-toned" />
            <span>{{ t('status.resources') }}</span>
          </div>
          <UIcon
            name="i-lucide-chevron-right"
            :class="[
              'size-4 text-toned transition-transform',
              isOpen('resources') ? 'rotate-90' : '',
            ]"
          />
        </button>

        <div v-if="isOpen('resources')" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            :label="t('status.appCpu')"
            :value="fmtPct(sample.process_cpu_percent)"
            :hint="cpuHint"
            icon="i-lucide-cpu"
            :color="cpuColor"
            value-wrap
          />
          <StatCard
            :label="t('status.memory')"
            :value="fmtMb(sample.rss_mb)"
            :hint="memoryHint"
            icon="i-lucide-memory-stick"
            :color="memoryColor"
            value-wrap
          />
          <StatCard
            :label="t('status.diskIo')"
            :value="fmtBps(diskReadBps)"
            :hint="
              t('status.diskIoHint', { read: fmtBps(diskReadBps), write: fmtBps(diskWriteNow) })
            "
            icon="i-lucide-hard-drive"
            color="neutral"
            value-wrap
          />
          <StatCard
            :label="t('status.network')"
            :value="fmtBps(networkTotalBps)"
            :hint="networkHint"
            icon="i-lucide-globe"
            color="neutral"
            value-wrap
          />
        </div>
      </section>

      <UAlert
        v-if="showBottleneckAlert"
        :color="bottleneckColor"
        variant="soft"
        :icon="bottleneckIcon"
        :title="bottleneckTitle"
        :description="bottleneckDescription"
      />

      <section class="space-y-3">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 text-start text-sm font-semibold text-highlighted"
          @click="toggleSection('appState')"
        >
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-layers" class="size-4 text-toned" />
            <span>{{ t('status.appState') }}</span>
          </div>
          <UIcon
            name="i-lucide-chevron-right"
            :class="[
              'size-4 text-toned transition-transform',
              isOpen('appState') ? 'rotate-90' : '',
            ]"
          />
        </button>

        <div v-if="isOpen('appState')" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-7">
          <StatCard
            :label="t('common.active')"
            :value="String(sample.active_jobs)"
            :hint="t('common.downloading')"
            icon="i-lucide-play"
            :color="sample.active_jobs > 0 ? 'info' : 'neutral'"
          />
          <StatCard
            :label="t('common.queued')"
            :value="String(sample.queued_jobs)"
            :hint="t('status.waiting')"
            icon="i-lucide-hourglass"
            color="neutral"
          />
          <StatCard
            :label="t('status.pool')"
            :value="sample.is_paused ? t('common.paused') : t('common.running')"
            :hint="t('status.workerState')"
            icon="i-lucide-pause-circle"
            :color="sample.is_paused ? 'warning' : 'success'"
          />
          <StatCard
            :label="t('status.workers')"
            :value="fmtNum(workerCount)"
            :hint="t('status.subprocesses')"
            icon="i-lucide-container"
            :color="workerCount > 0 ? 'info' : 'neutral'"
          />
          <StatCard
            :label="t('status.uptime')"
            :value="fmtUptime(sample.uptime_seconds)"
            icon="i-lucide-clock"
            color="neutral"
            value-wrap
          />
          <StatCard
            :label="t('common.threads')"
            :value="fmtNum(sample.threads)"
            :hint="t('status.processTree')"
            icon="i-lucide-split"
            color="neutral"
          />
          <StatCard
            :label="t('status.handles')"
            :value="fmtNum(sample.open_files)"
            :hint="connectionsHint"
            icon="i-lucide-link"
            color="neutral"
          />
        </div>
      </section>

      <section v-if="sample.children.length > 0" class="space-y-3">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 text-start text-sm font-semibold text-highlighted"
          @click="toggleSection('children')"
        >
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-container" class="size-4 text-toned" />
            <span>{{ t('status.childProcesses', { count: workerCount }) }}</span>
          </div>
          <UIcon
            name="i-lucide-chevron-right"
            :class="[
              'size-4 text-toned transition-transform',
              isOpen('children') ? 'rotate-90' : '',
            ]"
          />
        </button>

        <div v-if="isOpen('children')" class="overflow-x-auto rounded-lg border border-default">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-default bg-elevated/40">
                <th class="px-3 py-2 text-start font-medium text-highlighted">
                  {{ t('status.process') }}
                </th>
                <th class="px-3 py-2 text-start font-medium text-highlighted">
                  {{ t('status.pid') }}
                </th>
                <th class="px-3 py-2 text-start font-medium text-highlighted">
                  {{ t('status.cpu') }}
                </th>
                <th class="px-3 py-2 text-start font-medium text-highlighted">
                  {{ t('status.rss') }}
                </th>
                <th class="px-3 py-2 text-start font-medium text-highlighted">
                  {{ t('common.threads') }}
                </th>
                <th class="px-3 py-2 text-start font-medium text-highlighted">
                  {{ t('common.status') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="child in sample.children"
                :key="child.pid"
                class="border-b border-default last:border-b-0"
              >
                <td class="px-3 py-2 text-default font-medium">
                  <p class="max-w-80 truncate" :title="childDisplayName(child)">
                    {{ childDisplayName(child) }}
                  </p>
                  <p
                    v-if="childMeta(child)"
                    class="max-w-80 truncate text-xs font-normal text-toned"
                    :title="childMeta(child)"
                  >
                    {{ childMeta(child) }}
                  </p>
                </td>
                <td class="px-3 py-2 text-toned">{{ child.pid }}</td>
                <td class="px-3 py-2 text-toned">{{ fmtPct(child.cpu_percent) }}</td>
                <td class="px-3 py-2 text-toned">{{ fmtMb(child.rss_mb) }}</td>
                <td class="px-3 py-2 text-toned">
                  <p>{{ fmtNum(child.threads) }}</p>
                  <p
                    v-if="threadNames(child)"
                    class="max-w-56 truncate text-xs text-muted"
                    :title="threadNames(child)"
                  >
                    {{ threadNames(child) }}
                  </p>
                </td>
                <td class="px-3 py-2 text-toned">{{ child.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="space-y-3">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 text-start text-sm font-semibold text-highlighted"
          @click="toggleSection('diskUsage')"
        >
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-hard-drive" class="size-4 text-toned" />
            <span>{{ t('status.diskUsage') }}</span>
          </div>
          <UIcon
            name="i-lucide-chevron-right"
            :class="[
              'size-4 text-toned transition-transform',
              isOpen('diskUsage') ? 'rotate-90' : '',
            ]"
          />
        </button>

        <div v-if="isOpen('diskUsage')" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <StatCard
            v-for="(disk, path) in sample.disk_usage"
            :key="String(path)"
            :label="diskLabel(String(path), disk)"
            :value="`${disk.used_percent}%`"
            :hint="
              t('status.diskFree', { free: fmtGib(disk.free_gb), total: fmtGib(disk.total_gb) })
            "
            icon="i-lucide-folder"
            :color="
              disk.used_percent > 90 ? 'error' : disk.used_percent > 75 ? 'warning' : 'neutral'
            "
          />
        </div>
      </section>

      <section class="space-y-3">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 text-start text-sm font-semibold text-highlighted"
          @click="toggleSection('charts')"
        >
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-chart-area" class="size-4 text-toned" />
            <span>{{ t('status.charts') }}</span>
          </div>
          <UIcon
            name="i-lucide-chevron-right"
            :class="['size-4 text-toned transition-transform', isOpen('charts') ? 'rotate-90' : '']"
          />
        </button>

        <div v-if="isOpen('charts')" class="grid gap-4 lg:grid-cols-2">
          <div class="ytp-card bg-elevated/40 p-4">
            <Chart
              :label="t('status.cpuPercent')"
              icon="i-lucide-cpu"
              :values="historyCpu"
              :timestamps="historyTimestamps"
              color="info"
              :format-value="fmtChartPct"
            />
          </div>
          <div class="ytp-card bg-elevated/40 p-4">
            <Chart
              :label="t('status.memoryMb')"
              icon="i-lucide-memory-stick"
              :values="historyMem"
              :timestamps="historyTimestamps"
              color="warning"
              :format-value="fmtChartMb"
            />
          </div>
          <div class="ytp-card bg-elevated/40 p-4">
            <Chart
              :label="t('status.diskWrite')"
              icon="i-lucide-hard-drive"
              :values="historyDiskWrite"
              :timestamps="historyTimestamps"
              color="neutral"
              :format-value="fmtChartBps"
            />
          </div>
          <div class="ytp-card bg-elevated/40 p-4">
            <Chart
              :label="t('status.networkRecv')"
              icon="i-lucide-globe"
              :values="historyNetRecv"
              :timestamps="historyTimestamps"
              color="neutral"
              :format-value="fmtChartBps"
            />
          </div>
        </div>
      </section>

      <section v-if="bottlenecks && bottlenecks.bottlenecks.length > 0" class="space-y-3">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-2 text-start text-sm font-semibold text-highlighted"
          @click="toggleSection('diagnosis')"
        >
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-search" class="size-4 text-toned" />
            <span>{{ t('status.diagnosis') }}</span>
          </div>
          <UIcon
            name="i-lucide-chevron-right"
            :class="[
              'size-4 text-toned transition-transform',
              isOpen('diagnosis') ? 'rotate-90' : '',
            ]"
          />
        </button>

        <div v-if="isOpen('diagnosis')" class="space-y-3">
          <div
            v-for="item in bottlenecks.bottlenecks"
            :key="item.type"
            class="ytp-card bg-elevated/40 p-4"
          >
            <div class="flex items-start gap-3">
              <span :class="bottleneckDotClass(item.level)"></span>
              <div class="min-w-0 space-y-1">
                <p class="text-sm font-semibold text-default">{{ item.summary }}</p>
                <p class="text-sm text-toned">{{ item.details }}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <UAlert color="info" variant="soft">
        <template #description>
          <ul class="list-disc space-y-2 ps-5 text-sm text-default">
            <li v-html="t('status.helpAppCpu')"></li>
            <li v-html="t('status.helpSystemCpu')"></li>
            <li v-html="t('status.helpRss')"></li>
            <li v-html="t('status.helpUss')"></li>
            <li v-html="t('status.helpHandles')"></li>
            <li v-html="t('status.helpDiskIo')"></li>
            <li v-html="t('status.helpChildren')"></li>
            <li v-html="t('status.helpPool')"></li>
            <li v-html="t('status.helpBottlenecks')"></li>
          </ul>
        </template>
      </UAlert>
    </template>
  </main>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core';
import StatCard from '~/components/StatCard.vue';
import Chart from '~/components/Chart.vue';
import type { ChildProcess } from '~/types/stats';
import { usePageShell } from '~/composables/usePageShell';
const { t } = useI18n();

const pageShell = usePageShell('status');
const statsState = useStats();
const config = useYtpConfig();

const sample = computed(() => statsState.latest.value);
const bottlenecks = computed(() => statsState.bottlenecks.value);
const connected = computed(() => statsState.connected.value);
const isLoading = statsState.isLoading;
const lastError = statsState.lastError;

const monitorDisabled = computed(() => !config.app.monitor_enabled);

const openSections = useStorage<string[]>('status_open_sections', [
  'resources',
  'appState',
  'diskUsage',
]);

const isOpen = (id: string): boolean => openSections.value.includes(id);
const toggleSection = (id: string): void => {
  if (isOpen(id)) {
    openSections.value = openSections.value.filter((s) => s !== id);
  } else {
    openSections.value = [...openSections.value, id];
  }
};

// Bottleneck alert
const showBottleneckAlert = computed(() => {
  const b = bottlenecks.value;
  return b && b.status === 'attention' && b.bottlenecks.length > 0;
});

const bottleneckColor = computed<'error' | 'warning' | 'info'>(() => {
  const levels = bottlenecks.value?.bottlenecks.map((b) => b.level) ?? [];
  if (levels.includes('critical')) return 'error';
  if (levels.includes('warning')) return 'warning';
  return 'info';
});

const bottleneckIcon = computed(() => {
  if (bottleneckColor.value === 'error') return 'i-lucide-octagon-alert';
  if (bottleneckColor.value === 'warning') return 'i-lucide-triangle-alert';
  return 'i-lucide-info';
});

const bottleneckTitle = computed(() => {
  const count = bottlenecks.value?.bottlenecks.length ?? 0;
  if (count > 1) return t('status.possibleIssues', { count });
  return '';
});

const bottleneckDescription = computed(() => {
  return bottlenecks.value?.bottlenecks[0]?.summary ?? '';
});

// Derived values
const diskReadBps = computed(() => sample.value?.disk_read_bps ?? 0);
const diskWriteNow = computed(() => sample.value?.disk_write_bps ?? 0);
const networkTotalBps = computed(() => {
  const s = sample.value;
  if (!s) return 0;
  return (s.network_recv_bps ?? 0) + (s.network_sent_bps ?? 0);
});

const workerCount = computed(() => {
  const s = sample.value;
  return s?.children_count ?? s?.children.length ?? 0;
});

const networkHint = computed(() => {
  const s = sample.value;
  if (!s) return '';
  return t('status.networkStats', {
    down: fmtBps(s.network_recv_bps),
    up: fmtBps(s.network_sent_bps),
  });
});

const cpuHint = computed(() => {
  const s = sample.value;
  if (!s) return '';
  let hint = t('status.systemCpuHint', { value: fmtPct(s.system_cpu_percent) });
  const limit = s.cpu_limit;
  if (limit) hint += ` / ${t('common.limit')} ${limit}`;
  if (workerCount.value > 0) hint += ` / ${t('status.workers')} ${workerCount.value}`;
  return hint;
});

const cpuColor = computed<'error' | 'warning' | 'neutral'>(() => {
  const v = sample.value?.process_cpu_percent ?? 0;
  if (v >= 90) return 'error';
  if (v >= 70) return 'warning';
  return 'neutral';
});

const memoryColor = computed<'error' | 'warning' | 'neutral'>(() => {
  const pct = memoryPercent.value;
  if (pct && pct >= 90) return 'error';
  if (pct && pct >= 70) return 'warning';
  return 'neutral';
});

const memoryPercent = computed(() => {
  const cg = sample.value?.cgroup_memory;
  if (cg?.available && cg.working_set_percent != null) {
    return cg.working_set_percent;
  }
  return sample.value?.memory_percent ?? null;
});

const memoryHint = computed(() => {
  const s = sample.value;
  if (!s) return '';
  const parts: string[] = [];
  if (s.uss_mb) parts.push(`USS ${fmtMb(s.uss_mb)}`);
  const memPct = memoryPercent.value;
  if (memPct) parts.push(`${memPct}%`);
  return parts.join('  ');
});

const connectionsHint = computed(() => {
  const conn = sample.value?.connections;
  if (conn == null) return '';
  return t('status.connections', { count: conn });
});

// Sparkline data (last 60 samples)
const historyCpu = computed(() => {
  return statsState.history.value.slice(-60).map((s) => s.process_cpu_percent);
});
const historyMem = computed(() => {
  return statsState.history.value.slice(-60).map((s) => s.rss_mb ?? 0);
});
const historyDiskWrite = computed(() => {
  return statsState.history.value.slice(-60).map((s) => s.disk_write_bps ?? 0);
});
const historyNetRecv = computed(() => {
  return statsState.history.value.slice(-60).map((s) => s.network_recv_bps ?? 0);
});

const historyTimestamps = computed(() => {
  return statsState.history.value.slice(-60).map((s) => s.ts);
});

// Helpers
const fmtPct = (v: number | null | undefined): string => {
  if (v == null) return '\u2014';
  return `${Math.round(v)}%`;
};

const fmtMb = (v: number | null | undefined): string => {
  if (v == null) return '\u2014';
  if (v >= 1024 * 1024) return `${(v / 1024 / 1024).toFixed(1)} ${t('common.tib')}`;
  if (v >= 1024) return `${(v / 1024).toFixed(1)} ${t('common.gib')}`;
  return `${Math.round(v)} ${t('common.mib')}`;
};

const fmtGib = (v: number | null | undefined): string => {
  if (v == null) return '\u2014';
  if (v >= 1024) return `${(v / 1024).toFixed(2)} ${t('common.tib')}`;
  return `${Math.round(v)} ${t('common.gib')}`;
};

const fmtBps = (v: number | null | undefined): string => {
  if (v == null || v === 0) return `0 ${t('common.bytes')}${t('common.perSec')}`;
  const GIB = 1024 * 1024 * 1024;
  const TIB = GIB * 1024;
  if (v >= TIB) return `${(v / TIB).toFixed(1)} ${t('common.tib')}${t('common.perSec')}`;
  if (v >= GIB) return `${(v / GIB).toFixed(1)} ${t('common.gib')}${t('common.perSec')}`;
  if (v >= 1024 * 1024)
    return `${(v / 1024 / 1024).toFixed(1)} ${t('common.mib')}${t('common.perSec')}`;
  if (v >= 1024) return `${(v / 1024).toFixed(1)} ${t('common.kib')}${t('common.perSec')}`;
  return `${Math.round(v)} ${t('common.bytes')}${t('common.perSec')}`;
};

const fmtUptime = (seconds: number): string => {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0)
    return `${d}${t('common.dayAbbr')} ${h}${t('common.hourAbbr')} ${m}${t('common.minAbbr')}`;
  if (h > 0) return `${h}${t('common.hourAbbr')} ${m}${t('common.minAbbr')}`;
  return `${m}${t('common.minAbbr')}`;
};

const fmtNum = (v: number | null | undefined): string => {
  if (v == null) return '\u2014';
  return String(v);
};

const childDisplayName = (child: ChildProcess): string => child.display_name || child.name;

const childMeta = (child: ChildProcess): string => {
  const parts: string[] = [];
  if (child.display_name && child.display_name !== child.name) parts.push(child.name);
  if (child.cmdline && child.cmdline !== child.name && child.cmdline !== child.display_name) {
    parts.push(child.cmdline);
  }
  return parts.join('  ');
};

const threadNames = (child: ChildProcess): string =>
  child.thread_names?.filter(Boolean).join(', ') ?? '';

const fmtChartPct = (v: number): string => `${Math.round(v)}%`;
const fmtChartMb = (v: number): string => {
  if (v >= 1024 * 1024) return `${(v / 1024 / 1024).toFixed(1)}${t('common.tib')[0]}`;
  if (v >= 1024) return `${(v / 1024).toFixed(1)}${t('common.gib')[0]}`;
  return `${Math.round(v)}${t('common.mib')[0]}`;
};
const fmtChartBps = (v: number): string => {
  const GIB = 1024 * 1024 * 1024;
  const TIB = GIB * 1024;
  if (v >= TIB) return `${(v / TIB).toFixed(1)}${t('common.tib')[0]}`;
  if (v >= GIB) return `${(v / GIB).toFixed(1)}${t('common.gib')[0]}`;
  if (v >= 1024 * 1024) return `${(v / 1024 / 1024).toFixed(1)}${t('common.mib')[0]}`;
  if (v >= 1024) return `${(v / 1024).toFixed(1)}${t('common.kib')[0]}`;
  return `${Math.round(v)}`;
};

const diskLabel = (path: string, disk?: { label?: string; role?: string }): string => {
  if (disk?.role === 'temp') return t('status.diskTemp');
  if (disk?.role === 'config') return t('status.diskConfig');
  if (disk?.role === 'downloads') return t('common.downloads');

  const value = path.toLowerCase().replace(/\/+$/, '');
  if (value.endsWith('/tmp') || value.includes('/tmp/') || value.includes('temp'))
    return t('status.diskTemp');
  if (value.endsWith('/config') || value.includes('/config/') || value.includes('config'))
    return t('status.diskConfig');
  if (value.endsWith('/downloads') || value.includes('download')) return t('common.downloads');
  return disk?.label || path;
};

const bottleneckDotClass = (level: string): string => {
  const base = 'mt-0.5 inline-flex size-2.5 shrink-0 rounded-full';
  if (level === 'critical' || level === 'error') return `${base} bg-error`;
  if (level === 'warning') return `${base} bg-warning`;
  return `${base} bg-info`;
};

onMounted(async () => {
  if (!config.app.monitor_enabled) return;
  await statsState.fetchHistory();
  await statsState.fetchBottlenecks();
  statsState.connect();
});

onUnmounted(() => {
  statsState.disconnect();
});

const toggleStream = () => {
  if (statsState.connected.value) {
    statsState.disconnect();
  } else {
    statsState.connect();
  }
};
</script>
