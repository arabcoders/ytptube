import { defineStore } from 'pinia'
import type { item_request } from '~/types/item'
import type { StoreItem } from '~/types/store'
import { request } from '~/utils'

type StateType = 'queue' | 'history'
type KeyType = string

interface State {
  queue: Record<KeyType, StoreItem>
  history: Record<KeyType, StoreItem>
  pagination: {
    page: number
    per_page: number
    total: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
    isLoaded: boolean
    isLoading: boolean
  }
}

export const useStateStore = defineStore('state', () => {
  const state = reactive<State>({
    queue: {},
    history: {},
    pagination: {
      page: 1,
      per_page: 50,
      total: 0,
      total_pages: 0,
      has_next: false,
      has_prev: false,
      isLoaded: false,
      isLoading: false,
    },
  })

  const add = (type: StateType, key: KeyType, value: StoreItem): void => {
    if ('history' === type && state.pagination.total > 0) {
      state.pagination.total += 1
    }
    state[type][key] = value
  }

  const update = (type: StateType, key: KeyType, value: StoreItem): void => {
    state[type][key] = value
  }

  const remove = (type: StateType, key: KeyType): void => {
    if (!state[type][key]) {
      return
    }

    if ('history' === type && state.pagination.total > 0) {
      state.pagination.total -= 1
    }

    const { [key]: _, ...rest } = state[type]
    state[type] = rest
  }

  const get = (type: StateType, key: KeyType, defaultValue: StoreItem | null = null): StoreItem | null => {
    return state[type][key] || defaultValue
  }

  const has = (type: StateType, key: KeyType): boolean => {
    return !!state[type][key]
  }

  const clearAll = (type: StateType): void => {
    state[type] = {}
    if ('queue' === type) {
      return
    }

    state.pagination.total = 0
    state.pagination.page = 1
    state.pagination.total_pages = 0
    state.pagination.has_next = false
    state.pagination.has_prev = false
  }

  const addAll = (type: StateType, data: Record<KeyType, StoreItem>): void => {
    state[type] = data
  }

  const move = (fromType: StateType, toType: StateType, key: KeyType): void => {
    if (true === has(fromType, key)) {
      remove(fromType, key)
    }

    add(toType, key, get(fromType, key, {} as StoreItem) as StoreItem)
  }

  const count = (type: StateType): number => {
    if ('history' === type && state.pagination.total > 0) {
      return state.pagination.total
    }
    return Object.keys(state[type]).length
  }

  const loadPaginated = async (type: StateType, page: number = 1, per_page: number = 50, order: 'ASC' | 'DESC' = 'DESC', append: boolean = false, status?: string): Promise<void> => {
    if ('history' !== type) {
      throw new Error('Pagination is only supported for history type');
    }

    state.pagination.isLoading = true

    try {
      const params: Record<string, string> = {
        type: 'done',
        page: page.toString(),
        per_page: per_page.toString(),
        order
      }

      if (status) {
        params.status = status
      }

      const search = new URLSearchParams(params)

      const response = await request(`/api/history?${search}`)
      const data = await response.json()

      if (data.pagination) {
        state.pagination = { ...data.pagination, isLoaded: true, isLoading: false, }
        const items: Record<KeyType, StoreItem> = {}
        for (const item of data.items || []) {
          items[item._id] = item
        }

        state[type] = append ? { ...state[type], ...items } : items
      }
    } catch (error) {
      console.error(`Failed to load ${type} page ${page}:`, error)
      state.pagination.isLoading = false
    }
  }

  const loadNextPage = async (type: StateType, append: boolean = false): Promise<void> => {
    if ('history' !== type) {
      throw new Error('Pagination is only supported for history type');
    }

    if (!state.pagination.has_next || state.pagination.isLoading) {
      return
    }

    await loadPaginated(type, state.pagination.page + 1, state.pagination.per_page, 'DESC', append)
  }

  const loadPreviousPage = async (type: StateType): Promise<void> => {
    if ('history' !== type) {
      throw new Error('Pagination is only supported for history type');
    }

    if (!state.pagination.has_prev || state.pagination.isLoading) {
      return
    }

    await loadPaginated(type, state.pagination.page - 1, state.pagination.per_page)
  }

  const reloadCurrentPage = async (type: StateType): Promise<void> => {
    if ('history' !== type) {
      throw new Error('Pagination is only supported for history type');
    }
    if (!state.pagination.isLoaded) {
      return
    }

    await loadPaginated(type, state.pagination.page, state.pagination.per_page)
  }

  const getPagination = () => state.pagination

  const setHistoryCount = (count: number) => {
    state.pagination.total = count
    if (count > 0 && !state.pagination.isLoaded) {
      state.pagination.isLoaded = false
    }
  }

  /**
   * Load queue data from REST API.
   * Uses the /live endpoint to get real-time in-memory data with live progress.
   *
   * @returns Promise that resolves when queue is loaded
   */
  const loadQueue = async (): Promise<void> => {
    try {
      const response = await request('/api/history/live')
      const data = await response.json() as {
        "queue": Record<KeyType, StoreItem>,
        "history_count": number,
      }

      state.queue = data.queue || {}
      setHistoryCount(data.history_count)
    } catch (error) {
      console.error('Failed to load queue:', error)
      throw error
    }
  }

  /**
   * Add a download using WebSocket if connected, fallback to REST API.
   *
   * @param data - Download data (url, preset, folder, etc.)
   * @returns Promise that resolves when download is added
   */
  const addDownload = async (data: item_request): Promise<void> => {
    const socket = useSocketStore()
    const toast = useNotification()

    if (socket.isConnected) {
      socket.emit('add_url', data)
      return
    }

    try {
      const response = await request('/api/history/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      })

      if (!response.ok) {
        const error = await response.json()
        toast.error(error.error || 'Failed to add download')
        throw new Error(error.error || 'Failed to add download')
      }

      toast.success('Download added successfully')
      await loadQueue()
    } catch (error) {
      console.error('Failed to add download:', error)
      if (error instanceof Error && !error.message.includes('Failed to add download')) {
        toast.error('Failed to add download')
      }
      throw error
    }
  }

  /**
   * Start one or more downloads using WebSocket if connected, fallback to REST API.
   *
   * @param ids - Array of item IDs to start
   * @returns Promise that resolves when items are started
   */
  const startItems = async (ids: string[]): Promise<void> => {
    const socket = useSocketStore()
    const toast = useNotification()

    if (socket.isConnected) {
      ids.forEach(id => socket.emit('item_start', id))
      return
    }

    try {
      const response = await request('/api/history/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
      })

      if (!response.ok) {
        const error = await response.json()
        toast.error(error.error || 'Failed to start items')
        throw new Error(error.error || 'Failed to start items')
      }

      const result = await response.json()

      for (const id of ids) {
        if ('started' === result[id]) {
          const item = get('queue', id)
          if (item) {
            update('queue', id, { ...item, auto_start: true })
          }
        }
      }

      toast.success(`Started ${ids.length} item${1 === ids.length ? '' : 's'}`)
    } catch (error) {
      console.error('Failed to start items:', error)
      if (error instanceof Error && !error.message.includes('Failed to start items')) {
        toast.error('Failed to start items')
      }
      throw error
    }
  }

  /**
   * Pause one or more downloads using WebSocket if connected, fallback to REST API.
   *
   * @param ids - Array of item IDs to pause
   * @returns Promise that resolves when items are paused
   */
  const pauseItems = async (ids: string[]): Promise<void> => {
    const socket = useSocketStore()
    const toast = useNotification()

    if (socket.isConnected) {
      ids.forEach(id => socket.emit('item_pause', id))
      return
    }

    try {
      const response = await request('/api/history/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
      })

      if (!response.ok) {
        const error = await response.json()
        toast.error(error.error || 'Failed to pause items')
        throw new Error(error.error || 'Failed to pause items')
      }

      const result = await response.json()

      for (const id of ids) {
        if ('paused' === result[id]) {
          const item = get('queue', id)
          if (item) {
            update('queue', id, { ...item, auto_start: false })
          }
        }
      }

      toast.success(`Paused ${ids.length} item${1 === ids.length ? '' : 's'}`)
    } catch (error) {
      console.error('Failed to pause items:', error)
      if (error instanceof Error && !error.message.includes('Failed to pause items')) {
        toast.error('Failed to pause items')
      }
      throw error
    }
  }

  /**
   * Cancel one or more downloads using WebSocket if connected, fallback to REST API.
   *
   * @param ids - Array of item IDs to cancel
   * @returns Promise that resolves when items are cancelled
   */
  const cancelItems = async (ids: string[]): Promise<void> => {
    const socket = useSocketStore()
    const toast = useNotification()

    if (socket.isConnected) {
      ids.forEach(id => socket.emit('item_cancel', id))
      return
    }

    const itemsToMove: Record<string, StoreItem> = {}
    for (const id of ids) {
      const item = get('queue', id)
      if (item) {
        itemsToMove[id] = { ...item }
      }
    }

    try {
      const response = await request('/api/history/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids })
      })

      if (!response.ok) {
        const error = await response.json()
        toast.error(error.error || 'Failed to cancel items')
        throw new Error(error.error || 'Failed to cancel items')
      }

      const result = await response.json()

      for (const id of ids) {
        if ('ok' === result[id] && itemsToMove[id]) {
          remove('queue', id)
          const cancelledItem = { ...itemsToMove[id], status: 'cancelled' } as StoreItem
          add('history', id, cancelledItem)
        }
      }

      toast.success(`Cancelled ${ids.length} item${1 === ids.length ? '' : 's'}`)
    } catch (error) {
      console.error('Failed to cancel items:', error)
      if (error instanceof Error && !error.message.includes('Failed to cancel items')) {
        toast.error('Failed to cancel items')
      }
      throw error
    }
  }

  /**
   * Remove items using WebSocket if connected, fallback to REST API.
   *
   * @param type - The store type ('queue' or 'history')
   * @param ids - Array of item IDs to remove
   * @param removeFile - Whether to remove files from disk (default: false)
   * @returns Promise that resolves when items are removed
   */
  const removeItems = async (type: StateType, ids: string[], removeFile: boolean = false): Promise<void> => {
    const socket = useSocketStore()
    const toast = useNotification()

    if (socket.isConnected) {
      ids.forEach(id => socket.emit('item_delete', { id, remove_file: removeFile }))
      return
    }

    try {
      await deleteItems(type, { ids, removeFile })
    } catch (error) {
      console.error('Failed to remove items:', error)
      toast.error('Failed to remove items')
      throw error
    }
  }

  /**
   * Delete items by specific IDs or status filter.
   *
   * @param type - The store type ('queue' or 'history')
   * @param options - Delete options
   * @param options.ids - Array of item IDs to delete (if provided, status is ignored)
   * @param options.status - Status filter (e.g., 'finished' or '!finished')
   * @param options.removeFile - Whether to remove files from disk (default: true)
   *
   * @returns Number of items deleted
   */
  const deleteItems = async (
    type: StateType,
    options: { ids?: string[]; status?: string; removeFile?: boolean } = {}
  ): Promise<number> => {
    const { ids, status, removeFile = true } = options

    if (!ids && !status) {
      throw new Error('Either ids or status filter must be provided')
    }

    try {
      const body: Record<string, unknown> = {
        type: type === 'queue' ? 'queue' : 'done',
        remove_file: removeFile
      }

      if (ids) {
        body.ids = ids
      }

      if (status) {
        body.status = status
      }

      const response = await request('/api/history', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      const result = await response.json() as {
        items: Record<string, string>,
        deleted: number,
        error?: string,
        message?: string,
      }

      if (result.error || result.message || !response.ok) {
        throw new Error(result.error || result.message || 'Failed to delete items.')
      }

      for (const id of Object.keys(result.items)) {
        remove(type, id)
      }

      return result.deleted
    } catch (error) {
      console.error(`Failed to delete items:`, error)
      throw error
    }
  }

  return {
    ...toRefs(state),
    add,
    update,
    remove,
    get,
    has,
    clearAll,
    addAll,
    move,
    count,
    loadPaginated,
    loadNextPage,
    loadPreviousPage,
    reloadCurrentPage,
    getPagination,
    setHistoryCount,
    loadQueue,
    addDownload,
    startItems,
    pauseItems,
    cancelItems,
    removeItems,
    deleteItems,
  }
})
