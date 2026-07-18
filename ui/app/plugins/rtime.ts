import type { Ref, WatchStopHandle } from 'vue';
import { watch } from 'vue';
import { formatRelativeTime } from '~/utils/relativeTime';

type RTimeElementState = HTMLElement & { _next_timer?: number; _stop_rtime?: WatchStopHandle };

type I18nPlugin = {
  locale?: Ref<string> | string;
};

const readLocale = (source: Ref<string> | string | undefined): string => {
  if (!source) {
    return 'en';
  }

  return typeof source === 'string' ? source : source.value;
};

const parseInterval = (arg: string | undefined): number => {
  if (!arg) {
    return 60 * 1000;
  }

  const match = arg.match(/^(\d+)([smhd])$/);

  if (!match) {
    return 60 * 1000;
  }

  const [, numStr, unit] = match;
  const num = parseInt(String(numStr), 10);

  switch (unit) {
    case 'd':
      return num * 24 * 3600 * 1000;
    case 'h':
      return num * 3600 * 1000;
    case 'm':
      return num * 60 * 1000;
    case 's':
      return num * 1000;
    default:
      return 60 * 1000;
  }
};

export default defineNuxtPlugin((nuxtApp) => {
  const i18n = nuxtApp.$i18n as I18nPlugin | undefined;

  nuxtApp.vueApp.directive('rtime', {
    mounted(el: RTimeElementState, binding) {
      const intervalMs = parseInterval(binding.arg);
      const update = () => {
        const val = binding.value;
        el.textContent = formatRelativeTime(val, readLocale(i18n?.locale));
      };

      update();
      el._next_timer = window.setInterval(update, intervalMs);
      if (i18n?.locale && typeof i18n.locale !== 'string') {
        el._stop_rtime = watch(i18n.locale, update);
      }
    },
    updated(el: RTimeElementState, binding) {
      if (binding.oldValue !== binding.value) {
        if (null != el._next_timer) clearInterval(el._next_timer);
        el._stop_rtime?.();

        const intervalMs = parseInterval(binding.arg);
        const update = () => {
          const val = binding.value;
          el.textContent = formatRelativeTime(val, readLocale(i18n?.locale));
        };

        update();
        el._next_timer = window.setInterval(update, intervalMs);
        if (i18n?.locale && typeof i18n.locale !== 'string') {
          el._stop_rtime = watch(i18n.locale, update);
        }
      }
    },
    beforeUnmount(el: RTimeElementState) {
      if (null != el._next_timer) clearInterval(el._next_timer);
      el._stop_rtime?.();
    },
  });

  return {};
});
