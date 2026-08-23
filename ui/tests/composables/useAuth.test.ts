import { afterEach, beforeEach, describe, expect, it, spyOn } from 'bun:test';

import * as utils from '~/utils';
import { authRedirect, invalidateAuth, useAuth } from '~/composables/useAuth';

const state = (values: Partial<Parameters<typeof authRedirect>[0]> = {}) => ({
  disabled: false,
  setup_required: false,
  authenticated: false,
  user: null,
  ...values,
});

describe('authRedirect', () => {
  it('routes_setup', () =>
    expect(authRedirect(state({ setup_required: true }), '/')).toBe('/setup'));
  it('keeps_setup', () =>
    expect(authRedirect(state({ setup_required: true }), '/setup')).toBeNull());
  it('routes_login', () => expect(authRedirect(state(), '/tasks')).toBe('/login'));
  it('routes_authenticated_login', () =>
    expect(authRedirect(state({ authenticated: true }), '/login')).toBe('/'));
  it('allows_disabled', () => expect(authRedirect(state({ disabled: true }), '/tasks')).toBeNull());
});

describe('useAuth', () => {
  let requestSpy: ReturnType<typeof spyOn>;

  beforeEach(() => {
    invalidateAuth();
    requestSpy = spyOn(utils, 'request');
  });

  afterEach(() => {
    requestSpy.mockRestore();
    invalidateAuth();
  });

  it('caches_probe_result', async () => {
    requestSpy.mockResolvedValue({
      json: async () => state({ authenticated: true }),
    } as Response);
    const auth = useAuth();

    await auth.probe();
    await auth.probe();

    expect(requestSpy).toHaveBeenCalledTimes(1);
  });

  it('shares_pending_probe', async () => {
    let resolveRequest: ((response: Response) => void) | undefined;
    requestSpy.mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveRequest = resolve;
      }),
    );
    const auth = useAuth();
    const first = auth.probe();
    const second = auth.probe();

    expect(requestSpy).toHaveBeenCalledTimes(1);
    resolveRequest?.({ json: async () => state() } as Response);
    await Promise.all([first, second]);
  });

  it('forces_fresh_probe', async () => {
    requestSpy.mockResolvedValue({ json: async () => state() } as Response);
    const auth = useAuth();

    await auth.probe();
    await auth.probe(true);

    expect(requestSpy).toHaveBeenCalledTimes(2);
  });
});
