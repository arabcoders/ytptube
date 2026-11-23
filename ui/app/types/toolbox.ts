import type { DLFieldType } from '~/types/dl_fields';

export type ToolboxOptionValue = string | number | boolean | null;
export type ToolboxOptions = Record<string, ToolboxOptionValue | undefined>;

export type ToolboxOptionField = {
  name: string;
  label: string;
  description?: string;
  type: DLFieldType | 'number' | 'select';
  required: boolean;
  nullable: boolean;
  min?: number;
  max?: number;
  step?: number | 'any';
  items?: { label: string; value: ToolboxOptionValue }[];
  defaultValue?: ToolboxOptionValue;
};

export type ToolboxTool = {
  id: number;
  name: string;
  description: string;
  available: boolean;
  reason: string | null;
  supports_overwrite: boolean;
  options_schema: Record<string, unknown>;
};

export type ToolboxDefinitionSummary = {
  id: number;
  name: string;
  description: string;
  default: boolean;
};

export type ToolboxParam = {
  default: string | number | boolean;
  min?: number | null;
  max?: number | null;
  choices?: string[] | null;
};

export type ToolboxDefinitionInput = {
  name: string;
  description: string;
  output_extension: string;
  supports_overwrite: boolean;
  command: string[];
  env: Record<string, string>;
  params: Record<string, ToolboxParam>;
};

export type ToolboxDefinitionPayload = Omit<ToolboxDefinitionInput, 'params'> & {
  params: Record<
    string,
    Omit<ToolboxParam, 'default'> & { default: ToolboxParam['default'] | undefined }
  >;
};

export type ToolboxDefinition = ToolboxDefinitionInput & { id: number; default: boolean };

export type ToolboxStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'skipped'
  | 'failed'
  | 'cancelled'
  | 'interrupted';

export type ToolboxJob = {
  id: number;
  tool: number;
  file: string;
  extra: { overwrite_source: boolean; options: Record<string, unknown> };
  status: ToolboxStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: number | null;
  message: string | null;
  result: { outputs: readonly string[] } | null;
  error: string | null;
  error_code: string | null;
  log: string;
};
