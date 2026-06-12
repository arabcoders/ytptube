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
      throw new Error('Failed to load queue');
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
      toast.error(error.error || 'Failed to add download');
      throw new Error(error.error || 'Failed to add download');
    }

    toast.success('Download added successfully');
    await loadQueue();
  } catch (error) {
    console.error('Failed to add download:', error);
    if (error instanceof Error && !error.message.includes('Failed to add download')) {
      toast.error('Failed to add download');
    }
    throw error;
  }
};

const startItems = async (ids: string[]): Promise<void> => {
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
      toast.error(error.error || 'Failed to start items');
      throw new Error(error.error || 'Failed to start items');
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

    toast.success(`Started ${ids.length} item${1 === ids.length ? '' : 's'}`);
  } catch (error) {
    console.error('Failed to start items:', error);
    if (error instanceof Error && !error.message.includes('Failed to start items')) {
      toast.error('Failed to start items');
    }
    throw error;
  }
};

const pauseItems = async (ids: string[]): Promise<void> => {
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
      toast.error(error.error || 'Failed to pause items');
      throw new Error(error.error || 'Failed to pause items');
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

    toast.success(`Paused ${ids.length} item${1 === ids.length ? '' : 's'}`);
  } catch (error) {
    console.error('Failed to pause items:', error);
    if (error instanceof Error && !error.message.includes('Failed to pause items')) {
      toast.error('Failed to pause items');
    }
    throw error;
  }
};

const cancelItems = async (ids: string[]): Promise<void> => {
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
      toast.error(error.error || 'Failed to cancel items');
      throw new Error(error.error || 'Failed to cancel items');
    }

    const result = await response.json();

    for (const id of ids) {
      if ('ok' === result[id]) {
        remove(id);
      }
    }

    toast.success(`Cancelled ${ids.length} item${1 === ids.length ? '' : 's'}`);
  } catch (error) {
    console.error('Failed to cancel items:', error);
    if (error instanceof Error && !error.message.includes('Failed to cancel items')) {
      toast.error('Failed to cancel items');
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
  pauseItems,
  cancelItems,
});

export const useQueueState = () => queueStateApi;
