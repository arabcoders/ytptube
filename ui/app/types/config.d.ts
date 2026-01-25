import type { Preset } from "./presets";
import type { YTDLPOption } from './ytdlp';
import type { DLField } from "./dl_fields"

type AppConfig = {
  /** Path where downloaded files will be saved */
  download_path: string
  /** Indicates if files should be removed after download */
  remove_files: boolean
  /** Indicates if the UI should update the title with the current download status */
  ui_update_title: boolean
  /** Output template for yt-dlp, e.g. "%(title)s.%(ext)s" */
  output_template: string
  /** yt-dlp version, e.g. "2023.10.01" */
  ytdlp_version: string
  /** Maximum number of concurrent download workers */
  max_workers: number
  /** Maximum number of concurrent workers per extractor */
  max_workers_per_extractor: number
  /** Default preset name, e.g. "default" */
  default_preset: string
  /** Instance title for the app, null if not set */
  instance_title: string | null
  /** Indicates if the console is enabled */
  console_enabled: boolean
  /** Indicates if the file browser control is enabled */
  browser_control_enabled: boolean
  /** Indicates if file logging is enabled */
  file_logging: boolean
  /** Indicates if the app is in simple mode */
  simple_mode: boolean
  /** Indicates if the app is running in a native environment (e.g., Electron) */
  is_native: boolean
  /** App version in format "1.0.0" */
  app_version: string
  /** App version in semantic versioning format, e.g. "1.0.0" */
  app_commit_sha: string
  /** App build date in ISO format, e.g. "2023-10-01T12:00:00Z" */
  app_build_date: string
  /** App branch name, e.g. "main" or "develop" */
  app_branch: string
  /** When the app started */
  started: number,
  /** Application environment, e.g. "production", "development" */
  app_env: "production" | "development"
  /** Default number of items per page for pagination */
  default_pagination: number
  /** Indicates if the app should check for updates */
  check_for_updates: boolean
  /** New version available, empty string if none */
  new_version: string
  /** New yt-dlp version available, empty string if none */
  yt_new_version: string
}

type ConfigState = {
  /** Show or hide the download form */
  showForm: RemovableRef<boolean>
  /** Application configuration */
  app: AppConfig
  /** List of presets */
  presets: Array<Preset>
  /** List of custom download fields */
  dl_fields: Array<DLField>
  /** List of folders where files can be saved */
  folders: Array<string>
  /** List of yt-dlp options */
  ytdlp_options: Array<YTDLPOption>
  /** Indicates if downloads are currently paused */
  paused: boolean
  /** Indicates if the configuration has been loaded */
  is_loaded: boolean
  /** Indicates if the configuration is currently loading */
  is_loading: boolean
}

export type { AppConfig, ConfigState }
