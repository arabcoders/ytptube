import { computed, ref } from 'vue';

import { to_api_error, type ApiError } from '~/utils';

export const useFormSubmit = () => {
  const error = ref<ApiError | null>(null);
  const message = computed(() => error.value?.message ?? '');
  const fields = computed(() => error.value?.fields ?? {});

  const clear = (): void => {
    error.value = null;
  };

  const setError = (reason: unknown): void => {
    error.value = to_api_error(reason);
  };

  const run = async <T>(action: () => Promise<T>): Promise<T | null> => {
    clear();
    try {
      return await action();
    } catch (reason) {
      setError(reason);
      return null;
    }
  };

  return {
    error,
    message,
    fields,
    clear,
    setError,
    run,
  };
};
