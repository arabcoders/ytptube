<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showCompleted = !showCompleted">
    <span class="icon-text title is-4">
      <span class="icon">
        <i :class="showCompleted ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>History <span v-if="hasItems">({{ stateStore.count('history') }})</span></span>
    </span>
  </h1>

  <div v-if="showCompleted">
    <div class="columns is-multiline is-mobile has-text-centered" v-if="hasItems">
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-ghost is-inverted"
          @click="masterSelectAll = !masterSelectAll">
          <span class="icon-text is-block">
            <span class="icon">
              <i :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
            </span>
            <span v-if="!masterSelectAll">Select All</span>
            <span v-else>Unselect All</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-danger" :disabled="!hasSelected"
          @click="deleteSelectedItems">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid fa-trash-can" />
            </span>
            <span>Remove Selected</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasCompleted">
        <button type="button" class="button is-fullwidth is-primary is-inverted" @click="clearCompleted">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid fa-circle-check" />
            </span>
            <span>Clear Completed</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasIncomplete">
        <button type="button" class="button is-fullwidth is-info is-inverted" @click="clearIncomplete">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid fa-circle-xmark" />
            </span>
            <span>Clear Incomplete</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasIncomplete">
        <button type="button" class="button is-fullwidth is-warning is-inverted" @click="requeueIncomplete">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid fa-rotate-right" />
            </span>
            <span>Re-queue Incomplete</span>
          </span>
        </button>
      </div>
      <div class="column is-1-tablet">
        <button type="button" class="button is-fullwidth" @click="direction = direction === 'desc' ? 'asc' : 'desc'">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid" :class="direction === 'desc' ? 'fa-arrow-down-a-z' : 'fa-arrow-up-a-z'" />
            </span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline">
      <LateLoader :unrender="true" :min-height="hideThumbnail ? 210 : 410" class="column is-6"
        v-for="item in sortCompleted" :key="item._id">
        <div class="card"
          :class="{ 'is-bordered-danger': item.status === 'error', 'is-bordered-info': item.live_in || item.is_live }">
          <header class="card-header has-tooltip">

            <div class="card-header-title is-text-overflow is-block" v-tooltip="item.title">
              <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
            </div>

            <div class="card-header-icon">
              <a :href="item.url" class="has-text-primary" v-tooltip="'Copy url.'" @click.prevent="copyText(item.url)">
                <span class="icon"><i class="fa-solid fa-copy" /></span>
              </a>
              <button @click="hideThumbnail = !hideThumbnail">
                <span class="icon"><i class="fa-solid"
                    :class="{ 'fa-arrow-down': hideThumbnail, 'fa-arrow-up': !hideThumbnail, }" /></span>
              </button>
            </div>
          </header>
          <div v-if="false === hideThumbnail" class="card-image">
            <figure class="image is-3by1">
              <span v-if="'finished' === item.status" @click="playVideo(item)" class="play-overlay">
                <div class="play-icon"></div>
                <img :src="'/api/thumbnail?url=' + encodePath(item.extras.thumbnail)" v-if="item.extras?.thumbnail" />
                <img v-else src="/images/placeholder.png" />
              </span>
              <template v-else>
                <img v-if="item.extras?.thumbnail" :src="'/api/thumbnail?url=' + encodePath(item.extras.thumbnail)" />
                <img v-else src="/images/placeholder.png" />
              </template>
            </figure>
          </div>
          <div class="card-content">
            <div class="columns is-mobile is-multiline">
              <div class="column is-12" v-if="item.live_in">
                <span class="has-text-info">
                  Live stream is scheduled to start at {{ moment(item.live_in).format() }}
                </span>
              </div>
              <div class="column is-12" v-if="item.error">
                <span class="has-text-danger">{{ item.error }}</span>
              </div>
              <div class="column is-12" v-if="showMessage(item)">
                <span class="has-text-danger">{{ item.msg }}</span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow">
                <span v-if="!item.live_in && !item.is_live">
                  <span class="icon-text">
                    <span class="icon"
                      :class="{ 'has-text-success': item.status === 'finished', 'has-text-danger': item.status !== 'finished' }">
                      <i :class="setIcon(item)" />
                    </span>
                    <span v-if="item.status == 'finished' && item.is_live">Live Ended</span>
                    <span v-else>{{ ucFirst(item.status) }}</span>
                  </span>
                </span>
                <span v-else>
                  <span class="icon-text">
                    <span class="icon has-text-info">
                      <i class="fa-solid fa-calendar" />
                    </span>
                    <span>Live</span>
                  </span>
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow">
                <span class="user-hint" :date-datetime="item.datetime"
                  v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.datetime).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow"
                v-if="item.live_in && item.status != 'finished'">
                <span :date-datetime="item.live_in"
                  v-tooltip="'Starts at: ' + moment(item.live_in).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.live_in).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow" v-if="item.file_size">
                {{ formatBytes(item.file_size) }}
              </div>
              <div class="column is-half-mobile has-text-centered">
                <label class="checkbox is-block">
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                  Select
                </label>
              </div>
            </div>
            <div class="columns is-mobile is-multiline">
              <div class="column is-half-mobile" v-if="item.status != 'finished'">
                <a class="button is-warning is-fullwidth" v-tooltip="'Re-queue item.'" @click="reQueueItem(item)">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                    <span>Re-queue</span>
                  </span>
                </a>
              </div>
              <div class="column is-half-mobile">
                <a class="button is-danger is-fullwidth" @click="removeItem(item)">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-trash-can" /></span>
                    <span>Remove</span>
                  </span>
                </a>
              </div>
              <div class="column is-half-mobile" v-if="config.app?.keep_archive && item.status != 'finished'">
                <a class="button is-danger is-light is-fullwidth" v-tooltip="'Add link to archive.'"
                  @click="archiveItem(item)">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                    <span>Archive</span>
                  </span>
                </a>
              </div>
              <div class="column is-half-mobile" v-if="item.filename && item.status === 'finished'">
                <a class="button is-link is-fullwidth" :href="makeDownload(config, item)"
                  :download="item.filename?.split('/').reverse()[0]">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-download" /></span>
                    <span>Download</span>
                  </span>
                </a>
              </div>
              <div class="column is-half-mobile" v-if="item.url && !config.app.basic_mode">
                <button class="button is-info is-fullwidth" @click="emitter('getInfo', item.url)">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Information</span>
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </LateLoader>
    </div>

    <div class="content has-text-centered" v-if="!hasItems">
      <p v-if="socket.isConnected">
        <span class="icon-text">
          <span class="icon has-text-success">
            <i class="fa-solid fa-circle-check" />
          </span>
          <span>No records.</span>
        </span>
      </p>
      <p v-else>
        <span class="icon-text">
          <span class="icon">
            <i class="fa-solid fa-spinner fa-spin" />
          </span>
          <span>Connecting...</span>
        </span>
      </p>
    </div>

    <div class="modal is-active" v-if="video_link">
      <div class="modal-background" @click="closeVideo"></div>
      <div class="modal-content">
        <VideoPlayer type="default" :link="video_link" :isMuted="false" autoplay="true" :isControls="true"
          :title="video_title" :thumbnail="video_thumbnail" :artist="video_artist" class="is-fullwidth"
          @closeModel="closeVideo" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closeVideo"></button>
    </div>
  </div>
