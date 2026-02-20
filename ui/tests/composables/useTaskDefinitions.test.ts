import { beforeEach, describe, expect, it, mock, spyOn } from 'bun:test'

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
import { useTaskDefinitions } from '~/composables/useTaskDefinitions'
// eslint-disable-next-line import/first
import type { TaskDefinitionDetailed, TaskDefinitionSummary } from '~/types/task_definitions'

const summary: TaskDefinitionSummary = {
  id: 1,
  name: 'Test',
  priority: 1,
  updated_at: 123456,
}

const listPayload = (items: TaskDefinitionSummary[]) => ({
  items,
  pagination: {
    page: 1,
    per_page: 50,
    total: items.length,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  },
})

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
    successMock.mockClear()
    errorMock.mockClear()
  })

  it('sorts definitions by priority then name', async () => {
    const items = [
      { id: 1, name: 'B', priority: 2, updated_at: 1 },
      { id: 2, name: 'A', priority: 2, updated_at: 2 },
      { id: 3, name: 'C', priority: 1, updated_at: 3 },
    ]
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: listPayload(items),
    }))
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()
    expect(defs.definitions.value.map(d => d.id)).toEqual([3, 2, 1])
    requestSpy.mockRestore()
  })

  it('handles empty payload', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: listPayload([]),
    }))
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()
    expect(defs.definitions.value).toEqual([])
    expect(defs.lastError.value).toBeNull()
    requestSpy.mockRestore()
  })

  it('throws loadDefinitions error when throwInstead is true', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: false,
      status: 500,
      jsonData: { error: 'Server error' },
    }))
    const defs = useTaskDefinitions()
    defs.throwInstead.value = true
    await expect(defs.loadDefinitions()).rejects.toThrow('Server error')
    requestSpy.mockRestore()
  })

  it('returns null on getDefinition error', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: false,
      status: 404,
      jsonData: { error: 'Not Found' },
    }))
    const defs = useTaskDefinitions()
    defs.throwInstead.value = false
    const result = await defs.getDefinition(123)
    expect(result).toBeNull()
    expect(defs.lastError.value).toBe('Not Found')
    requestSpy.mockRestore()
  })

  it('creates definition successfully', async () => {
    const payload: TaskDefinitionDetailed = {
      id: 2,
      name: 'New',
      priority: 0,
      updated_at: 999,
      definition: { name: 'New', match: ['https://example.com'], parse: { link: { type: 'css', expression: 'a' } } },
    }
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: payload,
    }))
    const defs = useTaskDefinitions()
    await defs.createDefinition(payload.definition)
    expect(defs.definitions.value.some(item => item.id === payload.id)).toBe(true)
    requestSpy.mockRestore()
  })

  it('removes definition on deleteDefinition', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: listPayload([summary]),
    }))
    const defs = useTaskDefinitions()
    await defs.loadDefinitions()

    requestSpy.mockResolvedValueOnce(createMockResponse({
      ok: true,
      status: 200,
      jsonData: { status: 'deleted' },
    }))
    const result = await defs.deleteDefinition(summary.id)
    expect(result).toBe(true)
    expect(defs.definitions.value).toEqual([])
    requestSpy.mockRestore()
  })
})
