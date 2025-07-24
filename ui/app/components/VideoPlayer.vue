<style scoped>
.player {
  display: flex;
  justify-content: center;
  align-items: center;
  height: auto;
  max-height: 80vh;
  max-width: 80vw;
}
</style>
<template>
  <div v-if="infoLoaded">
    <video class="player" ref="video" :poster="uri(thumbnail)" :title="title" playsinline controls
      crossorigin="anonymous" preload="auto" autoplay>
      <source v-for="source in sources" :key="source.src" :src="source.src" @error="source.onerror"
        :type="source.type" />
      <track v-for="(track, i) in tracks" :key="track.file" :kind="track.kind" :label="track.label"
        :srclang="track.lang" :src="track.file" :default="notFirefox && 0 === i" />
    </video>
  </div>
  <div style="text-align: center;" v-else>
    <div class="icon">
      <i class="fa-solid fa-spinner fa-spin fa-4x" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import Hls from 'hls.js'

type video_track_element = {
  file: string,
  kind: string,
  label: string,
  lang: string,
}

type video_source_element = {
  src: string,
  type: string,
  onerror: (e: Event) => void,
}

type file_info = {
  title: string,
  mimetype: string,
  sidecar?: {
    image?: Array<{ file: string }>,
    text?: Array<{ file: string }>,
    subtitle?: Array<{ name: string, lang: string, file: string }>,
  }
  error?: string,
}

const config = useConfigStore()
const toast = useNotification()

const props = defineProps({
  item: {
    type: Object,
    default: () => ({}),
  }
})

const emitter = defineEmits(['closeModel'])

const video = useTemplateRef<HTMLMediaElement>('video')
const tracks = ref<Array<video_track_element>>([])
const sources = ref<Array<video_source_element>>([])

const thumbnail = ref('/images/placeholder.png')
const artist = ref('')
const title = ref('')
const isAudio = ref(false)
const isApple = /(iPhone|iPod|iPad).*AppleWebKit/i.test(navigator.userAgent)
const volume = useStorage('player_volume', 1)
const notFirefox = !navigator.userAgent.toLowerCase().includes('firefox')
const infoLoaded = ref(false)
const destroyed = ref(false)

let hls: Hls | null = null

const handle_event = (e: KeyboardEvent) => {
  if (e.key !== 'Escape') {
    return
  }
  emitter('closeModel')
}

const volume_change_handler = () => {
  if (!video.value) {
    return
  }

  volume.value = video.value.volume

  if (false === ("mediaSession" in navigator)) {
    return
  }

  navigator.mediaSession.setPositionState({
    duration: video.value.duration,
    playbackRate: video.value.playbackRate,
    position: video.value.currentTime,
  })
}

onMounted(async () => {
  const req = await request(makeDownload(config, props.item, 'api/file/info'))

  const response: file_info = await req.json()

  if (!req.ok) {
    toast.error(`Failed to fetch video info. ${response?.error}`)
    emitter('closeModel')
    return
  }

  await nextTick()

  if (props.item.extras?.thumbnail) {
    thumbnail.value = '/api/thumbnail?url=' + encodePath(props.item.extras.thumbnail)
  } else {
    if (response?.sidecar?.image && response.sidecar.image.length > 0) {
      thumbnail.value = makeDownload(config, { "filename": response.sidecar.image[0]['file'] })
    }
  }

  // -- check if mimetype is video/mp4 and device is apple
  // -- as always apple, apple like to be snowflakes.
  if (isApple) {
    const allowedCodec = response.mimetype && response.mimetype.includes('video/mp4')
    sources.value.push({
      src: makeDownload(config, props.item, allowedCodec ? 'api/download' : 'm3u8'),
      type: allowedCodec ? response.mimetype : 'application/x-mpegURL',
      onerror: (e: Event) => src_error(),
    })
  } else {
    sources.value.push({
      src: makeDownload(config, props.item, 'api/download'),
      type: response.mimetype,
      onerror: e => src_error(),
    })
  }

  if (props.item.extras?.channel) {
    artist.value = props.item.extras.channel
  }

  if (!artist.value && props.item.extras?.uploader) {
    artist.value = props.item.extras.uploader
  }

  if (props.item?.title) {
    title.value = props.item.title
  }
  else {
    if (response?.title) {
      title.value = response.title
    }
  }

  if (!props.item.extras?.is_video && props.item.extras?.is_audio) {
    isAudio.value = true
  }

  response.sidecar?.subtitle?.forEach((cap, _) => {
    tracks.value.push({
      kind: "captions",
      label: cap.name,
      lang: cap.lang,
      file: `${makeDownload(config, { filename: cap.file }, 'api/player/subtitle')}.vtt`
    })
  })

  if (isApple) {
    document.documentElement.style.setProperty('--webkit-text-track-display', 'block')
  }

  infoLoaded.value = true
  await nextTick()

  prepareVideoPlayer()
  document.addEventListener('keydown', handle_event)
})

onUpdated(() => prepareVideoPlayer())

onBeforeUnmount(() => {
  if (hls) {
    hls.destroy()
  }

  document.removeEventListener('keydown', handle_event)

  if (title.value) {
    window.document.title = 'YTPTube'
  }

  if (!video.value) {
    return
  }
  destroyed.value = true

  try {
    video.value.pause()
    video.value.querySelectorAll("source").forEach(source => source.removeAttribute("src"))
    video.value.removeEventListener('volumechange', volume_change_handler)
    video.value.load()
  }
  catch (e) {
    console.error(e)
  }
})

const prepareVideoPlayer = () => {
  if (!infoLoaded.value) {
    return
  }

  if (false === ("mediaSession" in navigator)) {
    return
  }

  let mediaMetadata: MediaMetadataInit = { title: title.value }

  if (thumbnail.value) {
    mediaMetadata.artwork = [{ src: thumbnail.value, sizes: '1920x1080', type: 'image/jpeg' }]
  }

  if (artist.value) {
    mediaMetadata.artist = artist.value
  }

  navigator.mediaSession.metadata = new MediaMetadata(mediaMetadata)
  if (title.value) {
    window.document.title = `YTPTube - Playing: ${title.value}`
  }

  if (!video.value) {
    return
  }

  video.value.volume = volume.value
  video.value.addEventListener('volumechange', volume_change_handler)
}

const src_error = async () => {
  if (hls) {
    return
  }
  await nextTick()
  if (destroyed.value) {
    return
  }
  console.warn('Direct play failed, trying HLS.')
  attach_hls(makeDownload(config, props.item, 'm3u8'))
}

const attach_hls = (link: string) => {
  if (!video.value) {
    return
  }

  hls = new Hls({
    debug: false,
    enableWorker: true,
    lowLatencyMode: true,
    backBufferLength: 120,
    fragLoadingTimeOut: 200000,
  })

  hls.loadSource(link)
  hls.attachMedia(video.value)
}
</script>