</template>

<script setup>
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import { makeDownload, formatBytes, ucFirst } from '~/utils/index'
import toast from '~/plugins/toast'

const emitter = defineEmits(['getInfo'])
const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()

const selectedElms = ref([])
const masterSelectAll = ref(false)
const showCompleted = useStorage('showCompleted', true)
const hideThumbnail = useStorage('hideThumbnailHistory', false)
const direction = useStorage('sortCompleted', 'desc')

const video_link = ref('')
const video_title = ref('')
const video_thumbnail = ref('')
const video_artist = ref('')

const playVideo = item => {
  video_thumbnail.value = '';
  video_artist.value = '';
  video_link.value = makeDownload(config, item, 'm3u8')
  video_title.value = item.title
  if (item.extras?.thumbnail) {
    video_thumbnail.value = '/api/thumbnail?url=' + encodePath(item.extras.thumbnail)
  }
  if (item.extras?.channel) {
    video_artist.value = item.extras.channel
  }
  if (!video_artist.value && item.extras?.uploader) {
    video_artist.value = item.extras.uploader
  }
  if (!item.extras?.is_video && item.extras?.is_audio) {
    video_audio.value = true
  }
}

const closeVideo = () => {
  video_link.value = ''
  video_title.value = ''
  video_thumbnail.value = ''
  video_artist.value = ''
}

