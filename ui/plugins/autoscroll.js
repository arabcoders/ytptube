let observer;
const AUTO_SCROLL_EVENTS = ['scroll', 'mousewheel', 'touchmove'];
let events_handlers = [];

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.directive('autoscroll', {
    mounted: async el => {
      let scrolledToBottom = true;

      AUTO_SCROLL_EVENTS.forEach((ev, index) => {
        events_handlers[index] = () => {
          scrolledToBottom = (el.scrollHeight - el.scrollTop) - el.clientHeight <= 80;
        }
        el.addEventListener(ev, events_handlers[index], { passive: true });
      });

      observer = new MutationObserver(_ => {
        if (false === scrolledToBottom) {
          return;
        }
        el.scrollTop = el.scrollHeight;
      });

      observer.observe(el, { childList: true, subtree: true });
    },
    unmounted: el => {
      AUTO_SCROLL_EVENTS.forEach((ev, index) => {
        el.removeEventListener(ev, events_handlers[index], { passive: true });
      });
      observer.disconnect();
    },
  })
});
