import { ref, readonly } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { request, parse_list_response, parse_api_response, parse_api_error } from '~/utils'
import type {
  Task,
  TaskPatch,
  TaskInspectRequest,
  TaskInspectResponse,
  TaskMetadataResponse,
} from '~/types/tasks'
import type { APIResponse, Pagination } from '~/types/responses'

/**
 * List of all tasks in memory.
 */
const tasks = ref<Array<Task>>([])
/**
 * Pagination state for tasks list.
 */
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
})
/**
 * Indicates if a request is in progress.
 */
const isLoading = ref<boolean>(false)
/**
 * Indicates if an add/update operation is in progress.
 */
const addInProgress = ref<boolean>(false)
/**
 * Stores the last error message, if any.
 */
const lastError = ref<string | null>(null)
/**
 * If true, methods will throw errors instead of returning null/false (for testing)
 */
const throwInstead = ref(false)
/**
 * Notification composable for showing success/error messages.
 */
const notify = useNotification()

/**
 * Sorts tasks by name (A-Z).
 * @param items Array of tasks
 * @returns Sorted array of tasks
 */
const sortTasks = (items: Array<Task>): Array<Task> => {
  return [...items].sort((a, b) => a.name.localeCompare(b.name))
}

/**
 * Safely reads JSON from a Response, returns null on error.
 * @param response Fetch Response object
 * @returns Parsed JSON or null
 */
const readJson = async (response: Response): Promise<unknown> => {
  try {
    const clone = response.clone()
    return await clone.json()
  }
  catch {
    return null
  }
}

/**
 * Throws an error if the response is not OK, using API error message if available.
 * @param response Fetch Response object
 * @throws Error with message from API or status code
 */
const ensureSuccess = async (response: Response): Promise<void> => {
  if (response.ok) {
    return
  }

  const payload = await readJson(response)
  const message = await parse_api_error(payload)
  throw new Error(message)
}

/**
 * Handles errors by updating lastError and showing a notification.
 * @param error Error object or unknown
 */
const handleError = (error: unknown): void => {
  const message = error instanceof Error ? error.message : 'Unexpected error occurred.'
  lastError.value = message
  notify.error(message)
}

/**
 * Updates or adds a task in the list, keeping sort order.
 * Also increments pagination.total if it's a new task.
 * @param item Task to update/add
 */
const updateTasksList = (item: Task): void => {
  const isNew = !tasks.value.some(existing => existing.id === item.id)
  tasks.value = sortTasks([
    ...tasks.value.filter(existing => existing.id !== item.id),
    item,
  ])
  if (isNew) {
    pagination.value.total++
  }
}

/**
 * Removes a task from the list by ID.
 * Also decrements pagination.total.
 * @param id Task ID
 */
const removeTask = (id: number) => {
  const initialLength = tasks.value.length
  tasks.value = tasks.value.filter(item => item.id !== id)
  if (tasks.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1)
  }
}

/**
 * Loads tasks from the API with pagination support.
 * @param page Page number
 * @param perPage Items per page
 */
