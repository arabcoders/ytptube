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
  id: string;
  name: string;
  description: string;
  available: boolean;
  reason: string | null;
  options_schema: Record<string, unknown>;
};

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
  tool: string;
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
