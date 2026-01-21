import { ref, readonly } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { request, parse_list_response, parse_api_response, parse_api_error } from '~/utils'
import type { notification } from '~/types/notification'
import type { APIResponse, Pagination } from '~/types/responses'

/**
 * List of all notifications in memory.
 */
const notifications = ref<Array<notification>>([])
/**
 * Pagination state for notifications list.
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
 * List of allowed notification events.
 */
const events = ref<Array<string>>([])
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
 * Sorts notifications by name (A-Z).
 * @param items Array of notifications
 * @returns Sorted array of notifications
 */
const sortNotifications = (items: Array<notification>): Array<notification> => {
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
 * Updates or adds a notification in the list, keeping sort order.
 * Also increments pagination.total if it's a new notification.
 * @param item Notification to update/add
 */
const updateNotifications = (item: notification): void => {
  const isNew = !notifications.value.some(existing => existing.id === item.id)
  notifications.value = sortNotifications([
    ...notifications.value.filter(existing => existing.id !== item.id),
    item,
  ])
  if (isNew) {
    pagination.value.total++
  }
}

/**
 * Removes a notification from the list by ID.
 * Also decrements pagination.total.
 * @param id Notification ID
 */
const removeNotification = (id: number) => {
  const initialLength = notifications.value.length
  notifications.value = notifications.value.filter(item => item.id !== id)
  if (notifications.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1)
  }
}

/**
 * Loads notification targets from the API with pagination support.
 * @param page Page number
 * @param perPage Items per page
 */
const loadNotifications = async (page: number = 1, perPage: number | undefined = undefined): Promise<void> => {
  await loadNotificationEvents()

  isLoading.value = true
  try {
    let url = `/api/notifications/?page=${page}`
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`
    }
    const response = await request(url)
    await ensureSuccess(response)

    const json = await response.json()
    const { items, pagination: paginationData } = await parse_list_response<notification>(json)

    notifications.value = sortNotifications(items)
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
 * Loads notification events from the API.
 */
const loadNotificationEvents = async (): Promise<void> => {
  if (events.value.length > 0) {
    return
  }

  try {
    const response = await request('/api/notifications/events/')
    await ensureSuccess(response)

    const json = await response.json()
    events.value = Array.isArray(json?.events) ? json.events : []
    lastError.value = null
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
  }
}

/**
 * Fetches a single notification by ID from the API.
 * @param id Notification ID
 * @returns Notification or null on error
 */
const getNotification = async (id: number): Promise<notification | null> => {
  try {
    const response = await request(`/api/notifications/${id}`)
    await ensureSuccess(response)

    const json = await response.json()
    const item = await parse_api_response<notification>(json)

    lastError.value = null
    return item
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return null
  }
}

/**
 * Creates a new notification via API.
 * @param item Notification to create
 * @param callback Optional callback with APIResponse result
 * @returns Created notification or null on error
 */
const createNotification = async (
  item: Omit<notification, 'id'>,
  callback?: (response: APIResponse<notification>) => void,
): Promise<notification | null> => {
  addInProgress.value = true
  try {
    const response = await request('/api/notifications/', {
      method: 'POST',
      body: JSON.stringify(item),
    })
    await ensureSuccess(response)

    const json = await response.json()
    const created = await parse_api_response<notification>(json)

    updateNotifications(created)
    notify.success('Notification target created.')
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
 * Updates an existing notification via API (PUT - full update).
 * @param id Notification ID
 * @param item Updated notification data
 * @param callback Optional callback with APIResponse result
 * @returns Updated notification or null on error
 */
const updateNotification = async (
  id: number,
  item: notification,
  callback?: (response: APIResponse<notification>) => void,
): Promise<notification | null> => {
  addInProgress.value = true
  try {
    if (item.id) {
      item.id = undefined
    }
    const response = await request(`/api/notifications/${id}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    })
    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<notification>(json)

    updateNotifications(updated)
    notify.success(`Notification target '${updated.name}' updated.`)
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
 * Partially updates an existing notification via API (PATCH).
 * @param id Notification ID
 * @param patch Partial notification data to update
 * @param callback Optional callback with APIResponse result
 * @returns Updated notification or null on error
 */
const patchNotification = async (
  id: number,
  patch: Partial<notification>,
  callback?: (response: APIResponse<notification>) => void,
): Promise<notification | null> => {
  addInProgress.value = true
  try {
    if (patch.id) {
      patch.id = undefined
    }
    const response = await request(`/api/notifications/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    await ensureSuccess(response)

    const json = await response.json()
    const updated = await parse_api_response<notification>(json)

    updateNotifications(updated)
    notify.success(`Notification target '${updated.name}' updated.`)
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
 * Deletes a notification by ID via API.
 * @param id Notification ID
 * @param callback Optional callback with APIResponse result
 * @returns true if deleted, false on error
 */
const deleteNotification = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/notifications/${id}`, { method: 'DELETE' })
    await ensureSuccess(response)

    removeNotification(id)
    notify.success('Notification target deleted.')
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
 * Determines if a notification URL is for Apprise (non-HTTP).
 * @param url Notification URL
 * @returns true if Apprise URL, false otherwise
 */
const isApprise = (url: string) => !url.startsWith('http')

/**
 * Clears the last error message.
 */
const clearError = () => lastError.value = null

/**
 * useNotifications composable
 *
 * Returns reactive state and CRUD methods for notifications.
 * @returns Object with state and API methods
 */
export const useNotifications = () => ({
  notifications: readonly(notifications),
  pagination: readonly(pagination),
  events: readonly(events),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadNotifications,
  loadNotificationEvents,
  getNotification,
  createNotification,
  updateNotification,
  patchNotification,
  deleteNotification,
  clearError,
  throwInstead,
  isApprise
})
