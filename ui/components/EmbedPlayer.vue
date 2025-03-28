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

<script setup>
import { onMounted, onUnmounted } from 'vue'

const props = defineProps({
  url: {
    type: String,
    required: true,
  }
})

const emitter = defineEmits(['closeModel'])

const eventFunc = e => {
  if (e.key === 'Escape') {
    emitter('closeModel')
  }
}

onMounted(async () => window.addEventListener('keydown', eventFunc))
onUnmounted(() => window.removeEventListener('keydown', eventFunc))
</script>
