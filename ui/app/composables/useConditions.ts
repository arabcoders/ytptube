import { ref, readonly } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { request, parse_list_response, parse_api_response, parse_api_error } from '~/utils'
import type {
  Condition,
  ConditionTestRequest,
  ConditionTestResponse,
  Pagination,
} from '~/types/conditions'
import type { APIResponse } from '~/types/responses'

/**
 * List of all conditions in memory.
 */
const conditions = ref<Array<Condition>>([])
/**
 * Pagination state for conditions list.
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
 * Used separately from isLoading for finer control.
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
 * Sorts conditions by priority (descending - higher number first), then name (A-Z).
 * @param items Array of Condition
 * @returns Sorted array of Condition
 */
const sortConditions = (items: Array<Condition>): Array<Condition> => {
  return [...items].sort((a, b) => {
    if (a.priority === b.priority) {
      return a.name.localeCompare(b.name)
    }

    return b.priority - a.priority
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
 * Updates or adds a condition in the conditions list, keeping sort order.
 * Also increments pagination.total if it's a new condition.
 * @param condition Condition to update/add
 */
const updateConditions = (condition: Condition): void => {
  const isNew = !conditions.value.some(item => item.id === condition.id)
  conditions.value = sortConditions([
    ...conditions.value.filter(item => item.id !== condition.id),
    condition,
  ])
  if (isNew) {
    pagination.value.total++
  }
}

/**
 * Removes a condition from the conditions list by ID.
 * Also decrements pagination.total.
 * @param id Condition ID
 */
const removeCondition = (id: number) => {
  const initialLength = conditions.value.length
  conditions.value = conditions.value.filter(item => item.id !== id)
  if (conditions.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1)
  }
}

/**
 * Loads all conditions from the API with pagination support.
 * Updates conditions, pagination, and lastError.
 * @param page Page number
 * @param perPage Items per page
 */
const loadConditions = async (page: number = 1, perPage: number | undefined = undefined): Promise<void> => {
  isLoading.value = true
  try {
    let url = `/api/conditions/?page=${page}`
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`
    }
    const response = await request(url)
    await ensureSuccess(response)

    const json = await response.json()
    const { items, pagination: paginationData } = await parse_list_response<Condition>(json)

    conditions.value = sortConditions(items)
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
 * Fetches a single condition by ID from the API.
 * @param id Condition ID
 * @returns Condition or null on error
 */
const getCondition = async (id: number): Promise<Condition | null> => {
  try {
    const response = await request(`/api/conditions/${id}`)
    await ensureSuccess(response)

    const json = await response.json()
    const condition = await parse_api_response<Condition>(json)

    lastError.value = null
    return condition
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Creates a new condition via API.
 * @param condition Condition to create
 * @param callback Optional callback with APIResponse result
 * @returns Created Condition or null on error
 */
const createCondition = async (
  condition: Omit<Condition, 'id'>,
  callback?: (response: APIResponse<Condition>) => void,
): Promise<Condition | null> => {
  addInProgress.value = true
  try {
    const response = await request('/api/conditions/', {
      method: 'POST',
      body: JSON.stringify(condition),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const created = await parse_api_response<Condition>(json)

    updateConditions(created)
    notify.success('Condition created.')
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
 * Updates an existing condition via API (PUT - full update).
 * @param id Condition ID
 * @param condition Updated Condition data
 * @param callback Optional callback with APIResponse result
 * @returns Updated Condition or null on error
 */
const updateCondition = async (
  id: number,
  condition: Condition,
  callback?: (response: APIResponse<Condition>) => void,
): Promise<Condition | null> => {
  addInProgress.value = true
  try {
    if (condition.id) {
      condition.id = undefined
    }
    const response = await request(`/api/conditions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(condition),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<Condition>(json)

    updateConditions(updated)
    notify.success(`Condition '${updated.name}' updated.`)
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
 * Partially updates an existing condition via API (PATCH).
 * @param id Condition ID
 * @param patch Partial Condition data to update
 * @param callback Optional callback with APIResponse result
 * @returns Updated Condition or null on error
 */
const patchCondition = async (
  id: number,
  patch: Partial<Condition>,
  callback?: (response: APIResponse<Condition>) => void,
): Promise<Condition | null> => {
  addInProgress.value = true
  try {
    if (patch.id) {
      patch.id = undefined
    }
    const response = await request(`/api/conditions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<Condition>(json)

    updateConditions(updated)
    notify.success(`Condition '${updated.name}' updated.`)
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
 * Deletes a condition by ID via API.
 * @param id Condition ID
 * @param callback Optional callback with APIResponse result
 * @returns true if deleted, false on error
 */
const deleteCondition = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/conditions/${id}`, { method: 'DELETE' })
    await ensureSuccess(response)

    removeCondition(id)
    notify.success('Condition deleted.')
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
 * Tests a condition against a URL.
 * @param testRequest Test request parameters
 * @returns Test result or null on error
 */
const testCondition = async (testRequest: ConditionTestRequest): Promise<ConditionTestResponse | null> => {
  try {
    const response = await request('/api/conditions/test/', {
      method: 'POST',
      body: JSON.stringify(testRequest),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const result = await parse_api_response<ConditionTestResponse>(json)

    lastError.value = null
    return result
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
 * useConditions composable
 *
 * Returns reactive state and CRUD methods for conditions.
 * @returns Object with state and API methods
 */
export const useConditions = () => ({
  conditions: readonly(conditions),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadConditions,
  getCondition,
  createCondition,
  updateCondition,
  patchCondition,
  deleteCondition,
  testCondition,
  clearError,
  throwInstead,
})
