import { describe, it, expect, beforeAll, beforeEach, afterEach, mock, spyOn } from 'bun:test'
import { ref } from 'vue'

type StorageEntry<T> = ReturnType<typeof ref<T>>

type MockEventSourceMessage = {
  event: string
  id?: string
  data: string
}

type MockFetchEventSourceOptions = {
  method: string
  headers: Record<string, string>
  credentials: RequestCredentials
  signal: AbortSignal
  openWhenHidden: boolean
  onopen: (response: Response) => Promise<void> | void
  onmessage: (event: MockEventSourceMessage) => Promise<void> | void
  onclose: () => Promise<void> | void
  onerror: (error: unknown) => unknown
}

const runtimeConfig = {
  app: {
    baseURL: '/base-path',
  },
}

;(globalThis as typeof globalThis & { useRuntimeConfig?: () => typeof runtimeConfig }).useRuntimeConfig = () => runtimeConfig

mock.module('#imports', () => ({
  useRuntimeConfig: () => runtimeConfig,
}))

const storageMap = new Map<string, StorageEntry<unknown>>()

const cloneValue = <T>(value: T): T => {
  return JSON.parse(JSON.stringify(value)) as T
}

const useStorageFn = mock(<T>(key: string, defaultValue: T) => {
  if (!storageMap.has(key)) {
    storageMap.set(key, ref(cloneValue(defaultValue)))
  }

  return storageMap.get(key) as StorageEntry<T>
})

mock.module('@vueuse/core', () => ({
  useStorage: useStorageFn,
}))

const fetchEventSourceMock = mock(
  async (_url: string, _options: MockFetchEventSourceOptions): Promise<void> => {},
)

mock.module('@microsoft/fetch-event-source', () => ({
  fetchEventSource: fetchEventSourceMock,
}))

type MockResponseInput = {
  ok: boolean
  status: number
  jsonData: unknown
}

