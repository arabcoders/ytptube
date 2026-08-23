import { authRedirect, useAuth } from '~/composables/useAuth';

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth();
  const path = to.path.replace(/\/$/, '') || '/';
  const state = await auth.probe(path === '/login' || path === '/setup');
  const redirect = authRedirect(state, path);
  return redirect ? navigateTo(redirect) : undefined;
});
