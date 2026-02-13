import { ref, readonly, computed, toRaw } from 'vue'

import { useNotification } from '~/composables/useNotification'
import { useConfigStore } from '~/stores/ConfigStore'
import { request, parse_api_error, sTrim, encodePath } from '~/utils'
import type { FileItem, Pagination } from '~/types/filebrowser'

const items = ref<FileItem[]>([])
const path = ref<string>('/')
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
})
const isLoading = ref<boolean>(false)
const lastError = ref<string | null>(null)
const selectedElms = ref<string[]>([])
const masterSelectAll = ref<boolean>(false)
const sort_by = ref<string>('name')
const sort_order = ref<string>('asc')
const search = ref<string>('')
const throwInstead = ref(false)
const notify = useNotification()

const readJson = async (response: Response): Promise<unknown> => {
  try {
    const clone = response.clone()
    return await clone.json()
  }
  catch {
    return null
  }
}

const ensureSuccess = async (response: Response): Promise<void> => {
  if (response.ok) {
    return
  }
  const payload = await readJson(response)
  const message = await parse_api_error(payload)
  throw new Error(message)
}

const handleError = (error: unknown): void => {
  const message = error instanceof Error ? error.message : 'Unexpected error occurred.'
  lastError.value = message
  notify.error(message)
}

const buildQueryParams = (page?: number): string => {
  const config = useConfigStore()
  const params = new URLSearchParams()
  params.set('page', String(page ?? pagination.value.page))
  params.set('per_page', String(config.app.default_pagination || 50))
  params.set('sort_by', sort_by.value)
  params.set('sort_order', sort_order.value)
  if (search.value) {
    params.set('search', search.value)
  }
  return params.toString()
}

const loadContents = async (dir: string = '/', page: number = 1): Promise<boolean> => {
  isLoading.value = true
  try {
    if (typeof dir !== 'string') {
      dir = '/'
    }

    dir = encodePath(sTrim(dir, '/'))
    const query = buildQueryParams(page)
    const response = await request(`/api/file/browser/${sTrim(dir, '/')}?${query}`)

    await ensureSuccess(response)

    const data = await response.json()

    items.value = data.contents || []
    path.value = data.path || '/'
    if (data.pagination) {
      pagination.value = data.pagination
    }

    selectedElms.value = []
    masterSelectAll.value = false
    lastError.value = null

    return true
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return false
  }
  finally {
    isLoading.value = false
  }
}

const changeSort = async (by: string): Promise<void> => {
  if (!['name', 'size', 'date', 'type'].includes(by)) {
    return
  }

  if (by !== sort_by.value) {
    sort_by.value = by
  }
  else {
    sort_order.value = sort_order.value === 'asc' ? 'desc' : 'asc'
  }

  await loadContents(path.value, 1)
}

const setSearch = async (value: string): Promise<void> => {
  search.value = value
  await loadContents(path.value, 1)
}

const setSortBy = (value: string): void => {
  sort_by.value = value
}

const setSortOrder = (value: string): void => {
  sort_order.value = value
}

const setSearchValue = (value: string): void => {
  search.value = value
}

const setPage = (value: number): void => {
  pagination.value.page = value
}

const changePage = async (page: number): Promise<void> => {
  await loadContents(path.value, page)
}

const performAction = async (
  item: FileItem,
  action: string,
  payload: Record<string, unknown>,
  callback?: (item: FileItem, action: string, data: Record<string, unknown>, source: FileItem) => void,
  multiple: boolean = false
): Promise<boolean> => {
  try {
    const response = await request('/api/file/actions', {
      method: 'POST',
      body: JSON.stringify([{ path: item.path, action, ...payload }]),
    })

    await ensureSuccess(response)

    const results = await response.json() as Array<{ path: string, status: boolean, error?: string, [key: string]: unknown }>

    for (const result of results) {
      if (!multiple && result.path !== item.path) {
        continue
      }

      if (!multiple && !result.status) {
        notify.error(`Failed to perform action: ${result.error || 'Unknown error'}`)
        return false
      }

      if (callback && typeof callback === 'function') {
        if (!multiple) {
          callback(item, action, payload as Record<string, unknown>, item)
        }
        else {
          const matchedItem = items.value.find(it => it.path === result.path)
          if (matchedItem) {
            callback(matchedItem, action, result as Record<string, unknown>, toRaw(item))
          }
        }
      }
    }

    return true
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return false
  }
}

