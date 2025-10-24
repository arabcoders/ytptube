<template>
  <div class="basic-wrapper">
    <div class="form-container" :class="{ 'is-centered': shouldCenterForm }">
      <section class="download-form box">
        <form class="download-form__body" autocomplete="off" @submit.prevent="addDownload">
          <label class="label" for="download-url">
            What you would like to download?
            <span class="is-pulled-right">
              <span class="icon is-pointer" :class="connectionStatusColor" @click="$emit('show_settings')"
                v-tooltip="'WebUI Settings'">
                <i class="fas fa-cogs" /></span>
            </span>
          </label>
          <div class="field has-addons">
            <div class="control">
              <button type="button" class="button is-info" @click="() => showExtras = !showExtras"
                v-tooltip="showExtras ? 'Hide extra options' : 'Show extra options'">
                <span class="icon"><i class="fas" :class="showExtras ? 'fa-chevron-up' : 'fa-chevron-down'" /></span>
              </button>
            </div>
            <div class="control is-expanded">
              <input id="download-url" v-model="formUrl" :disabled="!socketStore.isConnected || addInProgress"
                class="input" placeholder="https://..." type="url" required>
            </div>
            <div class="control">
              <button type="submit" class="button is-primary" :class="{ 'is-loading': addInProgress }"
                :disabled="!socketStore.isConnected || addInProgress || !formUrl.trim()">
                <span class="icon"><i class="fas fa-plus" /></span>
                <span>Add</span>
              </button>
            </div>
          </div>
          <div class="field has-addons" v-if="showExtras">
            <div class="control">
              <label class="button is-static">
                <span class="icon"><i class="fas fa-sliders" /></span>
                <span>Preset</span>
              </label>
            </div>
            <div class="control is-expanded">
              <div class="select is-fullwidth">
                <select id="preset" class="is-fullwidth" :disabled="!socketStore.isConnected || addInProgress"
                  v-model="formPreset.preset">
                  <optgroup label="Custom presets" v-if="presets.filter(p => !p?.default).length > 0">
                    <option v-for="cPreset in filter_presets(false)" :key="cPreset.name" :value="cPreset.name">
                      {{ cPreset.name }}
                    </option>
                  </optgroup>
                  <optgroup label="Default presets">
                    <option v-for="dPreset in filter_presets(true)" :key="dPreset.name" :value="dPreset.name">
                      {{ dPreset.name }}
                    </option>
                  </optgroup>
                </select>
              </div>
            </div>
          </div>

          <div class="columns is-multiline is-mobile" v-if="showExtras && configStore.dl_fields.length > 0">
            <div class="column is-6-tablet is-12-mobile">
              <DLInput id="force_download" type="bool" label="Force download"
                v-model="dlFields['--no-download-archive']" icon="fa-solid fa-download"
                :disabled="!socketStore.isConnected || addInProgress" description="Ignore archive and re-download." />
            </div>
            <div class="column is-6-tablet is-12-mobile" v-for="(fi, index) in sortedDLFields"
              :key="fi.id || `dlf-${index}`">
              <DLInput :id="fi?.id || `dlf-${index}`" :type="fi.kind" :description="fi.description" :label="fi.name"
                :icon="fi.icon" v-model="dlFields[fi.field]" :field="fi.field"
                :disabled="!socketStore.isConnected || addInProgress" />
            </div>
          </div>

        </form>
      </section>
    </div>

    <Transition name="queue-fade">
      <section v-if="hasAnyItems" key="queue" class="queue-section">
        <TransitionGroup name="queue-card" tag="div" class="columns is-multiline queue-card-columns">
          <div v-for="entry in displayItems" :key="entry.item._id" class="column is-12-mobile is-6-tablet">
            <article class="queue-card card" :class="{ 'is-history': 'history' === entry.source }">
              <div v-if="'queue' === entry.source && shouldShowProgress(entry.item)"
                class="progress-bar is-unselectable mb-3">
                <div class="progress-percentage">{{ updateProgress(entry.item) }}</div>
                <div class="progress" :style="{ width: getProgressWidth(entry.item) }"></div>
              </div>
              <div class="card-content">
                <article class="media">
                  <figure class="media-left">
                    <figure class="image is-16by9 queue-thumb" :class="{ 'is-clickable': isEmbedable(entry.item.url) }"
                      role="presentation" @click="openPlayer(entry.item)">
                      <img :src="resolveThumbnail(entry)" :alt="entry.item.title || 'Video thumbnail'" loading="lazy">
                      <span v-if="getDurationLabel(entry.item)" class="queue-thumb__badge">
                        {{ getDurationLabel(entry.item) }}
                      </span>
                      <span
                        v-if="entry.item.filename && entry.item.status === 'finished' || isEmbedable(entry.item.url)"
                        class="queue-thumb__overlay">
                        <span class="icon circle-border"
                          :class="{ 'has-text-danger': isEmbedable(entry.item.url) && (!entry.item.filename || entry.item.status !== 'finished') }">
                          <i class="fas fa-play" />
                        </span>
                      </span>
                    </figure>
                  </figure>
                  <div class="media-content is-grid">
                    <p class="title is-6 mb-0 queue-title">
                      <NuxtLink target="_blank" :href="entry.item.url">{{ entry.item.title }}</NuxtLink>
                    </p>
                    <div class="field is-grouped is-unselectable">
                      <div class="control">
                        <span class="tag is-size-7 has-text-weight-semibold is-uppercase"
                          :class="getSourceTagClass(entry)">
                          {{ getSourceLabel(entry) }}
                        </span>
                      </div>
                      <div class="control">
                        <span class="tag is-size-7 has-text-weight-semibold" :class="getStatusClass(entry.item)">
                          {{ getStatusLabel(entry.item) }}
                        </span>
                      </div>
                      <div class="control">
                        <span class="tag" :date-datetime="entry.item.datetime" v-rtime="entry.item.datetime" />
                      </div>
                    </div>
                    <p class="content is-size-7 has-text-grey queue-description">
                      <template v-if="entry.item.error || showMessage(entry.item)">
                        <template v-if="entry.item.error">
                          <span class="has-text-danger">{{ entry.item.error }}</span>
                        </template>
                        <template v-if="showMessage(entry.item)">
                          <span class="has-text-danger">{{ entry.item.msg }}</span>
                        </template>
                      </template>
                      <template v-else>
                        {{ getDescription(entry.item) || 'No description available.' }}
                      </template>
                    </p>
                  </div>
                </article>
                <div v-if="'queue' === entry.source" class="buttons are-small queue-actions mt-3">
                  <button v-if="canStart(entry.item)" class="button is-success is-light" type="button"
                    @click="startQueueItem(entry.item)">
                    <span class="icon"><i class="fas fa-circle-play" /></span>
                    <span>Start</span>
                  </button>
                  <button v-if="canPause(entry.item)" class="button is-warning is-light" type="button"
                    @click="pauseQueueItem(entry.item)">
                    <span class="icon"><i class="fas fa-pause" /></span>
                    <span>Pause</span>
                  </button>
                  <button class="button is-warning" type="button" @click="cancelDownload(entry.item)">
                    <span class="icon"><i class="fas fa-xmark" /></span>
                    <span>Cancel</span>
                  </button>
                </div>

                <div v-else class="buttons are-small queue-actions mt-3">
                  <a v-if="getDownloadLink(entry.item)" class="button is-link" :href="getDownloadLink(entry.item)"
                    :download="getDownloadName(entry.item)">
                    <span class="icon"><i class="fas fa-download" /></span>
                    <span>Download</span>
                  </a>
                  <button v-if="entry.item.status != 'finished' || !entry.item.filename" class="button is-info is-light"
                    type="button" @click="requeueItem(entry.item)">
                    <span class="icon"><i class="fas fa-rotate-right" /></span>
                    <span>Requeue</span>
                  </button>
                  <button class="button is-danger" type="button" @click="deleteHistoryItem(entry.item)">
                    <span class="icon"><i class="fas fa-trash" /></span>
                    <span>Delete</span>
                  </button>
                </div>
              </div>
            </article>
          </div>
        </TransitionGroup>
      </section>
    </Transition>

    <div class="modal is-active" v-if="videoItem">
      <div class="modal-background" @click="closePlayer"></div>
      <div class="modal-content is-unbounded-model">
        <VideoPlayer type="default" :isMuted="false" autoplay="true" :isControls="true" :item="videoItem"
          class="is-fullwidth" @closeModel="closePlayer" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closePlayer"></button>
    </div>

    <div class="modal is-active" v-if="embedUrl">
      <div class="modal-background" @click="closePlayer"></div>
      <div class="modal-content is-unbounded-model">
        <EmbedPlayer :url="embedUrl" @closeModel="closePlayer" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closePlayer"></button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useStorage } from '@vueuse/core'
