<template>
  <video ref="video" :poster="previewImageLink" :controls="isControls" :title="title">
    <source :src="link" type="application/x-mpegURL" />
  </video>
</template>

<script setup>
import { onMounted, onUpdated, ref, defineProps, defineEmits, onUnmounted } from 'vue'
import Hls from 'hls.js'
import Plyr from 'plyr'
import 'plyr/dist/plyr.css'

const props = defineProps({
  previewImageLink: {
    type: String,
    default: ''
  },
  link: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: ''
  },
  isControls: {
    type: Boolean,
    default: true
  },
})

const emitter = defineEmits(['closeModel'])

const video = ref(null)
const player = ref(null)
const hls = ref(null)
let eventHandler = null

onMounted(() => {
  prepareVideoPlayer()
  eventHandler = window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      emitter('closeModel')
    }
  })
})

onUpdated(() => {
  prepareVideoPlayer()
})

onUnmounted(() => {
  player.value.destroy()
  hls.value.destroy()
  window.removeEventListener('keydown', eventHandler)
})

const prepareVideoPlayer = () => {
  player.value = new Plyr(video.value, {
    clickToPlay: true,
    keyboard: { focused: true, global: true },
    controls: [
      'play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'pip', 'airplay', 'fullscreen'
    ],
    fullscreen: {
      enabled: true,
      fallback: true,
      iosNative: true,
    },
    storage: {
      enabled: true,
      key: 'plyr_volume'
    },
    mediaMetadata: {
      title: props.title.value
    }
  });

  hls.value = new Hls({
    debug: false,
    enableWorker: true,
    lowLatencyMode: true,
    backBufferLength: 90,
    fragLoadingTimeOut: 200000,
  });

  hls.value.loadSource(props.link)

  if (video.value) {
    hls.value.attachMedia(video.value)
  }
}

</script>

<style></style>
