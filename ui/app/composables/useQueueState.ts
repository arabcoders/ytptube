import { proxyRefs, reactive, toRefs } from 'vue';
import type { item_request } from '~/types/item';
import type { StoreItem } from '~/types/store';
import { request } from '~/utils';

type KeyType = string;

interface QueueState {
  queue: Record<KeyType, StoreItem>;
}

const state = reactive<QueueState>({
  queue: {},
});

const add = (key: KeyType, value: StoreItem): void => {
  state.queue[key] = value;
};

const update = (key: KeyType, value: StoreItem): void => {
  state.queue[key] = value;
};

const remove = (key: KeyType): void => {
  if (!state.queue[key]) {
    return;
  }

  const { [key]: _, ...rest } = state.queue;
  state.queue = rest;
};

const get = (key: KeyType, defaultValue: StoreItem | null = null): StoreItem | null => {
  return state.queue[key] || defaultValue;
};

const has = (key: KeyType): boolean => {
  return !!state.queue[key];
};

const clearAll = (): void => {
  state.queue = {};
};

const addAll = (data: Record<KeyType, StoreItem>): void => {
  state.queue = data;
};

const count = (): number => {
  return Object.keys(state.queue).length;
};

const loadQueue = async (): Promise<void> => {
  try {
    const response = await request('/api/history/live');
    const data = (await response.json()) as {
      queue: Record<KeyType, StoreItem>;
    };

    state.queue = data.queue || {};
  } catch (error) {
    console.error('Failed to load queue:', error);
    throw error;
  }
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
  remove,
  get,
  has,
  clearAll,
  addAll,
  count,
  loadQueue,
  addDownload,
  startItems,
  pauseItems,
  cancelItems,
});

export const useQueueState = () => queueStateApi;
