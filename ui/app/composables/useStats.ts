import { readonly, ref } from 'vue';
import { parse_api_error, parse_api_response, request } from '~/utils';
import type { StatsSample, StatsHistorySample, BottlenecksResponse } from '~/types/stats';

const latest = ref<StatsSample | null>(null);
const history = ref<StatsHistorySample[]>([]);
const bottlenecks = ref<BottlenecksResponse | null>(null);
const isLoading = ref(false);
const lastError = ref<string | null>(null);
const connected = ref(false);
const throwInstead = ref(false);

const MAX_HISTORY = 900;
let _es: EventSource | null = null;

const readJson = async (response: Response): Promise<unknown> => {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
};

const ensureSuccess = async (response: Response): Promise<void> => {
  if (response.ok) return;
  const payload = await readJson(response);
  throw new Error(await parse_api_error(payload));
};

const handleError = (error: unknown): void => {
  const { $i18n } = useNuxtApp();
  const t = $i18n?.t ?? ((key: string) => key);
  const message = error instanceof Error ? error.message : t('common.failedFetch');
  lastError.value = message;
};

const _toHistorySample = (s: StatsSample): StatsHistorySample => ({
  ts: s.ts,
  process_cpu_percent: s.process_cpu_percent,
  system_cpu_percent: s.system_cpu_percent,
  rss_mb: s.rss_mb,
  uss_mb: s.uss_mb,
  memory_percent: s.memory_percent,
  process_read_bps: s.process_read_bps,
  process_write_bps: s.process_write_bps,
  disk_read_bps: s.disk_read_bps,
  disk_write_bps: s.disk_write_bps,
  network_recv_bps: s.network_recv_bps,
  network_sent_bps: s.network_sent_bps,
  threads: s.threads,
  open_files: s.open_files,
  connections: s.connections,
  active_jobs: s.active_jobs,
  queued_jobs: s.queued_jobs,
  is_paused: s.is_paused ? 1 : 0,
  children_count: s.children_count ?? s.children.length,
});

