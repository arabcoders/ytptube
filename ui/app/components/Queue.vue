<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showQueue = !showQueue" v-if="hasQueuedItems">
    <span class="icon-text title is-4">
      <span class="icon">
        <i class="fas" :class="showQueue ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>Queue <span v-if="hasQueuedItems">({{ filteredItems.length }})</span>
        <span v-if="selectedElms.length > 0">&nbsp;- Selected: {{ selectedElms.length }}</span>
      </span>
    </span>
  </h1>

  <div v-if="showQueue">
    <div class="columns is-multiline is-mobile has-text-centered" v-if="filteredItems.length > 0">
      <div class="column is-half-mobile" v-if="'cards' === display_style">
        <button type="button" class="button is-fullwidth is-ghost" @click="masterSelectAll = !masterSelectAll">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fas" :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
            </span>
            <span v-if="!masterSelectAll">Select All</span>
            <span v-else>Unselect All</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasManualStart">
        <button type="button" class="button is-fullwidth is-success" :disabled="!hasSelected" @click="startItems">
          <span class="icon"><i class="fa-solid fa-circle-play" /></span>
          <span>Start</span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasPausable">
        <button type="button" class="button is-fullwidth is-warning is-background-warning-85" :disabled="!hasSelected"
          @click="pauseSelected">
          <span class="icon"><i class="fa-solid fa-pause" /></span>
          <span>Pause</span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="('cards' === display_style || hasSelected)">
        <button type="button" class="button is-fullwidth is-warning" :disabled="!hasSelected" @click="cancelSelected">
          <span class="icon"><i class="fa-solid fa-eject" /></span>
          <span>Cancel</span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline" v-if="'list' === display_style">
      <div class="column is-12" v-if="filteredItems.length > 0">
        <div :class="{ 'table-container': table_container }">
          <table class="table is-striped is-hoverable is-fullwidth is-bordered"
            style="min-width: 1300px; table-layout: fixed;">
            <thead>
              <tr class="has-text-centered is-unselectable">
                <th width="5%" v-tooltip="masterSelectAll ? 'Unselect all' : 'Select all'">
                  <a href="#" @click.prevent="masterSelectAll = !masterSelectAll">
                    <span class="icon-text is-block">
                      <span class="icon">
                        <i class="fa-regular"
                          :class="{ 'fa-square-check': !masterSelectAll, 'fa-square': masterSelectAll }" />
                      </span>
                    </span>
                  </a>
                </th>
                <th width="40%">Video Title</th>
                <th width="15%">Status</th>
                <th width="20%">Progress</th>
                <th width="15%">Created</th>
                <th width="10%">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredItems" :key="item._id">
                <td class="has-text-centered is-vcentered">
                  <label class="checkbox is-block">
                    <input class="completed-checkbox" type="checkbox" v-model="selectedElms"
                      :id="'checkbox-' + item._id" :value="item._id">
                  </label>
                </td>
                <td class="is-text-overflow is-vcentered">
                  <div class="is-inline is-pulled-right" v-if="item.downloaded_bytes || item.extras?.duration">
                    <span class="tag" v-if="item.downloaded_bytes">{{ formatBytes(item.downloaded_bytes) }}</span>
                    <span class="tag is-info" v-if="item.extras?.duration">
                      {{ formatTime(item.extras.duration) }}
                    </span>
                  </div>
                  <div v-if="showThumbnails && item.extras?.thumbnail">
                    <FloatingImage
                      :image="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))"
                      :title="item.title">
                      <div class="is-text-overflow">
                        <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
                      </div>
                    </FloatingImage>
                  </div>
                  <template v-else>
                    <div class="is-text-overflow" v-tooltip="item.title">
                      <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
                    </div>
                  </template>
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  <span class="icon" :class="setIconColor(item)">
                    <i class="fas fa-solid" :class="setIcon(item)" />
                  </span>
                  <span v-text="setStatus(item)" />
                </td>
                <td>
                  <div class="progress-bar is-unselectable">
                    <div class="progress-percentage">{{ updateProgress(item) }}</div>
                    <div class="progress" :style="{ width: percentPipe(item.percent as number) + '%' }"></div>
                  </div>
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  <span v-tooltip="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')"
                    :data-datetime="item.datetime" v-rtime="item.datetime" />
                </td>
                <td class="is-vcentered is-items-center">
                  <Dropdown icons="fa-solid fa-cogs" @open_state="s => table_container = !s"
                    :button_classes="'is-small'" label="Actions">
                    <template v-if="isEmbedable(item.url)">
                      <NuxtLink class="dropdown-item has-text-danger"
                        @click="embed_url = getEmbedable(item.url) as string">
                        <span class="icon"><i class="fa-solid fa-play" /></span>
                        <span>Play video</span>
                      </NuxtLink>
                      <hr class="dropdown-divider" />
                    </template>

                    <NuxtLink class="dropdown-item has-text-warning" @click="confirmCancel(item);">
                      <span class="icon"><i class="fa-solid fa-eject" /></span>
                      <span>Cancel Download</span>
                    </NuxtLink>

                    <template v-if="!item.auto_start && !item.status">
                      <hr class="dropdown-divider" />
                      <NuxtLink class="dropdown-item has-text-success" @click="startItem(item)">
                        <span class="icon"><i class="fa-solid fa-circle-play" /></span>
                        <span>Start Download</span>
                      </NuxtLink>
                    </template>

                    <template v-if="item.auto_start && !item.status">
                      <hr class="dropdown-divider" />
                      <NuxtLink class="dropdown-item has-text-warning" @click="pauseItem(item)">
                        <span class="icon"><i class="fa-solid fa-pause" /></span>
                        <span>Pause Download</span>
                      </NuxtLink>
                    </template>

                    <template v-if="!config.app.basic_mode">
                      <hr class="dropdown-divider" />

                      <NuxtLink class="dropdown-item" @click="emitter('getInfo', item.url, item.preset, item.cli)">
                        <span class="icon"><i class="fa-solid fa-info" /></span>
                        <span>yt-dlp Information</span>
                      </NuxtLink>

                      <NuxtLink class="dropdown-item" @click="emitter('getItemInfo', item._id)">
                        <span class="icon"><i class="fa-solid fa-info-circle" /></span>
                        <span>Local Information</span>
                      </NuxtLink>
                    </template>
                  </Dropdown>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-else>
      <LateLoader :unrender="true" :min-height="showThumbnails ? 475 : 265" class="column is-6"
        v-for="item in filteredItems" :key="item._id">
        <div class="card">
          <header class="card-header">
            <div class="card-header-title is-text-overflow is-block" v-tooltip="item.title">
              <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
            </div>
            <div class="card-header-icon">
              <div class="field is-grouped">

                <div class="control">
                  <span class="tag is-info" v-if="item.extras?.duration">
                    {{ formatTime(item.extras.duration) }}
                  </span>
                </div>
                <div class="control">
                  <button @click="hideThumbnail = !hideThumbnail" v-if="thumbnails">
                    <span class="icon"><i class="fa-solid"
                        :class="{ 'fa-arrow-down': hideThumbnail, 'fa-arrow-up': !hideThumbnail }" /></span>
                  </button>
                </div>
                <div class="control">
                  <label class="checkbox is-block">
                    <input class="completed-checkbox" type="checkbox" v-model="selectedElms"
                      :id="'checkbox-' + item._id" :value="item._id">
                  </label>
                </div>
              </div>
            </div>
          </header>
          <div v-if="showThumbnails" class="card-image">
            <figure class="image is-3by1">
              <span v-if="isEmbedable(item.url)" @click="embed_url = getEmbedable(item.url) as string"
                class="play-overlay">
                <div class="play-icon embed-icon"></div>
                <img @load="e => pImg(e)"
                  :src="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))"
                  v-if="item.extras?.thumbnail" />
                <img v-else src="/images/placeholder.png" />
              </span>
              <template v-else>
                <img @load="e => pImg(e)" v-if="item.extras?.thumbnail"
                  :src="uri('/api/thumbnail?id=' + item._id + '&url=' + encodePath(item.extras.thumbnail))" />
                <img v-else src="/images/placeholder.png" />
              </template>
            </figure>
          </div>
          <div class="card-content">
            <div class="columns is-multiline is-mobile">
              <div class="column is-12">
                <div class="progress-bar is-unselectable">
                  <div class="progress-percentage">{{ updateProgress(item) }}</div>
                  <div class="progress" :style="{ width: percentPipe(item.percent as number) + '%' }"></div>
                </div>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="icon" :class="setIconColor(item)">
                  <i class="fas fa-solid" :class="setIcon(item)" />
                </span>
                <span v-text="setStatus(item)" />
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="icon"><i class="fa-solid fa-sliders" /></span>
                <span v-tooltip="`Preset: ${item.preset}`" class="user-hint">{{ item.preset }}</span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span v-tooltip="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')" :data-datetime="item.datetime"
                  v-rtime="item.datetime" />
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable"
                v-if="item.downloaded_bytes" v-tooltip="`Saving to: ${makePath(item)}`">
                {{ formatBytes(item.downloaded_bytes) }}
              </div>

            </div>
            <div class="columns is-multiline is-mobile">
              <div class="column is-half-mobile">
                <button class="button is-warning is-fullwidth" @click="confirmCancel(item);">
                  <span class="icon"><i class="fa-solid fa-eject" /></span>
                  <span>Cancel</span>
                </button>
              </div>
              <div class="column is-half-mobile" v-if="!item.auto_start && !item.status">
                <button class="button is-success is-fullwidth" @click="startItem(item)">
                  <span class="icon"><i class="fa-solid fa-circle-play" /></span>
                  <span>Start</span>
                </button>
              </div>
              <div class="column is-half-mobile" v-if="item.auto_start && !item.status">
                <button class="button is-warning is-background-warning-85 is-fullwidth" @click="pauseItem(item)">
                  <span class="icon"><i class="fa-solid fa-pause" /></span>
                  <span>Pause</span>
                </button>
              </div>
              <div class="column is-half-mobile">
                <Dropdown icons="fa-solid fa-cogs" @open_state="s => table_container = !s" label="Actions">
                  <template v-if="isEmbedable(item.url)">
                    <NuxtLink class="dropdown-item has-text-danger"
                      @click="embed_url = getEmbedable(item.url) as string">
                      <span class="icon"><i class="fa-solid fa-play" /></span>
                      <span>Play video</span>
                    </NuxtLink>
                    <hr class="dropdown-divider" v-if="!config.app.basic_mode" />
                  </template>

                  <NuxtLink class="dropdown-item" @click="emitter('getInfo', item.url, item.preset, item.cli)"
                    v-if="!config.app.basic_mode">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>yt-dlp Information</span>
                  </NuxtLink>

                  <NuxtLink class="dropdown-item" @click="emitter('getItemInfo', item._id)"
                    v-if="!config.app.basic_mode">
                    <span class="icon"><i class="fa-solid fa-info-circle" /></span>
                    <span>Local Information</span>
                  </NuxtLink>
                </Dropdown>
              </div>
            </div>
          </div>
        </div>
      </LateLoader>
    </div>

    <div class="columns is-multiline" v-if="hasQueuedItems && filteredItems.length < 1 && query">
      <div class="column is-12">
        <Message message_class="has-background-warning-90 has-text-dark" title="No results for queued items"
          icon="fas fa-search" :useClose="true" @close="() => emitter('clear_search')" v-if="query">
          <span class="is-block">No results found for '<span class="is-underlined is-bold">{{ query }}</span>'.</span>
        </Message>
      </div>
    </div>

    <div class="modal is-active" v-if="embed_url">
      <div class="modal-background" @click="embed_url = ''"></div>
      <div class="modal-content is-unbounded-model">
        <EmbedPlayer :url="embed_url" @closeModel="embed_url = ''" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="embed_url = ''"></button>
    </div>
  </div>
