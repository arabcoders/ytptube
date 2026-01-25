import { ref, readonly } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { request, parse_list_response, parse_api_response, parse_api_error } from '~/utils'
import type { DLField, DLFieldRequest } from '~/types/dl_fields'
import type { APIResponse, Pagination } from '~/types/responses'

/**
 * List of all dl fields in memory.
 */
const dlFields = ref<Array<DLField>>([])
/**
 * Pagination state for dl fields list.
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
 * Sorts dl fields by order (ascending), then name (A-Z).
 * @param items Array of DLField
 * @returns Sorted array of DLField
 */
const sortDlFields = (items: Array<DLField>): Array<DLField> => {
  return [...items].sort((a, b) => {
    if (a.order === b.order) {
      return a.name.localeCompare(b.name)
    }

    return a.order - b.order
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
 * Updates or adds a dl field in the dlFields list, keeping sort order.
 * Also increments pagination.total if it's a new dl field.
 * @param field DLField to update/add
 */
const updateDlFields = (field: DLField): void => {
  const isNew = !dlFields.value.some(item => item.id === field.id)
  dlFields.value = sortDlFields([
    ...dlFields.value.filter(item => item.id !== field.id),
    field,
  ])
  if (isNew) {
    pagination.value.total++
  }
}

/**
 * Removes a dl field from the dlFields list by ID.
 * Also decrements pagination.total.
 * @param id DLField ID
 */
const removeDlField = (id: number) => {
  const initialLength = dlFields.value.length
  dlFields.value = dlFields.value.filter(item => item.id !== id)
  if (dlFields.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1)
  }
}

/**
 * Loads all dl fields from the API with pagination support.
 * Updates dlFields, pagination, and lastError.
 * @param page Page number
 * @param perPage Items per page
 */
const loadDlFields = async (page: number = 1, perPage: number | undefined = undefined): Promise<void> => {
  isLoading.value = true
  try {
    let url = `/api/dl_fields/?page=${page}`
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`
    }
    const response = await request(url)
    await ensureSuccess(response)

    const json = await response.json()
    const { items, pagination: paginationData } = await parse_list_response<DLField>(json)

    dlFields.value = sortDlFields(items)
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
 * Fetches a single dl field by ID from the API.
 * @param id DLField ID
 * @returns DLField or null on error
 */
const getDlField = async (id: number): Promise<DLField | null> => {
  try {
    const response = await request(`/api/dl_fields/${id}`)
    await ensureSuccess(response)

    const json = await response.json()
    const field = await parse_api_response<DLField>(json)

    lastError.value = null
    return field
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Creates a new dl field via API.
 * @param field DLFieldRequest to create
 * @param callback Optional callback with APIResponse result
 * @returns Created DLField or null on error
 */
const createDlField = async (
  field: DLFieldRequest,
  callback?: (response: APIResponse<DLField>) => void,
): Promise<DLField | null> => {
  addInProgress.value = true
  try {
    const response = await request('/api/dl_fields/', {
      method: 'POST',
      body: JSON.stringify(field),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const created = await parse_api_response<DLField>(json)

    updateDlFields(created)
    notify.success('DL field created.')
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
 * Updates an existing dl field via API (PUT - full update).
 * @param id DLField ID
 * @param field Updated DLField data
 * @param callback Optional callback with APIResponse result
 * @returns Updated DLField or null on error
 */
const updateDlField = async (
  id: number,
  field: DLField,
  callback?: (response: APIResponse<DLField>) => void,
): Promise<DLField | null> => {
  addInProgress.value = true
  try {
    if (field.id) {
      field.id = undefined
    }
    const response = await request(`/api/dl_fields/${id}`, {
      method: 'PUT',
      body: JSON.stringify(field),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<DLField>(json)

    updateDlFields(updated)
    notify.success(`DL field '${updated.name}' updated.`)
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
 * Partially updates an existing dl field via API (PATCH).
 * @param id DLField ID
 * @param patch Partial DLField data to update
 * @param callback Optional callback with APIResponse result
 * @returns Updated DLField or null on error
 */
const patchDlField = async (
  id: number,
  patch: Partial<DLField>,
  callback?: (response: APIResponse<DLField>) => void,
): Promise<DLField | null> => {
  addInProgress.value = true
  try {
    if (patch.id) {
      patch.id = undefined
    }
    const response = await request(`/api/dl_fields/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<DLField>(json)

    updateDlFields(updated)
    notify.success(`DL field '${updated.name}' updated.`)
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
 * Deletes a dl field by ID via API.
 * @param id DLField ID
 * @param callback Optional callback with APIResponse result
 * @returns true if deleted, false on error
 */
const deleteDlField = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/dl_fields/${id}`, { method: 'DELETE' })
    await ensureSuccess(response)

    removeDlField(id)
    notify.success('DL field deleted.')
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
 * Clears the last error message.
 */
const clearError = () => lastError.value = null

/**
 * useDlFields composable
 *
 * Returns reactive state and CRUD methods for dl fields.
 * @returns Object with state and API methods
 */
export const useDlFields = () => ({
  dlFields: readonly(dlFields),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadDlFields,
  getDlField,
  createDlField,
  updateDlField,
  patchDlField,
  deleteDlField,
  clearError,
  throwInstead,
})
