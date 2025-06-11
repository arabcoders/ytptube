<template>
  <div class="dropdown" :class="{ 'is-active': isOpen }" ref="dropdown">
    <div class="dropdown-trigger">
      <button class="button is-fullwidth is-justify-content-space-between" aria-haspopup="true" aria-controls="dropdown-menu" @click="toggle">
        <span class="icon" v-if="icons"><i :class="icons" /></span>
        <span>{{ label }}</span>
        <div class="is-pulled-right">
          <span class="icon"><i class="fas fa-angle-down" aria-hidden="true" /></span>
        </div>
      </button>
    </div>

    <div class="dropdown-menu" role="menu" id="dropdown-menu">
      <div class="dropdown-content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  label: {
    type: String,
    default: 'Select'
  },
  icons: {
    type: String,
    default: null
  }
})

const isOpen = ref(false)
const dropdown = ref(null)

const toggle = () => isOpen.value = !isOpen.value

const handleClickOutside = (event) => {
  if (dropdown.value && !dropdown.value.contains(event.target)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.dropdown {
  width: 100%;
}

.dropdown-trigger {
  width: 100%;
}

.dropdown-menu {
  width: 100%;
  max-height: 300px;
  overflow-y: auto;
  position: absolute;
  z-index: 1000;
}

.dropdown-content {
  width: 100%;
}
</style>
