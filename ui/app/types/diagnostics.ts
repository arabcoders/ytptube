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

export type DiagnosticsResponse = {
  status: DiagnosticReportStatus;
  generated_at: number;
  summary: DiagnosticSummary;
  runtime: DiagnosticRuntime;
  requirements: DiagnosticRequirements;
  checks: Array<DiagnosticCheck>;
};
