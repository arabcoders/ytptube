export default defineNuxtPlugin({
  name: 'chunk-recovery',
  // The router loads the initial route during its own pre plugin.
  order: -25,
  setup(nuxtApp) {
    const { baseURL, buildId } = nuxtApp.$config.app;
    const key = `ytptube:chunk-reload:${baseURL}`;

    nuxtApp.hook('app:chunkError', () => {
      if (!nuxtApp.isHydrating) {
        return;
      }

      try {
        if (window.sessionStorage.getItem(key) === buildId) {
          return;
        }
        window.sessionStorage.setItem(key, buildId);
      } catch {
        // Do not reload automatically if the tab cannot remember the attempt.
        return;
      }

      window.location.reload();
    });
  },
});
