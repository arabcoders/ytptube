<style>
.user-hint {
  user-select: none;
  cursor: help;
  border-bottom: 1px dotted;
}
</style>
<template>
  <div class="columns mt-3 is-mobile">
    <div class="column is-8-mobile">
      <div class="has-text-left" v-if="app_version">
        © {{ Year }} - <a v-tooltip="'App Version: ' + app_version" href="https://github.com/ArabCoders/ytptube"
          target="_blank">YTPTube</a>
        - <a v-tooltip="'yt-dlp Version: ' + ytdlp_version" href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a>
      </div>
    </div>
    <div class="column is-4-mobile" v-if="started > 1">
      <div class="has-text-right">
        <span class="user-hint" v-tooltip="'App Started: ' + moment.unix(started).format('YYYY-M-DD H:mm Z')">
          {{ moment.unix(started).fromNow() }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue'
import moment from "moment";

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
  started: {
    type: Number,
    required: true,
  },
})

</script>