</template>

<script setup lang="ts">
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import type { StoreItem } from '~/types/store'

const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string, cli: string): void
  (e: 'getItemInfo', id: string): void
  (e: 'clear_search'): void
}>()

const props = defineProps<{
  thumbnails?: boolean
  query?: string
}>()

const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()
const box = useConfirm()
const toast = useNotification()

const showQueue = useStorage('showQueue', true)
const hideThumbnail = useStorage('hideThumbnailQueue', false)
const display_style = useStorage('display_style', 'cards')
const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.95)

const selectedElms = ref<string[]>([])
const masterSelectAll = ref(false)
const embed_url = ref('')
const table_container = ref(false)

const showThumbnails = computed(() => !!props.thumbnails && !hideThumbnail.value)

watch(masterSelectAll, (value) => {
  if (value) {
    selectedElms.value = Object.values(stateStore.queue).map((element: StoreItem) => element._id)
  } else {
    selectedElms.value = []
  }
})

const filteredItems = computed<StoreItem[]>(() => {
  const q = props.query?.toLowerCase()
  if (!q) {
    return Object.values(stateStore.queue)
  }
  return Object.values(stateStore.queue).filter((i: StoreItem) =>
    Object.values(i).some(v => typeof v === 'string' && v.toLowerCase().includes(q))
  )
})

