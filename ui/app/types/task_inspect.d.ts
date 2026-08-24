import type { TaskDefinitionDocument } from '~/types/task_definitions';

export interface TaskInspectRequest {
  url: string;
  preset?: string;
  handler?: string;
  resolve_ids?: boolean;
  definition_id?: number;
  document?: TaskDefinitionDocument;
}

export interface TaskInspectSuccess {
  // The structure depends on TaskResult, but at minimum:
  success?: boolean;
  items?: Array<{
    url: string;
    title?: string | null;
    archive_id?: string | null;
    thumbnail?: string | null;
    metadata?: Record<string, unknown>;
  }>;
  metadata?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface TaskInspectError {
  error: string;
  message?: string;
}

export type TaskInspectResponse = TaskInspectSuccess | TaskInspectError;
