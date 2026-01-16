<template>
  <div class="popover-wrapper" ref="triggerElm" :tabindex="triggerTabIndex" @mouseenter="handleHoverEnter"
    @mouseleave="handleHoverLeave" @focusin="handleFocusIn" @focusout="handleFocusOut" @click="handleClick">
    <div class="popover-trigger">
      <slot name="trigger">
        <button type="button" class="button is-small is-rounded" aria-label="More information">
          <span class="icon is-small">
            <i class="fas fa-info-circle" aria-hidden="true" />
          </span>
        </button>
      </slot>
    </div>

    <Teleport to="body">
      <div v-if="isOpen" class="popover-portal" ref="portal">
        <div ref="popover" class="popover-card box" :class="placementClass" role="tooltip" :style="portalStyle"
          @mouseenter="handleHoverEnter" @mouseleave="handleHoverLeave">
          <button type="button" class="button is-bold is-fullwidth is-hidden-tablet" @click="closePopover">
            <span class="icon"><i class="fas fa-times" /></span>
            <span>Close</span>
          </button>

          <header v-if="hasTitleContent" class="popover-title mb-2">
            <slot name="title">
              <p class="title is-6 mb-1">{{ title }}</p>
            </slot>
          </header>

          <section v-if="hasBodyContent" class="popover-body">
            <slot>
              <p class="is-size-7 mb-0">{{ description }}</p>
            </slot>
          </section>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import type { PopoverProps } from '~/types/popover'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useSlots, watch, useTemplateRef } from 'vue'

const emit = defineEmits<{ (event: 'shown' | 'hidden'): void }>()

const props = withDefaults(defineProps<PopoverProps>(), {
  placement: 'top',
  trigger: 'hover',
  offset: 10,
  disabled: false,
  closeOnClickOutside: true,
  title: '',
  description: '',
  minWidth: 220,
  maxWidth: 340,
  maxHeight: 360,
  showDelay: 0
})

const slots = useSlots()
const isOpen = ref(false)
const triggerRef = useTemplateRef<HTMLElement>('triggerElm')
const popover = useTemplateRef<HTMLDivElement>('popover')
const portalStyle = ref<Record<string, string>>({})
const hoverTimeout = ref<number | null>(null)
const openTimeout = ref<number | null>(null)

const placementClass = computed(() => `is-${props.placement}`)
const triggerTabIndex = computed(() => props.trigger === 'hover' ? -1 : 0)

const hasTitleContent = computed(() => Boolean(props.title) || Boolean(slots.title))
const hasBodyContent = computed(() => Boolean(props.description) || Boolean(slots.default))

const clearHoverTimeout = () => {
  if (null !== hoverTimeout.value) {
    window.clearTimeout(hoverTimeout.value)
    hoverTimeout.value = null
  }
}

const clearOpenTimeout = () => {
  if (null !== openTimeout.value) {
    window.clearTimeout(openTimeout.value)
    openTimeout.value = null
  }
}

const scheduleClose = () => {
  clearHoverTimeout()
  clearOpenTimeout()
  hoverTimeout.value = window.setTimeout(() => {
    isOpen.value = false
  }, 120)
}

const openPopoverImmediate = async () => {
  if (props.disabled || isOpen.value) {
    return
  }

  isOpen.value = true
  await nextTick()
  updatePosition()
}

const openPopover = () => {
  clearOpenTimeout()
  if (props.showDelay && 0 < props.showDelay) {
    openTimeout.value = window.setTimeout(() => {
      openTimeout.value = null
      void openPopoverImmediate()
    }, props.showDelay)
    return
  }

  void openPopoverImmediate()
}

const closePopover = () => {
  if (!isOpen.value) {
    return
  }

  isOpen.value = false
}

const togglePopover = async () => {
  if (isOpen.value) {
    closePopover()
    return
  }

  openPopover()
}

const handleHoverEnter = () => {
  if ('hover' !== props.trigger || props.disabled) {
    return
  }

  clearHoverTimeout()
  openPopover()
}

const handleHoverLeave = () => {
  if ('hover' !== props.trigger) {
    return
  }

  clearOpenTimeout()
  scheduleClose()
}

const handleFocusIn = () => {
  if ('focus' !== props.trigger || props.disabled) {
    return
  }

  openPopover()
}

const handleFocusOut = () => {
  if ('focus' !== props.trigger) {
    return
  }

  clearOpenTimeout()
  scheduleClose()
}

const handleClick = (event: MouseEvent) => {
  if ('click' !== props.trigger || props.disabled) {
    return
  }

  event.stopPropagation()
  void togglePopover()
}

const handleDocumentClick = (event: MouseEvent) => {
  if (!props.closeOnClickOutside || 'click' !== props.trigger) {
    return
  }

  const target = event.target as Node | null
  const isInsideTrigger = Boolean(triggerRef.value && triggerRef.value.contains(target))
  const isInsidePopover = Boolean(popover.value && popover.value.contains(target))

  if (!isInsideTrigger && !isInsidePopover) {
    clearOpenTimeout()
    closePopover()
  }
}