import type { item_request } from '~/types/item'
import type { ItemStatus, StoreItem } from '~/types/store'
import { useNotification } from '~/composables/useNotification'
import { useConfigStore } from '~/stores/ConfigStore'
import { useStateStore } from '~/stores/StateStore'
import { useSocketStore } from '~/stores/SocketStore'
import { isEmbedable, getEmbedable } from '~/utils/embedable'
import EmbedPlayer from '~/components/EmbedPlayer.vue'
import { ag, encodePath, formatTime, makeDownload, request, stripPath, ucFirst, uri } from '~/utils'

defineEmits<{ (e: 'show_settings'): void }>()

const configStore = useConfigStore()
const stateStore = useStateStore()
const socketStore = useSocketStore()
const toast = useNotification()

const { app, paused, presets } = storeToRefs(configStore)
const { queue, history } = storeToRefs(stateStore)

const embedUrl = ref<string>('')
const videoItem = ref<StoreItem | null>(null)

const formUrl = ref<string>('')
const formPreset = ref<{ preset: string }>({ preset: app.value.default_preset || '' })
const addInProgress = ref<boolean>(false)
const showExtras = ref<boolean>(false)
const dlFields = useStorage<Record<string, any>>('dl_fields', {})
const show_thumbnail = useStorage<boolean>('show_thumbnail', true)