const loadTasks = async (page: number = 1, perPage: number | undefined = undefined): Promise<void> => {
  isLoading.value = true
  try {
    let url = `/api/tasks/?page=${page}`
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`
    }
    const response = await request(url)
    await ensureSuccess(response)

    const json = await response.json()
    const { items, pagination: paginationData } = await parse_list_response<Task>(json)

    tasks.value = sortTasks(items)
    pagination.value = paginationData
    lastError.value = null
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
  }
  finally {
    isLoading.value = false
  }
}

/**
 * Fetches a single task by ID from the API.
 * @param id Task ID
 * @returns Task or null on error
 */
const getTask = async (id: number): Promise<Task | null> => {
  try {
    const response = await request(`/api/tasks/${id}`)
    await ensureSuccess(response)

    const json = await response.json()
    const task = await parse_api_response<Task>(json)

    lastError.value = null
    return task
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Creates a new task via API.
 * @param task Task to create
 * @param callback Optional callback with APIResponse result
 * @returns Created task or null on error
 */
const createTask = async (
  task: Omit<Task, 'id' | 'created_at' | 'updated_at'>,
  callback?: (response: APIResponse<Task>) => void,
): Promise<Task | null> => {
  addInProgress.value = true
  try {
    const response = await request('/api/tasks/', {
      method: 'POST',
      body: JSON.stringify(task),
    })
    await ensureSuccess(response)

    const json = await response.json()
    const created = await parse_api_response<Task>(json)

    updateTasksList(created)
    notify.success('Task created.')
    lastError.value = null

    if (callback) {
      callback({ success: true, error: null, detail: null, data: created })
    }

    return created
  }
  catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unexpected error occurred.'
    handleError(error)

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined })
    }

    if (throwInstead.value) throw error
    return null
  }
  finally {
    addInProgress.value = false
  }
}

/**
 * Updates an existing task via API (PUT - full update).
 * @param id Task ID
 * @param task Updated task data
 * @param callback Optional callback with APIResponse result
 * @returns Updated task or null on error
 */
const updateTask = async (
  id: number,
  task: Omit<Task, 'id' | 'created_at' | 'updated_at'>,
  callback?: (response: APIResponse<Task>) => void,
): Promise<Task | null> => {
  addInProgress.value = true
  try {
    // Explicitly remove id, created_at, updated_at fields if present
    const { id: _, created_at: __, updated_at: ___, ...taskData } = task as Task
    
    const response = await request(`/api/tasks/${id}`, {
      method: 'PUT',
      body: JSON.stringify(taskData),
    })
    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<Task>(json)

    updateTasksList(updated)
    notify.success(`Task '${updated.name}' updated.`)
    lastError.value = null

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated })
    }

    return updated
  }
  catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unexpected error occurred.'
    handleError(error)

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined })
    }

    if (throwInstead.value) throw error
    return null
  }
  finally {
    addInProgress.value = false
  }
}

/**
 * Partially updates an existing task via API (PATCH).
 * @param id Task ID
 * @param patch Partial task data to update
 * @param callback Optional callback with APIResponse result
 * @returns Updated task or null on error
 */
const patchTask = async (
  id: number,
  patch: TaskPatch,
  callback?: (response: APIResponse<Task>) => void,
): Promise<Task | null> => {
  addInProgress.value = true
  try {
    const response = await request(`/api/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<Task>(json)

    updateTasksList(updated)
    notify.success(`Task '${updated.name}' updated.`)
    lastError.value = null

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated })
    }

    return updated
  }
  catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unexpected error occurred.'
    handleError(error)

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined })
    }

    if (throwInstead.value) throw error
    return null
  }
  finally {
    addInProgress.value = false
  }
}

/**
 * Deletes a task by ID via API.
 * @param id Task ID
 * @param callback Optional callback with APIResponse result
 * @returns true if deleted, false on error
 */
const deleteTask = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/tasks/${id}`, { method: 'DELETE' })
    await ensureSuccess(response)

    removeTask(id)
    notify.success('Task deleted.')
    lastError.value = null

    if (callback) {
      callback({ success: true, error: null, detail: null, data: true })
    }

    return true
  }
  catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unexpected error occurred.'
    handleError(error)

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: false })
    }

    if (throwInstead.value) throw error
    return false
  }
}

/**
 * Inspects a task handler to check if it can process the given URL.
 * @param request Task inspect request parameters
 * @returns Inspect result or null on error
 */
const inspectTaskHandler = async (request: TaskInspectRequest): Promise<TaskInspectResponse | null> => {
  try {
    const response = await fetch('/api/tasks/inspect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })

    const json = await response.json()
    lastError.value = null
    return json as TaskInspectResponse
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Marks all items from a task as downloaded in the download archive.
 * @param id Task ID
 * @returns Success message or null on error
 */
const markTaskItems = async (id: number): Promise<string | null> => {
  try {
    const response = await request(`/api/tasks/${id}/mark`, { method: 'POST' })
    await ensureSuccess(response)

    const json = await response.json()
    const message = json.message || 'All items marked as downloaded.'

    notify.success(message)
    lastError.value = null
    return message
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Removes all items from a task from the download archive.
 * @param id Task ID
 * @returns Success message or null on error
 */
const unmarkTaskItems = async (id: number): Promise<string | null> => {
  try {
    const response = await request(`/api/tasks/${id}/mark`, { method: 'DELETE' })
    await ensureSuccess(response)

    const json = await response.json()
    const message = json.message || 'All items removed from archive.'

    notify.success(message)
    lastError.value = null
    return message
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Generates metadata for a task (tvshow.nfo, info.json, thumbnails).
 * @param id Task ID
 * @returns Metadata response or null on error
 */
const generateTaskMetadata = async (id: number): Promise<TaskMetadataResponse | null> => {
  try {
    const response = await request(`/api/tasks/${id}/metadata`, { method: 'POST' })
    await ensureSuccess(response)

    const json = await response.json()
    const metadata = await parse_api_response<TaskMetadataResponse>(json)

    notify.success('Metadata generation completed.')
    lastError.value = null
    return metadata
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Clears the last error message.
 */
const clearError = () => lastError.value = null

/**
 * Resets all state to initial values (for testing only).
 */
const __resetForTesting = () => {
  tasks.value = []
  pagination.value = {
    page: 1,
    per_page: 50,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false,
  }
  isLoading.value = false
  addInProgress.value = false
  lastError.value = null
  throwInstead.value = false
}

/**
 * useTasks composable
 *
 * Returns reactive state and CRUD methods for tasks.
 * @returns Object with state and API methods
 */
export const useTasks = () => ({
  tasks: readonly(tasks),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
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
})
