import { proxyRefs, readonly, ref } from 'vue';
import { useYtpConfig } from '~/composables/useYtpConfig';
import { useHistoryState } from '~/composables/useHistoryState';
import { useNotification, type notificationOptions } from '~/composables/useNotification';
import { useQueueState } from '~/composables/useQueueState';
import { ensure_api_success, request } from '~/utils';
import type { StoreItem } from '~/types/store';
import type {
  ConfigUpdatePayload,
  WebSocketClientEmits,
  WebSocketEnvelope,
  WSEP as WSEP,
} from '~/types/sockets';

const t = (key: string, named: Record<string, unknown> = {}): string =>
  useNuxtApp().$i18n?.t(key, named) ?? key;

export type connectionStatus = 'connected' | 'disconnected' | 'connecting';

type SocketHandler = (...args: unknown[]) => void;
type HandlerRegistry = Map<SocketHandler, SocketHandler>;
type KnownEvent = keyof WSEP;
type NotificationEvent =
  | 'log_info'
  | 'log_success'
  | 'log_warning'
  | 'log_error'
  | 'task_finished'
  | 'task_error';
type ToastApi = Pick<ReturnType<typeof useNotification>, 'info' | 'success' | 'warning' | 'error'>;

const getRuntimeConfig = () => useRuntimeConfig();
const getConfig = () => useYtpConfig();
const getHistoryState = () => useHistoryState();
const getQueueState = () => useQueueState();
const getToast = () => useNotification();
let queueReloadTimer: ReturnType<typeof setTimeout> | null = null;

const scheduleQueueBackfill = (): void => {
  const queueState = getQueueState();

  if (!queueState.needsBackfill() || queueReloadTimer) {
    return;
  }

  queueReloadTimer = setTimeout(() => {
    queueReloadTimer = null;
    queueState.loadQueue(queueState.limit || undefined);
  }, 500);
};

const socket = ref<WebSocket | null>(null);
const isConnected = ref<boolean>(false);
const connectionStatus = ref<connectionStatus>('disconnected');
const wasHidden = ref<boolean>(false);
const reconnectTimeout = ref<NodeJS.Timeout | null>(null);
const manualDisconnect = ref<boolean>(false);
const reconnectAttempts = ref<number>(0);
let connectionPromise: Promise<void> | null = null;

const CONNECTION_DEADLINE = 5000;

