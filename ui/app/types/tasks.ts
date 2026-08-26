import type { Paginated } from '~/types/responses';

export interface Task {
  id?: number;
  name: string;
  url: string;
  folder?: string;
  preset?: string;
  timer?: string;
  template?: string;
  cli?: string;
  auto_start?: boolean;
  handler_enabled?: boolean;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

export type TaskPatch = Omit<Task, 'id' | 'created_at' | 'updated_at' | 'name' | 'url'> & {
  name?: string;
  url?: string;
};

export type TaskScheduleMetadata = {
  _type?: unknown;
  title?: unknown;
  fulltitle?: unknown;
};

export type TaskScheduleDraft = Required<
  Pick<Task, 'name' | 'url' | 'preset' | 'folder' | 'template' | 'cli' | 'timer'>
>;

export type TaskList = Paginated<Task>;

export interface TaskInspectRequest {
  url: string;
  preset?: string;
  handler?: string;
  static_only?: boolean;
  resolve_ids?: boolean;
}

export interface TaskInspectSuccess {
  matched: true;
  handler: string;
  message: string;
  items?: Array<{
    url: string;
    title?: string | null;
    archive_id?: string | null;
    thumbnail?: string | null;
    metadata?: Record<string, unknown>;
  }>;
  metadata?: Record<string, unknown> | null;
}

export interface TaskInspectFailure {
  matched: false;
  message: string;
  error: string;
}

export type TaskInspectResponse = TaskInspectSuccess | TaskInspectFailure;

export interface TaskMetadataResponse {
  id: string;
  id_type: string | null;
  title: string | null;
  description: string;
  uploader: string;
  tags: Array<string>;
  year: number | null;
  thumbnails: Record<string, string>;
  json_file?: string;
  nfo_file?: string;
}

export interface ExportedTask extends Omit<
  Task,
  'id' | 'created_at' | 'updated_at' | 'in_progress'
> {
  _type: string;
  _version: string;
}

export interface ErrorResponse {
  error: string;
  detail?: unknown;
}
