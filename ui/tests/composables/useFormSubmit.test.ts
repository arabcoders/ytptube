import { describe, expect, it } from 'bun:test';

import { useFormSubmit } from '~/composables/useFormSubmit';
import { ApiError } from '~/utils';

describe('useFormSubmit', () => {
  it('keeps_error_local', async () => {
    const submit = useFormSubmit();
    const error = new ApiError('api-error', {
      status: 422,
      payload: {
        detail: [{ loc: ['body', 'timer'], msg: 'timer-required' }],
      },
    });

    const result = await submit.run(async () => Promise.reject(error));

    expect(result).toBeNull();
    expect(submit.message.value).toBe('api-error');
    expect(submit.fields.value).toEqual({ timer: 'timer-required' });
  });

  it('clears_before_retry', async () => {
    const submit = useFormSubmit();
    await submit.run(async () => Promise.reject(new Error('failed')));

    const result = await submit.run(async () => 'saved');

    expect(result).toBe('saved');
    expect(submit.error.value).toBeNull();
  });

  it('clears_on_close', async () => {
    const submit = useFormSubmit();
    await submit.run(async () => Promise.reject(new Error('failed')));

    submit.clear();

    expect(submit.message.value).toBe('');
    expect(submit.error.value).toBeNull();
  });

  it('sets_local_error', () => {
    const submit = useFormSubmit();

    submit.setError(new Error('local-error'));

    expect(submit.message.value).toBe('local-error');
  });
});
