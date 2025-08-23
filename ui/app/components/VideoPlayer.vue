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
import { disableOpacity, enableOpacity } from '~/utils'

import type { StoreItem } from '~/types/store'
import type { file_info, video_source_element, video_track_element } from '~/types/video'

const config = useConfigStore()
const toast = useNotification()

const props = defineProps({
  item: {
    type: Object as () => StoreItem,
    default: () => ({}),
  }
})

const emitter = defineEmits(['closeModel'])

const video = useTemplateRef<HTMLVideoElement>('video')
const tracks = ref<Array<video_track_element>>([])
const sources = ref<Array<video_source_element>>([])

const thumbnail = ref('/images/placeholder.png')
const artist = ref('')
const title = ref('')
const isAudio = ref(false)
const hasVideoStream = ref(false)
const volume = useStorage('player_volume', 1)
const notFirefox = !navigator.userAgent.toLowerCase().includes('firefox')
const infoLoaded = ref(false)
const destroyed = ref(false)
const isApple = /(iPhone|iPod|iPad).*AppleWebKit/i.test(navigator.userAgent)
const havePoster = ref(false)

let unbindMediaSessionListeners: null | (() => void) = null
let hls: Hls | null = null
let detachDecodeGuard: null | (() => void) = null

const handle_event = (e: KeyboardEvent) => {
  if ('Escape' !== e.key) {
    return
  }
  emitter('closeModel')
}

const bindMediaSessionListeners = (el: HTMLVideoElement) => {
  const onLoadedMetadata = (e: Event) => updateMediaSessionPosition(e.currentTarget)
  const onTimeUpdate = (e: Event) => updateMediaSessionPosition(e.currentTarget)
  const onRateChange = (e: Event) => updateMediaSessionPosition(e.currentTarget)
  const onSeeked = (e: Event) => updateMediaSessionPosition(e.currentTarget)
  const onPause = async (e: Event) => {
    const target = (e.currentTarget as HTMLVideoElement) ?? null
    if (!target || destroyed.value) {
      return
    }
    const dataUrl = await captureFrame(target)
    if (dataUrl) {
      thumbnail.value = dataUrl
      havePoster.value = true
      applyMediaSessionMetadata()
    }
  }

  el.addEventListener('loadedmetadata', onLoadedMetadata)
  el.addEventListener('timeupdate', onTimeUpdate)
  el.addEventListener('ratechange', onRateChange)
  el.addEventListener('seeked', onSeeked)
  el.addEventListener('pause', onPause)

  return () => {
    el.removeEventListener('loadedmetadata', onLoadedMetadata)
    el.removeEventListener('timeupdate', onTimeUpdate)
    el.removeEventListener('ratechange', onRateChange)
    el.removeEventListener('seeked', onSeeked)
    el.removeEventListener('pause', onPause)
  }
}

const updateMediaSessionPosition = (target: EventTarget | null) => {
  if (false === ('mediaSession' in navigator)) {
    return
  }
  const el = (target as HTMLVideoElement) ?? null
  if (!el || destroyed.value) {
    return
  }
  const d = el.duration
  if (false === Number.isFinite(d) || 0 >= d) {
    return
  }
  try {
    navigator.mediaSession.setPositionState({
      duration: d,
      playbackRate: el.playbackRate,
      position: el.currentTime,
    })
  } catch { }
}

const volume_change_handler = () => {
  const el = video.value
  if (!el) {
    return
  }
  volume.value = el.volume
  updateMediaSessionPosition(el)
}

/**
 * Unified frame capture helper (merges previous captureCurrentFrame/captureFirstFramePoster logic).
 * Returns a JPEG data URL or '' on failure.
 */
