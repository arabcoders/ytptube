import { readonly, ref } from 'vue';
import { useNotification } from '~/composables/useNotification';
import { ensure_api_success, parse_api_response, parse_list_response, request } from '~/utils';
import { isToolboxActive } from '~/utils/toolbox';
import type { Pagination } from '~/types/responses';
import type { ToolboxJob, ToolboxOptions, ToolboxTool } from '~/types/toolbox';

const tools = ref<ToolboxTool[]>([]);
const jobs = ref<ToolboxJob[]>([]);
const pagination = ref<Pagination>({
  page: 1,
  per_page: 50,
  total: 0,
  total_pages: 0,
  has_next: false,
  has_prev: false,
});
const isLoading = ref(false);
const isToolsLoading = ref(false);
const inProgressIds = ref(new Set<number>());
const lastError = ref<string | null>(null);
const toolsError = ref<string | null>(null);
let toolsRequest: Promise<void> | null = null;

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : useNuxtApp().$i18n.t('common.unknownError');

const handleError = (error: unknown): void => {
  lastError.value = errorMessage(error);
  useNotification().error(lastError.value);
};

const updatePagination = (): void => {
  pagination.value.total_pages = Math.max(
    1,
    Math.ceil(pagination.value.total / pagination.value.per_page),
  );
  pagination.value.has_next = pagination.value.page < pagination.value.total_pages;
  pagination.value.has_prev = pagination.value.page > 1;
};

const update = (job: ToolboxJob): void => {
  const current = jobs.value.find((item) => item.id === job.id);
  if (current && !isToolboxActive(current) && isToolboxActive(job)) return;
  jobs.value = jobs.value.map((item) => (item.id === job.id ? job : item));
};

const upsert = (job: ToolboxJob): void => {
  if (jobs.value.some((item) => item.id === job.id)) {
    update(job);
    return;
  }
  if (
    pagination.value.page !== 1 ||
    (jobs.value.length >= pagination.value.per_page &&
      job.created_at < (jobs.value.at(-1)?.created_at ?? ''))
  )
    return;
  jobs.value = [job, ...jobs.value]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, pagination.value.per_page);
  pagination.value.total++;
  updatePagination();
};

const drop = (id: number): void => {
  const length = jobs.value.length;
  jobs.value = jobs.value.filter((item) => item.id !== id);
  if (jobs.value.length === length) return;
  pagination.value.total = Math.max(0, pagination.value.total - 1);
  updatePagination();
};

const loadTools = (): Promise<void> => {
  if (toolsRequest) return toolsRequest;
  isToolsLoading.value = true;
  toolsError.value = null;
  toolsRequest = (async () => {
    try {
      const response = await request('/api/toolbox/tools', { timeout: 20 });
      await ensure_api_success(response);
      const data = await parse_api_response<{ items: ToolboxTool[] }>(await response.json());
      tools.value = data.items;
    } catch (error) {
      toolsError.value = errorMessage(error);
      useNotification().error(toolsError.value);
    } finally {
      isToolsLoading.value = false;
      toolsRequest = null;
    }
  })();
  return toolsRequest;
};

const loadJobs = async (page = pagination.value.page): Promise<void> => {
  if (isLoading.value) return;
  isLoading.value = true;
  lastError.value = null;
  try {
    const query = new URLSearchParams({ page: String(page) });
    const response = await request(`/api/toolbox/jobs?${query}`, { timeout: 20 });
    await ensure_api_success(response);
    const data = await parse_list_response<ToolboxJob>(await response.json());
    jobs.value = data.items;
    pagination.value = data.pagination;
  } catch (error) {
    handleError(error);
  } finally {
    isLoading.value = false;
  }
};

const getJob = async (id: number): Promise<ToolboxJob> => {
  const response = await request(`/api/toolbox/jobs/${id}`, { timeout: 20 });
  await ensure_api_success(response);
  return parse_api_response<ToolboxJob>(await response.json());
};

const createJob = async (
  tool: string,
  file: string,
  overwriteSource = true,
  options: ToolboxOptions = {},
): Promise<ToolboxJob> => {
  const response = await request('/api/toolbox/jobs', {
    method: 'POST',
    body: JSON.stringify({ tool, file, extra: { overwrite_source: overwriteSource, options } }),
    timeout: 20,
  });
  await ensure_api_success(response);
  const job = await parse_api_response<ToolboxJob>(await response.json());
  upsert(job);
  return job;
};

const cancelJob = async (job: ToolboxJob): Promise<boolean> => {
  const current = jobs.value.find((item) => item.id === job.id) ?? job;
  if (inProgressIds.value.has(job.id) || !isToolboxActive(current)) return false;
  inProgressIds.value.add(job.id);
  try {
    const response = await request(`/api/toolbox/jobs/${job.id}/cancel`, {
      method: 'POST',
      timeout: 20,
    });
    await ensure_api_success(response);
    const updated = await parse_api_response<ToolboxJob>(await response.json());
    update(updated);
    return true;
  } catch (error) {
    handleError(error);
    return false;
  } finally {
    inProgressIds.value.delete(job.id);
  }
};

const deleteJob = async (job: ToolboxJob): Promise<boolean> => {
  const current = jobs.value.find((item) => item.id === job.id) ?? job;
  if (inProgressIds.value.has(job.id) || isToolboxActive(current)) return false;
  inProgressIds.value.add(job.id);
  try {
    const response = await request(`/api/toolbox/jobs/${job.id}`, {
      method: 'DELETE',
      timeout: 20,
    });
    await ensure_api_success(response);
    drop(job.id);
    return true;
  } catch (error) {
    handleError(error);
    return false;
  } finally {
    inProgressIds.value.delete(job.id);
  }
};

export const useToolbox = () => ({
  tools: readonly(tools),
  jobs: readonly(jobs),
  pagination: readonly(pagination),
  isLoading: readonly(isLoading),
  isToolsLoading: readonly(isToolsLoading),
  inProgressIds: readonly(inProgressIds),
  lastError: readonly(lastError),
  toolsError: readonly(toolsError),
  loadTools,
  loadJobs,
  getJob,
  createJob,
  cancelJob,
  deleteJob,
  update,
  upsert,
  drop,
});
