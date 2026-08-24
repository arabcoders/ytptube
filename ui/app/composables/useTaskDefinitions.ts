import { ref, readonly } from 'vue';

import { useNotification } from '~/composables/useNotification';
import { request, parse_list_response, parse_api_response, ensure_api_success } from '~/utils';
import type {
  ImpersonateTargetsResponse,
  TaskDefinitionDetailed,
  TaskDefinitionDocument,
  TaskDefinitionSummary,
} from '~/types/task_definitions';
import type { Pagination } from '~/types/responses';

const definitions = ref<Array<TaskDefinitionSummary>>([]);
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const isLoading = ref<boolean>(false);
const lastError = ref<string | null>(null);
const impersonateTargets = ref<string[]>([]);
const targetsLoaded = ref(false);

// Test hook: rethrow request errors instead of returning fallback values.
const throwInstead = ref(false);

const { $i18n } = useNuxtApp();
const t = $i18n?.t ?? ((key: string) => key);

const sortSummaries = (items: Array<TaskDefinitionSummary>): Array<TaskDefinitionSummary> => {
  return [...items].sort((a, b) => {
    if (a.priority === b.priority) {
      return a.name.localeCompare(b.name);
    }

    return a.priority - b.priority;
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

const updateSummaries = (summary: TaskDefinitionSummary): void => {
  const isNew = !definitions.value.some((item) => item.id === summary.id);
  definitions.value = sortSummaries([
    ...definitions.value.filter((item) => item.id !== summary.id),
    summary,
  ]);
  if (isNew) {
    pagination.value.total++;
  }
};

const removeSummary = (id: number) => {
  const initialLength = definitions.value.length;
  definitions.value = definitions.value.filter((item) => item.id !== id);
  if (definitions.value.length < initialLength) {
    pagination.value.total = Math.max(0, pagination.value.total - 1);
  }
};

const loadDefinitions = async (
  page: number = 1,
  perPage: number | undefined = undefined,
): Promise<void> => {
  isLoading.value = true;
  try {
    let url = `/api/tasks/definitions/?page=${page}`;
    if (perPage !== undefined) {
      url += `&per_page=${perPage}`;
    }
    const response = await request(url);
    await ensure_api_success(response);

    const json = await response.json();
    const { items, pagination: paginationData } =
      await parse_list_response<TaskDefinitionSummary>(json);

    definitions.value = sortSummaries(items);
    pagination.value = paginationData;
    lastError.value = null;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  } finally {
    isLoading.value = false;
  }
};

const getDefinition = async (id: number): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request(`/api/tasks/definitions/${id}`);
    await ensure_api_success(response);

    const payload = await response.json();
    const detailed = await parse_api_response<TaskDefinitionDetailed>(payload);
    lastError.value = null;
    return detailed;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const loadImpersonateTargets = async (): Promise<void> => {
  if (targetsLoaded.value) return;
  try {
    const response = await request('/api/tasks/definitions/impersonate-targets');
    await ensure_api_success(response);
    const payload = await parse_api_response<ImpersonateTargetsResponse>(response.json());
    impersonateTargets.value = Array.isArray(payload.targets)
      ? payload.targets.filter((target): target is string => typeof target === 'string')
      : [];
    targetsLoaded.value = true;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
  }
};

const createDefinition = async (
  definition: TaskDefinitionDocument,
): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request('/api/tasks/definitions/', {
      method: 'POST',
      body: JSON.stringify(definition),
    });

    await ensure_api_success(response);

    const payload = await parse_api_response<TaskDefinitionDetailed>(response.json());

    updateSummaries({
      id: payload.id,
      name: payload.name,
      priority: payload.priority,
      match_url: payload.match_url,
      enabled: payload.enabled,
      created_at: payload.created_at,
      updated_at: payload.updated_at,
    });

    useNotification().success(t('common.crudCreated', { type: t('taskDefinitions.definition') }));
    lastError.value = null;
    return payload;
  } catch (error) {
    setError(error);
    throw error;
  }
};

const updateDefinition = async (
  id: number,
  definition: TaskDefinitionDocument,
): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request(`/api/tasks/definitions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(definition),
    });

    await ensure_api_success(response);

    const payload = await parse_api_response<TaskDefinitionDetailed>(response.json());

    updateSummaries({
      id: payload.id,
      name: payload.name,
      priority: payload.priority,
      match_url: payload.match_url,
      enabled: payload.enabled,
      created_at: payload.created_at,
      updated_at: payload.updated_at,
    });

    useNotification().success(
      t('common.crudUpdated', { type: t('taskDefinitions.definition'), name: payload.name }),
    );
    lastError.value = null;
    return payload;
  } catch (error) {
    setError(error);
    throw error;
  }
};

const deleteDefinition = async (id: number): Promise<boolean> => {
  try {
    const response = await request(`/api/tasks/definitions/${id}`, { method: 'DELETE' });
    await ensure_api_success(response);

    removeSummary(id);
    useNotification().success(t('common.crudDeleted', { type: t('taskDefinitions.definition') }));
    lastError.value = null;
    return true;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return false;
  }
};

const toggleEnabled = async (
  id: number,
  enabled: boolean,
): Promise<TaskDefinitionDetailed | null> => {
  try {
    const response = await request(`/api/tasks/definitions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    });

    await ensure_api_success(response);

    const payload = await parse_api_response<TaskDefinitionDetailed>(response.json());

    updateSummaries({
      id: payload.id,
      name: payload.name,
      priority: payload.priority,
      match_url: payload.match_url,
      enabled: payload.enabled,
      created_at: payload.created_at,
      updated_at: payload.updated_at,
    });

    useNotification().success(
      t(enabled ? 'common.crudEnabled' : 'common.crudDisabled', {
        type: t('taskDefinitions.definition'),
      }),
    );
    lastError.value = null;
    return payload;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) throw error;
    return null;
  }
};

const clearError = () => (lastError.value = null);

export const useTaskDefinitions = () => ({
  definitions: readonly(definitions),
  impersonateTargets: readonly(impersonateTargets),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  lastError: readonly(lastError),
  loadDefinitions,
  loadImpersonateTargets,
  getDefinition,
  createDefinition,
  updateDefinition,
  deleteDefinition,
  toggleEnabled,
  clearError,
  throwInstead,
});

export default useTaskDefinitions;