const captureFrame = async (el: HTMLVideoElement): Promise<string> => {
  if (!el || destroyed.value) {
    return ''
  }
  if (0 === el.videoWidth || 0 === el.videoHeight) {
    return ''
  }

  const w = el.videoWidth
  const h = el.videoHeight

  try {
    if ('OffscreenCanvas' in window) {
      const c = new (window as any).OffscreenCanvas(w, h)
      const ctx = c.getContext('2d')
      if (!ctx) { return '' }
      ctx.drawImage(el, 0, 0, w, h)
      const blob = await c.convertToBlob({ type: 'image/jpeg', quality: 0.86 })
      return await new Promise<string>(r => {
        const fr = new FileReader()
        fr.onload = () => r(String(fr.result))
        fr.readAsDataURL(blob)
      })
    } else {
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      const ctx = c.getContext('2d')
      if (!ctx) { return '' }
      ctx.drawImage(el, 0, 0, w, h)
      return c.toDataURL('image/jpeg', 0.86)
    }
  } catch {
    return ''
  }
}

const captureFirstFramePoster = async (el: HTMLVideoElement): Promise<void> => {
  if (!el || destroyed.value) {
    return
  }
  if (havePoster.value) {
    return
  }
  if (0 === el.videoWidth || 0 === el.videoHeight) {
    return
  }

  const dataUrl = await captureFrame(el)
  if (!dataUrl) {
    return
  }

  thumbnail.value = dataUrl
  havePoster.value = true
  applyMediaSessionMetadata()
}

