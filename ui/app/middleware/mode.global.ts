import { cookieDefault, parseMode, routeTarget, savePref, usePref } from '~/composables/useMode';

export default defineNuxtRouteMiddleware(async (to) => {
  const path = to.path.replace(/\/+$/, '') || '/';
  const pref = usePref();

  if (to.query.simple !== undefined) {
    const value = parseMode(to.query.simple);
    if (value !== null) {
      savePref(value);
    }

    const query = { ...to.query };
    delete query.simple;
    const target = value === true ? '/simple' : value === false ? '/' : to.path;

    return navigateTo({ path: target, query, hash: to.hash }, { replace: true });
  }

  if (path !== '/') {
    return;
  }

  let def = cookieDefault();
  if (pref.value === null && def === null) {
    const cfg = useYtpConfig();
    await cfg.loadConfig();
    def = Boolean(cfg.app.simple_mode);
  }

  const target = routeTarget(path, pref.value, Boolean(def));
  if (target) {
    return navigateTo(target, { replace: true });
  }
});
