import * as utils from '~/utils/index'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useTasks } from '~/composables/useTasks'
import type { Task, TaskInspectResponse, TaskMetadataResponse, Pagination } from '~/types/tasks'

vi.mock('~/composables/useNotification', () => {
  const success = vi.fn()
  const error = vi.fn()
  return {
    useNotification: () => ({ success, error }),
    default: () => ({ success, error }),
  }
})

// Sample data
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

// Helper to create a mock Response object
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
    vi.clearAllMocks()
    // Reset composable state between tests
    const tasks = useTasks()
    tasks.__resetForTesting()
  })

  describe('loadTasks', () => {
    it('loads tasks with pagination successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('sorts tasks by name A-Z', async () => {
      const items = [
        { ...mockTask, id: 1, name: 'Zebra' },
        { ...mockTask, id: 2, name: 'Alpha' },
        { ...mockTask, id: 3, name: 'Beta' },
      ]

      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles empty tasks list', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles errors during load', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const tasks = useTasks()
      await tasks.loadTasks()

      expect(tasks.lastError.value).toBeTruthy()
    })

    it('respects page and per_page parameters', async () => {
      const requestSpy = vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })
  })

  describe('getTask', () => {
    it('fetches a single task successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles 404 not found', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.getTask(999)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBeTruthy()
    })
  })

  describe('createTask', () => {
    it('creates a task successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('calls callback on success', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()
      const newTask = { ...mockTask }
      delete (newTask as any).id

      await tasks.createTask(newTask, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: mockTask,
      })
    })

    it('calls callback on error', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: { detail: [{ loc: ['name'], msg: 'Field required', type: 'value_error' }] },
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()
      const newTask = { ...mockTask }
      delete (newTask as any).id

      await tasks.createTask(newTask, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
        }),
      )
    })
  })

  describe('updateTask', () => {
    it('updates a task successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('calls callback on success', async () => {
      const updatedTask = { ...mockTask, name: 'Updated' }
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: updatedTask,
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()

      await tasks.updateTask(1, updatedTask, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: updatedTask,
      })
    })

    it('removes id field from task before sending', async () => {
      const requestSpy = vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
      // The id field should be removed before sending
      expect('id' in requestBody).toBe(false)
    })
  })

  describe('patchTask', () => {
    it('patches a task successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockTask, enabled: false },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.patchTask(1, { enabled: false })

      expect(result?.enabled).toBe(false)
    })

    it('calls callback on patch success', async () => {
      const patchedTask = { ...mockTask, enabled: false }
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: patchedTask,
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()

      await tasks.patchTask(1, { enabled: false }, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: patchedTask,
      })
    })

    it('handles validation errors with callback', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: { detail: [{ loc: ['timer'], msg: 'Invalid CRON expression', type: 'value_error' }] },
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()

      await tasks.patchTask(1, { timer: 'invalid' }, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
        }),
      )
    })
  })

  describe('deleteTask', () => {
    it('deletes a task successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('calls callback on delete success', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()

      await tasks.deleteTask(1, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: true,
      })
    })

    it('calls callback on delete error', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const callback = vi.fn()
      const tasks = useTasks()

      await tasks.deleteTask(999, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
          data: false,
        }),
      )
    })
  })

  describe('inspectTaskHandler', () => {
    it('inspects task handler successfully', async () => {
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

      global.fetch = vi.fn().mockResolvedValueOnce(
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
    })

    it('handles handler not supported', async () => {
      const inspectResponse: TaskInspectResponse = {
        matched: false,
        handler: null,
        supported: false,
        items: [],
        metadata: null,
      }

      global.fetch = vi.fn().mockResolvedValueOnce(
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
    })

    it('handles inspect errors', async () => {
      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'))

      const tasks = useTasks()
      const result = await tasks.inspectTaskHandler({
        url: 'invalid',
      })

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBeTruthy()
    })
  })

  describe('markTaskItems', () => {
    it('marks all items as downloaded successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles mark errors', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.markTaskItems(999)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBeTruthy()
    })
  })

  describe('unmarkTaskItems', () => {
    it('unmarks items successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles unmark errors', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Task not found' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.unmarkTaskItems(999)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBeTruthy()
    })
  })

  describe('generateTaskMetadata', () => {
    it('generates metadata successfully', async () => {
      const metadataResponse: TaskMetadataResponse = {
        status: 'success',
        generated: ['tvshow.nfo', 'info.json', 'poster.jpg'],
      }

      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles metadata generation errors', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Failed to generate metadata' },
        }),
      )

      const tasks = useTasks()
      const result = await tasks.generateTaskMetadata(1)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBeTruthy()
    })
  })

  describe('error handling', () => {
    it('throws when throwInstead is true', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const tasks = useTasks()
      tasks.throwInstead.value = true

      await expect(tasks.loadTasks()).rejects.toThrow()
    })

    it('clears error on clearError call', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const tasks = useTasks()
      tasks.throwInstead.value = false

      await tasks.loadTasks()

      // Error should be set after failed load
      expect(tasks.lastError.value).toBeTruthy()

      tasks.clearError()

      expect(tasks.lastError.value).toBeNull()
    })

    it('parses API validation errors correctly', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
      // Clear any previous error
      tasks.clearError()
      
      const newTask = { ...mockTask, name: '', url: '' }
      delete (newTask as any).id

      const result = await tasks.createTask(newTask)

      expect(result).toBeNull()
      expect(tasks.lastError.value).toBeTruthy()
      expect(tasks.lastError.value).toContain('name: Field required')
      expect(tasks.lastError.value).toContain('url: Invalid URL format')
    })
  })

  describe('addInProgress state', () => {
    it('sets addInProgress during create operation', async () => {
      let inProgressDuringCall = false

      vi.spyOn(utils, 'request').mockImplementation(async (_url, _options) => {
        // Get fresh instance to check current state
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
    })

    it('resets addInProgress on error', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })
  })

  describe('isLoading state', () => {
    it('sets isLoading during loadTasks operation', async () => {
      let loadingDuringCall = false

      vi.spyOn(utils, 'request').mockImplementation(async (_url, _options) => {
        // Get fresh instance to check current state
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
    })
  })

  describe('task list updates', () => {
    it('updates existing task in list', async () => {
      // Load initial task
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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

      // Update task
      const updatedTask = { ...mockTask, name: 'Updated Name' }
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: updatedTask,
        }),
      )

      await tasks.updateTask(1, updatedTask)

      expect(tasks.tasks.value[0].name).toBe('Updated Name')
    })

    it('removes deleted task from list', async () => {
      // Load initial task
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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

      // Delete task
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockTask,
        }),
      )

      await tasks.deleteTask(1)

      expect(tasks.tasks.value).toHaveLength(0)
      expect(tasks.pagination.value.total).toBe(0)
    })
  })
})
