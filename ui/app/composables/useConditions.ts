import { ref, readonly } from 'vue';

import { useNotification } from '~/composables/useNotification';
import { request, parse_list_response, parse_api_response, ensure_api_success } from '~/utils';
import type {
  Condition,
  ConditionTestRequest,
  ConditionTestResponse,
  Pagination,
} from '~/types/conditions';
import type { APIResponse } from '~/types/responses';

const conditions = ref<Array<Condition>>([]);
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const isLoading = ref<boolean>(false);
const addInProgress = ref<boolean>(false);
const lastError = ref<string | null>(null);
// Test hook: rethrow request errors instead of returning fallback values.
const throwInstead = ref(false);

const { $i18n } = useNuxtApp();
const t = $i18n?.t ?? ((key: string) => key);

const sortConditions = (items: Array<Condition>): Array<Condition> => {
  return [...items].sort((a, b) => {
    if (a.priority === b.priority) {
      return a.name.localeCompare(b.name);
    }

    return b.priority - a.priority;
  });
};

const setError = (error: unknown): string => {
  const message = error instanceof Error ? error.message : t('common.unknownError');
  lastError.value = message;
  return message;
};

const handleError = (error: unknown): void => {
  const message = setError(error);
  useNotification().error(message);
};

const updateConditions = (condition: Condition): void => {
  const isNew = !conditions.value.some((item) => item.id === condition.id);
  conditions.value = sortConditions([
    ...conditions.value.filter((item) => item.id !== condition.id),
    condition,
  ]);
  if (isNew) {
    pagination.value.total++;
  }
};

const removeCondition = (id: number) => {
  const initialLength = conditions.value.length;
  conditions.value = conditions.value.filter((item) => item.id !== id);
  if (conditions.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1);
  }
};

const loadConditions = async (
  page: number = 1,
  perPage: number | undefined = undefined,
): Promise<void> => {
  isLoading.value = true;
  try {
    let url = `/api/conditions/?page=${page}`;
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`;
    }
    const response = await request(url);
    await ensure_api_success(response);

    const json = await response.json();
    const { items, pagination: paginationData } = await parse_list_response<Condition>(json);

    conditions.value = sortConditions(items);
    pagination.value = paginationData;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const getCondition = async (id: number): Promise<Condition | null> => {
  try {
    const response = await request(`/api/conditions/${id}`);
    await ensure_api_success(response);

    const json = await response.json();
    const condition = await parse_api_response<Condition>(json);

    lastError.value = null;
    return condition;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const createCondition = async (
  condition: Omit<Condition, 'id'>,
  callback?: (response: APIResponse<Condition>) => void,
): Promise<Condition | null> => {
  addInProgress.value = true;
  try {
    const response = await request('/api/conditions/', {
      method: 'POST',
      body: JSON.stringify(condition),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const created = await parse_api_response<Condition>(json);

    updateConditions(created);
    useNotification().success(t('common.crudCreated', { type: t('conditions.condition') }));
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

const updateCondition = async (
  id: number,
  condition: Condition,
  callback?: (response: APIResponse<Condition>) => void,
): Promise<Condition | null> => {
  addInProgress.value = true;
  try {
    if (condition.id) {
      condition.id = undefined;
    }
    const response = await request(`/api/conditions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(condition),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<Condition>(json);

    updateConditions(updated);
    useNotification().success(
      t('common.crudUpdated', { type: t('conditions.condition'), name: updated.name }),
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

const patchCondition = async (
  id: number,
  patch: Partial<Condition>,
  callback?: (response: APIResponse<Condition>) => void,
): Promise<Condition | null> => {
  addInProgress.value = true;
  try {
    if (patch.id) {
      patch.id = undefined;
    }
    const response = await request(`/api/conditions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<Condition>(json);

    updateConditions(updated);
    useNotification().success(
      t('common.crudUpdated', { type: t('conditions.condition'), name: updated.name }),
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

const deleteCondition = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/conditions/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);

    removeCondition(id);
    useNotification().success(t('common.crudDeleted', { type: t('conditions.condition') }));
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

const testCondition = async (
  testRequest: ConditionTestRequest,
): Promise<ConditionTestResponse | null> => {
  try {
    const response = await request('/api/conditions/test/', {
      method: 'POST',
      body: JSON.stringify(testRequest),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const result = await parse_api_response<ConditionTestResponse>(json);

    lastError.value = null;
    return result;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const clearError = () => (lastError.value = null);
export const useConditions = () => ({
  conditions: readonly(conditions),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadConditions,
  getCondition,
  createCondition,
  updateCondition,
  patchCondition,
  deleteCondition,
  testCondition,
  clearError,
  throwInstead,
});
