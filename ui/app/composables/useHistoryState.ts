import { computed, ref } from 'vue';

import { useNotification } from '~/composables/useNotification';
import type { WSEP } from '~/types/sockets';
import { useYtpConfig } from '~/composables/useYtpConfig';
import { parse_api_error, parse_list_response, request } from '~/utils';
import type { Pagination } from '~/types/responses';
import type { StoreItem } from '~/types/store';

type HistoryLoadOptions = {
  order?: 'ASC' | 'DESC';
  status?: string;
  perPage?: number;
};

const items = ref<StoreItem[]>([]);
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const isLoading = ref<boolean>(false);
const isLoaded = ref<boolean>(false);
const lastError = ref<string | null>(null);
const throwInstead = ref(false);

const readJson = async (response: Response): Promise<unknown> => {
  try {
    const clone = response.clone();
    return await clone.json();
  } catch {
    return null;
  }
};

const ensureSuccess = async (response: Response): Promise<void> => {
  if (response.ok) {
    return;
  }

  const payload = await readJson(response);
  const message = await parse_api_error(payload);
  throw new Error(message);
};

const handleError = (error: unknown): void => {
  const message = error instanceof Error ? error.message : 'Unexpected error occurred.';
  lastError.value = message;
  useNotification().error(message);
};

const pageSize = computed<number>(() => {
  const config = useYtpConfig();
  return Number(config.app.default_pagination || 50);
});

const buildQuery = (
  page: number,
  perPage: number,
  order: 'ASC' | 'DESC' = 'DESC',
  status?: string,
): string => {
  const params = new URLSearchParams({
    type: 'done',
    page: String(page),
    per_page: String(perPage),
    order,
  });

  if (status) {
    params.set('status', status);
  }

  return params.toString();
};

const loadHistory = async (page: number = 1, options: HistoryLoadOptions = {}): Promise<void> => {
  const { order = 'DESC', status, perPage = pageSize.value } = options;

  isLoading.value = true;

  try {
    const response = await request(`/api/history?${buildQuery(page, perPage, order, status)}`);
    await ensureSuccess(response);

    const data = await response.json();
    const { items: loadedItems, pagination: paginationData } =
      await parse_list_response<StoreItem>(data);

    items.value = loadedItems;
    pagination.value = paginationData;
    isLoaded.value = true;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) {
      throw error;
    }
  } finally {
    isLoading.value = false;
  }
};

const reloadHistory = async (options: HistoryLoadOptions = {}): Promise<void> => {
  const targetPage = isLoaded.value ? pagination.value.page : 1;
  await loadHistory(targetPage, options);
};

const deleteHistoryItems = async (
  options: {
    ids?: string[];
    status?: string;
    removeFile?: boolean;
  } = {},
): Promise<number> => {
  const { ids, status, removeFile = true } = options;

  if (!ids && !status) {
    throw new Error('Either ids or status filter must be provided');
  }

  try {
    const response = await request('/api/history', {
      method: 'DELETE',
      body: JSON.stringify({
        type: 'done',
        ids,
        status,
        remove_file: removeFile,
      }),
    });

    await ensureSuccess(response);

    const result = (await response.json()) as {
      deleted?: number;
      error?: string;
      message?: string;
    };

    if (result.error || result.message) {
      throw new Error(result.error || result.message);
    }

    return Number(result.deleted ?? 0);
  } catch (error) {
    handleError(error);
    if (throwInstead.value) {
      throw error;
    }
    return 0;
  }
};

const resetHistory = (): void => {
  items.value = [];
  pagination.value = {
    page: 1,
    per_page: pageSize.value,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_prev: false,
  };
  isLoaded.value = false;
  lastError.value = null;
};

const addHistoryItem = (item: StoreItem): void => {
  const existingIndex = items.value.findIndex((existing) => existing._id === item._id);

  if (existingIndex !== -1) {
    items.value = [
      item,
      ...items.value.slice(0, existingIndex),
      ...items.value.slice(existingIndex + 1),
    ];
    return;
  }

  items.value = [item, ...items.value];
  pagination.value.total++;

  if (items.value.length > pagination.value.per_page) {
    items.value = items.value.slice(0, pagination.value.per_page);
  }

  pagination.value.total_pages = Math.max(
    1,
    Math.ceil(pagination.value.total / pagination.value.per_page),
  );
  pagination.value.has_next = pagination.value.page < pagination.value.total_pages;
};

const historyMoveHandler = (
  shouldHandle: () => boolean = () => isLoaded.value,
): ((payload: WSEP['item_moved']) => void) => {
  return (payload: WSEP['item_moved']): void => {
    if ('history' !== payload.data.to || !shouldHandle()) {
      return;
    }

    addHistoryItem(payload.data.item);
  };
};

export const useHistoryState = () => {
  return {
    items,
    pagination,
    isLoading,
    isLoaded,
    lastError,
    pageSize,
    loadHistory,
    reloadHistory,
    deleteHistoryItems,
    resetHistory,
    upsertHistoryItem: addHistoryItem,
    historyMoveHandler,
  };
};
