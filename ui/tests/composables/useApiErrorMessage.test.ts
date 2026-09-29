import { describe, it, expect, mock } from 'bun:test';
import en from '../../i18n/locales/en.json';

const get = (key: string): string | undefined => {
  let value: unknown = en;

  for (const part of key.split('.')) {
    if (!value || typeof value !== 'object' || !(part in value)) {
      return undefined;
    }

    value = (value as Record<string, unknown>)[part];
  }

  return typeof value === 'string' ? value : undefined;
};

const t = (key: string, params?: Record<string, unknown>): string => {
  if (key.startsWith('api.')) {
    return `label:${key}`;
  }

  return params ? `${key}:${JSON.stringify(params)}` : key;
};

const te = (key: string): boolean => get(key) != null;

mock.module('#imports', () => ({
  useI18n: () => ({ t, te }),
}));

globalThis.useI18n = () => ({ t, te });

const { useApiErrorMessage } = await import('~/composables/useApiErrorMessage');

describe('useApiErrorMessage', () => {
  const { messageFor } = useApiErrorMessage();

  it('returns translated message for known code', () => {
    const result = messageFor({ code: 'NOT_FOUND', params: { resource: 'api.resources.file' } });
    expect(result).toBe('errors.NOT_FOUND:{"resource":"label:api.resources.file"}');
  });

  it('returns localized unavailable-file message', () => {
    const result = messageFor({ code: 'FILE_UNAVAILABLE', params: { file: 'video.mp4' } });
    expect(result).toContain('errors.FILE_UNAVAILABLE:');
    expect(result).toContain('video.mp4');
  });

  it('resolves api param labels before interpolation', () => {
    const result = messageFor({
      code: 'NOT_FOUND',
      params: { resource: 'api.resources.taskDefinition' },
    });
    expect(result).toBe('errors.NOT_FOUND:{"resource":"label:api.resources.taskDefinition"}');
  });

  it('falls back to backend error for unknown code', () => {
    const result = messageFor({
      code: 'SOME_UNKNOWN_CODE',
      error: 'backend-error',
    });
    expect(result).toBe('backend-error');
  });

  it('falls back to backend message when code is unknown', () => {
    const result = messageFor({
      code: 'UNKNOWN_CODE',
      message: 'backend-message',
    });
    expect(result).toBe('backend-message');
  });

  it('returns detail string when no other text available', () => {
    const result = messageFor({
      detail: 'validation-detail',
    });
    expect(result).toBe('validation-detail');
  });

  it.each([null, undefined])('returns localized generic error for %s payload', (payload) => {
    const result = messageFor(payload);
    expect(result).toBe('errors.UNKNOWN');
  });

  it('returns string payload unchanged', () => {
    const result = messageFor('string-payload');
    expect(result).toBe('string-payload');
  });

  it('returns empty string fallback for empty string payload', () => {
    const result = messageFor('');
    expect(result).toBe('errors.UNKNOWN');
  });

  it('returns localized generic for empty object payload', () => {
    const result = messageFor({});
    expect(result).toBe('errors.UNKNOWN');
  });

  it('uses custom fallback key when provided', () => {
    const result = messageFor(null, 'errors.BAD_REQUEST');
    expect(result).toBe('errors.BAD_REQUEST');
  });

  it('prefers code over error text', () => {
    const result = messageFor({
      code: 'INVALID',
      params: { field: 'api.fields.url' },
      error: 'raw-backend-error',
    });
    expect(result).toBe('errors.INVALID:{"field":"label:api.fields.url"}');
  });

  it('returns array detail text when no other text available', () => {
    const result = messageFor({
      detail: [{ loc: ['body', 'name'], msg: 'required', type: 'missing' }],
    });
    expect(result).toBe('name: required');
  });

  it('prefers error over message when no code', () => {
    const result: ReturnType<typeof messageFor> = messageFor({
      error: 'error-value',
      message: 'message-value',
    });
    expect(result).toBe('error-value');
  });
});
