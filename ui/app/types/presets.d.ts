type Preset = {
  id?: number;
  name: string;
  description: string;
  folder: string;
  template: string;
  cookies: string;
  cli: string;
  default: boolean;
  /** Higher values sort first. */
  priority: number;
};

type PresetRequest = {
  name: string;
  description?: string;
  folder?: string;
  template?: string;
  cookies?: string;
  cli?: string;
  priority?: number;
};

export type { Preset, PresetRequest };
