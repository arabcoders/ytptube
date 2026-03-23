import { useColorMode } from '#imports';

export default defineNuxtPlugin(() => {
  const legacyTheme = window.localStorage.getItem('theme');
  if (!legacyTheme) {
    return;
  }

  const nextPreference = 'auto' === legacyTheme ? 'system' : legacyTheme;
  if (!['system', 'light', 'dark'].includes(nextPreference)) {
    window.localStorage.removeItem('theme');
    return;
  }

  if (!window.localStorage.getItem('nuxt-color-mode')) {
    const colorMode = useColorMode();
    colorMode.preference = nextPreference as 'system' | 'light' | 'dark';
  }

  window.localStorage.removeItem('theme');
});
