import type { Paginated } from '~/types/responses'

/**
 * Main Task interface matching backend Task schema.
 */
export interface Task {
  id?: number
  name: string
  url: string
  folder?: string
  preset?: string
  timer?: string
  template?: string
  cli?: string
  auto_start?: boolean
  handler_enabled?: boolean
  enabled?: boolean
  created_at?: string
  updated_at?: string
}

/**
 * Partial Task interface for PATCH operations.
 */
export type TaskPatch = Omit<Task, 'id' | 'created_at' | 'updated_at' | 'name' | 'url'> & {
  name?: string
  url?: string
}

/**
 * Paginated list of tasks response.
 */
export type TaskList = Paginated<Task>

/**
 * Task handler inspect request.
 */
export interface TaskInspectRequest {
  url: string
  preset?: string
  handler?: string
  static_only?: boolean
}

/**
 * Task handler inspect response - success.
 */
export interface TaskInspectSuccess {
  matched: true
  handler: string
  message: string
}

/**
 * Task handler inspect response - failure.
 */
export interface TaskInspectFailure {
  matched: false
  message: string
  error: string
}

/**
 * Task handler inspect response (union type).
 */
export type TaskInspectResponse = TaskInspectSuccess | TaskInspectFailure

/**
 * Task metadata response.
 */
export interface TaskMetadataResponse {
  id: string
  id_type: string | null
  title: string | null
  description: string
  uploader: string
  tags: Array<string>
  year: number | null
  thumbnails: Record<string, string>
  json_file?: string
  nfo_file?: string
}

/**
 * Exported task for import/export functionality.
 */
export interface ExportedTask extends Omit<Task, 'id' | 'created_at' | 'updated_at' | 'in_progress'> {
  _type: string
  _version: string
}

/**
 * Generic error response.
 */
export interface ErrorResponse {
  error: string
  detail?: unknown
}

/**
 * Legacy alias for backward compatibility (deprecated).
 * @deprecated Use Task instead
 */
export type task_item = Task

/**
 * Legacy alias for backward compatibility (deprecated).
 * @deprecated Use ExportedTask instead
 */
export type exported_task = ExportedTask

/**
 * Legacy alias for backward compatibility (deprecated).
 * @deprecated Use ErrorResponse instead
 */
export type error_response = ErrorResponse
