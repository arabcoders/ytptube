<template>
  <div class="dropdown" :class="{ 'is-active': isOpen, 'drop-up': dropUp }" ref="dropdown">
    <div class="dropdown-trigger">
      <button class="button is-fullwidth is-justify-content-space-between" aria-haspopup="true" type="button"
        aria-controls="dropdown-menu" @click="toggle" :class="button_classes">
        <span class="icon" v-if="icons"><i :class="icons" /></span>
        <span :class="{ 'is-sr-only': hideLabel }">{{ label }}</span>
        <div class="is-pulled-right">
          <span class="icon"><i class="fas fa-angle-down" aria-hidden="true" /></span>
        </div>
      </button>
    </div>

    <Teleport to="body">
      <div v-if="isOpen" class="dropdown is-active dropdown-portal" ref="menu" :style="menuStyle">
        <div class="dropdown-menu" role="menu">
          <div class="dropdown-content" @click="handle_slot_click">
            <template v-if="hideLabel">
              <div class="dropdown-label">
                <span class="icon-text">
                  <span class="icon" v-if="icons"><i :class="icons" /></span>
                  <span>{{ label }}</span>
                </span>
              </div>
              <div class="dropdown-divider"></div>
            </template>
            <slot />
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watchEffect, useTemplateRef } from 'vue'

const emitter = defineEmits(['open_state'])
const props = defineProps({
  label: {
    type: String,
    default: 'Select'
  },
  icons: {
    type: String,
    default: null
  },
  button_classes: {
    type: String,
    default: ''
  },
  hide_label_on_mobile: {
    type: Boolean,
    default: false
  }
})

const isOpen = ref(false)
const dropUp = ref(false)
const dropdown = useTemplateRef<HTMLDivElement>('dropdown')
const menu = useTemplateRef<HTMLDivElement>('menu')
const menuStyle = ref<Record<string, string>>({})
const isMobile = useMediaQuery({ maxWidth: 1024 })

const hideLabel = computed(() => isMobile.value && props.hide_label_on_mobile)

const updatePosition = () => {
  if (!dropdown.value || !isOpen.value) {
    return
  }

  const triggerRect = dropdown.value.getBoundingClientRect()
  const menuHeight = menu.value?.offsetHeight || 300
  const spaceBelow = window.innerHeight - triggerRect.bottom
  const spaceAbove = triggerRect.top

  // Determine if dropdown should appear above or below
  const shouldDropUp = spaceBelow < menuHeight + 24 && spaceAbove > spaceBelow
  dropUp.value = shouldDropUp

  // Calculate position
  const left = triggerRect.left
  const width = triggerRect.width

  if (shouldDropUp) {
    // Position above the trigger
    const bottom = window.innerHeight - triggerRect.top
    menuStyle.value = {
      position: 'fixed',
      left: `${left}px`,
      bottom: `${bottom}px`,
      width: `${width}px`,
      top: 'auto'
    }
  } else {
    // Position below the trigger
    const top = triggerRect.bottom
    menuStyle.value = {
      position: 'fixed',
      left: `${left}px`,
      top: `${top}px`,
      width: `${width}px`,
      bottom: 'auto'
    }
  }
}

const toggle = async () => {
  isOpen.value = !isOpen.value

  if (isOpen.value) {
    await nextTick()
    updatePosition()
  }
}

const handle_slot_click = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (target.closest('.dropdown-item')) {
    isOpen.value = false
  }
}

const handle_event = (event: MouseEvent) => {
  if (!dropdown.value) {
    return
  }

  const target = event.target as HTMLElement

  if (!dropdown.value.contains(target) && !menu.value?.contains(target)) {
    isOpen.value = false
  }
}

const handleScroll = () => {
  if (isOpen.value) {
    updatePosition()
  }
}

const handleResize = () => {
  if (isOpen.value) {
    updatePosition()
  }
}

watchEffect(() => emitter('open_state', isOpen.value))

onMounted(() => {
  document.addEventListener('click', handle_event)
  window.addEventListener('scroll', handleScroll, true) // Use capture to catch all scroll events
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handle_event)
  window.removeEventListener('scroll', handleScroll, true)
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.dropdown {
  width: 100%;
  position: relative;
}

.dropdown-trigger {
  width: 100%;
}
</style>

<style>
.dropdown.dropdown-portal {
  position: fixed;
  z-index: 1000;
}

.dropdown.dropdown-portal .dropdown-menu {
  display: block !important;
  /* Override Bulma's display: none */
  position: static;
  /* Don't use absolute positioning inside fixed container */
  max-height: 300px;
  overflow-y: auto;
  padding-top: 4px;
}

.dropdown.dropdown-portal .dropdown-content {
  background-color: var(--bulma-dropdown-content-background-color, var(--bulma-scheme-main, #fff));
  border-radius: var(--bulma-dropdown-content-radius, var(--bulma-radius, 4px));
  box-shadow: var(--bulma-dropdown-content-shadow, var(--bulma-shadow, 0 0.5em 1em -0.125em rgba(10, 10, 10, 0.1), 0 0px 0 1px rgba(10, 10, 10, 0.02)));
  padding-top: var(--bulma-dropdown-content-padding-top, 0.5rem);
  padding-bottom: var(--bulma-dropdown-content-padding-bottom, 0.5rem);
}

.dropdown-label {
  font-weight: 600;
  padding: 0.5rem 0.75rem;
  color: var(--bulma-dropdown-label-color, var(--bulma-text-color, #4a4a4a));
}
</style>
