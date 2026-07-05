import type { BottlenecksResponse } from '~/types/stats';

export type DiagnosticStatus = 'pass' | 'fail' | 'warn' | 'skip';
export type DiagnosticReportStatus = 'ok' | 'degraded' | 'error';

export type DiagnosticCheck = {
  id: string;
  label: string;
  group: string;
  required: boolean;
  status: DiagnosticStatus;
  description: string;
  message: string;
  details: Record<string, string | number | boolean | null | undefined>;
};

export type DiagnosticSummary = {
  total: number;
  pass: number;
  fail: number;
  warn: number;
  skip: number;
  required_failed: number;
};

export type DiagnosticRuntime = {
  app_version: string;
  app_branch: string;
  app_commit_sha: string;
  app_build_date: string;
  started: number;
  uptime_seconds: number;
  platform: string;
  platform_release: string;
  platform_machine: string;
  python_version: string;
  python_minimum: string;
  is_native: boolean;
  console_enabled: boolean;
};

export type DiagnosticRequirements = {
  python: {
    current: string;
    required: string;
    supported: boolean;
    note: string;
  };
};

export type DiagnosticStats =
  | {
      enabled: false;
    }
  | {
      enabled: true;
      window_seconds?: number;
      sample_count?: number;
      summary?: {
        averages: DiagnosticStatsValues;
        max: DiagnosticStatsValues;
      };
      bottlenecks?: BottlenecksResponse;
      error?: string;
    };

export type DiagnosticStatsValues = {
  process_cpu_percent: number | null;
  system_cpu_percent: number | null;
  memory_percent: number | null;
  rss_mb: number | null;
  process_read_bps: number | null;
  process_write_bps: number | null;
  disk_read_bps: number | null;
  disk_write_bps: number | null;
  network_recv_bps: number | null;
  network_sent_bps: number | null;
  active_jobs: number | null;
  queued_jobs: number | null;
  children_count: number | null;
};

export type DiagnosticsResponse = {
  status: DiagnosticReportStatus;
  generated_at: number;
  summary: DiagnosticSummary;
  runtime: DiagnosticRuntime;
  requirements: DiagnosticRequirements;
  stats: DiagnosticStats;
  checks: Array<DiagnosticCheck>;
};
