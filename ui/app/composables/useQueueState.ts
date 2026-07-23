import { proxyRefs, reactive, toRefs } from 'vue';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import { request } from '~/utils';

type KeyType = string;

interface QueueState {
  queue: Record<KeyType, StoreItem>;
  total: number;
  loaded: number;
  limit: number;
  is_loaded: boolean;
  is_loading: boolean;
}

type QueueMeta = {
  queue_count?: number;
  queue_loaded?: number;
  queue_limit?: number;
};

const state = reactive<QueueState>({
  queue: {},
  total: 0,
  loaded: 0,
  limit: 0,
  is_loaded: false,
  is_loading: false,
});

const visibleCount = (): number => Object.keys(state.queue).length;

const syncLoaded = (): void => {
  state.loaded = visibleCount();
  if (state.total < state.loaded) {
    state.total = state.loaded;
  }
};

const canAddVisible = (): boolean => state.limit < 1 || visibleCount() < state.limit;

const isActive = (item: StoreItem): boolean => {
  return ['started', 'preparing', 'downloading', 'postprocessing'].includes(item.status || '');
};

const applyMeta = (meta: QueueMeta = {}): void => {
  state.loaded = Number(meta.queue_loaded ?? visibleCount());
  state.total = Number(meta.queue_count ?? state.loaded);
  state.limit = Number(meta.queue_limit ?? 0);
  syncLoaded();
};

const add = (key: KeyType, value: StoreItem): void => {
  if (state.queue[key]) {
    state.queue[key] = value;
    syncLoaded();
    return;
  }

  state.total += 1;

  if (!canAddVisible()) {
    return;
  }

  state.queue[key] = value;
  syncLoaded();
};

const reveal = (key: KeyType, value: StoreItem): void => {
  if (state.queue[key]) {
    state.queue[key] = value;
    syncLoaded();
    return;
  }

  state.queue[key] = value;
  syncLoaded();
};

const update = (key: KeyType, value: StoreItem): void => {
  if (!state.queue[key]) {
    if (isActive(value)) {
      reveal(key, value);
    }
    return;
  }

  state.queue[key] = value;
  syncLoaded();
};

const patch = (key: KeyType, fields: Partial<StoreItem>): void => {
  if (state.queue[key]) {
    Object.assign(state.queue[key], fields);
  }
};

const remove = (key: KeyType): void => {
  if (!state.queue[key]) {
    return;
  }

  const { [key]: _, ...rest } = state.queue;
  state.queue = rest;
  state.total = Math.max(0, state.total - 1);
  syncLoaded();
};

const drop = (key: KeyType): void => {
  if (state.queue[key]) {
    const { [key]: _, ...rest } = state.queue;
    state.queue = rest;
  }

  state.total = Math.max(0, state.total - 1);
  syncLoaded();
};

const get = (key: KeyType, defaultValue: StoreItem | null = null): StoreItem | null => {
  return state.queue[key] || defaultValue;
};

const has = (key: KeyType): boolean => {
  return !!state.queue[key];
};

const clearAll = (): void => {
  state.queue = {};
  state.total = 0;
  state.loaded = 0;
  state.limit = 0;
  state.is_loaded = false;
  state.is_loading = false;
};

const addAll = (data: Record<KeyType, StoreItem>, meta: QueueMeta = {}): void => {
  state.queue = data;
  state.is_loaded = true;
  applyMeta(meta);
};

const count = (): number => {
  return state.total;
};

const isLoaded = (): boolean => {
  return state.is_loaded;
};

const shown = (): number => {
  return visibleCount();
};

const hasMore = (): boolean => {
  if (!state.is_loaded) {
    return false;
  }

  return state.total > visibleCount();
};

const needsBackfill = (): boolean => {
  if (!state.is_loaded) {
    return false;
  }

  if (state.limit < 1) {
    return false;
  }

  return visibleCount() < Math.min(state.limit, state.total);
};

const loadQueue = async (limit?: number): Promise<void> => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);

  if (state.is_loading) {
    return;
  }

  state.is_loading = true;

  try {
    const params = new URLSearchParams();
    if (typeof limit === 'number') {
      params.set('limit', String(limit));
    }

    const query = params.toString();
    const response = await request(`/api/history/live${query ? `?${query}` : ''}`);
    if (!response.ok) {
      throw new Error(t('common.failedFetch'));
    }

    const data = (await response.json()) as {
      queue: Record<KeyType, StoreItem>;
    } & QueueMeta;

    addAll(data.queue || {}, data);
  } catch (error) {
    console.error('Failed to load queue:', error);
    throw error;
  } finally {
    state.is_loading = false;
  }
};

const loadMore = async (): Promise<void> => {
  if (!hasMore()) {
    return;
  }

  const step = state.limit > 0 ? state.limit : Math.max(visibleCount(), 100);
  await loadQueue(Math.max(visibleCount() + 1, state.limit + step));
};