const sortByNewest = (items: StoreItem[]): StoreItem[] => items.slice().sort((a, b) => (b.timestamp ?? 0) - (a.timestamp ?? 0))

const queueItems = computed<StoreItem[]>(() => sortByNewest(Object.values(queue.value ?? {})))
const historyEntries = computed<StoreItem[]>(() => sortByNewest(Object.values(history.value ?? {})))

const downloadingStatuses: ReadonlySet<ItemStatus | null> = new Set(['downloading', 'postprocessing', 'preparing'])

const isDownloading = (status: ItemStatus | null): boolean => downloadingStatuses.has(status)

const downloadingItems = computed<StoreItem[]>(() => queueItems.value.filter(item => isDownloading(item.status)))
const queuedItems = computed<StoreItem[]>(() => queueItems.value.filter(item => !isDownloading(item.status)))

type DisplayEntry = { item: StoreItem; source: 'queue' | 'history' }

const displayItems = computed<DisplayEntry[]>(() => [
  ...downloadingItems.value.map(item => ({ item, source: 'queue' as const })),
  ...queuedItems.value.map(item => ({ item, source: 'queue' as const })),
  ...historyEntries.value.map(item => ({ item, source: 'history' as const })),
])

const hasActiveQueue = computed<boolean>(() => queueItems.value.length > 0)
const hasAnyItems = computed<boolean>(() => hasActiveQueue.value || historyEntries.value.length > 0)
const shouldCenterForm = computed<boolean>(() => 0 === queueItems.value.length && 0 === historyEntries.value.length)

