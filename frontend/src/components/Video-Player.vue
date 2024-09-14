<style>
:root {
  --plyr-captions-background: rgba(0, 0, 0, 0.6);
  --plyr-captions-text-color: #f3db4d;
  --webkit-text-track-display: none;
}

.plyr__caption {
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);
  font-size: 140%;
  font-weight: bold;
}

.plyr--full-ui ::-webkit-media-text-track-container {
  display: var(--webkit-text-track-display);
}
</style>

<template>
  <video ref="video" :poster="previewImageLink" :controls="isControls" :title="title" playsinline>
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
let player = null;
let hls = null;

const eventFunc = e => {
  if (e.key === 'Escape') {
    emitter('closeModel')
  }
}

onMounted(() => {
  if (/(iPhone|iPod|iPad).*AppleWebKit/i.test(navigator.userAgent)) {
    document.documentElement.style.setProperty('--webkit-text-track-display', 'block');
  }

  prepareVideoPlayer()
  window.addEventListener('keydown', eventFunc)
})

onUpdated(() => prepareVideoPlayer())

onUnmounted(() => {
  if (player) {
    player.destroy()
  }
  if (hls) {
    hls.destroy()
  }
  window.removeEventListener('keydown', eventFunc)
})

const prepareVideoPlayer = () => {
  player = new Plyr(video.value, {
    debug: false,
    clickToPlay: true,
    keyboard: { focused: true, global: true },
    controls: [
      'play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'
    ],
    fullscreen: {
      enabled: true,
      fallback: true,
      iosNative: true,
    },
    storage: {
      enabled: true,
      key: 'plyr'
    },
    mediaMetadata: {
      title: props.title
    },
    captions: {
      update: true,
    }
  });

  hls = new Hls({
    debug: false,
    enableWorker: true,
    lowLatencyMode: true,
    backBufferLength: 90,
    fragLoadingTimeOut: 200000,
  });

  hls.loadSource(props.link)

  if (video.value) {
    hls.attachMedia(video.value)
  }
}
</script>
