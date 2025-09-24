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
}

type Preset = {
  /** Unique identifier for the preset */
  id?: string
  /** Preset name, e.g. "default" */
  name: string
  /** Optional description for the preset */
  description: string
  /** Folder where files will be saved, e.g. "/downloads" */
  folder: string
  /** Output template for the preset, e.g. "%(title)s.%(ext)s" */
  template: string
  /** Cookies for the preset, e.g. "cookies.txt" */
  cookies: string
  /** Additional command line options for yt-dlp */
  cli: string
  /** Indicates if this is the default preset */
  default: boolean
}

type ConfigState = {
  /** Show or hide the download form */
  showForm: RemovableRef<boolean>
  /** Application configuration */
  app: AppConfig
  /** List of presets */
  presets: Preset[]
  /** List of custom download fields */
  dl_fields: DLField[]
  /** List of folders where files can be saved */
  folders: string[]
  /** List of yt-dlp options */
  ytdlp_options: YTDLPOption[]
  /** Indicates if downloads are currently paused */
  paused: boolean
  /** Indicates if the configuration has been loaded */
  is_loaded: boolean
}

export type { AppConfig, Preset, ConfigState }
