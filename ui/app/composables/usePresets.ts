import { ref, readonly } from 'vue';

import { useNotification } from '~/composables/useNotification';
import { request, parse_list_response, parse_api_response, ensure_api_success } from '~/utils';
import type { Preset, PresetRequest } from '~/types/presets';
import type { APIResponse, Pagination } from '~/types/responses';

const presets = ref<Array<Preset>>([]);
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

const sortPresets = (items: Array<Preset>): Array<Preset> => {
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

const updatePresets = (preset: Preset): void => {
  const isNew = !presets.value.some((item) => item.id === preset.id);
  presets.value = sortPresets([...presets.value.filter((item) => item.id !== preset.id), preset]);
  if (isNew) {
    pagination.value.total++;
  }
};

const removePreset = (id: number) => {
  const initialLength = presets.value.length;
  presets.value = presets.value.filter((item) => item.id !== id);
  if (presets.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1);
  }
};

const loadPresets = async (
  page: number = 1,
  perPage: number | undefined = undefined,
  options: { excludeDefaults?: boolean } = {},
): Promise<void> => {
  isLoading.value = true;
  try {
    let url = `/api/presets/?page=${page}`;
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`;
    }
    if (options.excludeDefaults) {
      url += '&exclude_defaults=true';
    }

    const response = await request(url);
    await ensure_api_success(response);

    const json = await response.json();
    const { items, pagination: paginationData } = await parse_list_response<Preset>(json);

    presets.value = sortPresets(items);
    pagination.value = paginationData;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const getPreset = async (id: number): Promise<Preset | null> => {
  try {
    const response = await request(`/api/presets/${id}`);
    await ensure_api_success(response);

    const json = await response.json();
    const preset = await parse_api_response<Preset>(json);

    lastError.value = null;
    return preset;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const createPreset = async (
  preset: PresetRequest,
  callback?: (response: APIResponse<Preset>) => void,
): Promise<Preset | null> => {
  addInProgress.value = true;
  try {
    const response = await request('/api/presets/', {
      method: 'POST',
      body: JSON.stringify(preset),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const created = await parse_api_response<Preset>(json);

    updatePresets(created);
    useNotification().success(t('common.crudCreated', { type: t('common.presetLabel') }));
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

const updatePreset = async (
  id: number,
  preset: Preset,
  callback?: (response: APIResponse<Preset>) => void,
): Promise<Preset | null> => {
  addInProgress.value = true;
  try {
    const payload = { ...preset };
    if (payload.id) {
      payload.id = undefined;
    }
    if ('default' in payload) {
      payload.default = false;
    }
    const response = await request(`/api/presets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<Preset>(json);

    updatePresets(updated);
    useNotification().success(
      t('common.crudUpdated', { type: t('common.presetLabel'), name: updated.name }),
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

const patchPreset = async (
  id: number,
  patch: Partial<Preset>,
  callback?: (response: APIResponse<Preset>) => void,
): Promise<Preset | null> => {
  addInProgress.value = true;
  try {
    const payload = { ...patch };
    if (payload.id) {
      payload.id = undefined;
    }
    if ('default' in payload) {
      payload.default = false;
    }
    const response = await request(`/api/presets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });

    await ensure_api_success(response);

    const json = await response.json();
    const updated = await parse_api_response<Preset>(json);

    updatePresets(updated);
    useNotification().success(
      t('common.crudUpdated', { type: t('common.presetLabel'), name: updated.name }),
    );
    lastError.value = null;

    if (callback) {
      callback({ success: true, error: null, detail: null, data: updated });
    }

    return updated;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : t('common.unknownError');
    handleError(error);

    if (callback) {
      callback({ success: false, error: errorMessage, detail: error, data: undefined });
    }

    if (throwInstead.value) throw error;
    return null;
  } finally {
    addInProgress.value = false;
  }
};

const deletePreset = async (
  id: number,
  callback?: (response: APIResponse<boolean>) => void,
): Promise<boolean> => {
  try {
    const response = await request(`/api/presets/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);

    removePreset(id);
    useNotification().success(t('common.crudDeleted', { type: t('common.presetLabel') }));
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

export const usePresets = () => ({
  presets: readonly(presets),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  addInProgress: readonly(addInProgress),
  lastError: readonly(lastError),
  loadPresets,
  getPreset,
  createPreset,
  updatePreset,
  patchPreset,
  deletePreset,
  clearError,
  throwInstead,
});
