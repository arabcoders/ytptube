<template>
  <div ref="targetEl" :style="`min-height:${fixedMinHeight || props.minHeight || 0}px`">
    <slot v-if="shouldRender" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'

const props = defineProps<{
  renderOnIdle?: boolean
  unrender?: boolean
  minHeight?: number
  unrenderDelay?: number
}>()

const shouldRender = ref(false)
const targetEl = ref<HTMLElement | null>(null)
const fixedMinHeight = ref(0)

let unrenderTimer: ReturnType<typeof setTimeout> | null = null
let renderTimer: ReturnType<typeof setTimeout> | null = null

function onIdle(cb: () => void): void {
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(cb)
  } else {
    setTimeout(() => nextTick(cb), 300)
  }
}

const { stop } = useIntersectionObserver(targetEl, ([{ isIntersecting }]) => {
  if (isIntersecting) {
    if (unrenderTimer) clearTimeout(unrenderTimer)

    renderTimer = setTimeout(() => { shouldRender.value = true }, props.unrender ? 200 : 0)

    shouldRender.value = true

    if (!props.unrender) {
      stop()
    }
  }
  else if (props.unrender) {
    if (renderTimer) {
      clearTimeout(renderTimer)
    }

    unrenderTimer = setTimeout(() => {
      if (targetEl.value?.clientHeight) {
        fixedMinHeight.value = targetEl.value.clientHeight
      }
      shouldRender.value = false
    }, props.unrenderDelay ?? 6000)
  }
}, { rootMargin: '600px', })

if (props.renderOnIdle) {
  onIdle(() => {
    shouldRender.value = true
    if (!props.unrender) {
      stop()
    }
  })
}

onBeforeUnmount(() => {
  if (renderTimer) {
    clearTimeout(renderTimer)

  }
  if (unrenderTimer) {
    clearTimeout(unrenderTimer)
  }
})
</script>
