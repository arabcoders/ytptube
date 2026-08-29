import { computed, ref } from 'vue';
import { parse_api_error, request } from '~/utils';

type User = { id: number; username: string };
export type AuthStatus = {
  disabled: boolean;
  setup_required: boolean;
  authenticated: boolean;
  user: User | null;
};

export const authRedirect = (state: AuthStatus, path: string): string | null => {
  if (state.disabled) return path === '/setup' || path === '/login' ? '/' : null;
  if (state.setup_required) return path === '/setup' ? null : '/setup';
  if (path === '/setup' || path === '/login') return state.authenticated ? '/' : null;
  return state.authenticated ? null : '/login';
};

const status = ref<AuthStatus | null>(null);
let probePromise: Promise<AuthStatus> | null = null;
let probeVersion = 0;

export const invalidateAuth = (): void => {
  probeVersion += 1;
  probePromise = null;
  status.value = null;
};

const updateStatus = (value: AuthStatus): void => {
  probeVersion += 1;
  probePromise = null;
  status.value = value;
};

export const useAuth = () => {
  const probe = async (force: boolean = false): Promise<AuthStatus> => {
    if (!force && status.value) {
      return status.value;
    }

    if (!force && probePromise) {
      return probePromise;
    }

    const version = ++probeVersion;
    const operation = (async (): Promise<AuthStatus> => {
      const response = await request('/api/auth/status');
      const value = (await response.json()) as AuthStatus;
      if (version === probeVersion) {
        status.value = value;
      }
      return value;
    })();
    probePromise = operation;

    try {
      return await operation;
    } finally {
      if (probePromise === operation) {
        probePromise = null;
      }
    }
  };

  const submit = async (path: string, payload: Record<string, string>): Promise<User> => {
    const response = await request(path, { method: 'POST', body: JSON.stringify(payload) });
    const data = (await response.json()) as { user?: User };
    if (!response.ok || !data.user) {
      throw new Error(await parse_api_error(data));
    }
    updateStatus({ disabled: false, setup_required: false, authenticated: true, user: data.user });
    return data.user;
  };

  const login = (username: string, password: string) =>
    submit('/api/auth/login', { username, password });
  const setup = (username: string, password: string) =>
    submit('/api/auth/setup', { username, password });
  const logout = async (): Promise<void> => {
    await request('/api/auth/logout', { method: 'POST' });
    if (status.value) {
      updateStatus({ ...status.value, authenticated: false, user: null });
    } else {
      invalidateAuth();
    }
  };

  return { status: computed(() => status.value), probe, login, setup, logout };
};
