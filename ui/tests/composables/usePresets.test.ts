import * as utils from '~/utils/index'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { usePresets } from '~/composables/usePresets'
import type { Preset, PresetRequest } from '~/types/presets'
import type { Pagination } from '~/types/responses'

vi.mock('~/composables/useNotification', () => {
  const success = vi.fn()
  const error = vi.fn()
  return {
    useNotification: () => ({ success, error }),
    default: () => ({ success, error }),
  }
})

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
    vi.clearAllMocks()
  })

  describe('loadPresets', () => {
    it('loads presets with pagination successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('sorts presets by priority then name', async () => {
      const items = [
        { ...mockPreset, id: 1, name: 'B', priority: 2 },
        { ...mockPreset, id: 2, name: 'A', priority: 2 },
        { ...mockPreset, id: 3, name: 'C', priority: 1 },
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

      const presets = usePresets()
      await presets.loadPresets()

      const sorted = presets.presets.value
      expect(sorted[0].priority).toBe(2)
      expect(sorted[0].name).toBe('A')
      expect(sorted[1].priority).toBe(2)
      expect(sorted[1].name).toBe('B')
      expect(sorted[2].priority).toBe(1)
      expect(sorted[2].name).toBe('C')
    })

    it('handles empty presets list', async () => {
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

      const presets = usePresets()
      await presets.loadPresets()

      expect(presets.presets.value).toEqual([])
      expect(presets.lastError.value).toBeNull()
    })

    it('handles errors during load', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const presets = usePresets()
      await presets.loadPresets()

      expect(presets.lastError.value).toBeTruthy()
    })
  })

  describe('getPreset', () => {
    it('fetches a single preset successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('handles 404 not found', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          jsonData: { error: 'Preset not found' },
        }),
      )

      const presets = usePresets()
      const result = await presets.getPreset(999)

      expect(result).toBeNull()
      expect(presets.lastError.value).toBeTruthy()
    })
  })

  describe('createPreset', () => {
    it('creates a preset successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
      expect(presets.pagination.value.total).toBe(initialTotal + 1)
    })

    it('calls callback on success', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const callback = vi.fn()
      const presets = usePresets()
      const newPreset: PresetRequest = {
        name: 'New Preset',
        description: 'Desc',
        cli: '--format best',
      }

      await presets.createPreset(newPreset, callback)

      expect(callback).toHaveBeenCalledWith({
        success: true,
        error: null,
        detail: null,
        data: mockPreset,
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
      const presets = usePresets()
      const newPreset: PresetRequest = {
        name: 'New Preset',
        description: 'Desc',
        cli: '--format best',
      }

      await presets.createPreset(newPreset, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
        }),
      )
    })
  })

  describe('updatePreset', () => {
    it('updates a preset successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const presets = usePresets()
      const result = await presets.updatePreset(1, mockPreset)

      expect(result).toEqual(mockPreset)
    })

    it('strips id from update payload', async () => {
      const requestSpy = vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })
  })

  describe('patchPreset', () => {
    it('patches a preset successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: { ...mockPreset, priority: 20 },
        }),
      )

      const presets = usePresets()
      const result = await presets.patchPreset(1, { priority: 20 })

      expect(result?.priority).toBe(20)
    })

    it('strips id and default from patch payload', async () => {
      const requestSpy = vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })
  })

  describe('deletePreset', () => {
    it('deletes a preset successfully', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
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
    })

    it('calls callback on delete success', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        }),
      )

      const callback = vi.fn()
      const presets = usePresets()

      await presets.deletePreset(1, callback)

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
          jsonData: { error: 'Preset not found' },
        }),
      )

      const callback = vi.fn()
      const presets = usePresets()

      await presets.deletePreset(999, callback)

      expect(callback).toHaveBeenCalledWith(
        expect.objectContaining({
          success: false,
          error: expect.any(String),
          data: false,
        }),
      )
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

      const presets = usePresets()
      presets.throwInstead.value = true

      await expect(presets.loadPresets()).rejects.toThrow()
    })

    it('clears error on clearError call', async () => {
      vi.spyOn(utils, 'request').mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          jsonData: { error: 'Server error' },
        }),
      )

      const presets = usePresets()
      presets.throwInstead.value = false

      await presets.loadPresets()

      expect(presets.lastError.value).toBeTruthy()

      presets.clearError()

      expect(presets.lastError.value).toBeNull()
    })
  })

  describe('addInProgress state', () => {
    it('sets addInProgress during create operation', async () => {
      let inProgressDuringCall = false

      vi.spyOn(utils, 'request').mockImplementation(async () => {
        const presets = usePresets()
        inProgressDuringCall = presets.addInProgress.value
        return createMockResponse({
          ok: true,
          status: 200,
          jsonData: mockPreset,
        })
      })

      const presets = usePresets()
      const newPreset: PresetRequest = {
        name: 'New Preset',
        description: 'Desc',
        cli: '--format best',
      }

      await presets.createPreset(newPreset)

      expect(inProgressDuringCall).toBe(true)
      expect(presets.addInProgress.value).toBe(false)
    })
  })
})