export const createConnectionDeadline = (
  now: () => number = () => performance.now(),
): {
  expiresAt: number;
  remaining: () => number;
  arm: (callback: () => void, delay?: number) => void;
  clear: () => void;
} => {
  const expiresAt = now() + CONNECTION_DEADLINE;
  let timer: ReturnType<typeof setTimeout> | null = null;
  return {
    expiresAt,
    remaining: () => Math.max(0, expiresAt - now()),
    arm: (callback, delay) => {
      if (null !== timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(callback, delay ?? Math.max(0, expiresAt - now()));
    },
    clear: () => {
      if (null !== timer) {
        clearTimeout(timer);
        timer = null;
      }
    },
  };
};

export type ConnectionAttempt = {
  deadline: ReturnType<typeof createConnectionDeadline>;
  isActive: () => boolean;
  cancel: () => void;
  recover: () => boolean;
  finish: () => void;
};

let currentAttempt: ConnectionAttempt | null = null;
let connectionOwner: ConnectionAttempt | null = null;

export const createConnectionAttempt = (
  deadline = createConnectionDeadline(),
): ConnectionAttempt => {
  let active = true;
  let recovered = false;
  return {
    deadline,
    isActive: () => active && !recovered,
    cancel: () => {
      active = false;
      deadline.clear();
    },
    recover: () => {
      if (!active || recovered) {
        return false;
      }
      recovered = true;
      active = false;
      deadline.clear();
      return true;
    },
    finish: () => {
      active = false;
      deadline.clear();
    },
  };
};

const handlers = new Map<string, HandlerRegistry>();

const emit = <K extends keyof WebSocketClientEmits>(
  event: K,
  data: WebSocketClientEmits[K],
): void => {
  if (!socket.value || WebSocket.OPEN !== socket.value.readyState) {
    return;
  }
  socket.value.send(JSON.stringify({ event, data }));
};

function on<K extends KnownEvent>(event: K | K[], callback: (payload: WSEP[K]) => void): void;
function on<K extends KnownEvent>(
  event: K | K[],
  callback: (event: K, payload: WSEP[K]) => void,
  withEvent: true,
): void;
function on(event: string | string[], callback: SocketHandler, withEvent?: boolean): void;
function on(event: string | string[], callback: SocketHandler, withEvent: boolean = false): void {
  const events = Array.isArray(event) ? event : [event];
  events.forEach((eventName) => {
    if (!handlers.has(eventName)) {
      handlers.set(eventName, new Map());
    }

    const registry = handlers.get(eventName) as HandlerRegistry;
    const handler =
      true === withEvent
        ? (payload: unknown) => callback(eventName, payload)
        : (payload: unknown) => callback(payload);

    registry.set(callback, handler);
  });
}

function off<K extends KnownEvent>(event: K | K[], callback?: (payload: WSEP[K]) => void): void;
function off(event: string | string[], callback?: SocketHandler): void;
function off(event: string | string[], callback?: SocketHandler): void {
  const events = Array.isArray(event) ? event : [event];
  events.forEach((eventName) => {
    const registry = handlers.get(eventName);
    if (!registry) {
      return;
    }

    if (!callback) {
      registry.clear();
      handlers.delete(eventName);
      return;
    }

    registry.delete(callback);
    if (0 === registry.size) {
      handlers.delete(eventName);
    }
  });
}

const getSessionId = (): string | null => null;

const dispatch = (eventName: string, payload: unknown): void => {
  const registry = handlers.get(eventName);
  if (!registry) {
    return;
  }

  registry.forEach((handler) => handler(payload));
};

const handleVisibilityChange = () => {
  if (document.hidden) {
    wasHidden.value = true;
    return;
  }

  if (true === wasHidden.value && false === isConnected.value) {
    if (null !== reconnectTimeout.value) {
      clearTimeout(reconnectTimeout.value);
      reconnectTimeout.value = null;
    }

    reconnectTimeout.value = setTimeout(() => {
      if (false === isConnected.value) {
        console.debug('[SocketStore] Page visible after background, reconnecting...');
        reconnect();
      }
      reconnectTimeout.value = null;
    }, 100);
  }

  wasHidden.value = false;
};

const setupVisibilityListener = () => {
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  }
};

const cleanupVisibilityListener = () => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  }
  if (null !== reconnectTimeout.value) {
    clearTimeout(reconnectTimeout.value);
    reconnectTimeout.value = null;
  }
};

const scheduleReconnect = () => {
  if (true === manualDisconnect.value || true === isConnected.value) {
    return;
  }

  if (reconnectAttempts.value >= 50) {
    return;
  }

  if (null !== reconnectTimeout.value) {
    return;
  }

  reconnectTimeout.value = setTimeout(() => {
    reconnectAttempts.value += 1;
    reconnectTimeout.value = null;
    connect();
  }, 5000);
};

const clearConnectionTimer = (): void => {
  if (currentAttempt) {
    currentAttempt.cancel();
  }
};

const recoverConnection = (attempt: ConnectionAttempt, message: string): void => {
  if (attempt !== currentAttempt || !attempt.recover()) {
    return;
  }

  const activeSocket = socket.value;
  socket.value = null;
  if (activeSocket) {
    try {
      activeSocket.close();
    } catch {
      // Some WebSocket implementations throw when closing a connecting socket.
    }
  }
  currentAttempt = null;
  connectionPromise = null;
  connectionOwner = null;
  isConnected.value = false;
  connectionStatus.value = 'disconnected';
  dispatch('connect_error', { message });
  scheduleReconnect();
};

const armConnectionTimer = (attempt: ConnectionAttempt, delay: number): void => {
  attempt.deadline.arm(() => {
    recoverConnection(attempt, 'WebSocket connection timed out.');
  }, delay);
};

const reconnect = () => {
  if (null !== reconnectTimeout.value) {
    clearTimeout(reconnectTimeout.value);
    reconnectTimeout.value = null;
  }

  if (true === isConnected.value) {
    return;
  }
  connect();
  connectionStatus.value = 'connecting';
};

const disconnect = () => {
  manualDisconnect.value = true;
  clearConnectionTimer();
  currentAttempt = null;
  connectionPromise = null;
  connectionOwner = null;
  if (null !== socket.value) {
    socket.value.close();
    socket.value = null;
  }
  isConnected.value = false;
  connectionStatus.value = 'disconnected';
  cleanupVisibilityListener();
};

