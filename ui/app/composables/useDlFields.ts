import { ref, readonly } from 'vue';

import { useNotification } from '~/composables/useNotification';
import { request, parse_list_response, parse_api_response, ensure_api_success } from '~/utils';
import type { DLField, DLFieldRequest } from '~/types/dl_fields';
import type { APIResponse, Pagination } from '~/types/responses';

const dlFields = ref<Array<DLField>>([]);
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
const notify = useNotification();
const { $i18n } = useNuxtApp();
const t = $i18n?.t ?? ((key: string) => key);

const sortDlFields = (items: Array<DLField>): Array<DLField> => {
  return [...items].sort((a, b) => {
    if (a.order === b.order) {
      return a.name.localeCompare(b.name);
    }

    return a.order - b.order;
  });
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

const updateDlFields = (field: DLField): void => {
  const isNew = !dlFields.value.some((item) => item.id === field.id);
  dlFields.value = sortDlFields([...dlFields.value.filter((item) => item.id !== field.id), field]);
  if (isNew) {
    pagination.value.total++;
  }
};

const removeDlField = (id: number) => {
  const initialLength = dlFields.value.length;
  dlFields.value = dlFields.value.filter((item) => item.id !== id);
  if (dlFields.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1);
  }
};

const loadDlFields = async (
  page: number = 1,
  perPage: number | undefined = undefined,
): Promise<void> => {
  isLoading.value = true;
  try {
    let url = `/api/dl_fields/?page=${page}`;
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`;
    }
    const response = await request(url);
    await ensure_api_success(response);

    const json = await response.json();
    const { items, pagination: paginationData } = await parse_list_response<DLField>(json);

    dlFields.value = sortDlFields(items);
    pagination.value = paginationData;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const getDlField = async (id: number): Promise<DLField | null> => {
  try {
    const response = await request(`/api/dl_fields/${id}`);
    await ensure_api_success(response);

    const json = await response.json();
    const field = await parse_api_response<DLField>(json);

    lastError.value = null;
    return field;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const createDlField = async (
  field: DLFieldRequest,
  callback?: (response: APIResponse<DLField>) => void,
): Promise<DLField | null> => {
  addInProgress.value = true;
  try {
    const response = await request('/api/dl_fields/', {
      method: 'POST',
      body: JSON.stringify(field),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const created = await parse_api_response<DLField>(json);

    updateDlFields(created);
    notify.success(t('common.crudCreated', { type: t('customFields.field') }));
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

const updateDlField = async (
  id: number,
  field: DLField,
  callback?: (response: APIResponse<DLField>) => void,
): Promise<DLField | null> => {
  addInProgress.value = true;
  try {
    if (field.id) {
      field.id = undefined;
    }
    const response = await request(`/api/dl_fields/${id}`, {
      method: 'PUT',
      body: JSON.stringify(field),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<DLField>(json);

    updateDlFields(updated);
    notify.success(t('common.crudUpdated', { type: t('customFields.field'), name: updated.name }));
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

const patchDlField = async (
  id: number,
  patch: Partial<DLField>,
  callback?: (response: APIResponse<DLField>) => void,
): Promise<DLField | null> => {
  addInProgress.value = true;
  try {
    if (patch.id) {
      patch.id = undefined;
    }
    const response = await request(`/api/dl_fields/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<DLField>(json);

    updateDlFields(updated);
    notify.success(t('common.crudUpdated', { type: t('customFields.field'), name: updated.name }));
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

const deleteDlField = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/dl_fields/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);

    removeDlField(id);
    notify.success(t('common.crudDeleted', { type: t('customFields.field') }));
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

const clearError = () => (lastError.value = null);

export const useDlFields = () => ({
  dlFields: readonly(dlFields),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadDlFields,
  getDlField,
  createDlField,
  updateDlField,
  patchDlField,
  deleteDlField,
  clearError,
  throwInstead,
});
