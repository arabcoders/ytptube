import type { ApiErrorPayload } from '~/types/responses';

export const useApiErrorMessage = () => {
  const { t, te } = useI18n();

  const resolveParams = (
    params: Record<string, string | number | boolean | null> = {},
  ): Record<string, string | number | boolean | null> => {
    return Object.fromEntries(
      Object.entries(params).map(([key, value]) => {
        if (typeof value === 'string' && value.startsWith('api.') && te(value)) {
          return [key, t(value)];
        }

        return [key, value];
      }),
    );
  };

  const detailText = (detail: ApiErrorPayload['detail']): string => {
    if (typeof detail === 'string') {
      return detail;
    }

    if (!Array.isArray(detail)) {
      return '';
    }

    return detail
      .map((err) => {
        const field = Array.isArray(err.loc) ? err.loc.at(-1) : undefined;
        if (field && err.msg) {
          return `${field}: ${err.msg}`;
        }
        return err.msg || err.code || '';
      })
      .filter(Boolean)
      .join(', ');
  };

  const messageFor = (
    payload: ApiErrorPayload | string | null | undefined,
    fallbackKey = 'errors.UNKNOWN',
  ): string => {
    if (typeof payload === 'string') {
      return payload || t(fallbackKey);
    }

    if (!payload) {
      return t(fallbackKey);
    }

    if (payload.code) {
      const key = `errors.${payload.code}`;

      if (te(key)) {
        const detail = detailText(payload.detail);
        const msg = t(key, resolveParams(payload.params));
        return detail ? `${msg} - ${detail}` : msg;
      }
    }

    if (payload.error) {
      const detail = detailText(payload.detail);
      return detail ? `${payload.error} - ${detail}` : payload.error;
    }

    if (payload.message) {
      return payload.message;
    }

    const detail = detailText(payload.detail);
    if (detail) {
      return detail;
    }

    return t(fallbackKey);
  };

  return {
    messageFor,
  };
};
