import { ref, readonly } from 'vue';

import { useNotification } from '~/composables/useNotification';
import { request, parse_list_response, parse_api_response, ensure_api_success } from '~/utils';
import type { notification } from '~/types/notification';
import type { APIResponse, Pagination } from '~/types/responses';

const notifications = ref<Array<notification>>([]);
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const events = ref<Array<string>>([]);
const isLoading = ref<boolean>(false);
const addInProgress = ref<boolean>(false);
const lastError = ref<string | null>(null);
// Test hook: rethrow request errors instead of returning fallback values.
const throwInstead = ref(false);
const notify = useNotification();
const { $i18n } = useNuxtApp();
const t = $i18n?.t ?? ((key: string) => key);

const sortNotifications = (items: Array<notification>): Array<notification> => {
  return [...items].sort((a, b) => a.name.localeCompare(b.name));
};

const setError = (error: unknown): string => {
  const message = error instanceof Error ? error.message : t('common.unknownError');
  lastError.value = message;
  return message;
};

const handleError = (error: unknown): void => {
  const message = setError(error);
  notify.error(message);
};

const updateNotifications = (item: notification): void => {
  const isNew = !notifications.value.some((existing) => existing.id === item.id);
  notifications.value = sortNotifications([
    ...notifications.value.filter((existing) => existing.id !== item.id),
    item,
  ]);
  if (isNew) {
    pagination.value.total++;
  }
};

const removeNotification = (id: number) => {
  const initialLength = notifications.value.length;
  notifications.value = notifications.value.filter((item) => item.id !== id);
  if (notifications.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1);
  }
};

const loadNotifications = async (
  page: number = 1,
  perPage: number | undefined = undefined,
): Promise<void> => {
  await loadNotificationEvents();

  isLoading.value = true;
  try {
    let url = `/api/notifications/?page=${page}`;
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`;
    }
    const response = await request(url);
    await ensure_api_success(response);

    const json = await response.json();
    const { items, pagination: paginationData } = await parse_list_response<notification>(json);

    notifications.value = sortNotifications(items);
    pagination.value = paginationData;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const loadNotificationEvents = async (): Promise<void> => {
  if (events.value.length > 0) {
    return;
  }

  try {
    const response = await request('/api/notifications/events/');
    await ensure_api_success(response);

    const json = await response.json();
    events.value = Array.isArray(json?.events) ? json.events : [];
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  }
};

const getNotification = async (id: number): Promise<notification | null> => {
  try {
    const response = await request(`/api/notifications/${id}`);
    await ensure_api_success(response);

    const json = await response.json();
    const item = await parse_api_response<notification>(json);

    lastError.value = null;
    return item;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const createNotification = async (
  item: Omit<notification, 'id'>,
  callback?: (response: APIResponse<notification>) => void,
): Promise<notification | null> => {
  addInProgress.value = true;
  try {
    const response = await request('/api/notifications/', {
      method: 'POST',
      body: JSON.stringify(item),
    });
    await ensure_api_success(response);

    const json = await response.json();
    const created = await parse_api_response<notification>(json);

    updateNotifications(created);
    notify.success(t('common.crudCreated', { type: t('notificationsPage.target') }));
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: created });
    }

    return created;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    setError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    throw error;
  } finally {
    addInProgress.value = false;
  }
};

const updateNotification = async (
  id: number,
  item: notification,
  callback?: (response: APIResponse<notification>) => void,
): Promise<notification | null> => {
  addInProgress.value = true;
  try {
    if (item.id) {
      item.id = undefined;
    }
    const response = await request(`/api/notifications/${id}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    });
    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<notification>(json);

    updateNotifications(updated);
    notify.success(
      t('common.crudUpdated', { type: t('notificationsPage.target'), name: updated.name }),
    );
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated });
    }

    return updated;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    setError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    throw error;
  } finally {
    addInProgress.value = false;
  }
};

const patchNotification = async (
  id: number,
  patch: Partial<notification>,
  callback?: (response: APIResponse<notification>) => void,
): Promise<notification | null> => {
  addInProgress.value = true;
  try {
    if (patch.id) {
      patch.id = undefined;
    }
    const response = await request(`/api/notifications/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<notification>(json);

    updateNotifications(updated);
    notify.success(
      t('common.crudUpdated', { type: t('notificationsPage.target'), name: updated.name }),
    );
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated });
    }

    return updated;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    setError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    throw error;
  } finally {
    addInProgress.value = false;
  }
};

const deleteNotification = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/notifications/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);

    removeNotification(id);
    notify.success(t('common.crudDeleted', { type: t('notificationsPage.target') }));
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: true });
    }

    return true;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    handleError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: false });
    }

    if (throwInstead.value) throw error;
    return false;
  }
};

const isApprise = (url: string) => !url.startsWith('http');

const clearError = () => (lastError.value = null);

export const useNotifications = () => ({
  notifications: readonly(notifications),
  pagination: readonly(pagination),
  events: readonly(events),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadNotifications,
  loadNotificationEvents,
  getNotification,
  createNotification,
  updateNotification,
  patchNotification,
  deleteNotification,
  clearError,
  throwInstead,
  isApprise,
});