const addDownload = async (data: item_request): Promise<void> => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const socket = useAppSocket();
  const toast = useNotification();

  if (socket.isConnected) {
    socket.emit('add_url', data);
    return;
  }

  try {
    const response = await request('/api/history/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      toast.error(error.error || t('queue.failedToAdd'));
      throw new Error(error.error || t('queue.failedToAdd'));
    }

    toast.success(t('queue.added'));
    await loadQueue();
  } catch (error) {
    console.error('Failed to add download:', error);
    if (error instanceof Error && !error.message.includes(t('queue.failedToAdd'))) {
      toast.error(t('queue.failedToAdd'));
    }
    throw error;
  }
};

const startItems = async (ids: string[]): Promise<void> => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const socket = useAppSocket();
  const toast = useNotification();

  if (socket.isConnected) {
    ids.forEach((id) => socket.emit('item_start', id));
    return;
  }

  try {
    const response = await request('/api/history/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });

    if (!response.ok) {
      const error = await response.json();
      toast.error(error.error || t('queue.failedToStart'));
      throw new Error(error.error || t('queue.failedToStart'));
    }

    const result = await response.json();

    for (const id of ids) {
      if ('started' === result[id]) {
        const item = get(id);
        if (item) {
          update(id, { ...item, auto_start: true });
        }
      }
    }

    toast.success(t('queue.startedCount', { count: ids.length }));
  } catch (error) {
    console.error('Failed to start items:', error);
    if (error instanceof Error && !error.message.includes(t('queue.failedToStart'))) {
      toast.error(t('queue.failedToStart'));
    }
    throw error;
  }
};

const forceStartItems = async (ids: string[]): Promise<void> => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const toast = useNotification();

  try {
    const response = await request('/api/history/force-start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });

    if (!response.ok) {
      const error = await response.json();
      toast.error(error.error || t('queue.failedToForceStart'));
      throw new Error(error.error || t('queue.failedToForceStart'));
    }

    const result = (await response.json()) as Record<string, string>;
    for (const id of ids) {
      if ('started' === result[id]) {
        const item = get(id);
        if (item) {
          update(id, { ...item, auto_start: true, force_start: true });
        }
      }
    }

    toast.success(t('queue.forceStartedCount', { count: ids.length }));
  } catch (error) {
    console.error('Failed to force start items:', error);
    throw error;
  }
};

const pauseItems = async (ids: string[]): Promise<void> => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const socket = useAppSocket();
  const toast = useNotification();

  if (socket.isConnected) {
    ids.forEach((id) => socket.emit('item_pause', id));
    return;
  }

  try {
    const response = await request('/api/history/pause', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });

    if (!response.ok) {
      const error = await response.json();
      toast.error(error.error || t('queue.failedToPause'));
      throw new Error(error.error || t('queue.failedToPause'));
    }

    const result = await response.json();

    for (const id of ids) {
      if ('paused' === result[id]) {
        const item = get(id);
        if (item) {
          update(id, { ...item, auto_start: false });
        }
      }
    }

    toast.success(t('queue.pausedCount', { count: ids.length }));
  } catch (error) {
    console.error('Failed to pause items:', error);
    if (error instanceof Error && !error.message.includes(t('queue.failedToPause'))) {
      toast.error(t('queue.failedToPause'));
    }
    throw error;
  }
};

const cancelItems = async (ids: string[]): Promise<void> => {
  const t = useNuxtApp().$i18n?.t ?? ((key: string) => key);
  const socket = useAppSocket();
  const toast = useNotification();

  if (socket.isConnected) {
    ids.forEach((id) => socket.emit('item_cancel', id));
    return;
  }

  try {
    const response = await request('/api/history/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });

    if (!response.ok) {
      const error = await response.json();
      toast.error(error.error || t('queue.failedToCancel'));
      throw new Error(error.error || t('queue.failedToCancel'));
    }

    const result = await response.json();

    for (const id of ids) {
      if ('ok' === result[id]) {
        remove(id);
      }
    }

    toast.success(t('queue.cancelledCount', { count: ids.length }));
  } catch (error) {
    console.error('Failed to cancel items:', error);
    if (error instanceof Error && !error.message.includes(t('queue.failedToCancel'))) {
      toast.error(t('queue.failedToCancel'));
    }
    throw error;
  }
};

const queueStateApi = proxyRefs({
  ...toRefs(state),
  add,
  update,
  patch,
  remove,
  drop,
  get,
  has,
  clearAll,
  addAll,
  count,
  isLoaded,
  shown,
  hasMore,
  needsBackfill,
  loadQueue,
  loadMore,
  addDownload,
  startItems,
  forceStartItems,
  pauseItems,
  cancelItems,
});

export const useQueueState = () => queueStateApi;