export const withWsTicket = (url: string, ticket?: string): string => {
  if (!ticket) {
    return url;
  }
  const target = new URL(url);
  target.searchParams.set('ticket', ticket);
  return target.toString();
};

const buildWsUrl = (ticket?: string): string => {
  const runtimeConfig = getRuntimeConfig();
  const basePath = runtimeConfig.app.baseURL.replace(/\/$/, '');
  const wsPath = `${basePath}/ws?_=${Date.now()}`;
  const configuredBase = runtimeConfig.public.wss?.trim();

  if (configuredBase) {
    return withWsTicket(new URL(wsPath, configuredBase).toString(), ticket);
  }

  const scheme = 'https:' === window.location.protocol ? 'wss' : 'ws';
  return withWsTicket(new URL(wsPath, `${scheme}://${window.location.host}`).toString(), ticket);
};

const connect = (): void => {
  const runtimeConfig = getRuntimeConfig();

  if (socket.value && WebSocket.OPEN === socket.value.readyState) {
    return;
  }

  if (socket.value && WebSocket.CONNECTING === socket.value.readyState) {
    return;
  }

  if (connectionPromise) {
    return;
  }

  manualDisconnect.value = false;
  connectionStatus.value = 'connecting';

  clearConnectionTimer();
  const attempt = createConnectionAttempt();
  currentAttempt = attempt;
  armConnectionTimer(attempt, CONNECTION_DEADLINE);

  connectionPromise = (async () => {
    let ticket: string | undefined;
    if (useAuth().status.value?.disabled !== true) {
      const remaining = attempt.deadline.remaining();
      if (0 === remaining) {
        throw new Error('WebSocket connection timed out.');
      }
      const response = await request('/api/auth/ws-ticket', {
        method: 'POST',
        timeout: remaining / 1000,
      });
      await ensure_api_success(response);
      const payload = (await response.json()) as { ticket?: string };
      if (!payload.ticket) {
        throw new Error('WebSocket ticket was not returned.');
      }
      ticket = payload.ticket;
    }

    if (attempt !== currentAttempt || !attempt.isActive() || manualDisconnect.value) {
      return;
    }

    const remaining = attempt.deadline.remaining();
    if (0 === remaining) {
      throw new Error('WebSocket connection timed out.');
    }
    armConnectionTimer(attempt, remaining);

    const ws = new WebSocket(buildWsUrl(ticket));
    socket.value = ws;

    if ('development' === runtimeConfig.public?.APP_ENV) {
      window.ws = ws;
    }

    ws.addEventListener('open', () => {
      if (socket.value !== ws) {
        return;
      }
      isConnected.value = true;
      connectionStatus.value = 'connected';
      attempt.finish();
      currentAttempt = null;
      reconnectAttempts.value = 0;
      dispatch('connect', null);
    });

    ws.addEventListener('close', () => {
      if (socket.value !== ws) {
        return;
      }
      attempt.finish();
      if (currentAttempt === attempt) {
        currentAttempt = null;
      }
      isConnected.value = false;
      connectionStatus.value = 'disconnected';
      dispatch('disconnect', null);
      scheduleReconnect();
    });

    ws.addEventListener('error', () => {
      if (socket.value !== ws) {
        return;
      }
      attempt.finish();
      if (currentAttempt === attempt) {
        currentAttempt = null;
      }
      isConnected.value = false;
      connectionStatus.value = 'disconnected';
      dispatch('connect_error', { message: t('common.unknownError') });
      scheduleReconnect();
    });

    ws.addEventListener('message', (event: MessageEvent<string>) => {
      let payload: WebSocketEnvelope | null;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }

      if (!payload?.event || 'string' != typeof payload.event) {
        return;
      }

      let data = payload.data;
      if ('string' === typeof data) {
        try {
          data = JSON.parse(data);
        } catch {
          data = payload.data;
        }
      }

      dispatch(payload.event, data);
    });

    setupVisibilityListener();
  })()
    .catch((cause: unknown) => {
      const message = cause instanceof Error ? cause.message : t('common.unknownError');
      recoverConnection(attempt, message);
    })
    .finally(() => {
      if (connectionOwner === attempt) {
        connectionPromise = null;
        connectionOwner = null;
      }
    });
  connectionOwner = attempt;
};

on('connect', () => getConfig().loadConfig(false));

on('connected', () => {
  getConfig().loadConfig(false);
});

