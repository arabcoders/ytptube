import { ref, readonly } from 'vue';
import { useNotification } from '~/composables/useNotification';
import { request, parse_list_response, parse_api_response, ensure_api_success } from '~/utils';
import type {
  Task,
  TaskPatch,
  TaskInspectRequest,
  TaskInspectResponse,
  TaskMetadataResponse,
} from '~/types/tasks';
import type { APIResponse, Pagination } from '~/types/responses';

const tasks = ref<Array<Task>>([]);
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const isLoading = ref<boolean>(false);
const addInProgress = ref<boolean>(false);
const inProgressIds = ref<Set<number>>(new Set());
const lastError = ref<string | null>(null);
// Test hook: rethrow request errors instead of returning fallback values.
const throwInstead = ref(false);

const { $i18n } = useNuxtApp();
const t = $i18n?.t ?? ((key: string) => key);

const sortTasks = (items: Array<Task>): Array<Task> => {
  return [...items].sort((a, b) => a.name.localeCompare(b.name));
};

const setError = (error: unknown): string => {
  const message = error instanceof Error ? error.message : t('common.unknownError');
  lastError.value = message;
  return message;
};

const handleError = (error: unknown): void => {
  const message = setError(error);
  useNotification().error(message);
};

const updateTasksList = (item: Task): void => {
  const isNew = !tasks.value.some((existing) => existing.id === item.id);
  tasks.value = sortTasks([...tasks.value.filter((existing) => existing.id !== item.id), item]);
  if (isNew) {
    pagination.value.total++;
  }
};

const removeTask = (id: number) => {
  const initialLength = tasks.value.length;
  tasks.value = tasks.value.filter((item) => item.id !== id);
  if (tasks.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1);
  }
};

const loadTasks = async (
  page: number = 1,
  perPage: number | undefined = undefined,
): Promise<void> => {
  isLoading.value = true;
  try {
    let url = `/api/tasks/?page=${page}`;
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`;
    }
    const response = await request(url);
    await ensure_api_success(response);

    const json = await response.json();
    const { items, pagination: paginationData } = await parse_list_response<Task>(json);

    tasks.value = sortTasks(items);
    pagination.value = paginationData;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const getTask = async (id: number): Promise<Task | null> => {
  try {
    const response = await request(`/api/tasks/${id}`);
    await ensure_api_success(response);

    const json = await response.json();
    const task = await parse_api_response<Task>(json);

    lastError.value = null;
    return task;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const createTask = async (
  task:
    | Omit<Task, 'id' | 'created_at' | 'updated_at'>
    | Omit<Task, 'id' | 'created_at' | 'updated_at'>[],
  callback?: (response: APIResponse<Task | Task[]>) => void,
): Promise<Task | Task[] | null> => {
  addInProgress.value = true;
  try {
    const response = await request('/api/tasks/', {
      method: 'POST',
      body: JSON.stringify(task),
    });
    await ensure_api_success(response);

    const json = await response.json();
    const created = await parse_api_response<Task | Array<Task>>(json);

    if (Array.isArray(created)) {
      useNotification().success(t('common.crudCreated', { type: t('tasks.task') }));
      created.forEach((item) => updateTasksList(item));
      lastError.value = null;

      if (callback) {
        callback({ success: true, error: null, detail: null, data: created });
      }

      return created;
    }

    updateTasksList(created);
    useNotification().success(t('common.crudCreated', { type: t('tasks.task') }));
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: created });
    }

    return created;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    setError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    throw error;
  } finally {
    addInProgress.value = false;
  }
};

const updateTask = async (
  id: number,
  task: Omit<Task, 'id' | 'created_at' | 'updated_at'>,
  callback?: (response: APIResponse<Task>) => void,
): Promise<Task | null> => {
  addInProgress.value = true;
  try {
    // Explicitly remove id, created_at, updated_at fields if present
    const { id: _, created_at: __, updated_at: ___, ...taskData } = task as Task;

    const response = await request(`/api/tasks/${id}`, {
      method: 'PUT',
      body: JSON.stringify(taskData),
    });
    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<Task>(json);

    updateTasksList(updated);
    useNotification().success(
      t('common.crudUpdated', { type: t('tasks.task'), name: updated.name }),
    );
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated });
    }

    return updated;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    setError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    throw error;
  } finally {
    addInProgress.value = false;
  }
};

const patchTask = async (
  id: number,
  patch: TaskPatch,
  callback?: (response: APIResponse<Task>) => void,
): Promise<Task | null> => {
  addInProgress.value = true;
  try {
    const response = await request(`/api/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<Task>(json);

    updateTasksList(updated);
    useNotification().success(
      t('common.crudUpdated', { type: t('tasks.task'), name: updated.name }),
    );
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated });
    }

    return updated;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    setError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    throw error;
  } finally {
    addInProgress.value = false;
  }
};

const deleteTask = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/tasks/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);

    removeTask(id);
    useNotification().success(t('common.crudDeleted', { type: t('tasks.task') }));
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: true });
    }

    return true;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    handleError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: false });
    }

    if (throwInstead.value) throw error;
    return false;
  }
};

const inspectTaskHandler = async (
  payload: TaskInspectRequest,
): Promise<TaskInspectResponse | null> => {
  try {
    const response = await request('/api/tasks/inspect', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    const json = await response.json();
    lastError.value = null;
    return json as TaskInspectResponse;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const markTaskItems = async (id: number): Promise<string | null> => {
  try {
    const response = await request(`/api/tasks/${id}/mark`, { method: 'POST' });
    await ensure_api_success(response);

    const json = await response.json();
    const message = json.message || t('tasks.allMarkedDownloaded');

    useNotification().success(message);
    lastError.value = null;
    return message;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const unmarkTaskItems = async (id: number): Promise<string | null> => {
  try {
    const response = await request(`/api/tasks/${id}/mark`, { method: 'DELETE' });
    await ensure_api_success(response);

    const json = await response.json();
    const message = json.message || t('tasks.allRemovedArchive');

    useNotification().success(message);
    lastError.value = null;
    return message;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const generateTaskMetadata = async (id: number): Promise<TaskMetadataResponse | null> => {
  try {
    const response = await request(`/api/tasks/${id}/metadata`, { method: 'POST' });
    await ensure_api_success(response);

    const json = await response.json();
    const metadata = await parse_api_response<TaskMetadataResponse>(json);

    useNotification().success(t('tasks.metadataCompleted'));
    lastError.value = null;
    return metadata;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const clearError = () => (lastError.value = null);

const isTaskInProgress = (id: number): boolean => inProgressIds.value.has(id);

const setTaskInProgress = (id: number): void => {
  inProgressIds.value.add(id);
};

const clearTaskInProgress = (id: number): void => {
  inProgressIds.value.delete(id);
};

const __resetForTesting = () => {
  tasks.value = [];
  pagination.value = {
    page: 1,
    per_page: 50,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false,
  };
  isLoading.value = false;
  addInProgress.value = false;
  lastError.value = null;
  throwInstead.value = false;
  inProgressIds.value = new Set();
};

export const useTasks = () => ({
  tasks: readonly(tasks),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  inProgressIds: readonly(inProgressIds),
  isTaskInProgress,
  setTaskInProgress,
  clearTaskInProgress,
  loadTasks,
  getTask,
  createTask,
  updateTask,
  patchTask,
  deleteTask,
  inspectTaskHandler,
  markTaskItems,
  unmarkTaskItems,
  generateTaskMetadata,
  clearError,
  throwInstead,
  __resetForTesting,
});