onMounted(async () => {
  disableOpacity()
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
    havePoster.value = true
  } else {
    if (response.sidecar?.image?.[0]?.file) {
      thumbnail.value = makeDownload(config, { 'filename': response.sidecar.image[0].file })
      havePoster.value = true
    }
  }

  hasVideoStream.value = Array.isArray(response.ffprobe?.video)
    && response.ffprobe.video.some(s => 'video' === s.codec_type)

  if (!props.item.extras?.is_video && props.item.extras?.is_audio) {
    isAudio.value = true
  } else {
    if (false === hasVideoStream.value) {
      isAudio.value = true
    }
  }

  if (isApple) {
    const allowedCodec = response.mimetype && response.mimetype.includes('video/mp4')
    const src = makeDownload(config, props.item, allowedCodec ? 'api/download' : 'm3u8')
    sources.value.push({
      src,
      type: allowedCodec ? response.mimetype : 'application/x-mpegURL',
      onerror: (e: Event) => src_error(),
    })
  } else {
    const src = makeDownload(config, props.item, 'api/download')
    sources.value.push({
      src,
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
  } else {
    if (response?.title) {
      title.value = response.title
    } else {
      if (response.ffprobe?.metadata?.tags?.title) {
        title.value = response.ffprobe.metadata.tags.title
      }
    }
  }

  response.sidecar?.subtitle?.forEach((cap, _) => {
    tracks.value.push({
      kind: 'captions',
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

  if (video.value) {
    unbindMediaSessionListeners = bindMediaSessionListeners(video.value)
  }

  document.addEventListener('keydown', handle_event)
})

const applyMediaSessionMetadata = () => {
  if (false === ('mediaSession' in navigator)) {
    return
  }
  const meta: MediaMetadataInit = { title: title.value }
  if (artist.value) {
    meta.artist = artist.value
  }
  if (thumbnail.value) {
    meta.artwork = [{ src: thumbnail.value, sizes: '1920x1080', type: 'image/jpeg' }]
  }
  try { navigator.mediaSession.metadata = new MediaMetadata(meta) } catch { }
}

onUpdated(() => prepareVideoPlayer())

onBeforeUnmount(() => {
  enableOpacity()
  if (hls) {
    hls.destroy()
  }

  document.removeEventListener('keydown', handle_event)

  if (unbindMediaSessionListeners) {
    unbindMediaSessionListeners()
    unbindMediaSessionListeners = null
  }

  if (title.value) {
    window.document.title = 'YTPTube'
  }

  if (!video.value) {
    return
  }
  destroyed.value = true

  try {
    video.value.pause()
    video.value.querySelectorAll('source').forEach(source => source.removeAttribute('src'))
    video.value.removeEventListener('volumechange', volume_change_handler)
    if (detachDecodeGuard) {
      detachDecodeGuard()
      detachDecodeGuard = null
    }
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

  applyMediaSessionMetadata()

  if (title.value) {
    window.document.title = `YTPTube - Playing: ${title.value}`
  }

  if (!video.value) {
    return
  }

  video.value.volume = volume.value
  video.value.addEventListener('volumechange', volume_change_handler)

  if (detachDecodeGuard) {
    detachDecodeGuard()
    detachDecodeGuard = null
  }

  if (hasVideoStream.value) {
    if ('requestVideoFrameCallback' in video.value) {
      ; (video.value as any).requestVideoFrameCallback(() => captureFirstFramePoster(video.value!))
    } else {
      const tryOnce = () => captureFirstFramePoster(video.value!)
        ; (video.value as any).addEventListener('loadeddata', tryOnce, { once: true })
    }

    detachDecodeGuard = attachDecodeFailGuard(video.value, () => src_error())
  }
}

function attachDecodeFailGuard(el: HTMLVideoElement, onFail: () => void): () => void {
  let rvfcId: number | null = null
  let timer: number | null = null
  let armed = false
  let done = false

  const clearAll = () => {
    if (null !== timer) {
      clearTimeout(timer)
      timer = null
    }
    if (null !== rvfcId && 'cancelVideoFrameCallback' in el) {
      ; (el as any).cancelVideoFrameCallback(rvfcId)
      rvfcId = null
    }
    el.removeEventListener('loadeddata', onLoadedData)
    el.removeEventListener('error', onError)
    el.removeEventListener('emptied', onError)
  }

  const ok = () => {
    if (done) return
    done = true
    clearAll()
  }

  const fail = () => {
    if (done) return
    done = true
    clearAll()
    onFail()
  }

  const decodedFrames = (): number => {
    try {
      const q = 'getVideoPlaybackQuality' in el ? (el as any).getVideoPlaybackQuality() : null
      if (q && 'totalVideoFrames' in q) {
        return Number(q.totalVideoFrames || 0)
      }
      const anyEl = el as any
      if ('webkitDecodedFrameCount' in anyEl) {
        return Number(anyEl.webkitDecodedFrameCount || 0)
      }
    } catch { }
    return 0
  }

  const armCheck = () => {
    if (armed || done) return
    armed = true

    if ('requestVideoFrameCallback' in el) {
      rvfcId = (el as any).requestVideoFrameCallback(() => ok())
      timer = window.setTimeout(() => fail(), 1000)
      return
    }

    timer = window.setTimeout(() => {
      if (0 === (el as any).videoWidth || 0 === (el as any).videoHeight || 0 === decodedFrames()) {
        fail()
      } else {
        ok()
      }
    }, 800)
  }

  const onLoadedData = () => armCheck()
  const onError = () => fail()

  el.addEventListener('loadeddata', onLoadedData, { once: true })
  el.addEventListener('error', onError)
  el.addEventListener('emptied', onError)

  if (4 <= el.readyState || 2 <= el.readyState) {
    queueMicrotask(armCheck)
  }

  return clearAll
}

const src_error = async () => {
  if (hls) {
    return
  }
  await nextTick()
  if (destroyed.value) {
    return
  }

  console.warn('Source failed to load, attempting HLS fallback...')
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

  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    applyMediaSessionMetadata()
  })

  hls.on(Hls.Events.LEVEL_LOADED, () => {
    if (video.value) {
      if ('requestVideoFrameCallback' in video.value) {
        ; (video.value as any).requestVideoFrameCallback(() => captureFirstFramePoster(video.value!))
      } else {
        const once = () => captureFirstFramePoster(video.value!)
          ; (video.value as any).addEventListener('loadeddata', once, { once: true })
      }
    }
  })

  hls.loadSource(link)
  hls.attachMedia(video.value)
}
</script>