const hasSelected = computed(() => 0 < selectedElms.value.length)
const hasQueuedItems = computed(() => 0 < stateStore.count('queue'))
const hasManualStart = computed(() => {
  if (0 > stateStore.count('queue')) {
    return false
  }
  for (const key in stateStore.queue) {
    const item = stateStore.queue[key] as StoreItem
    if (!item.status && false === item.auto_start) {
      return true
    }
  }
  return false
})

const hasPausable = computed(() => {
  if (0 > stateStore.count('queue')) {
    return false
  }
  for (const key in stateStore.queue) {
    const item = stateStore.queue[key] as StoreItem
    if (!item.status && true === item.auto_start) {
      return true
    }
  }
  return false
})

const setIcon = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'fa-hourglass-half'
  }
  if ('downloading' === item.status && item.is_live) {
    return 'fa-globe fa-spin'
  }
  if ('downloading' === item.status) {
    return 'fa-download'
  }
  if ('postprocessing' === item.status) {
    return 'fa-cog fa-spin'
  }
  if (null === item.status && true === config.paused) {
    return 'fa-pause-circle'
  }
  if (!item.status) {
    return 'fa-question'
  }
  return 'fa-spinner fa-spin'
}

const setStatus = (item: StoreItem): string => {
  if (!item.auto_start) {
    return 'Pending'
  }
  if (null === item.status && true === config.paused) {
    return 'Paused'
  }
  if ('downloading' === item.status && item.is_live) {
    return 'Streaming'
  }
  if ('preparing' === item.status) {
    // @ts-ignore
    return ag(item, 'extras.external_downloader') ? 'External-DL' : 'Preparing..'
  }
  if (!item.status) {
    return 'Unknown...'
  }
  return ucFirst(item.status)
}