const handleEscape = (event: KeyboardEvent) => {
  if ('Escape' === event.key && isOpen.value) {
    closePopover()
  }
}

const updatePosition = () => {
  if (!triggerRef.value || !popover.value) {
    return
  }

  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const constrainedMaxWidth = Math.min(props.maxWidth, viewportWidth * 0.96)

  popover.value.style.minWidth = `${props.minWidth}px`
  popover.value.style.maxWidth = `${constrainedMaxWidth}px`
  popover.value.style.maxHeight = `${props.maxHeight}px`
  popover.value.style.overflowY = 'auto'

  const triggerRect = triggerRef.value.getBoundingClientRect()
  const popoverRect = popover.value.getBoundingClientRect()
  const offset = props.offset

  let effectivePlacement = props.placement

  if ('top' === props.placement) {
    const spaceAbove = triggerRect.top - offset
    if (spaceAbove < popoverRect.height) {
      effectivePlacement = 'bottom'
    }
  } else if ('bottom' === props.placement) {
    const spaceBelow = viewportHeight - triggerRect.bottom - offset
    if (spaceBelow < popoverRect.height) {
      effectivePlacement = 'top'
    }
  } else if ('left' === props.placement) {
    const spaceLeft = triggerRect.left - offset
    if (spaceLeft < popoverRect.width) {
      effectivePlacement = 'right'
    }
  } else if ('right' === props.placement) {
    const spaceRight = viewportWidth - triggerRect.right - offset
    if (spaceRight < popoverRect.width) {
      effectivePlacement = 'left'
    }
  }

  let top = triggerRect.bottom + offset
  let left = triggerRect.left + (triggerRect.width - popoverRect.width) / 2

  if ('top' === effectivePlacement) {
    top = triggerRect.top - popoverRect.height - offset
  } else if ('left' === effectivePlacement) {
    top = triggerRect.top + (triggerRect.height - popoverRect.height) / 2
    left = triggerRect.left - popoverRect.width - offset
  } else if ('right' === effectivePlacement) {
    top = triggerRect.top + (triggerRect.height - popoverRect.height) / 2
    left = triggerRect.right + offset
  }

  const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)
  const maxLeft = viewportWidth - popoverRect.width - 8
  const maxTop = viewportHeight - popoverRect.height - 8

  const clampedTop = clamp(Math.round(top), 8, maxTop)
  const clampedLeft = clamp(Math.round(left), 8, maxLeft)

  portalStyle.value = {
    position: 'fixed',
    top: `${clampedTop}px`,
    left: `${clampedLeft}px`,
    minWidth: `${props.minWidth}px`,
    maxWidth: `${constrainedMaxWidth}px`,
    maxHeight: `${props.maxHeight}px`,
    overflowY: 'auto'
  }
}

watch(isOpen, async (value) => {
  if (value) {
    await nextTick()
    updatePosition()
    await nextTick()
    emit('shown')
    return
  }

  emit('hidden')
})

onMounted(() => {
  document.addEventListener('click', handleDocumentClick, true)
  document.addEventListener('keydown', handleEscape)
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick, true)
  document.removeEventListener('keydown', handleEscape)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
  clearHoverTimeout()
  clearOpenTimeout()
})
</script>

<style>
.popover-wrapper {
  position: relative;
  display: inline-flex;
  max-width: 100%;
  min-width: 0;
}

.popover-trigger {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-width: 0;
}

.popover-trigger>* {
  max-width: 100%;
  min-width: 0;
}

.popover-portal {
  position: fixed;
  z-index: 1050;
  inset: 0;
  pointer-events: none;
}

.popover-card {
  position: fixed;
  background-color: var(--bulma-scheme-main, #fff);
  color: var(--bulma-text, #363636);
  border: 1px solid var(--bulma-border, rgba(0, 0, 0, 0.08));
  box-shadow: var(--bulma-shadow, 0 0.5em 1em -0.125em rgba(10, 10, 10, 0.1), 0 0px 0 1px rgba(10, 10, 10, 0.02));
  border-radius: var(--bulma-radius-large, 0.5rem);
  pointer-events: auto;
  padding: 0.9rem 1rem;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.popover-title {
  color: var(--bulma-text-strong, #1f1f1f);
}

.popover-card::after {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  background: inherit;
  border-left: inherit;
  border-top: inherit;
  transform: rotate(45deg);
}

.popover-card.is-top::after {
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
}

.popover-card.is-bottom::after {
  top: -6px;
  left: 50%;
  transform: translateX(-50%) rotate(45deg);
}

.popover-card.is-left::after {
  right: -6px;
  top: 50%;
  transform: translateY(-50%) rotate(45deg);
}

.popover-card.is-right::after {
  left: -6px;
  top: 50%;
  transform: translateY(-50%) rotate(45deg);
}
</style>
