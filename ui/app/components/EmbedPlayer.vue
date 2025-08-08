<style scoped>
.embed-content {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 80vh;
  width: 80vw;
}
</style>

<template>
  <div class="content">
    <h1 class="has-text-white">Not downloaded yet.</h1>
    <iframe class="embed-content" :src="url" frameborder="0" allowfullscreen />
  </div>
</template>

<script setup lang="ts">
import { disableOpacity, enableOpacity } from '~/utils'

defineProps({
  url: {
    type: String,
    required: true,
  }
})

const emitter = defineEmits(['closeModel'])

const handle_event = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') {
    return
  }
  emitter('closeModel')
}

onMounted(() => {
  document.addEventListener('keydown', handle_event)
  disableOpacity()
})

onBeforeUnmount(() => {
  enableOpacity()
  document.removeEventListener('keydown', handle_event)
})
</script>