watch(masterSelectAll, (value) => {
  for (const key in stateStore.history) {
    const element = stateStore.history[key]
    if (value) {
      selectedElms.value.push(element._id)
    } else {
      selectedElms.value = []
    }
  }
})

const sortCompleted = computed(() => {
  const thisDirection = direction.value
  return Object.values(stateStore.history).sort((a, b) => {
    if ('asc' === thisDirection) {
      return new Date(a.datetime) - new Date(b.datetime)
    }
    return new Date(b.datetime) - new Date(a.datetime)
  })
})

const hasSelected = computed(() => selectedElms.value.length > 0)
const hasItems = computed(() => stateStore.count('history') > 0)

const showMessage = (item) => {
  if (!item?.msg || item.msg === item?.error) {
    return false
  }

  return item.msg.length > 0
}

const hasIncomplete = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false
  }

  for (const key in stateStore.history) {
    const element = stateStore.history[key]
    if (element.status !== 'finished') {
      return true
    }
  }
  return false
})

const hasCompleted = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false
  }

  for (const key in stateStore.history) {
    const element = stateStore.history[key]
    if (element.status === 'finished') {
      return true
    }
  }
  return false
})

const deleteSelectedItems = () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }

  let msg = `Are you sure you want to delete '${selectedElms.value.length}' items?`
  if (true === config.app.remove_files) {
    msg += '\nThis will delete the files from the server if they exist.'
  }

  if (false === confirm(msg)) {
    return
  }

  for (const key in selectedElms.value) {
    const item = stateStore.history[selectedElms.value[key]]
    if ('finished' === item.status) {
      socket.emit('archive_item', item)
    }
    socket.emit('item_delete', {
      id: item._id,
      remove_file: config.app.remove_files,
    })
  }
}

const clearCompleted = () => {
  let msg = 'Are you sure you want to clear all completed downloads?'
  if (false === confirm(msg)) {
    return
  }

  for (const key in stateStore.history) {
    if ('finished' === ag(stateStore.get('history', key, {}), 'status')) {
      socket.emit('item_delete', { id: stateStore.history[key]._id, remove_file: false, })
    }
  }
}

const clearIncomplete = () => {
  if (false === confirm('Are you sure you want to clear all in-complete downloads?')) {
    return
  }

  for (const key in stateStore.history) {
    if (stateStore.history[key].status !== 'finished') {
      socket.emit('item_delete', {
        id: stateStore.history[key]._id,
        remove_file: false,
      })
    }
  }
}

const setIcon = item => {
  if (item.status === 'finished' && item.is_live) {
    return 'fa-solid fa-globe'
  }

  if (item.status === 'finished') {
    return 'fa-solid fa-circle-check'
  }

  if (item.status === 'error') {
    return 'fa-solid fa-circle-xmark'
  }

  if (item.status === 'cancelled') {
    return 'fa-solid fa-eject'
  }

  return 'fa-solid fa-circle'
}

const requeueIncomplete = () => {
  if (false === confirm('Are you sure you want to re-queue all incomplete downloads?')) {
    return false
  }

  for (const key in stateStore.history) {
    const item = stateStore.get('history', key, {})
    if ('finished' === item.status) {
      continue
    }
    reQueueItem(item)
  }
}

const archiveItem = item => {
  if (!confirm(`Archive '${item.title ?? item.id ?? item.url ?? '??'}'?`)) {
    return
  }
  socket.emit('archive_item', item)
  socket.emit('item_delete', { id: item._id, remove_file: false })
}

const removeItem = item => {
  const msg = `Remove '${item.title ?? item.id ?? item.url ?? '??'}'?\n this will delete the file from the server.`
  if (config.app.remove_files && !confirm(msg)) {
    return false
  }

  socket.emit('item_delete', {
    id: item._id,
    remove_file: config.app.remove_files
  })
}

const reQueueItem = item => {
  socket.emit('item_delete', { id: item._id, remove_file: false })
  socket.emit('add_url', {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    ytdlp_config: item.ytdlp_config,
    ytdlp_cookies: item.ytdlp_cookies,
    output_template: item.output_template,
  })
}
</script>
