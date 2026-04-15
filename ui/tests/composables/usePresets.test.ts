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
import { usePresets } from '~/composables/usePresets'
// eslint-disable-next-line import/first
import type { Preset, PresetRequest } from '~/types/presets'
// eslint-disable-next-line import/first
import type { Pagination } from '~/types/responses'

const mockPreset: Preset = {
  id: 1,
  name: 'Test Preset',
  description: 'Test description',
  folder: 'Downloads',
  template: '%(title)s.%(ext)s',
  cookies: 'cookie=value',
  cli: '--format best',
  default: false,
  priority: 10,
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

describe('usePresets', () => {
  beforeEach(() => {
    successMock.mockClear()
    errorMock.mockClear()
  })

  describe('loadPresets', () => {
    it('loads presets with pagination successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: {
            items: [mockPreset],
            pagination: mockPagination,
          },
        }),
      )

      const presets = usePresets()
      await presets.loadPresets()

      expect(presets.presets.value).toHaveLength(1)
      expect(presets.presets.value[0]).toEqual(mockPreset)
      expect(presets.pagination.value).toEqual(mockPagination)
      expect(presets.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

    it('sorts presets by priority then name', async () => {
      const items = [
        { ...mockPreset, id: 1, name: 'B', priority: 2 },
        { ...mockPreset, id: 2, name: 'A', priority: 2 },
        { ...mockPreset, id: 3, name: 'C', priority: 1 },
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

      const presets = usePresets()
      await presets.loadPresets()

      const sorted = presets.presets.value
      expect(sorted[0].priority).toBe(2)
      expect(sorted[0].name).toBe('A')
      expect(sorted[1].priority).toBe(2)
      expect(sorted[1].name).toBe('B')
      expect(sorted[2].priority).toBe(1)
      expect(sorted[2].name).toBe('C')
      requestSpy.mockRestore()
    })

  })

  describe('getPreset', () => {
    it('fetches a single preset successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      const result = await presets.getPreset(1)

      expect(result).toEqual(mockPreset)
      expect(presets.lastError.value).toBeNull()
      requestSpy.mockRestore()
    })

  })

  describe('createPreset', () => {
    it('creates a preset successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      const initialTotal = presets.pagination.value.total
      const newPreset: PresetRequest = {
        name: 'New Preset',
        description: 'Desc',
        cli: '--format best',
      }

      const result = await presets.createPreset(newPreset)

      expect(result).toEqual(mockPreset)
      expect(presets.presets.value).toContainEqual(mockPreset)
      expect(presets.pagination.value.total).toBeGreaterThanOrEqual(initialTotal)
      requestSpy.mockRestore()
    })

  })

  describe('updatePreset', () => {
    it('updates a preset successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      const result = await presets.updatePreset(1, mockPreset)

      expect(result).toEqual(mockPreset)
      requestSpy.mockRestore()
    })

    it('strips id from update payload', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      await presets.updatePreset(1, { ...mockPreset, default: true })

      const requestBody = JSON.parse((requestSpy.mock.calls[0][1] as any).body)
      expect(requestBody.id).toBeUndefined()
      expect(requestBody.default).toBe(false)
      requestSpy.mockRestore()
    })
  })

  describe('patchPreset', () => {
    it('patches a preset successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockPreset, priority: 20 },
        }),
      )

      const presets = usePresets()
      const result = await presets.patchPreset(1, { priority: 20 })

      expect(result?.priority).toBe(20)
      requestSpy.mockRestore()
    })

    it('strips id and default from patch payload', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      await presets.patchPreset(1, { id: 10, default: true })

      const requestBody = JSON.parse((requestSpy.mock.calls[0][1] as any).body)
      expect(requestBody.id).toBeUndefined()
      expect(requestBody.default).toBe(false)
      requestSpy.mockRestore()
    })
  })

  describe('deletePreset', () => {
    it('deletes a preset successfully', async () => {
      const requestSpy = spyOn(utils, 'request')
      requestSpy.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      const initialTotal = presets.pagination.value.total

      const result = await presets.deletePreset(mockPreset.id!)

      expect(result).toBe(true)
      expect(presets.pagination.value.total).toBe(Math.max(0, initialTotal - 1))
      requestSpy.mockRestore()
    })

  })

})