on('item_added', (data: WSEP['item_added']) => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const queueState = getQueueState();
  const toast = getToast();

  if (queueState.isLoaded()) {
    queueState.add(data.data._id, data.data);
  }

  toast.success(t('queue.itemQueued', { title: ag(data.data, 'title') }));
});

on('queue_reordered', (data: WSEP['queue_reordered']) => getQueueState().reorder(data.data.order));

export const handleNotification = (
  event: NotificationEvent,
  data: WSEP[NotificationEvent],
  toast: ToastApi = getToast(),
): void => {
  const message =
    'string' === typeof data?.message
      ? data.message
      : String((data?.data as Record<string, unknown>)?.message ?? '');
  const extra = ((data?.data as Record<string, unknown>)?.data ||
    data?.data ||
    {}) as notificationOptions;

  switch (event) {
    case 'log_info':
      toast.info(message, extra);
      break;
    case 'log_success':
      toast.success(message, extra);
      break;
    case 'log_warning':
      toast.warning(message, extra);
      break;
    case 'log_error':
    case 'task_error':
      toast.error(message, extra);
      break;
    case 'task_finished':
      toast.success(message, { ...extra, lowPriority: true });
      break;
  }
};

on(
  ['log_info', 'log_success', 'log_warning', 'log_error', 'task_finished', 'task_error'],
  handleNotification,
  true,
);

on('item_cancelled', (data: WSEP['item_cancelled']) => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const queueState = getQueueState();
  const toast = getToast();
  const id = data.data._id;

  if (!queueState.isLoaded()) {
    return;
  }

  if (true !== queueState.has(id)) {
    return;
  }

  toast.warning(
    t('queue.downloadCancelled', { title: ag(queueState.get(id, {} as StoreItem), 'title') }),
  );
});

on('item_deleted', (data: WSEP['item_deleted']) => {
  const queueState = getQueueState();
  const id = data.data._id;

  const historyState = getHistoryState();
  if (historyState.isLoaded.value) {
    historyState.drop(id);
  }

  if (!queueState.isLoaded()) {
    return;
  }

  if (true === queueState.has(id)) {
    queueState.remove(id);
    scheduleQueueBackfill();
  }
});

on('item_bulk_deleted', (data: WSEP['item_bulk_deleted']) => {
  const historyState = getHistoryState();
  for (const id of data.data.ids ?? []) {
    historyState.drop(id);
  }
});

on('item_updated', (data: WSEP['item_updated']) => {
  const queueState = getQueueState();

  if (queueState.isLoaded()) {
    queueState.update(data.data._id, data.data);
  }

  const historyState = getHistoryState();

  if (historyState.isLoaded.value) {
    historyState.update(data.data._id, data.data);
  }
});

on('item_progress', (data: WSEP['item_progress']) => {
  const queueState = getQueueState();
  const id = data.data._id;

  if (true === queueState.has(id)) {
    queueState.patch(id, data.data as Partial<StoreItem>);
  }
});

on('item_moved', (data: WSEP['item_moved']) => {
  const queueState = getQueueState();
  const to = data.data.to;
  const id = data.data.item._id;

  if (!queueState.isLoaded()) {
    return;
  }

  if ('queue' === to) {
    queueState.add(id, data.data.item);
  }

  if ('history' === to) {
    if ('queue' === data.data.from) {
      queueState.drop(id);
      scheduleQueueBackfill();
      return;
    }

    if (true === queueState.has(id)) {
      queueState.remove(id);
      scheduleQueueBackfill();
    }
  }
});

on(
  ['paused', 'resumed'],
  (event, data: WSEP['paused']) => {
    const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
    const config = getConfig();
    const toast = getToast();
    const pausedState = Boolean(data.data.paused);
    config.update('paused', pausedState);

    if ('resumed' === event) {
      toast.success(t('queue.queueResumed'));
      return;
    }

    toast.warning(t('queue.queuePaused'), { timeout: 10000 });
  },
  true,
);

on('config_update', (data: WSEP['config_update']) => {
  const config = getConfig();
  const configUpdate = data.data as ConfigUpdatePayload;
  if (!configUpdate) {
    return;
  }
  config.patch(configUpdate.feature, configUpdate.action, configUpdate.data);
});

const appSocketApi = proxyRefs({
  connect,
  reconnect,
  disconnect,
  on,
  off,
  emit,
  isConnected,
  getSessionId,
  connectionStatus: readonly(connectionStatus),
});

export const useAppSocket = () => appSocketApi;
