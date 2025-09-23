// Types for api/tasks/inspect

export interface TaskInspectRequest {
    url: string;
    preset?: string;
    handler?: string;
}

export interface TaskInspectSuccess {
    // The structure depends on TaskResult, but at minimum:
    success?: boolean;
    [key: string]: unknown;
}

export interface TaskInspectError {
    error: string;
    message?: string;
}

export type TaskInspectResponse = TaskInspectSuccess | TaskInspectError;
