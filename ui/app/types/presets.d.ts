type Preset = {
  id?: string
  name: string
  cli: string
  cookies: string
  default: boolean
  description: string
  folder: string
  template: string
}

type PresetImport = Preset & {
  _type: 'preset'
  _version: string
}

export type { Preset, PresetImport }