const performMassAction = async (
  actions: Array<{ path: string, action: string, [key: string]: unknown }>,
  callback?: (result: { path: string, status: boolean, error?: string }) => void
): Promise<boolean> => {
  try {
    const response = await request('/api/file/actions', {
      method: 'POST',
      body: JSON.stringify(actions),
    })

    await ensureSuccess(response)

    const results = await response.json() as Array<{ path: string, status: boolean, error?: string }>

    for (const result of results) {
      if (!result.status) {
        notify.error(`Failed to perform action on '${result.path}': ${result.error || 'Unknown error'}`)
        continue
      }

      if (callback && typeof callback === 'function') {
        callback(result)
      }
    }

    return true
  }
  catch (error) {
    handleError(error)
    if (throwInstead.value) throw error
    return false
  }
}

const createDirectory = async (dir: string, newDir: string): Promise<boolean> => {
  const trimmedDir = sTrim(newDir, '/')
  if (!trimmedDir || trimmedDir === dir) {
    return false
  }

  const success = await performAction(
    { path: dir || '/' } as FileItem,
    'directory',
    { new_dir: trimmedDir },
    () => {
      notify.success(`Successfully created '${trimmedDir}'.`)
    }
  )

  return success
}

const renameItem = async (item: FileItem, newName: string): Promise<boolean> => {
  const trimmedName = newName.trim()
  if (!trimmedName || trimmedName === item.name) {
    return false
  }

  return await performAction(
    item,
    'rename',
    { new_name: trimmedName },
    (it, _, data) => {
      const source = data as { new_path?: string }
      if (source.new_path) {
        it.name = source.new_path.split('/').pop() || trimmedName
        it.path = source.new_path
      }
      notify.success(`Renamed '${item.name}'.`)
    },
    true
  )
}

const deleteItem = async (item: FileItem): Promise<boolean> => {
  return await performAction(
    item,
    'delete',
    {},
    () => {
      items.value = items.value.filter(i => i.path !== item.path)
      notify.warning(`Deleted '${item.name}'.`)
    }
  )
}

const moveItem = async (item: FileItem, newPath: string): Promise<boolean> => {
  const trimmedPath = sTrim(newPath, '/') || '/'
  if (!trimmedPath || trimmedPath === item.path) {
    return false
  }

  return await performAction(
    item,
    'move',
    { new_path: trimmedPath },
    (it, _, data) => {
      const source = data as { new_path?: string; path?: string }
      if (source.path) {
        items.value = items.value.filter(i => i.path !== source.path)
      }
      notify.success(`Moved '${item.name}' to '${trimmedPath}'.`)
    },
    true
  )
}

const deleteSelected = async (): Promise<boolean> => {
  if (selectedElms.value.length < 1) {
    notify.error('No items selected.')
    return false
  }

  const actions = selectedElms.value.map(p => {
    return { path: p, action: 'delete' }
  })

  const success = await performMassAction(actions, (result) => {
    const item = items.value.find(it => it.path === result.path)
    if (item) {
      items.value = items.value.filter(it => it.path !== result.path)
      notify.warning(`Deleted '${item.name}'.`)
    }
  })

  if (success) {
    selectedElms.value = []
  }

  return success
}

const moveSelected = async (newPath: string): Promise<boolean> => {
  if (selectedElms.value.length < 1) {
    notify.error('No items selected.')
    return false
  }

  const trimmedPath = sTrim(newPath, '/') || '/'
  const actions = selectedElms.value.map(p => ({
    path: p,
    action: 'move',
    new_path: trimmedPath,
  }))

  const success = await performMassAction(actions, (result) => {
    items.value = items.value.filter(it => it.path !== result.path)
    notify.success(`Moved '${result.path}' to '${trimmedPath}'.`)
  })

  if (success) {
    selectedElms.value = []
  }

  return success
}

const clearError = (): void => {
  lastError.value = null
}

const reset = (): void => {
  items.value = []
  path.value = '/'
  pagination.value = {
    page: 1,
    per_page: 50,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false,
  }
  selectedElms.value = []
  masterSelectAll.value = false
  search.value = ''
  lastError.value = null
}

const filteredItems = computed<FileItem[]>(() => {
  return items.value
})

export const useBrowser = () => ({
  items: readonly(items),
  path: readonly(path),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  lastError: readonly(lastError),
  selectedElms,
  masterSelectAll,
  sort_by,
  sort_order,
  search,
  filteredItems,

  loadContents,
  changeSort,
  setSearch,
  setSortBy,
  setSortOrder,
  setSearchValue,
  setPage,
  changePage,
  createDirectory,
  renameItem,
  deleteItem,
  moveItem,
  deleteSelected,
  moveSelected,
  performAction,
  performMassAction,
  clearError,
  reset,
  throwInstead,
})