const addDownload = async (): Promise<void> => {
  const url = formUrl.value.trim()
  if (!url) {
    toast.error('Please enter a valid URL.')
    return
  }

  let cli = ''

  const dlFieldsExtra = ['--no-download-archive']

  const is_valid = (dl_field: string): boolean => {
    if (dlFieldsExtra.includes(dl_field)) {
      return true
    }

    if (configStore.dl_fields && configStore.dl_fields.length > 0) {
      return configStore.dl_fields.some(f => dl_field === f.field)
    }

    return false
  }

  if (dlFields.value && Object.keys(dlFields.value).length > 0) {
    const joined = []
    for (const [key, value] of Object.entries(dlFields.value)) {
      if (false === is_valid(key)) {
        continue
      }

      if ([undefined, null, '', false].includes(value as any)) {
        continue
      }

      const keyRegex = new RegExp(`(^|\\s)${key}(\\s|$)`)
      if (cli && keyRegex.test(cli)) {
        continue
      }

      joined.push(true === value ? `${key}` : `${key} ${value}`)
    }

    if (joined.length > 0) {
      cli = joined.join(' ')
    }
  }

  const payload: item_request[] = [{
    url,
    preset: formPreset.value.preset || app.value.default_preset,
    cli: cli || '',
    auto_start: true,
  }]

  try {
    addInProgress.value = true
    const response = await request('/api/history', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    const data = await response.json()

    if (!response.ok) {
      toast.error(data?.error ?? 'Failed to add download.')
      return
    }

    const failures = Array.isArray(data) ? data.filter((item: Record<string, any>) => false === item?.status) : []
    if (failures.length > 0) {
      failures.forEach((item: Record<string, any>) => toast.error(item?.msg ?? 'Failed to add download.'))
      return
    }

    formUrl.value = ''
    formPreset.value.preset = app.value.default_preset || ''
    dlFields.value = {}
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to add download.'
    toast.error(message)
  } finally {
    addInProgress.value = false
  }
}

const resolveThumbnail = (entry: DisplayEntry): string => {
  if (!show_thumbnail.value) {
    return '/images/placeholder.png'
  }

  const { item, source } = entry

  const sidecarImage = item.sidecar?.image?.[0]?.file
  if ('history' === source && sidecarImage) {
    const relativePath = stripPath(app.value.download_path ?? '', sidecarImage)
    return uri(`/api/download/${encodeURIComponent(relativePath)}`)
  }

  const remoteThumb = ag<string | null>(item, 'extras.thumbnail', null)
  if (remoteThumb) {
    return uri(`/api/thumbnail?id=${item._id}&url=${encodePath(remoteThumb)}`)
  }

  return '/images/placeholder.png'
}

const openPlayer = (item: StoreItem): void => {
  if (item.filename && item.status === 'finished') {
    videoItem.value = item
    return
  }

  if (!isEmbedable(item.url)) {
    return
  }
  const embed = getEmbedable(item.url)
  if (embed) {
    embedUrl.value = embed
  }
}

const closePlayer = (): void => {
  embedUrl.value = ''
  videoItem.value = null
}

const getSourceLabel = (entry: DisplayEntry): string => {
  if ('history' === entry.source) {
    return 'History'
  }
  if (isDownloading(entry.item.status)) {
    return 'Active'
  }
  return 'Queued'
}

const getSourceTagClass = (entry: DisplayEntry): string => {
  if ('history' === entry.source) {
    return 'is-light'
  }
  if (isDownloading(entry.item.status)) {
    return 'is-info is-light'
  }
  return 'is-warning is-light'
}

const getDescription = (item: StoreItem): string => {
  const direct = (item.description ?? '').toString().trim()
  if (direct) {
    return direct
  }

  const extrasDescription = ag<string | null>(item, 'extras.description', null)?.toString().trim()
  if (extrasDescription) {
    return extrasDescription
  }

  const errorDescription = item.error?.trim()
  if (errorDescription) {
    return errorDescription
  }

  const message = ag<string | null>(item, 'msg', null)?.toString().trim()
  if (message) {
    return message
  }

  return ''
}

const getDurationLabel = (item: StoreItem): string | null => {
  const duration = ag<number | null>(item, 'extras.duration', null)
  if (null == duration || Number.isNaN(duration) || 0 >= duration) {
    return null
  }
  return formatTime(duration)
}

const statusOverrides: Record<string, string> = {
  downloading: 'Downloading',
  postprocessing: 'Post-processing',
  preparing: 'Preparing',
  finished: 'Completed',
  error: 'Error',
  cancelled: 'Cancelled',
  not_live: 'Not live yet',
  skip: 'Skipped',
}

const getStatusLabel = (item: StoreItem): string => {
  if (null === item.status) {
    return 'Queued'
  }
  return statusOverrides[item.status] ?? ucFirst(item.status.replace(/_/g, ' '))
}

const statusColorMap: Record<string, string> = {
  downloading: 'has-text-info',
  postprocessing: 'has-text-link',
  preparing: 'has-text-link',
  finished: 'has-text-success',
  error: 'has-text-danger',
  cancelled: 'has-text-grey',
  not_live: 'has-text-warning',
  skip: 'has-text-grey',
}

const getStatusClass = (item: StoreItem): string => {
  if (null === item.status) {
    return 'has-text-grey'
  }
  return statusColorMap[item.status] ?? 'has-text-info'
}

const shouldShowProgress = (item: StoreItem): boolean => isDownloading(item.status) || null === item.status

const percentPipe = (value: number | null): string => {
  if (null === value || Number.isNaN(value)) {
    return '00.00'
  }
  return parseFloat(String(value)).toFixed(2)
}

const ETAPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return 'Live'
  }
  if (value < 60) {
    return `${Math.round(value)}s`
  }
  if (value < 3600) {
    return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`
  }
  const hours = Math.floor(value / 3600)
  const minutes = value % 3600
  return `${hours}h ${Math.floor(minutes / 60)}m ${Math.round(minutes % 60)}s`
}

const speedPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return '0KB/s'
  }
  const k = 1024
  const dm = 2
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s', 'EB/s', 'ZB/s', 'YB/s']
  const i = Math.floor(Math.log(value) / Math.log(k))
  return `${parseFloat((value / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

const updateProgress = (item: StoreItem): string => {
  let text = ''
  if (!item.auto_start) {
    return 'Manual start'
  }
  if (null === item.status && true === paused.value) {
    return 'Global Pause'
  }
  if ('postprocessing' === item.status) {
    return 'Post-processors are running.'
  }
  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader') ? 'External downloader.' : 'Preparing'
  }
  if (null != item.status) {
    text += item.percent && !item.is_live ? `${percentPipe(item.percent)}%` : 'Live'
  }
  text += item.speed ? ` - ${speedPipe(item.speed)}` : ' - Waiting..'
  if (null != item.status && item.eta) {
    text += ` - ${ETAPipe(item.eta)}`
  }
  return text
}

const getProgressWidth = (item: StoreItem): string => {
  const percent = parseFloat(percentPipe(item.percent ?? 0))
  const clamped = Number.isNaN(percent) ? 0 : Math.min(100, Math.max(0, percent))
  return `${clamped}%`
}

const canStart = (item: StoreItem): boolean => !item.status && false === item.auto_start
const canPause = (item: StoreItem): boolean => !item.status && true === item.auto_start

const startQueueItem = (item: StoreItem): void => {
  socketStore.emit('item_start', item._id)
}

const pauseQueueItem = (item: StoreItem): void => {
  socketStore.emit('item_pause', item._id)
}

const cancelDownload = (item: StoreItem): void => {
  socketStore.emit('item_cancel', item._id)
}

const getDownloadLink = (item: StoreItem): string => {
  if (!item.filename) {
    return ''
  }
  return makeDownload(app.value, item)
}

const getDownloadName = (item: StoreItem): string => {
  if (!item.filename) {
    return 'download'
  }
  const segments = item.filename.split('/')
  return segments[segments.length - 1] || 'download'
}

const requeueItem = (item: StoreItem): void => {
  if (!item.url) {
    toast.error('Unable to requeue item; missing URL.')
    return
  }

  const payload: item_request = {
    url: item.url,
    preset: item.preset || app.value.default_preset,
    folder: item.folder,
    template: item.template,
    cookies: item.cookies,
    cli: item.cli,
    auto_start: item.auto_start ?? true,
  }

  if (item.extras && Object.keys(item.extras).length > 0) {
    payload.extras = JSON.parse(JSON.stringify(item.extras))
  }

  socketStore.emit('item_delete', { id: item._id, remove_file: false })
  socketStore.emit('add_url', payload)
}

const deleteHistoryItem = (item: StoreItem): void => {
  socketStore.emit('item_delete', { id: item._id, remove_file: app.value.remove_files })
  toast.info('Removed from history queue.')
}

const filter_presets = (flag: boolean = true) => presets.value.filter(item => item.default === flag)

const showMessage = (item: StoreItem) => {
  if (!item?.msg || item.msg === item?.error) {
    return false
  }
  return (item.msg?.length || 0) > 0
}

// eslint-disable-next-line vue/no-side-effects-in-computed-properties
const sortedDLFields = computed(() => configStore.dl_fields.sort((a, b) => (a.order || 0) - (b.order || 0)))

const connectionStatusColor = computed(() => {
  switch (socketStore.connectionStatus) {
    case 'connected':
      return 'has-text-success'
    case 'connecting':
      return 'has-text-warning fa-spin'
    case 'disconnected':
    default:
      return 'has-text-danger'
  }
})

</script>

<style scoped>
.basic-wrapper {
  min-height: calc(100vh - 6rem);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2.5rem;
  padding: 2rem 1rem 4rem;
}

.form-container {
  width: 100%;
  display: flex;
  justify-content: center;
  transition: transform 0.45s cubic-bezier(0.25, 0.8, 0.25, 1),
    filter 0.35s ease;
  will-change: transform;
}

.form-container.is-centered {
  transform: translateY(30vh);
  filter: drop-shadow(0 18px 32px rgba(10, 10, 10, 0.25));
}

.download-form {
  width: min(560px, 100%);
  transition: box-shadow 0.45s ease;
}

.download-form__body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.queue-section {
  width: min(1100px, 100%);
  display: flex;
  flex-direction: column;
  gap: 2rem;
  transform-origin: top center;
}

.queue-card-columns {
  margin-top: 0.75rem;
}

.queue-card {
  height: 100%;
  transition: transform 0.3s ease, box-shadow 0.35s ease;
}

.queue-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 14px 30px rgba(10, 10, 10, 0.12);
}

.queue-card .card-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}


.queue-card .media-left {
  margin-right: 1rem;
}

.queue-thumb {
  position: relative;
  width: 12rem;
  max-width: 100%;
  border-radius: 0.5rem;
  overflow: hidden;
}

.queue-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.queue-thumb.is-clickable {
  cursor: pointer;
}

.queue-thumb__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0);
  color: #fff;
  transition: background-color 0.2s ease;
  pointer-events: none;
  z-index: 0;
}

