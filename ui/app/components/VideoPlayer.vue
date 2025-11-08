<style scoped>
.player {
  display: flex;
  justify-content: center;
  align-items: center;
  height: auto;
  max-height: 80vh;
  max-width: 80vw;
  position: relative;
}

.keyboard-help {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.95);
  color: var(--bulma-white);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  border-radius: 4px;
  overflow-y: auto;
  padding: 2rem;
}

.shortcuts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
  max-width: 1000px;
  width: 100%;
}

.shortcut-section {
  text-align: left;
}

.shortcut-section h3 {
  color: var(--bulma-primary);
  margin-bottom: 1rem;
  font-size: 1.1rem;
}

.shortcut-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  font-size: 0.95rem;
}

.shortcut-item span:first-child {
  flex: 1;
}

.shortcut-item .kbd-group {
  display: flex;
  gap: 0.5rem;
  margin-left: auto;
}

.shortcut-key {
  background: rgba(255, 255, 255, 0.1);
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  margin-right: 1rem;
  font-family: monospace;
  font-weight: bold;
  min-width: 60px;
  text-align: center;
}

.help-close-hint {
  margin-top: 2rem;
  font-size: 0.9rem;
  color: var(--bulma-light);
}
</style>

<template>
  <div v-if="infoLoaded">
    <div style="position: relative;">
      <video class="player" ref="video" :poster="uri(thumbnail)" playsinline controls crossorigin="anonymous"
        preload="auto" autoplay>
        <source v-for="source in sources" :key="source.src" :src="source.src" @error="source.onerror"
          :type="source.type" />
        <track v-for="(track, i) in tracks" :key="track.file" :kind="track.kind" :label="track.label"
          :srclang="track.lang" :src="track.file" :default="notFirefox && 0 === i" />
      </video>

      <div class="is-flex is-justify-content-space-between">
        <div>
          <span v-if="infoLoaded && !usingHls && hasVideoStream" class="is-hidden-mobile has-text-info is-pointer"
            @click.prevent="forceSwitchToHls">
            <span class="icon"><i class="fa-solid fa-arrows-rotate" /></span>
            <span>Trouble playing? switch to HLS stream.</span>
          </span>
        </div>
        <div>
          <span class="is-hidden-mobile has-text-grey-lighter is-pointer" @click="showHelp = !showHelp">
            <span class="icon"><i class="fa-solid fa-question" /></span>
            <span>Show keyboard shortcuts with <kbd>?</kbd> or <kbd>/</kbd></span>
          </span>
        </div>
      </div>

      <div v-if="showHelp" class="keyboard-help" @click.self="showHelp = false">
        <h2 style="margin-bottom: 1.5rem;">Keyboard Shortcuts</h2>

        <div class="shortcuts-grid">
          <div class="shortcut-section">
            <h3>Playback Control</h3>
            <div class="shortcut-item">
              <span>Play/Pause</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">SPACE</kbd>
                <kbd class="shortcut-key">K</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Rewind 10s</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">J</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Forward 10s</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">L</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Mute/Unmute</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">M</kbd>
              </div>
            </div>
          </div>

          <div class="shortcut-section">
            <h3>Seeking</h3>
            <div class="shortcut-item">
              <span>Seek Back 5s</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">←</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Seek Forward 5s</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">→</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Jump to Start</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">HOME</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Jump to End</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">END</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Jump to %</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">0-9</kbd>
              </div>
            </div>
          </div>

          <div class="shortcut-section">
            <h3>Volume & Speed</h3>
            <div class="shortcut-item">
              <span>Increase Volume</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">↑</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Decrease Volume</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">↓</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Increase Speed</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">'</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Decrease Speed</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">;</kbd>
              </div>
            </div>
          </div>

          <div class="shortcut-section">
            <h3>Display & Other</h3>
            <div class="shortcut-item">
              <span>Fullscreen</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">F</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Picture in Picture (PiP)</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">P</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Toggle Captions</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">C</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Frame Advance</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">.</kbd>
              </div>
            </div>
            <div class="shortcut-item">
              <span>Frame Rewind</span>
              <div class="kbd-group">
                <kbd class="shortcut-key">,</kbd>
              </div>
            </div>
          </div>
        </div>

        <div class="help-close-hint">Click outside or press <kbd>?</kbd> or <kbd>/</kbd> to close</div>
      </div>
    </div>
  </div>
  <div style="text-align: center;" v-else>
    <div class="icon">
      <i class="fa-solid fa-spinner fa-spin fa-4x" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useStorage } from '@vueuse/core'
import { watch } from 'vue'
import Hls from 'hls.js'
import { disableOpacity, enableOpacity } from '~/utils'
import { useKeyboardShortcuts } from '~/composables/useKeyboardShortcuts'

import type { StoreItem } from '~/types/store'
import type { file_info, video_source_element, video_track_element } from '~/types/video'

const config = useConfigStore()
const toast = useNotification()

