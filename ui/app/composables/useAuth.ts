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
  if (state.disabled) return null;
  if (state.setup_required) return path === '/setup' ? null : '/setup';
  if (path === '/setup' || path === '/login') return state.authenticated ? '/' : null;
  return state.authenticated ? null : '/login';
};

const status = ref<AuthStatus | null>(null);

export const useAuth = () => {
  const probe = async (): Promise<AuthStatus> => {
    const response = await request('/api/auth/status');
    status.value = (await response.json()) as AuthStatus;
    return status.value;
  };

  const submit = async (path: string, payload: Record<string, string>): Promise<User> => {
    const response = await request(path, { method: 'POST', body: JSON.stringify(payload) });
    const data = (await response.json()) as { user?: User };
    if (!response.ok || !data.user) {
      throw new Error(await parse_api_error(data));
    }
    status.value = { disabled: false, setup_required: false, authenticated: true, user: data.user };
    return data.user;
  };

  const login = (username: string, password: string) =>
    submit('/api/auth/login', { username, password });
  const setup = (username: string, password: string) =>
    submit('/api/auth/setup', { username, password });
  const logout = async (): Promise<void> => {
    await request('/api/auth/logout', { method: 'POST' });
    status.value = status.value ? { ...status.value, authenticated: false, user: null } : null;
  };

  return { status: computed(() => status.value), probe, login, setup, logout };
};
