import { ref, readonly } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { request, parse_list_response, parse_api_response, parse_api_error } from '~/utils'
import type { Preset, PresetRequest } from '~/types/presets'
import type { APIResponse, Pagination } from '~/types/responses'

/**
 * List of all presets in memory.
 */
const presets = ref<Array<Preset>>([])
/**
 * Pagination state for presets list.
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
 * Sorts presets by priority (descending), then name (A-Z).
 * @param items Array of Preset
 * @returns Sorted array of Preset
 */
const sortPresets = (items: Array<Preset>): Array<Preset> => {
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
 * Updates or adds a preset in the presets list, keeping sort order.
 * Also increments pagination.total if it's a new preset.
 * @param preset Preset to update/add
 */
const updatePresets = (preset: Preset): void => {
  const isNew = !presets.value.some(item => item.id === preset.id)
  presets.value = sortPresets([
    ...presets.value.filter(item => item.id !== preset.id),
    preset,
  ])
  if (isNew) {
    pagination.value.total++
  }
}

/**
 * Removes a preset from the presets list by ID.
 * Also decrements pagination.total.
 * @param id Preset ID
 */
const removePreset = (id: number) => {
  const initialLength = presets.value.length
  presets.value = presets.value.filter(item => item.id !== id)
  if (presets.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1)
  }
}

/**
 * Loads all presets from the API with pagination support.
 * Updates presets, pagination, and lastError.
 * @param page Page number
 * @param perPage Items per page
 */
const loadPresets = async (page: number = 1, perPage: number | undefined = undefined): Promise<void> => {
  isLoading.value = true
  try {
    let url = `/api/presets/?page=${page}`
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`
    }
    const response = await request(url)
    await ensureSuccess(response)

    const json = await response.json()
    const { items, pagination: paginationData } = await parse_list_response<Preset>(json)

    presets.value = sortPresets(items)
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
 * Fetches a single preset by ID from the API.
 * @param id Preset ID
 * @returns Preset or null on error
 */
const getPreset = async (id: number): Promise<Preset | null> => {
  try {
    const response = await request(`/api/presets/${id}`)
    await ensureSuccess(response)

    const json = await response.json()
    const preset = await parse_api_response<Preset>(json)

    lastError.value = null
    return preset
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Creates a new preset via API.
 * @param preset PresetRequest to create
 * @param callback Optional callback with APIResponse result
 * @returns Created Preset or null on error
 */
const createPreset = async (
  preset: PresetRequest,
  callback?: (response: APIResponse<Preset>) => void,
): Promise<Preset | null> => {
  addInProgress.value = true
  try {
    const response = await request('/api/presets/', {
      method: 'POST',
      body: JSON.stringify(preset),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const created = await parse_api_response<Preset>(json)

    updatePresets(created)
    notify.success('Preset created.')
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
 * Updates an existing preset via API (PUT - full update).
 * @param id Preset ID
 * @param preset Updated Preset data
 * @param callback Optional callback with APIResponse result
 * @returns Updated Preset or null on error
 */
const updatePreset = async (
  id: number,
  preset: Preset,
  callback?: (response: APIResponse<Preset>) => void,
): Promise<Preset | null> => {
  addInProgress.value = true
  try {
    const payload = { ...preset }
    if (payload.id) {
      payload.id = undefined
    }
    if ('default' in payload) {
      payload.default = false
    }
    const response = await request(`/api/presets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<Preset>(json)

    updatePresets(updated)
    notify.success(`Preset '${updated.name}' updated.`)
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
 * Partially updates an existing preset via API (PATCH).
 * @param id Preset ID
 * @param patch Partial Preset data
 * @param callback Optional callback with APIResponse result
 * @returns Updated Preset or null on error
 */
const patchPreset = async (
  id: number,
  patch: Partial<Preset>,
  callback?: (response: APIResponse<Preset>) => void,
): Promise<Preset | null> => {
  addInProgress.value = true
  try {
    const payload = { ...patch }
    if (payload.id) {
      payload.id = undefined
    }
    if ('default' in payload) {
      payload.default = false
    }
    const response = await request(`/api/presets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })

    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<Preset>(json)

    updatePresets(updated)
    notify.success(`Preset '${updated.name}' updated.`)
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
 * Deletes a preset by ID via API.
 * @param id Preset ID
 * @param callback Optional callback with APIResponse result
 * @returns true if deleted, false on error
 */
const deletePreset = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/presets/${id}`, { method: 'DELETE' })
    await ensureSuccess(response)

    removePreset(id)
    notify.success('Preset deleted.')
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
 * usePresets composable
 *
 * Returns reactive state and CRUD methods for presets.
 * @returns Object with state and API methods
 */
export const usePresets = () => ({
  presets: readonly(presets),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadPresets,
  getPreset,
  createPreset,
  updatePreset,
  patchPreset,
  deletePreset,
  clearError,
  throwInstead,
})
