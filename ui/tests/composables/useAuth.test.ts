import { describe, expect, it } from 'bun:test';

import { authRedirect } from '~/composables/useAuth';

const state = (values: Partial<Parameters<typeof authRedirect>[0]> = {}) => ({
  disabled: false,
  setup_required: false,
  authenticated: false,
  user: null,
  ...values,
});

describe('authRedirect', () => {
  it('routes_setup', () => expect(authRedirect(state({ setup_required: true }), '/')).toBe('/setup'));
  it('keeps_setup', () => expect(authRedirect(state({ setup_required: true }), '/setup')).toBeNull());
  it('routes_login', () => expect(authRedirect(state(), '/tasks')).toBe('/login'));
  it('routes_authenticated_login', () => expect(authRedirect(state({ authenticated: true }), '/login')).toBe('/'));
  it('allows_disabled', () => expect(authRedirect(state({ disabled: true }), '/tasks')).toBeNull());
});
