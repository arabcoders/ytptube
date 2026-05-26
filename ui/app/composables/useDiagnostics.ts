import { computed, readonly, ref } from 'vue';
import { useNotification } from '~/composables/useNotification';
import type { DiagnosticCheck, DiagnosticsResponse } from '~/types/diagnostics';
import { parse_api_error, parse_api_response, request } from '~/utils';

const diagnostics = ref<DiagnosticsResponse | null>(null);
const isLoading = ref(false);
const lastError = ref<string | null>(null);
const throwInstead = ref(false);

const groupedChecks = computed<Record<string, Array<DiagnosticCheck>>>(() => {
  return (diagnostics.value?.checks ?? []).reduce<Record<string, Array<DiagnosticCheck>>>(
    (acc, check) => {
      if (!acc[check.group]) {
        acc[check.group] = [];
      }

      acc[check.group]?.push(check);
      return acc;
    },
    {},
  );
});

const groupOrder = computed<Array<string>>(() => Object.keys(groupedChecks.value));

const readJson = async (response: Response): Promise<unknown> => {
  try {
    return await response.clone().json();
  } catch {
    return null;
  }
};

const ensureSuccess = async (response: Response): Promise<void> => {
  if (response.ok) {
    return;
  }

  const payload = await readJson(response);
  throw new Error(await parse_api_error(payload));
};

const handleError = (error: unknown): void => {
  const message = error instanceof Error ? error.message : 'Failed to load diagnostics.';
  lastError.value = message;
  useNotification().error(message);
};

const loadDiagnostics = async (force: boolean = false): Promise<DiagnosticsResponse | null> => {
  if (isLoading.value) {
    return diagnostics.value;
  }

  if (diagnostics.value && !force) {
    return diagnostics.value;
  }

  isLoading.value = true;
  lastError.value = null;

  try {
    const response = await request(`/api/system/diagnostics${force ? '?refresh=1' : ''}`);
    await ensureSuccess(response);

    diagnostics.value = await parse_api_response<DiagnosticsResponse>(response.json());
    return diagnostics.value;
  } catch (error) {
    handleError(error);
    if (throwInstead.value) {
      throw error;
    }
    return null;
  } finally {
    isLoading.value = false;
  }
};

const clearError = (): void => {
  lastError.value = null;
};

const __resetForTesting = (): void => {
  diagnostics.value = null;
  isLoading.value = false;
  lastError.value = null;
  throwInstead.value = false;
};

export const useDiagnostics = () => ({
  diagnostics: readonly(diagnostics),
  isLoading: readonly(isLoading),
  lastError: readonly(lastError),
  groupedChecks,
  groupOrder,
  loadDiagnostics,
  clearError,
  throwInstead,
  __resetForTesting,
});