const createMockResponse = ({ ok, status, jsonData }: MockResponseInput): Response => {
  return {
    ok,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    redirected: false,
    statusText: ok ? 'OK' : 'Error',
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

let utils: Awaited<typeof import('~/utils/index')>
let useConsoleSession: typeof import('~/composables/useConsoleSession').useConsoleSession

beforeAll(async () => {
  utils = await import('~/utils/index')
  ;({ useConsoleSession } = await import('~/composables/useConsoleSession'))
})

beforeEach(() => {
  storageMap.clear()
  useStorageFn.mockClear()
  fetchEventSourceMock.mockClear()
})

afterEach(() => {
  const session = useConsoleSession()
  session.__resetForTesting()
})

describe('useConsoleSession', () => {
  it('start_session', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { session_id: 'sess-1', command: '--help', status: 'running' },
      }),
    )
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          session_id: 'sess-1',
          command: '--help',
          status: 'completed',
          last_event_id: '2',
          exit_code: 0,
        },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
      options.onmessage({
        event: 'output',
        id: '1',
        data: JSON.stringify({ line: 'line one' }),
      })
      options.onmessage({
        event: 'close',
        id: '2',
        data: JSON.stringify({ exitcode: 0 }),
      })
    })

    const session = useConsoleSession()
    const started = await session.startSession({ command: '--help', displayCommand: '--help' })
    await Promise.resolve()
    await Promise.resolve()

    expect(started).toBe(true)
    expect(session.state.value.sessionId).toBe('sess-1')
    expect(session.state.value.command).toBe('--help')
    expect(session.state.value.status).toBe('finished')
    expect(session.state.value.lastEventId).toBe('2')
    expect(session.state.value.exitCode).toBe(0)
    expect(session.state.value.transcript).toEqual([
      'user@YTPTube ~\n',
      '$ yt-dlp --help\n',
      'line one\n',
    ])

    requestSpy.mockRestore()
  })

  it('restore_with_cursor', async () => {
    const session = useConsoleSession()
    session.state.value = {
      sessionId: 'sess-restore',
      command: '--version',
      status: 'running',
      lastEventId: '42',
      exitCode: null,
      transcript: ['user@YTPTube ~\n', '$ yt-dlp --version\n'],
      error: '',
    }

    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { session_id: 'sess-restore', command: '--version', status: 'running', last_event_id: '42' },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
    })

    await session.restoreSession()

    expect(fetchEventSourceMock).toHaveBeenCalledTimes(1)

    const streamCall = fetchEventSourceMock.mock.calls[0]
    if (!streamCall) {
      throw new Error('Expected fetchEventSource to be called once.')
    }

    const [streamUrl, streamOptions] = streamCall
    expect(streamUrl).toContain('/base-path/api/system/terminal/sess-restore/stream?since=42')
    expect(streamOptions.headers['Last-Event-ID']).toBe('42')
    expect(streamOptions.method).toBe('GET')

    requestSpy.mockRestore()
  })

  it('mark_expired_404', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { session_id: 'sess-expired', command: '--help', status: 'running' },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(
        new Response(JSON.stringify({ error: 'Session expired' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    const session = useConsoleSession()
    const started = await session.startSession({ command: '--help', displayCommand: '--help' })

    expect(started).toBe(true)
    expect(session.state.value.status).toBe('expired')
    expect(session.state.value.command).toBe('--help')
    expect(session.state.value.transcript).toEqual([
      'user@YTPTube ~\n',
      '$ yt-dlp --help\n',
    ])
    expect(fetchEventSourceMock).toHaveBeenCalledTimes(1)

    requestSpy.mockRestore()
  })

  it('restore_after_stream_error', async () => {
    const session = useConsoleSession()
    session.state.value = {
      sessionId: 'sess-reconnect',
      command: '--version',
      status: 'error',
      lastEventId: '7',
      exitCode: null,
      transcript: ['user@YTPTube ~\n', '$ yt-dlp --version\n'],
      error: 'Stream failed',
    }

    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { session_id: 'sess-reconnect', command: '--version', status: 'running', last_event_id: '7' },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
    })

    await session.restoreSession()

    expect(fetchEventSourceMock).toHaveBeenCalledTimes(1)
    expect(session.state.value.status).toBe('running')
    expect(session.state.value.error).toBe('')

    requestSpy.mockRestore()
  })

  it('dedupe_replayed_events', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { session_id: 'sess-dupe', command: '--help', status: 'running' },
      }),
    )
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          session_id: 'sess-dupe',
          command: '--help',
          status: 'completed',
          last_event_id: '9',
          exit_code: 0,
        },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
      options.onmessage({
        event: 'output',
        id: '8',
        data: JSON.stringify({ line: 'first line' }),
      })
      options.onmessage({
        event: 'output',
        id: '8',
        data: JSON.stringify({ line: 'first line' }),
      })
      options.onmessage({
        event: 'close',
        id: '9',
        data: JSON.stringify({ exitcode: 0 }),
      })
    })

    const session = useConsoleSession()
    await session.startSession({ command: '--help', displayCommand: '--help' })
    await Promise.resolve()
    await Promise.resolve()

    expect(session.state.value.transcript).toEqual([
      'user@YTPTube ~\n',
      '$ yt-dlp --help\n',
      'first line\n',
    ])

    requestSpy.mockRestore()
  })

  it('refresh_final_status', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { session_id: 'sess-int', command: '--help', status: 'running' },
      }),
    )
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          session_id: 'sess-int',
          command: '--help',
          status: 'interrupted',
          last_event_id: '2',
          exit_code: -15,
        },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
      options.onmessage({
        event: 'output',
        id: '1',
        data: JSON.stringify({ line: 'partial output' }),
      })
      options.onmessage({
        event: 'close',
        id: '2',
        data: JSON.stringify({ exitcode: -15 }),
      })
    })

    const session = useConsoleSession()
    await session.startSession({ command: '--help', displayCommand: '--help' })
    await Promise.resolve()
    await Promise.resolve()

    expect(session.state.value.status).toBe('interrupted')
    expect(session.state.value.exitCode).toBe(-15)
    expect(session.state.value.error).toBe('')

    requestSpy.mockRestore()
  })

  it('cancel_without_reset', async () => {
    const session = useConsoleSession()
    session.state.value = {
      sessionId: 'sess-stop',
      command: '--help',
      status: 'running',
      lastEventId: '3',
      exitCode: null,
      transcript: ['user@YTPTube ~\n', '$ yt-dlp --help\n', 'chunk\n'],
      error: '',
    }

    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: { message: 'Terminal session cancellation requested.', session_id: 'sess-stop' },
      }),
    )

    const result = await session.cancelSession()

    expect(result).toEqual({ status: 'cancelled' })
    expect(session.state.value.sessionId).toBe('sess-stop')
    expect(session.state.value.status).toBe('running')
    expect(session.state.value.error).toBe('')

    const deleteCall = requestSpy.mock.calls.find(
      (call) => call[0] === '/api/system/terminal/sess-stop' && call[1]?.method === 'DELETE',
    )
    expect(deleteCall).toEqual(['/api/system/terminal/sess-stop', { method: 'DELETE' }])

    requestSpy.mockRestore()
  })

  it('disconnect_local', async () => {
    const session = useConsoleSession()
    session.state.value = {
      sessionId: 'sess-detach',
      command: '--help',
      status: 'running',
      lastEventId: '3',
      exitCode: null,
      transcript: ['user@YTPTube ~\n', '$ yt-dlp --help\n'],
      error: '',
    }

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
      return new Promise<void>(() => {})
    })

    void session.restoreSession()
    await Promise.resolve()
    await Promise.resolve()

    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockClear()
    session.disconnect()

    expect(requestSpy).toHaveBeenCalledTimes(0)
    expect(session.state.value.sessionId).toBe('sess-detach')

    requestSpy.mockRestore()
  })

  it('refresh_missing_cancel', async () => {
    const session = useConsoleSession()
    session.state.value = {
      sessionId: 'sess-missing',
      command: '--help',
      status: 'running',
      lastEventId: '3',
      exitCode: null,
      transcript: ['user@YTPTube ~\n', '$ yt-dlp --help\n'],
      error: '',
    }

    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: false,
        status: 404,
        jsonData: { error: 'Terminal session not found.' },
      }),
    )

    const result = await session.cancelSession()

    expect(result).toEqual({ status: 'missing', message: 'Terminal session not found.' })
    expect(session.state.value.status).toBe('running')

    requestSpy.mockRestore()
  })

  it('clear_transcript', () => {
    const session = useConsoleSession()
    session.state.value = {
      sessionId: 'sess-active',
      command: '--help',
      status: 'running',
      lastEventId: '15',
      exitCode: null,
      transcript: ['user@YTPTube ~\n', '$ yt-dlp --help\n', 'chunk\n'],
      error: '',
    }

    session.clearTranscript()

    expect(session.state.value.transcript).toEqual([])
    expect(session.state.value.sessionId).toBe('sess-active')
    expect(session.state.value.status).toBe('running')
    expect(session.state.value.lastEventId).toBe('15')
  })

  it('filter_hidden_recents', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          items: [
            {
              session_id: 'sess-newer',
              command: '--version',
              status: 'completed',
              created_at: 10,
              started_at: 11,
              finished_at: 20,
              expires_at: 100,
              available_until: 100,
              exit_code: 0,
              last_sequence: 2,
            },
            {
              session_id: 'sess-hidden',
              command: '--help',
              status: 'running',
              created_at: 1,
              started_at: 2,
              finished_at: null,
              expires_at: null,
              available_until: null,
              exit_code: null,
              last_sequence: 1,
            },
          ],
        },
      }),
    )

    const session = useConsoleSession()
    session.hideRecentSession('sess-hidden')
    await session.fetchRecentSessions()

    expect(session.recentSessions.value).toEqual([
      {
        sessionId: 'sess-newer',
        command: '--version',
        status: 'completed',
        createdAt: 10,
        startedAt: 11,
        finishedAt: 20,
        expiresAt: 100,
        availableUntil: 100,
        exitCode: 0,
        lastSequence: 2,
      },
    ])

    requestSpy.mockRestore()
  })

  it('replay_recent_session', async () => {
    const requestSpy = spyOn(utils, 'request')
    requestSpy.mockResolvedValueOnce(
      createMockResponse({
        ok: true,
        status: 200,
        jsonData: {
          items: [
            {
              session_id: 'sess-replay',
              command: '--help',
              status: 'completed',
              created_at: 10,
              started_at: 11,
              finished_at: 12,
              expires_at: 100,
              available_until: 100,
              exit_code: 0,
              last_sequence: 2,
            },
          ],
        },
      }),
    )

    fetchEventSourceMock.mockImplementationOnce(async (_url, options) => {
      await options.onopen(new Response('', { status: 200 }))
      options.onmessage({
        event: 'output',
        id: '1',
        data: JSON.stringify({ line: 'restored output' }),
      })
      options.onmessage({
        event: 'close',
        id: '2',
        data: JSON.stringify({ exitcode: 0 }),
      })
    })

    const session = useConsoleSession()
    const replayed = await session.replaySession({
      sessionId: 'sess-replay',
      command: '--help',
      status: 'completed',
      createdAt: 10,
      startedAt: 11,
      finishedAt: 12,
      expiresAt: 100,
      availableUntil: 100,
      exitCode: 0,
      lastSequence: 2,
    })
    await Promise.resolve()
    await Promise.resolve()

    expect(replayed).toBe(true)
    expect(session.state.value.sessionId).toBe('sess-replay')
    expect(session.state.value.transcript).toEqual(['restored output\n'])

    const streamCall = fetchEventSourceMock.mock.calls.at(-1)
    expect(streamCall?.[0]).toContain('/base-path/api/system/terminal/sess-replay/stream')

    requestSpy.mockRestore()
  })
})
