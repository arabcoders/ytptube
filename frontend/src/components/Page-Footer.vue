<template>
  <div class="columns is-multiline mt-3">
    <div class="column has-text-left">
      {{ Year }} © YTPtube - {{ app_version }}
    </div>
    <div class="column has-text-right">
      <a href="https://github.com/ArabCoders/ytptube" target="_blank">
        Github
      </a>
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