const setIconColor = (item: StoreItem): string => {
  if ('downloading' === item.status) {
    return 'has-text-success'
  }
  if ('postprocessing' === item.status) {
    return 'has-text-info'
  }
  if (!item.auto_start || (null === item.status && true === config.paused)) {
    return 'has-text-warning'
  }
  return ''
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
  return parseFloat((value / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

const percentPipe = (value: number | null): string => {
  if (null === value || 0 === value) {
    return '00.00'
  }
  return parseFloat(String(value)).toFixed(2)
}

const updateProgress = (item: StoreItem): string => {
  let string = ''
  if (!item.auto_start) {
    return 'Manual start'
  }
  if (null === item.status && true === config.paused) {
    return 'Global Pause'
  }
  if ('postprocessing' === item.status) {
    return 'Post-processors are running.'
  }
  if ('preparing' === item.status) {
    // @ts-ignore
    return ag(item, 'extras.external_downloader') ? 'External downloader.' : 'Preparing'
  }
  if (null != item.status) {
    string += item.percent && !item.is_live ? percentPipe(item.percent) + '%' : 'Live'
  }
  string += item.speed ? ' - ' + speedPipe(item.speed) : ' - Waiting..'
  if (null != item.status && item.eta) {
    string += ' - ' + ETAPipe(item.eta)
  }
  return string
}

const confirmCancel = (item: StoreItem) => {
  if (true !== box.confirm(`Cancel '${item.title}'?`)) {
    return false
  }
  cancelItems(item._id)
  return true
}

const cancelSelected = () => {
  if (true !== box.confirm(`Cancel '${selectedElms.value.length}' selected items?`)) {
    return false
  }
  cancelItems(selectedElms.value)
  selectedElms.value = []
  masterSelectAll.value = false
  return true
}

const cancelItems = (item: string | string[]) => {
  const items: string[] = []
  if ('object' === typeof item) {
    for (const key in item) {
      items.push((item as any)[key])
    }
  } else {
    items.push(item)
  }
  if (0 > items.length) {
    return
  }
  items.forEach(id => socket.emit('item_cancel', id))
}

const startItem = (item: StoreItem) => socket.emit('item_start', item._id)
const pauseItem = (item: StoreItem) => socket.emit('item_pause', item._id)

const startItems = () => {
  if (1 > selectedElms.value.length) {
    return
  }
  let filtered: string[] = []
  selectedElms.value.forEach(id => {
    const item = stateStore.get('queue', id) as StoreItem
    if (item && !item.auto_start && !item.status) {
      filtered.push(id)
    }
  })
  selectedElms.value = []
  if (1 > filtered.length) {
    toast.error('No eligible items to start.')
    return
  }
  if (true !== box.confirm(`Start '${filtered.length}' selected items?`)) {
    return false
  }
  filtered.forEach(id => socket.emit('item_start', id))
}

const pauseSelected = () => {
  if (1 > selectedElms.value.length) {
    return
  }
  let filtered: string[] = []
  selectedElms.value.forEach(id => {
    const item = stateStore.get('queue', id) as StoreItem
    if (item && item.auto_start && !item.status) {
      filtered.push(id)
    }
  })
  selectedElms.value = []
  if (1 > filtered.length) {
    toast.error('No eligible items to pause.')
    return
  }
  if (true !== box.confirm(`Pause '${filtered.length}' selected items?`)) {
    return false
  }
  filtered.forEach(id => socket.emit('item_pause', id))
}

const pImg = (e: Event) => {
  const target = e.target as HTMLImageElement
  target.naturalHeight > target.naturalWidth ? target.classList.add('image-portrait') : null
}

watch(embed_url, v => {
  if (!bg_enable.value) {
    return
  }
  document.querySelector('body')?.setAttribute('style', `opacity: ${v ? 1 : bg_opacity.value}`)
})

const makePath = (item: StoreItem) => {
  const parts = [
    eTrim(item.download_dir, '/').replace(config.app.download_path, ''),
  ]
  if (item?.filename) {
    parts.push(eTrim(item.filename, '/'))
  }

  return '/' + sTrim(parts.filter(p => !!p).map(p => p.replace(/\\/g, '/').replace(/\/+/g, '/')).join('/'), '/')
}
</script>
