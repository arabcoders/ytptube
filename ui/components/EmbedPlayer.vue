<template>
  <div class="content">
    <h1 class="has-text-white">Not downloaded yet.</h1>
    <figure class="image is-16by9">
      <iframe class="has-ratio" :src="url" frameborder="0" allowfullscreen />
    </figure>
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
