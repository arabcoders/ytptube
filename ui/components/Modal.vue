<template>
  <div>
    <div class="modal is-active">
      <div class="model-title" v-if="title" />
      <div class="modal-background" @click="closeModal"></div>
      <div class="modal-content" style="width:70vw;">
        <slot />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closeModal"></button>
    </div>
  </div>
</template>

<script setup>
const emitter = defineEmits(['close'])

const props = defineProps({
  title: {
    type: String,
    default: '',
    required: false,
  },
})

const closeModal = () => emitter('close')

const eventFunc = e => {
  if (e.key === 'Escape') {
    emitter('close')
  }
}

onMounted(() => window.addEventListener('keydown', eventFunc))
onUnmounted(() => window.removeEventListener('keydown', eventFunc))
</script>
