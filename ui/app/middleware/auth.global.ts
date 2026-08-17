import { authRedirect, useAuth } from '~/composables/useAuth';

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth();
  const state = await auth.probe();
  const redirect = authRedirect(state, to.path.replace(/\/$/, '') || '/');
  return redirect ? navigateTo(redirect) : undefined;
});