.queue-thumb.is-clickable:hover .queue-thumb__overlay {
  background: rgba(0, 0, 0, 0.45);
}

.queue-thumb__badge {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 0.7rem;
  line-height: 1;
  z-index: 1;
}

.queue-title {
  overflow: hidden;
}

.queue-title a {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-description {
  max-height: 4.5rem;
  min-height: 2.5rem;
  overflow: hidden;
  display: -webkit-box;
  line-clamp: 3;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.queue-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: auto;
}

.queue-fade-enter-active,
.queue-fade-leave-active {
  transition: opacity 0.35s ease, transform 0.45s ease;
}

.queue-fade-enter-from,
.queue-fade-leave-to {
  opacity: 0;
  transform: translateY(18px);
}

.queue-card-enter-active,
.queue-card-leave-active {
  transition: opacity 0.3s ease, transform 0.35s ease;
}

.queue-card-enter-from,
.queue-card-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

.queue-card-leave-active {
  position: absolute;
}

@media (max-width: 768px) {
  .form-container.is-centered {
    transform: translateY(18vh);
  }

  .queue-card .media {
    flex-direction: column;
    align-items: flex-start;
  }

  .queue-card .media-left {
    margin-right: 0;
    margin-bottom: 1rem;
    width: 100%;
  }

  .queue-thumb {
    width: 100%;
  }

  .queue-card .media-content {
    width: 100%;
  }

  .queue-title {
    width: 100%;
  }

  .queue-actions {
    width: 100%;
    justify-content: flex-end;
  }
}

.progress-bar {
  border-radius: 0.75rem 0.75rem 0 0
}

.circle-border {
  border: 2px solid;
  border-radius: 50%;
  padding: 0.5rem;
}
</style>
