import { describe, it, expect, beforeEach, mock, spyOn } from 'bun:test'

const successMock = mock(() => {})
const errorMock = mock(() => {})

globalThis.useNotificationStore = () => ({
  add: () => 'test-id',
  markRead: () => {},
}) as any

mock.module('~/composables/useNotification', () => ({
  useNotification: () => ({ success: successMock, error: errorMock }),
  default: () => ({ success: successMock, error: errorMock }),
}))

mock.module('~/stores/notification', () => ({
  useNotificationStore: () => ({
    add: () => 'test-id',
    markRead: () => {},
  }),
}))

// eslint-disable-next-line import/first
import * as utils from '~/utils/index'
// eslint-disable-next-line import/first
import { useTasks } from '~/composables/useTasks'
// eslint-disable-next-line import/first
import type { Task, TaskInspectResponse, TaskMetadataResponse, Pagination } from '~/types/tasks'

const mockTask: Task = {
  id: 1,
  name: 'Test Task',
  url: 'https://www.youtube.com/channel/UCtest123',
  folder: 'youtube/Test',
  preset: 'default',
  timer: '0 12 * * *',
  template: '%(title)s.%(ext)s',
  cli: '--format best',
  auto_start: true,
  handler_enabled: true,
  enabled: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const mockPagination: Pagination = {
  page: 1,
  per_page: 50,
  total: 1,
  total_pages: 1,
  has_next: false,
  has_prev: false,
}

function createMockResponse({ ok, status, jsonData }: { ok: boolean; status: number; jsonData: any }) {
  return {
    ok,
    status,
    headers: new Headers(),
    redirected: false,
    statusText: '',
    type: 'basic',
    url: '',
    body: null,
    bodyUsed: false,
    clone() {
      return this
    },
    async json() {
      return jsonData
    },
    text: async () => JSON.stringify(jsonData),
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
  } as Response
}

describe('useTasks', () => {
  beforeEach(() => {
    successMock.mockClear()
    errorMock.mockClear()
    const tasks = useTasks()
    tasks.__resetForTesting()
  })

  describe('loadTasks', () => {
    it('load_tasks', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockTask],
            pagination: mockPagination,
          },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(tasks.tasks.value).toHaveLength(1)
      expect(tasks.tasks.value[0]).toEqual(mockTask)
      expect(tasks.pagination.value).toEqual(mockPagination)
      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('sort_name', async () => {
      const items = [
        { ...mockTask, id: 1, name: 'Zebra' },
        { ...mockTask, id: 2, name: 'Alpha' },
        { ...mockTask, id: 3, name: 'Beta' },
      ]

      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items,
            pagination: mockPagination,
          },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      const sorted = tasks.tasks.value
      expect(sorted[0].name).toBe('Alpha')
      expect(sorted[1].name).toBe('Beta')
      expect(sorted[2].name).toBe('Zebra')
      requestSpy.mockRestore()
    })

    it('handle_empty_list', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [],
            pagination: { ...mockPagination, total: 0 },
          },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(tasks.tasks.value).toEqual([])
      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('store_load_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(tasks.lastError.value).toBe('Server error')
      requestSpy.mockRestore()
    })

    it('pass_pagination', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockTask],
            pagination: { ...mockPagination, page: 2 },
          },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks(2, 25)

      expect(requestSpy).toHaveBeenCalledWith('/api/tasks/?page=2&per_page=25')
      requestSpy.mockRestore()
    })
  })

  describe('getTask', () => {
    it('get_task', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      const tasks = useTasks()
      const result = await tasks.getTask(1)

      expect(result).toEqual(mockTask)
      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('store_404_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.getTask(999)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBe('Task not found')
      requestSpy.mockRestore()
    })
  })

  describe('createTask', () => {
    it('create_task', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      const tasks = useTasks()
      const initialTotal = tasks.pagination.value.total
      const newTask = { ...mockTask }
      delete (newTask as any).id

      const result = await tasks.createTask(newTask)

      expect(result).toEqual(mockTask)
      expect(tasks.tasks.value).toContainEqual(mockTask)
      expect(tasks.pagination.value.total).toBe(initialTotal + 1)
      requestSpy.mockRestore()
    })

  })

  describe('updateTask', () => {
    it('update_task', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockTask, name: 'Updated Name' },
        }),
      )

      const tasks = useTasks()
      const updated = { ...mockTask, name: 'Updated Name' }

      const result = await tasks.updateTask(1, updated)

      expect(result?.name).toBe('Updated Name')
      requestSpy.mockRestore()
    })

    it('strip_update_id', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      const tasks = useTasks()
      const taskWithId = { ...mockTask }
      await tasks.updateTask(1, taskWithId)

      const requestBody = JSON.parse((requestSpy.mock.calls[0][1] as any).body)
      expect('id' in requestBody).toBe(false)
      requestSpy.mockRestore()
    })
  })

  describe('patchTask', () => {
    it('patch_task', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockTask, enabled: false },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.patchTask(1, { enabled: false })

      expect(result?.enabled).toBe(false)
      requestSpy.mockRestore()
    })

  })

  describe('deleteTask', () => {
    it('delete_task', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      const tasks = useTasks()
      const initialTotal = tasks.pagination.value.total

      const result = await tasks.deleteTask(mockTask.id!)

      expect(result).toBe(true)
      expect(tasks.pagination.value.total).toBe(Math.max(0, initialTotal - 1))
      requestSpy.mockRestore()
    })

  })

  describe('inspectTaskHandler', () => {
    it('inspect_handler', async () => {
      const inspectResponse: TaskInspectResponse = {
        matched: true,
        handler: 'YoutubeHandler',
        supported: true,
        items: [
          {
            url: 'https://www.youtube.com/watch?v=test123',
            title: 'Test Video',
            archive_id: 'youtube test123',
            metadata: { published: '2024-01-01T00:00:00Z' },
          },
        ],
        metadata: {
          feed_url: 'https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123',
          entry_count: 1,
        },
      }

      const fetchSpy = spyOn(globalThis, 'fetch')
      fetchSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: inspectResponse,
        }),
      )

      const tasks = useTasks()
      const result = await tasks.inspectTaskHandler({
        url: 'https://www.youtube.com/channel/UCtest123',
      })

      expect(result).toEqual(inspectResponse)
      expect(result?.matched).toBe(true)
      expect(result?.handler).toBe('YoutubeHandler')
      fetchSpy.mockRestore()
    })

    it('handle_unsupported_handler', async () => {
      const inspectResponse: TaskInspectResponse = {
        matched: false,
        handler: null,
        supported: false,
        items: [],
        metadata: null,
      }

      const fetchSpy = spyOn(globalThis, 'fetch')
      fetchSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: inspectResponse,
        }),
      )

      const tasks = useTasks()
      const result = await tasks.inspectTaskHandler({
        url: 'https://unsupported.com',
      })

      expect(result?.supported).toBe(false)
      expect(result?.matched).toBe(false)
      fetchSpy.mockRestore()
    })

    it('store_inspect_error', async () => {
      const fetchSpy = spyOn(globalThis, 'fetch')
      fetchSpy.mockRejectedValueOnce(new Error('Network error'))

      const tasks = useTasks()
      const result = await tasks.inspectTaskHandler({
        url: 'invalid',
      })

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBe('Network error')
      fetchSpy.mockRestore()
    })
  })

  describe('markTaskItems', () => {
    it('mark_items', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { message: 'Marked 15 items' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.markTaskItems(1)

      expect(result).toBe('Marked 15 items')
      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('store_mark_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.markTaskItems(999)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBe('Task not found')
      requestSpy.mockRestore()
    })
  })

  describe('unmarkTaskItems', () => {
    it('unmark_items', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { message: 'Unmarked 10 items' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.unmarkTaskItems(1)

      expect(result).toBe('Unmarked 10 items')
      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('store_unmark_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.unmarkTaskItems(999)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBe('Task not found')
      requestSpy.mockRestore()
    })
  })

  describe('generateTaskMetadata', () => {
    it('generate_metadata', async () => {
      const metadataResponse: TaskMetadataResponse = {
        status: 'success',
        generated: ['tvshow.nfo', 'info.json', 'poster.jpg'],
      }

      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: metadataResponse,
        }),
      )

      const tasks = useTasks()
      const result = await tasks.generateTaskMetadata(1)

      expect(result).toEqual(metadataResponse)
      expect(result?.status).toBe('success')
      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('store_metadata_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Failed to generate metadata' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.generateTaskMetadata(1)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBe('Failed to generate metadata')
      requestSpy.mockRestore()
    })
  })

  describe('error handling', () => {
    it('throw_on_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const tasks = useTasks()
      tasks.throwInstead.value = true

      await expect(tasks.loadTasks()).rejects.toThrow()
      requestSpy.mockRestore()
    })

    it('clear_error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const tasks = useTasks()
      tasks.throwInstead.value = false

      await tasks.loadTasks()

      expect(tasks.lastError.value).toBe('Server error')

      tasks.clearError()

      expect(tasks.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('parse_validation_errors', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: {
            detail: [
              { loc: ['name'], msg: 'Field required', type: 'value_error.missing' },
              { loc: ['url'], msg: 'Invalid URL format', type: 'value_error.url' },
            ],
          },
        }),
      )

      const tasks = useTasks()
      tasks.clearError()
      
      const newTask = { ...mockTask, name: '', url: '' }
      delete (newTask as any).id

      const result = await tasks.createTask(newTask)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBe('name: Field required, url: Invalid URL format')
      expect(tasks.lastError.value).toContain('name: Field required')
      expect(tasks.lastError.value).toContain('url: Invalid URL format')
      requestSpy.mockRestore()
    })
  })

  describe('addInProgress state', () => {
    it('set_add_in_progress', async () => {
      let inProgressDuringCall = false

      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockImplementation(async (_url, _options) => {
        const currentTasks = useTasks()
        inProgressDuringCall = currentTasks.addInProgress.value
        return createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        })
      })

      const tasks = useTasks()
      const newTask = { ...mockTask }
      delete (newTask as any).id

      await tasks.createTask(newTask)

      expect(inProgressDuringCall).toBe(true)
      expect(tasks.addInProgress.value).toBe(false)
      requestSpy.mockRestore()
    })

    it('reset_add_in_progress', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: { error: 'Bad request' },
        }),
      )

      const tasks = useTasks()
      const newTask = { ...mockTask }
      delete (newTask as any).id

      await tasks.createTask(newTask)

      expect(tasks.addInProgress.value).toBe(false)
      requestSpy.mockRestore()
    })
  })

  describe('isLoading state', () => {
    it('set_loading', async () => {
      let loadingDuringCall = false

      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockImplementation(async (_url, _options) => {
        const currentTasks = useTasks()
        loadingDuringCall = currentTasks.isLoading.value
        return createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockTask],
            pagination: mockPagination,
          },
        })
      })

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(loadingDuringCall).toBe(true)
      expect(tasks.isLoading.value).toBe(false)
      requestSpy.mockRestore()
    })
  })

  describe('task list updates', () => {
    it('update_list_item', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockTask],
            pagination: mockPagination,
          },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(tasks.tasks.value).toHaveLength(1)
      expect(tasks.tasks.value[0].name).toBe('Test Task')

      const updatedTask = { ...mockTask, name: 'Updated Name' }
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: updatedTask,
        }),
      )

      await tasks.updateTask(1, updatedTask)

      expect(tasks.tasks.value[0].name).toBe('Updated Name')
      requestSpy.mockRestore()
    })

    it('remove_list_item', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockTask],
            pagination: { ...mockPagination, total: 1 },
          },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(tasks.tasks.value).toHaveLength(1)
      expect(tasks.pagination.value.total).toBe(1)

      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      await tasks.deleteTask(1)

      expect(tasks.tasks.value).toHaveLength(0)
      expect(tasks.pagination.value.total).toBe(0)
      requestSpy.mockRestore()
    })
  })
})
