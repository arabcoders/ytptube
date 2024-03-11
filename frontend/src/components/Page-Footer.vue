<template>
  <div class="columns is-multiline mt-3">
    <div class="column has-text-left">
      © {{ Year }} - <a href="https://github.com/ArabCoders/ytptube" target="_blank">YTPTube</a>@{{ app_version }}
      <span class="is-hidden-mobile">
        - <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a>@{{ ytdlp_version }}
      </span>
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
  ytdlp_version: {
    type: String,
    required: true,
  },
})

</script>
