import type { Preset } from './presets';
import type { YTDLPOption } from './ytdlp';
import type { DLField } from './dl_fields';

type AppConfig = {
  download_path: string;
  remove_files: boolean;
  output_template: string;
  ytdlp_version: string;
  max_workers: number;
  max_workers_per_extractor: number;
  default_preset: string;
  instance_title: string | null;
  console_enabled: boolean;
  monitor_enabled: boolean;
  browser_control_enabled: boolean;
  file_logging: boolean;
  simple_mode: boolean;
  is_native: boolean;
  app_version: string;
  app_commit_sha: string;
  app_build_date: string;
  app_branch: string;
  started: number;
  app_env: 'production' | 'development';
  default_pagination: number;
  /** Zero disables the UI queue limit. */
  queue_display_limit: number;
  /** Additional attempts allowed after a retryable download failure. */
  retry: number;
  /** Start a fresh download on the final retry attempt. */
  retry_fresh: boolean;
  /** Log level from the saved configuration. */
  log_level: 'debug' | 'info' | 'warning' | 'error' | '';
  /** Log level currently applied by the running process. */
  runtime_log_level: 'debug' | 'info' | 'warning' | 'error' | '';
  check_for_updates: boolean;
  new_version: string;
  yt_new_version: string;
};

type ConfigState = {
  showForm: RemovableRef<boolean>;
  app: AppConfig;
  presets: Array<Preset>;
  dl_fields: Array<DLField>;
  ytdlp_options: Array<YTDLPOption>;
  paused: boolean;
  is_loaded: boolean;
  is_loading: boolean;
};

export type { AppConfig, ConfigState };
