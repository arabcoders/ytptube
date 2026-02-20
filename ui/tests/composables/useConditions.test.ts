import { describe, it, expect, beforeEach, mock, spyOn } from 'bun:test'

const successMock = mock(() => {})
const errorMock = mock(() => {})

globalThis.useNotificationStore = () => ({
  add: () => 'test-id',
  markRead: () => {},
}) as any

const documentStub: any = globalThis.document ?? {}
documentStub.hasFocus = () => true
;(globalThis as any).document = documentStub

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
import { useConditions } from '~/composables/useConditions'
// eslint-disable-next-line import/first
import type { Condition, Pagination } from '~/types/conditions'

const mockCondition: Condition = {
  id: 1,
  name: 'Test Condition',
  filter: 'duration > 60',
  cli: '--format best',
  extras: { test: true },
  enabled: true,
  priority: 10,
  description: 'Test description',
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

describe('useConditions', () => {
  beforeEach(() => {
    successMock.mockClear()
    errorMock.mockClear()
  })

  describe('loadConditions', () => {
    it('loads conditions with pagination successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockCondition],
            pagination: mockPagination,
          },
        }),
      )

      const conditions = useConditions()
      await conditions.loadConditions()

      expect(conditions.conditions.value).toHaveLength(1)
      expect(conditions.conditions.value[0]).toEqual(mockCondition)
      expect(conditions.pagination.value).toEqual(mockPagination)
      expect(conditions.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('sorts conditions by priority then name', async () => {
      const items = [
        { ...mockCondition, id: 1, name: 'B', priority: 2 },
        { ...mockCondition, id: 2, name: 'A', priority: 2 },
        { ...mockCondition, id: 3, name: 'C', priority: 1 },
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

      const conditions = useConditions()
      await conditions.loadConditions()

      const sorted = conditions.conditions.value
      expect(sorted[0].priority).toBe(2)
      expect(sorted[0].name).toBe('A')
      expect(sorted[1].priority).toBe(2)
      expect(sorted[1].name).toBe('B')
      expect(sorted[2].priority).toBe(1)
      expect(sorted[2].name).toBe('C')
      requestSpy.mockRestore()
    })

    it('handles empty conditions list', async () => {
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

      const conditions = useConditions()
      await conditions.loadConditions()

      expect(conditions.conditions.value).toEqual([])
      expect(conditions.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('handles errors during load', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const conditions = useConditions()
      await conditions.loadConditions()

      expect(conditions.lastError.value).toBeTruthy()
      requestSpy.mockRestore()
    })
  })

  describe('getCondition', () => {
    it('fetches a single condition successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        }),
      )

      const conditions = useConditions()
      const result = await conditions.getCondition(1)

      expect(result).toEqual(mockCondition)
      expect(conditions.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('handles 404 not found', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Condition not found' },
        }),
      )

      const conditions = useConditions()
      const result = await conditions.getCondition(999)

      expect(result).toBeNull()
      expect(conditions.lastError.value).toBeTruthy()
      requestSpy.mockRestore()
    })
  })

  describe('createCondition', () => {
    it('creates a condition successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        }),
      )

      const conditions = useConditions()
      const initialTotal = conditions.pagination.value.total
      const newCondition = { ...mockCondition }
      delete newCondition.id

      const result = await conditions.createCondition(newCondition)

      expect(result).toEqual(mockCondition)
      expect(conditions.conditions.value).toContainEqual(mockCondition)
      expect(conditions.pagination.value.total).toBe(initialTotal + 1)
      requestSpy.mockRestore()
    })

    it('calls callback on success', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()
      const newCondition = { ...mockCondition }
      delete newCondition.id

      await conditions.createCondition(newCondition, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: mockCondition,
      })
      requestSpy.mockRestore()
    })

    it('calls callback on error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: { detail: [{ loc: ['name'], msg: 'Field required', type: 'value_error' }] },
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()
      const newCondition = { ...mockCondition }
      delete newCondition.id

      await conditions.createCondition(newCondition, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
        }),
      )
      requestSpy.mockRestore()
    })
  })

  describe('updateCondition', () => {
    it('updates a condition successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockCondition, name: 'Updated Name' },
        }),
      )

      const conditions = useConditions()
      const updated = { ...mockCondition, name: 'Updated Name' }

      const result = await conditions.updateCondition(1, updated)

      expect(result?.name).toBe('Updated Name')
      requestSpy.mockRestore()
    })

    it('calls callback on success', async () => {
      const updatedCondition = { ...mockCondition, name: 'Updated' }
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: updatedCondition,
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()

      await conditions.updateCondition(1, updatedCondition, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: updatedCondition,
      })
      requestSpy.mockRestore()
    })

    it('removes id field from condition before sending', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        }),
      )

      const conditions = useConditions()
      await conditions.updateCondition(1, mockCondition)

      const requestBody = JSON.parse((requestSpy.mock.calls[0][1] as any).body)
      expect(requestBody.id).toBeUndefined()
      requestSpy.mockRestore()
    })
  })

  describe('patchCondition', () => {
    it('patches a condition successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockCondition, enabled: false },
        }),
      )

      const conditions = useConditions()
      const result = await conditions.patchCondition(1, { enabled: false })

      expect(result?.enabled).toBe(false)
      requestSpy.mockRestore()
    })

    it('calls callback on patch success', async () => {
      const patchedCondition = { ...mockCondition, enabled: false }
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: patchedCondition,
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()

      await conditions.patchCondition(1, { enabled: false }, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: patchedCondition,
      })
      requestSpy.mockRestore()
    })

    it('handles validation errors with callback', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: { detail: [{ loc: ['priority'], msg: 'Invalid priority', type: 'value_error' }] },
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()

      await conditions.patchCondition(1, { priority: -1 }, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
        }),
      )
      requestSpy.mockRestore()
    })
  })

  describe('deleteCondition', () => {
    it('deletes a condition successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        }),
      )

      const conditions = useConditions()
      const initialTotal = conditions.pagination.value.total

      const result = await conditions.deleteCondition(mockCondition.id!)

      expect(result).toBe(true)
      expect(conditions.pagination.value.total).toBe(Math.max(0, initialTotal - 1))
      requestSpy.mockRestore()
    })

    it('calls callback on delete success', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()

      await conditions.deleteCondition(1, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: true,
      })
      requestSpy.mockRestore()
    })

    it('calls callback on delete error', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Condition not found' },
        }),
      )

      const callback = mock(() => {})
      const conditions = useConditions()

      await conditions.deleteCondition(999, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
          data: false,
        }),
      )
      requestSpy.mockRestore()
    })
  })

  describe('testCondition', () => {
    it('tests a condition successfully', async () => {
      const testResponse = {
        status: true,
        condition: 'duration > 60',
        data: { duration: 120 },
      }

      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: testResponse,
        }),
      )

      const conditions = useConditions()
      const result = await conditions.testCondition({
        url: 'https://example.com/video',
        condition: 'duration > 60',
      })

      expect(result).toEqual(testResponse)
      expect(result?.status).toBe(true)
      requestSpy.mockRestore()
    })

    it('handles test errors', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 400,
          jsonData: { error: 'Invalid URL' },
        }),
      )

      const conditions = useConditions()
      const result = await conditions.testCondition({
        url: 'invalid',
        condition: 'test',
      })

      expect(result).toBeNull()
      expect(conditions.lastError.value).toBeTruthy()
      requestSpy.mockRestore()
    })
  })

  describe('error handling', () => {
    it('throws when throwInstead is true', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const conditions = useConditions()
      conditions.throwInstead.value = true

      await expect(conditions.loadConditions()).rejects.toThrow()
      requestSpy.mockRestore()
    })

    it('clears error on clearError call', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const conditions = useConditions()
      conditions.throwInstead.value = false

      await conditions.loadConditions()

      expect(conditions.lastError.value).toBeTruthy()

      conditions.clearError()

      expect(conditions.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })
  })

  describe('addInProgress state', () => {
    it('sets addInProgress during create operation', async () => {
      let inProgressDuringCall = false

      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockImplementation(async () => {
        const conditions = useConditions()
        inProgressDuringCall = conditions.addInProgress.value
        return createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockCondition,
        })
      })

      const conditions = useConditions()
      const newCondition = { ...mockCondition }
      delete newCondition.id

      await conditions.createCondition(newCondition)

      expect(inProgressDuringCall).toBe(true)
      expect(conditions.addInProgress.value).toBe(false)
      requestSpy.mockRestore()
    })
  })
})
