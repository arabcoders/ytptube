import { ref, readonly } from 'vue'
import { defineStore } from 'pinia'
import type { ConfigState } from "~/types/config";
import type { StoreItem } from "~/types/store";
import type {
  ConfigUpdatePayload,
  WebSocketClientEmits,
  WebSocketEnvelope,
  WSEP as WSEP
} from "~/types/sockets";

export type connectionStatus = 'connected' | 'disconnected' | 'connecting';

type SocketHandler = (...args: unknown[]) => void
type HandlerRegistry = Map<SocketHandler, SocketHandler>
type KnownEvent = keyof WSEP

export const useSocketStore = defineStore('socket', () => {
  const runtimeConfig = useRuntimeConfig()
  const config = useConfigStore()
  const stateStore = useStateStore()
  const toast = useNotification()

  const socket = ref<WebSocket | null>(null)
  const isConnected = ref<boolean>(false)
  const connectionStatus = ref<connectionStatus>('disconnected')
  const error = ref<string | null>(null)
  const error_count = ref<number>(0)
  const wasHidden = ref<boolean>(false)
  const reconnectTimeout = ref<NodeJS.Timeout | null>(null)
  const manualDisconnect = ref<boolean>(false)
  const reconnectAttempts = ref<number>(0)

  const handlers = new Map<string, HandlerRegistry>()

  const emit = <K extends keyof WebSocketClientEmits>(event: K, data: WebSocketClientEmits[K]): void => {
    if (!socket.value || WebSocket.OPEN !== socket.value.readyState) {
      return
    }
    socket.value.send(JSON.stringify({ event, data }))
  }

  function on<K extends KnownEvent>(event: K, callback: (payload: WSEP[K]) => void): void
  function on<K extends KnownEvent>(event: K[], callback: (payload: WSEP[K]) => void): void
  function on<K extends KnownEvent>(
    event: K | K[],
    callback: (event: K, payload: WSEP[K]) => void,
    withEvent: true
  ): void
  function on(event: string | string[], callback: SocketHandler, withEvent?: boolean): void
  function on(event: string | string[], callback: SocketHandler, withEvent: boolean = false): void {
    const events = Array.isArray(event) ? event : [event]
    events.forEach((eventName) => {
      if (!handlers.has(eventName)) {
        handlers.set(eventName, new Map())
      }

      const registry = handlers.get(eventName) as HandlerRegistry
      const handler = true === withEvent
        ? (payload: unknown) => callback(eventName, payload)
        : (payload: unknown) => callback(payload)

      registry.set(callback, handler)
    })
  }

  function off<K extends KnownEvent>(event: K, callback?: (payload: WSEP[K]) => void): void
  function off<K extends KnownEvent>(event: K[], callback?: (payload: WSEP[K]) => void): void
  function off(event: string | string[], callback?: SocketHandler): void
  function off(event: string | string[], callback?: SocketHandler): void {
    const events = Array.isArray(event) ? event : [event]
    events.forEach((eventName) => {
      const registry = handlers.get(eventName)
      if (!registry) {
        return
      }

      if (!callback) {
        registry.clear()
        handlers.delete(eventName)
        return
      }

      registry.delete(callback)
      if (0 === registry.size) {
        handlers.delete(eventName)
      }
    })
  }

  const getSessionId = (): string | null => null

  const dispatch = (eventName: string, payload: unknown): void => {
    const registry = handlers.get(eventName)
    if (!registry) {
      return
    }

    registry.forEach((handler) => handler(payload))
  }

  const handleVisibilityChange = () => {
    if (document.hidden) {
      wasHidden.value = true
      return
    }

    if (true === wasHidden.value && false === isConnected.value) {
      if (null !== reconnectTimeout.value) {
        clearTimeout(reconnectTimeout.value)
        reconnectTimeout.value = null
      }

      reconnectTimeout.value = setTimeout(() => {
        if (false === isConnected.value) {
          console.debug('[SocketStore] Page visible after background, reconnecting...')
          reconnect()
        }
        reconnectTimeout.value = null
      }, 100)
    }

    wasHidden.value = false
  }

  const setupVisibilityListener = () => {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityChange)
    }
  }

  const cleanupVisibilityListener = () => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
    if (null !== reconnectTimeout.value) {
      clearTimeout(reconnectTimeout.value)
      reconnectTimeout.value = null
    }
  }

  const scheduleReconnect = () => {
    if (true === manualDisconnect.value || true === isConnected.value) {
      return
    }

    if (reconnectAttempts.value >= 50) {
      return
    }

    if (null !== reconnectTimeout.value) {
      return
    }

    reconnectTimeout.value = setTimeout(() => {
      reconnectAttempts.value += 1
      reconnectTimeout.value = null
      connect()
    }, 5000)
  }

  const reconnect = () => {
    if (true === isConnected.value) {
      return
    }
    connect()
    connectionStatus.value = 'connecting'
  }

  const disconnect = () => {
    manualDisconnect.value = true
    if (null === socket.value) {
      return
    }
    socket.value.close()
    socket.value = null
    isConnected.value = false
    connectionStatus.value = 'disconnected'
    cleanupVisibilityListener()
  }

  const buildWsUrl = (): string => {
    const basePath = runtimeConfig.app.baseURL.replace(/\/$/, '')
    const wsPath = `${basePath}/ws?_=${Date.now()}`
    const configuredBase = runtimeConfig.public.wss?.trim()

    if (configuredBase) {
      return new URL(wsPath, configuredBase).toString()
    }

    const scheme = 'https:' === window.location.protocol ? 'wss' : 'ws'
    return new URL(wsPath, `${scheme}://${window.location.host}`).toString()
  }

  const connect = () => {
    if (socket.value && WebSocket.OPEN === socket.value.readyState) {
      return
    }

    if (socket.value && WebSocket.CONNECTING === socket.value.readyState) {
      return
    }

    manualDisconnect.value = false
    connectionStatus.value = 'connecting'

    socket.value = new WebSocket(buildWsUrl())

    if ('development' === runtimeConfig.public?.APP_ENV) {
      window.ws = socket.value
    }

    socket.value.addEventListener('open', () => {
      isConnected.value = true
      connectionStatus.value = 'connected'
      error.value = null
      error_count.value = 0
      reconnectAttempts.value = 0
      dispatch('connect', null)
    })

    socket.value.addEventListener('close', () => {
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      error.value = 'Disconnected from server.'
      dispatch('disconnect', null)
      scheduleReconnect()
    })

    socket.value.addEventListener('error', () => {
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      error.value = 'Connection error: Unknown error'
      error_count.value += 1
      dispatch('connect_error', { message: 'Unknown error' })
      scheduleReconnect()
    })

    socket.value.addEventListener('message', (event: MessageEvent<string>) => {
      let payload: WebSocketEnvelope | null = null
      try {
        payload = JSON.parse(event.data)
      } catch {
        return
      }

      if (!payload?.event || 'string' != typeof payload.event) {
        return
      }

      let data = payload.data
      if ('string' === typeof data) {
        try {
          data = JSON.parse(data)
        } catch {
          data = payload.data
        }
      }

      dispatch(payload.event, data)
    })

    setupVisibilityListener()
  }

  on('configuration', (data: WSEP['configuration']) => {
    config.setAll({
      app: data.data.config,
      presets: data.data.presets,
      dl_fields: data.data.dl_fields,
      paused: Boolean(data.data.paused)
    } as unknown as Partial<ConfigState>)
  })

  on('connected', (data: WSEP['connected']) => {
    if (!data?.data) {
      return
    }

    if (data.data.folders) {
      config.add('folders', data.data.folders)
    }

    if ('number' === typeof data.data.history_count) {
      stateStore.setHistoryCount(data.data.history_count)
    }

    error.value = null
  })

  on('active_queue', (data: WSEP['active_queue']) => {
    if (!data.data.queue) {
      return
    }
    stateStore.addAll('queue', data.data.queue || {})
  })

  on('item_added', (data: WSEP['item_added']) => {
    stateStore.add('queue', data.data._id, data.data)
    toast.success(`Item queued: ${ag(stateStore.get('queue', data.data._id, {} as StoreItem), 'title')}`)
  })

  on(['log_info', 'log_success', 'log_warning', 'log_error'], (event, data: WSEP['log_info']) => {
    const message = 'string' === typeof data?.message
      ? data.message
      : String((data?.data as Record<string, unknown>)?.message ?? '')
    const extra = (data?.data as Record<string, unknown>)?.data || data?.data || {}
    switch (event) {
      case 'log_info':
        toast.info(message, extra)
        break
      case 'log_success':
        toast.success(message, extra)
        break
      case 'log_warning':
        toast.warning(message, extra)
        break
      case 'log_error':
        toast.error(message, extra)
        break
    }
  }, true)

  on('item_cancelled', (data: WSEP['item_cancelled']) => {
    const id = data.data._id

    if (true !== stateStore.has('queue', id)) {
      return
    }

    toast.warning(`Download cancelled: ${ag(stateStore.get('queue', id, {} as StoreItem), 'title')}`)

    if (true === stateStore.has('queue', id)) {
      stateStore.remove('queue', id)
    }
  })

  on('item_deleted', (data: WSEP['item_deleted']) => {
    const id = data.data._id

    if (true !== stateStore.has('history', id)) {
      return
    }

    stateStore.remove('history', id)
  })

  on('item_updated', (data: WSEP['item_updated']) => {
    const id = data.data._id

    if (true === stateStore.has('history', id)) {
      stateStore.update('history', id, data.data)
      return
    }

    if (true === stateStore.has('queue', id)) {
      stateStore.update('queue', id, data.data)
    }
  })

  on('item_moved', (data: WSEP['item_moved']) => {
    const to = data.data.to
    const id = data.data.item._id

    if ('queue' === to) {
      if (true === stateStore.has('history', id)) {
        stateStore.remove('history', id)
      }
      stateStore.add('queue', id, data.data.item)
    }

    if ('history' === to) {
      if (true === stateStore.has('queue', id)) {
        stateStore.remove('queue', id)
      }
      stateStore.add('history', id, data.data.item)
    }
  })

  on(['paused', 'resumed'], (event, data: WSEP['paused']) => {
    const pausedState = Boolean(data.data.paused)
    config.update('paused', pausedState)

    if ('resumed' === event) {
      toast.success('Download queue resumed.')
      return
    }

    toast.warning('Download queue paused.', { timeout: 10000 })
  }, true)

  on('config_update', (data: WSEP['config_update']) => {
    const configUpdate = data.data as ConfigUpdatePayload
    if (!configUpdate) {
      return
    }
    config.patch(configUpdate.feature, configUpdate.action, configUpdate.data)
  })

  return {
    connect, reconnect, disconnect,
    on, off, emit,
    isConnected,
    getSessionId,
    connectionStatus: readonly(connectionStatus) as Readonly<Ref<connectionStatus>>,
    error: readonly(error) as Readonly<Ref<string | null>>,
    error_count: readonly(error_count) as Readonly<Ref<number>>,
  }
})
