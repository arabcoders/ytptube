import { describe, expect, it } from 'bun:test';

import { useFormSubmit } from '~/composables/useFormSubmit';
import { ApiError } from '~/utils';

describe('useFormSubmit', () => {
  it('keeps_error_local', async () => {
    const submit = useFormSubmit();
    const error = new ApiError('Invalid task.', {
      status: 422,
      payload: {
        detail: [{ loc: ['body', 'timer'], msg: 'Timer is required.' }],
      },
    });

    const result = await submit.run(async () => Promise.reject(error));

    expect(result).toBeNull();
    expect(submit.message.value).toBe('Invalid task.');
    expect(submit.fields.value).toEqual({ timer: 'Timer is required.' });
  });

  it('clears_before_retry', async () => {
    const submit = useFormSubmit();
    await submit.run(async () => Promise.reject(new Error('Failed.')));

    const result = await submit.run(async () => 'saved');

    expect(result).toBe('saved');
    expect(submit.error.value).toBeNull();
  });

  it('clears_on_close', async () => {
    const submit = useFormSubmit();
    await submit.run(async () => Promise.reject(new Error('Failed.')));

    submit.clear();

    expect(submit.message.value).toBe('');
    expect(submit.error.value).toBeNull();
  });

  it('sets_local_error', () => {
    const submit = useFormSubmit();

    submit.setError(new Error('Invalid import.'));

    expect(submit.message.value).toBe('Invalid import.');
  });
});