const props = defineProps({ item: { type: Object as () => StoreItem, default: () => ({}) } })

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
const showHelp = ref(false)
const usingHls = ref(false)

let unbindMediaSessionListeners: null | (() => void) = null
let hls: Hls | null = null
let cleanupKeyboardShortcuts: null | (() => void) = null

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

const restoreDefaultTextTrack = async () => {
  const el = video.value
  if (!el) {
    return
  }

  try {
    const tracksList = el.textTracks
    if (!tracksList || 0 === tracksList.length) {
      return
    }

    // Check if first track has cues - if not, we need to reload tracks
    const firstTrack = tracksList[0] as TextTrack | undefined
    const needsReload = firstTrack && (!firstTrack.cues || firstTrack.cues.length === 0)

    if (needsReload) {
      const trackElements = el.querySelectorAll('track')

      trackElements.forEach((trackEl, idx) => {
        const parent = trackEl.parentNode
        const clone = trackEl.cloneNode(true) as HTMLTrackElement
        trackEl.remove()
        setTimeout(() => {
          if (parent) {
            parent.appendChild(clone)
            // Set mode after cues load
            clone.addEventListener('load', () => {
              const trackObj = clone.track
              if (trackObj) {
                trackObj.mode = idx === 0 ? 'showing' : 'disabled'
              }
            }, { once: true })
          }
        }, idx * 10)
      })

      return
    }

    for (let i = 0; i < tracksList.length; i += 1) {
      const track = tracksList[i] as TextTrack | undefined
      if (track) {
        track.mode = 'disabled'
      }
    }

    await new Promise(resolve => setTimeout(resolve, 50))

    for (let i = 0; i < tracksList.length; i += 1) {
      const track = tracksList[i] as TextTrack | undefined
      if (!track) {
        continue
      }
      const newMode = 0 === i ? 'showing' : 'disabled'
      track.mode = newMode
    }
  } catch (error) {
    console.warn('Failed to restore subtitle track state', error)
  }
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
    const src = makeDownload(config, props.item, allowedCodec ? 'api/download' : 'm3u8', allowedCodec ? false : true)
    sources.value.push({
      src,
      type: allowedCodec ? response.mimetype : 'application/x-mpegURL',
      onerror: (err: Event) => src_error(err),
    })
    usingHls.value = !allowedCodec
  } else {
    const src = makeDownload(config, props.item, 'api/download', false)
    sources.value.push({ src, type: response.mimetype, onerror: (err: Event) => src_error(err), })
    usingHls.value = false
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

  const keyboardShortcutsResult = useKeyboardShortcuts({
    videoElement: video,
    enabled: ref(true),
    closePlayer: () => emitter('closeModel'),
  })

  cleanupKeyboardShortcuts = keyboardShortcutsResult.attach()

  watch(keyboardShortcutsResult.showHelp, newVal => showHelp.value = newVal)

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
  try {
    navigator.mediaSession.metadata = new MediaMetadata(meta)
  } catch { }
}

onUpdated(() => prepareVideoPlayer())

onBeforeUnmount(() => {
  enableOpacity()
  if (hls) {
    hls.destroy()
    hls = null
  }

  usingHls.value = false

  document.removeEventListener('keydown', handle_event)

  if (cleanupKeyboardShortcuts) {
    cleanupKeyboardShortcuts()
    cleanupKeyboardShortcuts = null
  }

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
  restoreDefaultTextTrack()

  if (hasVideoStream.value) {
    if ('requestVideoFrameCallback' in video.value) {
      ; (video.value as any).requestVideoFrameCallback(() => captureFirstFramePoster(video.value!))
    } else {
      const tryOnce = () => captureFirstFramePoster(video.value!);
      ; (video.value as any).addEventListener('loadeddata', tryOnce, { once: true })
    }
  }
}

const src_error = async (e: any) => {
  if (hls) {
    return
  }

  await nextTick()
  if (destroyed.value) {
    return
  }

  if (video.value && (notFirefox && video.value.paused)) {
    return
  }

  console.warn('Source failed to load, attempting HLS fallback via hls.js...', e)
  attach_hls(makeDownload(config, props.item, 'm3u8', true))
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

  hls.on(Hls.Events.MANIFEST_PARSED, () => applyMediaSessionMetadata())
  hls.on(Hls.Events.MANIFEST_PARSED, async () => {
    await new Promise(resolve => setTimeout(resolve, 100))
    await restoreDefaultTextTrack()
  })

  hls.on(Hls.Events.MEDIA_ATTACHED, async () => {
    await new Promise(resolve => setTimeout(resolve, 200))
    await restoreDefaultTextTrack()
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
  usingHls.value = true
}

const forceSwitchToHls = () => {
  if (usingHls.value) {
    return
  }

  if (!hasVideoStream.value) {
    toast.error('Cannot switch to HLS: stream has no video track.')
    return
  }

  attach_hls(makeDownload(config, props.item, 'm3u8', true))
}
</script>
