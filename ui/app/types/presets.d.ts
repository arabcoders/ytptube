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
  /** Priority for sorting. Higher priority presets appear first */
  priority: number
}

type PresetImport = Preset & {
  _type: 'preset'
  _version: string
}

export type { Preset, PresetImport }
