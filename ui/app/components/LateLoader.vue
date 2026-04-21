<template>
  <div ref="targetEl" :style="`min-height:${fixedMinHeight || props.minHeight || 0}px`">
    <slot v-if="shouldRender" />
  </div>
</template>

<script setup lang="ts">
import { useIntersectionObserver } from '@vueuse/core';

const props = defineProps<{
  renderOnIdle?: boolean;
  unrender?: boolean;
  minHeight?: number;
  unrenderDelay?: number;
}>();

const ROOT_MARGIN = 600;
const nuxtApp = useNuxtApp();

const shouldRender = ref(false);
const targetEl = ref<HTMLElement | null>(null);
const fixedMinHeight = ref(0);

let unrenderTimer: ReturnType<typeof setTimeout> | null = null;
let renderTimer: ReturnType<typeof setTimeout> | null = null;

function ensureRenderedIfNearViewport(): void {
  if (!targetEl.value) {
    return;
  }

  const rect = targetEl.value.getBoundingClientRect();
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

  if (
    rect.bottom < -ROOT_MARGIN ||
    rect.top > viewportHeight + ROOT_MARGIN ||
    rect.right < 0 ||
    rect.left > viewportWidth
  ) {
    return;
  }

  if (unrenderTimer) {
    clearTimeout(unrenderTimer);
    unrenderTimer = null;
  }

  if (renderTimer) {
    clearTimeout(renderTimer);
    renderTimer = null;
  }

  shouldRender.value = true;
}

const { stop } = useIntersectionObserver(
  targetEl,
  (entries) => {
    const entry = entries[0];
    if (entry?.isIntersecting) {
      if (unrenderTimer) clearTimeout(unrenderTimer);

      renderTimer = setTimeout(
        () => {
          shouldRender.value = true;
        },
        props.unrender ? 200 : 0,
      );

      ensureRenderedIfNearViewport();

      if (!props.unrender) {
        stop();
      }
    } else if (props.unrender) {
      if (renderTimer) {
        clearTimeout(renderTimer);
      }

      unrenderTimer = setTimeout(() => {
        if (targetEl.value?.clientHeight) {
          fixedMinHeight.value = targetEl.value.clientHeight;
        }
        shouldRender.value = false;
      }, props.unrenderDelay ?? 6000);
    }
  },
  { rootMargin: `${ROOT_MARGIN}px` },
);

const removePageHooks = [
  nuxtApp.hook('page:finish', () => {
    requestAnimationFrame(() => {
      ensureRenderedIfNearViewport();
    });
  }),
  nuxtApp.hook('page:transition:finish', () => {
    requestAnimationFrame(() => {
      ensureRenderedIfNearViewport();
    });
  }),
];

onMounted(() => {
  window.addEventListener('resize', ensureRenderedIfNearViewport, { passive: true });
  requestAnimationFrame(() => {
    ensureRenderedIfNearViewport();
  });
});

if (props.renderOnIdle) {
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(() => {
      shouldRender.value = true;
      if (!props.unrender) {
        stop();
      }
    });
  } else {
    setTimeout(
      () =>
        nextTick(() => {
          shouldRender.value = true;
          if (!props.unrender) {
            stop();
          }
        }),
      300,
    );
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', ensureRenderedIfNearViewport);
  removePageHooks.forEach((removeHook) => removeHook());

  if (renderTimer) {
    clearTimeout(renderTimer);
  }
  if (unrenderTimer) {
    clearTimeout(unrenderTimer);
  }
});
</script>
