let observer: MutationObserver;
const AUTO_SCROLL_EVENTS = ['scroll', 'mousewheel', 'touchmove'] as const;
const events_handlers: Array<(ev: Event) => void> = [];

const on_mounted = (el: HTMLElement) => {
  let scrolledToBottom = true;

  AUTO_SCROLL_EVENTS.forEach((ev, index) => {
    const handler = () => {
      scrolledToBottom = (el.scrollHeight - el.scrollTop) - el.clientHeight <= 80;
    };
    events_handlers[index] = handler;
    el.addEventListener(ev as string, handler, { passive: true } as AddEventListenerOptions);
  });

  observer = new MutationObserver(() => {
    if (false === scrolledToBottom) return;
    el.scrollTop = el.scrollHeight;
  });

  observer.observe(el, { childList: true, subtree: true });
}
const on_unmounted = (el: HTMLElement) => {
  AUTO_SCROLL_EVENTS.forEach((ev, index) => {
    const handler = events_handlers[index];
    if (handler) {
      el.removeEventListener(ev as string, handler, { passive: true } as EventListenerOptions);
    }
  });
  observer.disconnect();
}

export default defineNuxtPlugin(nuxtApp => {
  nuxtApp.vueApp.directive('autoscroll', {
    mounted: on_mounted,
    unmounted: on_unmounted,
  });
});
