<template>
  <div>
    <div class="modal is-active">
      <div class="model-title" v-if="title" />
      <div class="modal-background" @click="emitter('close')"></div>
      <div class="modal-content" style="width:70vw;">
        <slot />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="emitter('close')"></button>
    </div>
  </div>
</template>

<script setup lang="ts">
const emitter = defineEmits(['close'])

defineProps({
  title: {
    type: String,
    default: '',
    required: false,
  },
})

const handle_event = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') {
    return
  }
  emitter('close')
}

onMounted(() => document.addEventListener('keydown', handle_event))
onBeforeUnmount(() => document.removeEventListener('keydown', handle_event))
</script>
