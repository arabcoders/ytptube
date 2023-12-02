<template>
  <div class="columns is-multiline mt-3">
    <div class="column has-text-left">
      © {{ Year }} <a href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</a> - {{ app_version }}
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'

const Year = new Date().getFullYear()

defineProps({
  app_version: {
    type: String,
    required: true,
  },
})

</script>
