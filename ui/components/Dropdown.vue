<template>
  <div class="dropdown" :class="{ 'is-active': isOpen, 'drop-up': dropUp }" ref="dropdown">
    <div class="dropdown-trigger">
      <button class="button is-fullwidth is-justify-content-space-between" aria-haspopup="true"
        aria-controls="dropdown-menu" @click="toggle" :class="button_classes">
        <span class="icon" v-if="icons"><i :class="icons" /></span>
        <span>{{ label }}</span>
        <div class="is-pulled-right">
          <span class="icon"><i class="fas fa-angle-down" aria-hidden="true" /></span>
        </div>
      </button>
    </div>

    <div class="dropdown-menu" role="menu" id="dropdown-menu">
      <div class="dropdown-content" @click="handle_slot_click">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const emitter = defineEmits(['open_state'])
defineProps({
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
  }
})

const isOpen = ref(false)
const dropUp = ref(false)
const dropdown = useTemplateRef<HTMLDivElement>('dropdown')

const toggle = async () => {
  isOpen.value = !isOpen.value

  if (isOpen.value && dropdown.value) {
    await nextTick()
    const rect = dropdown.value.getBoundingClientRect()
    const menu = dropdown.value.querySelector('.dropdown-menu') as HTMLElement
    const menuHeight = menu?.offsetHeight || 0
    const spaceBelow = window.innerHeight - rect.bottom
    dropUp.value = spaceBelow < menuHeight + 24
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

  if (!dropdown.value.contains(target)) {
    isOpen.value = false
  }
}

watchEffect(() => emitter('open_state', isOpen.value))
onMounted(() => document.addEventListener('click', handle_event))
onBeforeUnmount(() => document.removeEventListener('click', handle_event))
</script>

<style scoped>
.dropdown {
  width: 100%;
  position: relative;
}

.dropdown-trigger {
  width: 100%;
}

.dropdown-menu {
  width: 100%;
  max-height: 300px;
  overflow-y: auto;
  z-index: 1000;
}

.dropdown-content {
  z-index: 99;
  width: 100%;
}

.dropdown.drop-up .dropdown-menu {
  bottom: 100%;
  top: auto;
  position: absolute;
}
</style>