const fetchLatest = async (): Promise<void> => {
  isLoading.value = true;
  try {
    const response = await request('/api/stats/latest');
    await ensureSuccess(response);
    const body = await response.clone().json();
    // /api/stats/latest returns the sample directly, or {} when no data yet.
    const sample =
      body != null && typeof body === 'object' && 'ts' in body ? (body as StatsSample) : null;
    if (sample) {
      latest.value = sample;
      _appendHistory(sample);
    }
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const fetchHistory = async (range: string = '30m'): Promise<void> => {
  isLoading.value = true;
  lastError.value = null;
  try {
    const response = await request(`/api/stats/history?range=${range}`);
    await ensureSuccess(response);
    const body = await response.clone().json();
    // /api/stats/history returns the samples array directly.
    const items: StatsHistorySample[] = Array.isArray(body) ? (body as StatsHistorySample[]) : [];
    if (items.length > 0) {
      history.value = items.slice(-MAX_HISTORY);
      // Prime latest from last history entry so cards show immediately, SSE replaces it live.
      if (!latest.value) {
        const last = items[items.length - 1]!;
        latest.value = {
          ts: last.ts,
          process_cpu_percent: last.process_cpu_percent,
          system_cpu_percent: last.system_cpu_percent,
          cpu_limit: null,
          effective_cpu_count: 0,
          rss_mb: last.rss_mb,
          uss_mb: last.uss_mb,
          vms_mb: null,
          memory_percent: last.memory_percent,
          cgroup_memory: null,
          process_read_bps: last.process_read_bps,
          process_write_bps: last.process_write_bps,
          process_io_available: false,
          disk_read_bps: last.disk_read_bps,
          disk_write_bps: last.disk_write_bps,
          disk_usage: {},
          network_recv_bps: last.network_recv_bps,
          network_sent_bps: last.network_sent_bps,
          threads: last.threads,
          open_files: last.open_files,
          connections: last.connections,
          children: [],
          children_count: last.children_count,
          active_jobs: last.active_jobs,
          queued_jobs: last.queued_jobs,
          is_paused: last.is_paused === 1,
          uptime_seconds: 0,
        };
      }
    }
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const _appendHistory = (s: StatsSample): void => {
  history.value = [...history.value, _toHistorySample(s)].slice(-MAX_HISTORY);
};

const connect = (): void => {
  if (_es) return;

  const baseUrl = window.location.origin;
  _es = new EventSource(`${baseUrl}/api/stats/stream`);
  connected.value = true;

  _es.addEventListener('sample', (event: MessageEvent) => {
    try {
      const sample: StatsSample = JSON.parse(event.data) as StatsSample;
      latest.value = sample;
      _appendHistory(sample);
      lastError.value = null;
    } catch {
      // Ignore parse errors.
    }
  });

  _es.addEventListener('bottleneck', (event: MessageEvent) => {
    try {
      bottlenecks.value = JSON.parse(event.data) as BottlenecksResponse;
    } catch {
      // Ignore parse errors.
    }
  });

  _es.addEventListener('error', () => {
    const { $i18n } = useNuxtApp();
    const t = $i18n?.t ?? ((key: string) => key);
    connected.value = false;
    lastError.value = t('common.streamConnectionLost');
    disconnect();
    // Auto-reconnect after a delay.
    setTimeout(() => {
      if (!_es) connect();
    }, 5000);
  });

  _es.onopen = () => {
    connected.value = true;
    lastError.value = null;
  };
};

const disconnect = (): void => {
  if (_es) {
    _es.close();
    _es = null;
  }
  connected.value = false;
};

const fetchBottlenecks = async (): Promise<void> => {
  isLoading.value = true;
  lastError.value = null;
  try {
    const response = await request('/api/stats/bottlenecks');
    await ensureSuccess(response);
    bottlenecks.value = await parse_api_response<BottlenecksResponse>(response.json());
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const clearError = (): void => {
  lastError.value = null;
};

const __resetForTesting = (): void => {
  disconnect();
  latest.value = null;
  history.value = [];
  bottlenecks.value = null;
  isLoading.value = false;
  lastError.value = null;
  connected.value = false;
  throwInstead.value = false;
};

const _btlScenarios: Record<string, () => BottlenecksResponse> = {
  cpu: () => ({
    status: 'attention',
    window_samples: 30,
    averages: {
      process_cpu_percent: 92,
      system_cpu_percent: 80,
      memory_percent: 45,
      process_read_mbps: 2.1,
      process_write_mbps: 8.3,
      disk_read_mbps: 4.5,
      disk_write_mbps: 12.1,
      network_recv_mbps: 1.5,
      network_sent_mbps: 0.8,
      active_jobs: 4,
    },
    bottlenecks: [
      {
        type: 'cpu',
        level: 'critical',
        summary: 'App CPU usage is high.',
        details:
          'Average app CPU usage was 92% over the last 30 samples. 4 active downloads were running.',
      },
    ],
  }),
  memory: () => ({
    status: 'attention',
    window_samples: 30,
    averages: {
      process_cpu_percent: 35,
      system_cpu_percent: 50,
      memory_percent: 88,
      process_read_mbps: 3.1,
      process_write_mbps: 15.2,
      disk_read_mbps: 6.3,
      disk_write_mbps: 28.7,
      network_recv_mbps: 0.9,
      network_sent_mbps: 0.3,
      active_jobs: 2,
    },
    bottlenecks: [
      {
        type: 'memory',
        level: 'warning',
        summary: 'Memory pressure is high.',
        details: 'Average memory usage was 88% over the last 30 samples.',
      },
    ],
  }),
  io: () => ({
    status: 'attention',
    window_samples: 30,
    averages: {
      process_cpu_percent: 28,
      system_cpu_percent: 42,
      memory_percent: 52,
      process_read_mbps: 4.2,
      process_write_mbps: 86.5,
      disk_read_mbps: 44.1,
      disk_write_mbps: 112.3,
      network_recv_mbps: 2.1,
      network_sent_mbps: 1.4,
      active_jobs: 3,
    },
    bottlenecks: [
      {
        type: 'process_io_write',
        level: 'warning',
        summary: 'The app appears to be write I/O bound.',
        details: 'App write rate averaged 86.5 MB/s while CPU averaged 28%.',
      },
      {
        type: 'disk_write',
        level: 'info',
        summary: 'System disk write throughput is high.',
        details: 'Disk write rate averaged 112.3 MB/s.',
      },
    ],
  }),
  network: () => ({
    status: 'attention',
    window_samples: 30,
    averages: {
      process_cpu_percent: 22,
      system_cpu_percent: 35,
      memory_percent: 38,
      process_read_mbps: 1.8,
      process_write_mbps: 6.1,
      disk_read_mbps: 3.2,
      disk_write_mbps: 9.4,
      network_recv_mbps: 72.5,
      network_sent_mbps: 8.3,
      active_jobs: 1,
    },
    bottlenecks: [
      {
        type: 'network_download',
        level: 'info',
        summary: 'Network receive throughput is high.',
        details: 'Network receive rate averaged 72.5 MB/s.',
      },
    ],
  }),
  multi: () => ({
    status: 'attention',
    window_samples: 30,
    averages: {
      process_cpu_percent: 96,
      system_cpu_percent: 88,
      memory_percent: 92,
      process_read_mbps: 5.1,
      process_write_mbps: 94.7,
      disk_read_mbps: 52.3,
      disk_write_mbps: 145.8,
      network_recv_mbps: 68.9,
      network_sent_mbps: 12.4,
      active_jobs: 6,
    },
    bottlenecks: [
      {
        type: 'cpu',
        level: 'critical',
        summary: 'App CPU usage is high.',
        details: 'Average app CPU usage was 96%. 6 active downloads running.',
      },
      {
        type: 'memory',
        level: 'critical',
        summary: 'Memory pressure is high.',
        details: 'Average memory usage was 92%.',
      },
      {
        type: 'process_io_write',
        level: 'warning',
        summary: 'The app appears to be write I/O bound.',
        details: 'App write rate averaged 94.7 MB/s while CPU averaged 96%.',
      },
      {
        type: 'network_download',
        level: 'info',
        summary: 'Network receive throughput is high.',
        details: 'Network receive rate averaged 68.9 MB/s.',
      },
    ],
  }),
  clear: () => ({
    status: 'ok',
    window_samples: 30,
    averages: {
      process_cpu_percent: 15,
      system_cpu_percent: 30,
      memory_percent: 35,
      process_read_mbps: 1.2,
      process_write_mbps: 2.1,
      disk_read_mbps: 3.4,
      disk_write_mbps: 5.6,
      network_recv_mbps: 0.8,
      network_sent_mbps: 0.2,
      active_jobs: 0,
    },
    bottlenecks: [],
  }),
};

const seedBottleneck = (scenario: string): void => {
  const data = _btlScenarios[scenario];
  bottlenecks.value = data ? data() : _btlScenarios.cpu!();
};

const seedSample = (): void => {
  const now = Date.now() / 1000;
  latest.value = {
    ts: now,
    process_cpu_percent: 42,
    system_cpu_percent: 65,
    cpu_limit: 4,
    effective_cpu_count: 4,
    rss_mb: 812,
    uss_mb: 620,
    vms_mb: 1234,
    memory_percent: 58,
    cgroup_memory: null,
    process_read_bps: 2457600,
    process_write_bps: 43122688,
    process_io_available: true,
    disk_read_bps: 6_348_800,
    disk_write_bps: 46_530_560,
    disk_usage: {
      '/downloads': {
        label: 'Downloads',
        role: 'downloads',
        total_gb: 500,
        used_gb: 320,
        free_gb: 180,
        used_percent: 64,
      },
      '/downloads/tmp': {
        label: 'Temp',
        role: 'temp',
        total_gb: 200,
        used_gb: 120,
        free_gb: 80,
        used_percent: 60,
      },
    },
    network_recv_bps: 1_024_000,
    network_sent_bps: 512_000,
    threads: 18,
    open_files: 124,
    connections: 5,
    children: [
      {
        pid: 1,
        name: 'ffmpeg',
        display_name: 'ffmpeg',
        cmdline: 'ffmpeg -i input -c copy output.mp4',
        status: 'running',
        cpu_percent: 180,
        rss_mb: 420,
        threads: 12,
        thread_names: ['ffmpeg-main', 'ffmpeg-worker'],
      },
      {
        pid: 2,
        name: 'python',
        display_name: 'download-demo: Example video',
        cmdline: 'python -m app.main',
        status: 'running',
        cpu_percent: 45,
        rss_mb: 230,
        threads: 8,
        thread_names: ['python', 'status-updates'],
      },
      {
        pid: 3,
        name: 'chromium',
        display_name: 'chromium',
        cmdline: 'chromium --headless',
        status: 'sleeping',
        cpu_percent: 5,
        rss_mb: 580,
        threads: 24,
        thread_names: ['CrBrowserMain', 'Chrome_IOThread'],
      },
    ],
    children_count: 3,
    active_jobs: 3,
    queued_jobs: 18,
    is_paused: false,
    uptime_seconds: 15_600,
  };
};

if (import.meta.client) {
  (window as any).ytpSeedBottleneck = seedBottleneck;
  (window as any).ytpSeedSample = seedSample;
  (window as any).ytpSeedStats = (scenario?: string) => {
    seedSample();
    if (scenario) seedBottleneck(scenario);
  };
}

export const useStats = () => ({
  latest: readonly(latest),
  history: readonly(history),
  bottlenecks: readonly(bottlenecks),
  isLoading: readonly(isLoading),
  lastError: readonly(lastError),
  connected: readonly(connected),
  fetchLatest,
  fetchHistory,
  connect,
  disconnect,
  fetchBottlenecks,
  clearError,
  throwInstead,
  __resetForTesting,
});
