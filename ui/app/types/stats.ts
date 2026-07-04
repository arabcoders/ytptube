export type StatsSample = {
  ts: number;
  process_cpu_percent: number;
  system_cpu_percent: number;
  cpu_limit: number | null;
  effective_cpu_count: number;
  rss_mb: number | null;
  uss_mb: number | null;
  vms_mb: number | null;
  memory_percent: number | null;
  cgroup_memory: CgroupMemory | null;
  process_read_bps: number | null;
  process_write_bps: number | null;
  process_io_available: boolean;
  disk_read_bps: number | null;
  disk_write_bps: number | null;
  disk_usage: Record<string, DiskUsage>;
  network_recv_bps: number | null;
  network_sent_bps: number | null;
  threads: number | null;
  open_files: number | null;
  connections: number | null;
  children: ChildProcess[];
  children_count: number;
  active_jobs: number;
  queued_jobs: number;
  is_paused: boolean;
  uptime_seconds: number;
};

export type CgroupMemory = {
  available: boolean;
  usage_bytes: number | null;
  usage_mb: number | null;
  working_set_bytes: number | null;
  working_set_mb: number | null;
  limit_bytes: number | null;
  limit_mb: number | null;
  usage_percent: number | null;
  working_set_percent: number | null;
};

export type DiskUsage = {
  label?: string;
  role?: string;
  total_gb: number;
  used_gb: number;
  free_gb: number;
  used_percent: number;
};

export type ChildProcess = {
  pid: number;
  name: string;
  display_name?: string;
  cmdline?: string | null;
  status: string;
  cpu_percent: number;
  rss_mb: number | null;
  threads: number | null;
  thread_names?: readonly string[];
};

export type StatsHistorySample = {
  ts: number;
  process_cpu_percent: number;
  system_cpu_percent: number;
  rss_mb: number | null;
  uss_mb: number | null;
  memory_percent: number | null;
  process_read_bps: number | null;
  process_write_bps: number | null;
  disk_read_bps: number | null;
  disk_write_bps: number | null;
  network_recv_bps: number | null;
  network_sent_bps: number | null;
  threads: number | null;
  open_files: number | null;
  connections: number | null;
  active_jobs: number;
  queued_jobs: number;
  is_paused: number;
  children_count: number;
};

export type Bottleneck = {
  type: string;
  level: 'info' | 'warning' | 'critical';
  summary: string;
  details: string;
};

export type BottleneckAverages = {
  process_cpu_percent: number | null;
  system_cpu_percent: number | null;
  memory_percent: number | null;
  process_read_mbps: number | null;
  process_write_mbps: number | null;
  disk_read_mbps: number | null;
  disk_write_mbps: number | null;
  network_recv_mbps: number | null;
  network_sent_mbps: number | null;
  active_jobs: number | null;
};

export type BottlenecksResponse = {
  status: 'ok' | 'attention' | 'unknown';
  window_samples: number;
  averages: BottleneckAverages;
  bottlenecks: Bottleneck[];
};
