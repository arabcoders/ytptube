import * as utils from '~/utils/index'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useTaskDefinitions } from '~/composables/useTaskDefinitions'
import type { TaskDefinitionSummary } from '~/types/task_definitions'

vi.mock('~/composables/useNotification', () => {
  const success = vi.fn()
  const error = vi.fn()
  return {
    useNotification: () => ({ success, error }),
    default: () => ({ success, error })
  }
})

// Sample data
const summary: TaskDefinitionSummary = {
  id: 'abc',
  name: 'Test',
  priority: 1,
  updated_at: 123456,
}


// Helper to create a mock Response object
function createMockResponse({ ok, status, jsonData }: { ok: boolean, status: number, jsonData: any }) {
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
    clone() { return this },
    async json() { return jsonData },
    text: async () => JSON.stringify(jsonData),
    arrayBuffer: async () => new ArrayBuffer(0),
    blob: async () => new Blob(),
    formData: async () => new FormData(),
  } as Response
}

describe('useTaskDefinitions', () => {

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sorts definitions by priority then name', async () => {
    const items = [
      { id: '1', name: 'B', priority: 2, updated_at: 1 },
      { id: '2', name: 'A', priority: 2, updated_at: 2 },
      { id: '3', name: 'C', priority: 1, updated_at: 3 },
    ]
    vi.spyOn(utils, 'request').mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: items,
    }))
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()
    expect(defs.definitions.value.map(d => d.id)).toEqual(['3', '2', '1'])
  })

  it('handles empty payload', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: [],
    }))
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()
    expect(defs.definitions.value).toEqual([])
    expect(defs.lastError.value).toBeNull()
  })

  it('handles malformed payload', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ jsonData: [{}] })
    })
    const defs = useTaskDefinitions()
    await expect(defs.loadDefinitions()).resolves.toBeUndefined()
  })

  it('handles malformed payload (throws when throwInstead is true)', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ jsonData: [{}] })
    })
    const defs = useTaskDefinitions()
    defs.throwInstead.value = true
    await expect(defs.loadDefinitions()).rejects.toThrow()
  })

  it('handles duplicate IDs (no deduplication, both present)', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { id: 'dup', name: 'A', priority: 1 },
        { id: 'dup', name: 'B', priority: 2 },
      ]
    })
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()
    expect(defs.definitions.value.length).toBe(2)
    expect(defs.definitions.value[0].name).toBe('A')
    expect(defs.definitions.value[1].name).toBe('B')
  })

  it('handles error on getDefinition', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({})
    })
    const defs = useTaskDefinitions()
    await expect(defs.getDefinition('notfound')).rejects.toThrow('Request failed with status 404')
  })

  it('handles malformed getDefinition response', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    })
    const defs = useTaskDefinitions()
    await expect(defs.getDefinition('bad')).rejects.toThrow('Task definition response is missing definition payload.')
  })

  it('handles error on createDefinition', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({})
    })
    const defs = useTaskDefinitions()
    await expect(defs.createDefinition({ id: 'fail', name: 'Fail', priority: 1 })).rejects.toThrow('Request failed with status 400')
  })

  it('handles error on updateDefinition', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({})
    })
    const defs = useTaskDefinitions()
    await expect(defs.updateDefinition({ id: 'fail', name: 'Fail', priority: 1 })).rejects.toThrow('Request failed with status 400')
  })

  it('handles error on deleteDefinition', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({})
    })
    const defs = useTaskDefinitions()
    await expect(defs.deleteDefinition('fail')).rejects.toThrow('Request failed with status 400')
  })

  it('loads definitions successfully (duplicate test)', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: [summary],
    }))
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()
    expect(defs.definitions.value).toEqual([summary])
    expect(defs.lastError.value).toBeNull()
  })


  it('calls success notification on createDefinition', async () => {
    vi.spyOn(utils, 'request').mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    })
    const defs = useTaskDefinitions()
    await defs.createDefinition({ id: 'new', name: 'New', priority: 1 })
    // Access the spy directly from the mock
    const notify = (await import('~/composables/useNotification')).useNotification()
    expect(notify.success).toHaveBeenCalledWith('Task definition created.')
  })
});
