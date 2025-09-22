import { ref, readonly } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { request } from '~/utils'
import type {
  TaskDefinitionDetailed,
  TaskDefinitionDocument,
  TaskDefinitionErrorResponse,
  TaskDefinitionSummary,
} from '~/types/task_definitions'

/**
 * Reactive list of all task definition summaries, sorted by priority and name.
 */
const definitions = ref<Array<TaskDefinitionSummary>>([])
/**
 * Indicates if a request is in progress.
 */
const isLoading = ref<boolean>(false)
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
 * Sorts task definition summaries by priority (ascending), then name (A-Z).
 * @param items Array of TaskDefinitionSummary
 * @returns Sorted array of TaskDefinitionSummary
 */
const sortSummaries = (items: Array<TaskDefinitionSummary>): Array<TaskDefinitionSummary> => {
  return [...items].sort((a, b) => {
    if (a.priority === b.priority) {
      return a.name.localeCompare(b.name)
    }

    return a.priority - b.priority
  })
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

  let message = `Request failed with status ${response.status}`
  if (payload && typeof payload === 'object' && 'error' in payload) {
    const errorPayload = payload as TaskDefinitionErrorResponse
    if (typeof errorPayload.error === 'string' && errorPayload.error.length > 0) {
      message = errorPayload.error
    }
  }

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
 * Updates or adds a summary in the definitions list, keeping sort order.
 * @param summary TaskDefinitionSummary to update/add
 */
const updateSummaries = (summary: TaskDefinitionSummary): void => {
  definitions.value = sortSummaries([
    ...definitions.value.filter(item => item.id !== summary.id),
    summary,
  ])
}

/**
 * Removes a summary from the definitions list by ID.
 * @param id Task definition ID
 */
const removeSummary = (id: string) => definitions.value = definitions.value.filter(item => item.id !== id)

/**
 * Loads all task definition summaries from the API.
 * Updates definitions and lastError.
 */
const loadDefinitions = async (): Promise<void> => {
  isLoading.value = true
  try {
    const response = await request('/api/task_definitions/')
    await ensureSuccess(response)

    const payload = await response.json() as unknown
    if (!Array.isArray(payload)) {
      throw new Error('Unexpected response while loading task definitions.')
    }

    const summaries: Array<TaskDefinitionSummary> = payload.map(item => {
      if (!item || 'object' !== typeof item) {
        throw new Error('Encountered malformed task definition entry.')
      }

      const entry = item as Record<string, unknown>
      return {
        id: String(entry.id ?? ''),
        name: String(entry.name ?? ''),
        priority: Number(entry.priority ?? 0),
        updated_at: Number(entry.updated_at ?? 0),
      }
    })

    definitions.value = sortSummaries(summaries)
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
 * Fetches a detailed task definition by ID from the API.
 * @param id Task definition ID
 * @returns TaskDefinitionDetailed or null on error
 */
const getDefinition = async (id: string): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request(`/api/task_definitions/${id}`)
    await ensureSuccess(response)

    const payload = await response.json() as unknown
    if (!payload || 'object' !== typeof payload) {
      throw new Error('Unexpected response while retrieving task definition.')
    }

    const entry = payload as Record<string, unknown>
    if (!('definition' in entry) || 'object' !== typeof entry.definition) {
      throw new Error('Task definition response is missing definition payload.')
    }

    const detailed: TaskDefinitionDetailed = {
      id: String(entry.id ?? ''),
      name: String(entry.name ?? ''),
      priority: Number(entry.priority ?? 0),
      updated_at: Number(entry.updated_at ?? 0),
      definition: entry.definition as TaskDefinitionDocument,
    }

    lastError.value = null
    return detailed
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Creates a new task definition via API.
 * @param definition TaskDefinitionDocument to create
 * @returns Created TaskDefinitionDetailed or null on error
 */
const createDefinition = async (definition: TaskDefinitionDocument): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request('/api/task_definitions/', {
      method: 'POST',
      body: JSON.stringify({ definition }),
    })

    await ensureSuccess(response)

    const payload = await response.json() as TaskDefinitionDetailed

    updateSummaries({
      id: payload.id,
      name: payload.name,
      priority: payload.priority,
      updated_at: payload.updated_at,
    })

    notify.success('Task definition created.')
    lastError.value = null
    return payload
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Updates an existing task definition via API.
 * @param id Task definition ID
 * @param definition Updated TaskDefinitionDocument
 * @returns Updated TaskDefinitionDetailed or null on error
 */
const updateDefinition = async (id: string, definition: TaskDefinitionDocument): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request(`/api/task_definitions/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ definition }),
    })

    await ensureSuccess(response)

    const payload = await response.json() as TaskDefinitionDetailed

    updateSummaries({
      id: payload.id,
      name: payload.name,
      priority: payload.priority,
      updated_at: payload.updated_at,
    })

    notify.success('Task definition updated.')
    lastError.value = null
    return payload
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Deletes a task definition by ID via API.
 * @param id Task definition ID
 * @returns true if deleted, false on error
 */
const deleteDefinition = async (id: string): Promise<boolean> => {
  try {
    const response = await request(`/api/task_definitions/${id}`, { method: 'DELETE' })
    await ensureSuccess(response)

    removeSummary(id)
    notify.success('Task definition deleted.')
    lastError.value = null
    return true
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return false
  }
}

/**
 * Clears the last error message.
 */
const clearError = () => lastError.value = null

/**
 * useTaskDefinitions composable
 *
 * Returns reactive state and CRUD methods for task definitions.
 * @returns Object with state and API methods
 */
export const useTaskDefinitions = () => ({
  definitions: readonly(definitions),
  isLoading: readonly(isLoading),
  lastError: readonly(lastError),
  loadDefinitions,
  getDefinition,
  createDefinition,
  updateDefinition,
  deleteDefinition,
  clearError,
  throwInstead,
})

export default useTaskDefinitions
