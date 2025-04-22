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
      <div class="column is-half-mobile" v-if="display_style === 'cards'">
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
      <div class="column is-half-mobile" v-if="hasDownloaded">
        <button type="button" class="button is-fullwidth is-link" :disabled="!hasSelected" @click="downloadSelected">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-download" /></span>
            <span>Download</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile">
        <button type="button" class="button is-fullwidth is-danger" :disabled="!hasSelected"
          @click="deleteSelectedItems">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-trash-can" /></span>
            <span>{{ config.app.remove_files ? 'Remove' : 'Clear' }}</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasCompleted">
        <button type="button" class="button is-fullwidth is-primary is-inverted" @click="clearCompleted">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-circle-check" /></span>
            <span>Clear Completed</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasIncomplete">
        <button type="button" class="button is-fullwidth is-info is-inverted" @click="clearIncomplete">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-circle-xmark" /></span>
            <span>Clear Incomplete</span>
          </span>
        </button>
      </div>
      <div class="column is-half-mobile" v-if="hasIncomplete">
        <button type="button" class="button is-fullwidth is-warning is-inverted" @click="requeueIncomplete">
          <span class="icon-text is-block">
            <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
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

    <div class="columns is-multiline" v-if="'list' === display_style">
      <div class="column is-12" v-if="hasItems">
        <div class="table-container">
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
                <th width="15%">Created</th>
                <th width="10%">Size/Starts</th>
                <th width="20%">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in sortCompleted" :key="item._id">
                <td class="is-vcentered has-text-centered">
                  <label class="checkbox is-block">
                    <input class="completed-checkbox" type="checkbox" v-model="selectedElms"
                      :id="'checkbox-' + item._id" :value="item._id">
                  </label>
                </td>
                <td class="is-vcentered">
                  <div class="is-text-overflow" v-tooltip="item.title">
                    <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
                  </div>
                  <div v-if="item.error">
                    <span class="has-text-danger">{{ item.error }}</span>
                  </div>
                  <div v-if="showMessage(item)">
                    <span class="has-text-danger">{{ item.msg }}</span>
                  </div>
                </td>
                <td class="is-vcentered has-text-centered is-unselectable">
                  <span class="icon-text">
                    <span class="icon" :class="setIconColor(item)"><i :class="setIcon(item)" /></span>
                    <span>{{ setStatus(item) }}</span>
                  </span>
                </td>
                <td class="is-vcentered has-text-centered is-unselectable">
                  <span class="user-hint" :date-datetime="item.datetime"
                    v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                    {{ moment(item.datetime).fromNow() }}
                  </span>
                </td>
                <td class="is-vcentered has-text-centered is-unselectable"
                  v-if="item.live_in && 'not_live' === item.status">
                  <span class="icon"><i class="fa-solid fa-spin fa-rotate-right" /></span>
                  <span :date-datetime="item.live_in" class="user-hint"
                    v-tooltip="'Will automatically be requeued at: ' + moment(item.live_in).format('YYYY-M-DD H:mm Z')">
                    {{ moment(item.live_in).fromNow() }}
                  </span>
                </td>
                <td class="is-vcentered has-text-centered is-unselectable" v-else>
                  {{ item.file_size ? formatBytes(item.file_size) : '-' }}
                </td>
                <td class="is-vcentered is-items-center">
                  <div class="field is-grouped is-grouped-centered">
                    <div class="control" v-if="('finished' === item.status && item.filename) || isEmbedable(item.url)">
                      <button v-if="'finished' === item.status && item.filename" @click="playVideo(item)"
                        v-tooltip="'Play video'" class="button is-danger is-light is-small">
                        <span class="icon"><i class="fa-solid fa-play" /></span>
                      </button>
                      <button v-else @click="embed_url = getEmbedable(item.url)" v-tooltip="'Play video'"
                        class="button is-danger is-small">
                        <span class="icon"><i class="fa-solid fa-play" /></span>
                      </button>
                    </div>
                    <div class="control" v-if="item.status != 'finished' || !item.filename">
                      <button class="button is-warning is-fullwidth is-small" v-tooltip="'Re-queue video'"
                        @click="(event) => reQueueItem(item, event)">
                        <span class="icon"><i class="fa-solid fa-rotate-right" /></span>
                      </button>
                    </div>
                    <div class="control" v-if="config.app?.keep_archive && item.status != 'finished'">
                      <button class="button is-danger is-light is-fullwidth is-small" v-tooltip="'Add link to archive'"
                        @click="archiveItem(item)">
                        <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                      </button>
                    </div>
                    <div class="control" v-if="item.filename && item.status === 'finished'">
                      <a class="button is-link is-fullwidth is-small" :href="makeDownload(config, item)"
                        v-tooltip="'Download video'" :download="item.filename?.split('/').reverse()[0]">
                        <span class="icon"><i class="fa-solid fa-download" /></span>
                      </a>
                    </div>
                    <div class="control" v-if="item.url && !config.app.basic_mode">
                      <button class="button is-info is-fullwidth is-small" @click="emitter('getInfo', item.url)"
                        v-tooltip="'Show video information'">
                        <span class="icon"><i class="fa-solid fa-info" /></span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-danger is-fullwidth is-small" @click="removeItem(item)"
                        v-tooltip="'Remove video'">
                        <span class="icon"><i class="fa-solid fa-trash-can" /></span>
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="columns is-multiline" v-else>
      <LateLoader :unrender="true" :min-height="hideThumbnail ? 210 : 410" class="column is-6"
        v-for="item in sortCompleted" :key="item._id">
        <div class="card"
          :class="{ 'is-bordered-danger': item.status === 'error', 'is-bordered-info': item.live_in || item.is_live }">
          <header class="card-header has-tooltip">

            <div class="card-header-title is-text-overflow is-block" v-tooltip="item.title">
              <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
            </div>

            <div class="card-header-icon">
              <span v-if="hideThumbnail">
                <a v-if="'finished' === item.status && item.filename" href="#" @click.prevent="playVideo(item)"
                  v-tooltip="'Play video.'">
                  <span class="icon"><i class="fa-solid fa-play" /></span>
                </a>
                <a v-else-if="isEmbedable(item.url)" href="#" @click.prevent="embed_url = getEmbedable(item.url)"
                  v-tooltip="'Play video.'">
                  <span class="icon"><i class="fa-solid fa-play" /></span>
                </a>
              </span>
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
              <span v-if="'finished' === item.status && item.filename" @click="playVideo(item)" class="play-overlay">
                <div class="play-icon"></div>
                <img @load="e => pImg(e)" :src="'/api/thumbnail?url=' + encodePath(item.extras.thumbnail)"
                  v-if="item.extras?.thumbnail" />
                <img v-else src="/images/placeholder.png" />
              </span>
              <span v-else-if="isEmbedable(item.url)" @click="embed_url = getEmbedable(item.url)" class="play-overlay">
                <div class="play-icon embed-icon"></div>
                <img @load="e => pImg(e)" :src="'/api/thumbnail?url=' + encodePath(item.extras.thumbnail)"
                  v-if="item.extras?.thumbnail" />
                <img v-else src="/images/placeholder.png" />
              </span>
              <template v-else>
                <img @load="e => pImg(e)" v-if="item.extras?.thumbnail"
                  :src="'/api/thumbnail?url=' + encodePath(item.extras.thumbnail)" />
                <img v-else src="/images/placeholder.png" />
              </template>
            </figure>
          </div>
          <div class="card-content">
            <div class="columns is-mobile is-multiline">
              <div class="column is-12" v-if="item.error">
                <span class="has-text-danger">{{ item.error }}</span>
              </div>
              <div class="column is-12" v-if="showMessage(item)">
                <span class="has-text-danger">{{ item.msg }}</span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="icon-text">
                  <span class="icon" :class="setIconColor(item)"><i :class="setIcon(item)" /></span>
                  <span>{{ setStatus(item) }}</span>
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable"
                v-if="item.live_in && 'not_live' === item.status">
                <span class="icon"><i class="fa-solid fa-spin fa-rotate-right" /></span>
                <span :date-datetime="item.live_in" class="user-hint"
                  v-tooltip="'Will automatically be requeued at: ' + moment(item.live_in).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.live_in).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="user-hint" :date-datetime="item.datetime"
                  v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.datetime).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable"
                v-if="item.file_size">
                {{ formatBytes(item.file_size) }}
              </div>
              <div class="column is-half-mobile has-text-centered is-unselectable">
                <label class="checkbox is-block">
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                  Select
                </label>
              </div>
            </div>
            <div class="columns is-mobile is-multiline">
              <div class="column is-half-mobile" v-if="item.status != 'finished' || !item.filename">
                <a class="button is-warning is-fullwidth" @click="(event) => reQueueItem(item, event)">
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
                <a class="button is-danger is-light is-fullwidth" @click="archiveItem(item)">
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

    <div class="modal is-active" v-if="video_item">
      <div class="modal-background" @click="closeVideo"></div>
      <div class="modal-content is-unbounded-model">
        <VideoPlayer type="default" :isMuted="false" autoplay="true" :isControls="true" :item="video_item"
          class="is-fullwidth" @closeModel="closeVideo" />
      </div>
      <button class="modal-close is-large" aria-label="close" @click="closeVideo"></button>
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

<script setup>
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import { makeDownload, formatBytes } from '~/utils/index'
import { isEmbedable, getEmbedable } from '~/utils/embedable'

const emitter = defineEmits(['getInfo', 'add_new'])
const config = useConfigStore()
const stateStore = useStateStore()
const socket = useSocketStore()
const toast = useToast()

const selectedElms = ref([])
const masterSelectAll = ref(false)
const showCompleted = useStorage('showCompleted', true)
const hideThumbnail = useStorage('hideThumbnailHistory', false)
const direction = useStorage('sortCompleted', 'desc')
const display_style = useStorage('display_style', 'cards')

const embed_url = ref('')
const video_item = ref(null)

const playVideo = item => video_item.value = item
const closeVideo = () => video_item.value = null

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)

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

const hasDownloaded = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false
  }

  for (const key in stateStore.history) {
    const element = stateStore.history[key]
    if (element.status === 'finished' && element.filename) {
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
  if ('finished' === item.status) {
    if (!item.filename) {
      return 'fa-solid fa-exclamation'
    }
    return item.is_live ? 'fa-solid fa-globe' : 'fa-solid fa-circle-check'
  }

  if ('error' === item.status) {
    return 'fa-solid fa-circle-xmark'
  }

  if ('cancelled' === item.status) {
    return 'fa-solid fa-eject'
  }

  if ('not_live' === item.status) {
    return 'fa-solid fa-headset'
  }

  return 'fa-solid fa-circle'
}

const setIconColor = item => {
  if ('finished' === item.status) {
    if (!item.filename) {
      return 'has-text-warning'
    }
    return 'has-text-success'
  }

  if ('not_live' === item.status) {
    return 'has-text-info'
  }

  if ('cancelled' === item.status) {
    return 'has-text-warning'
  }

  return 'has-text-danger'
}

const setStatus = item => {
  if ('finished' === item.status) {
    if (!item.filename) {
      return 'Skipped?'
    }
    return item.is_live ? 'Live Ended' : 'Completed'
  }

  if ('error' === item.status) {
    return 'Error'
  }

  if ('cancelled' === item.status) {
    return display_style.value === 'cards' ? 'User Cancelled' : 'Cancelled'
  }

  if ('not_live' === item.status) {
    return display_style.value === 'cards' ? 'Live Stream' : 'Live'
  }

  return item.status
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

const reQueueItem = (item, event = null) => {
  let extras = {}

  if (item?.extras) {
    Object.keys(item.extras).forEach(k => {
      if (k && true === k.startsWith('playlist')) {
        extras[k] = item.extras[k]
      }
    })
  }

  const item_req = {
    url: item.url,
    preset: item.preset,
    folder: item.folder,
    cookies: item.cookies,
    template: item.template,
    cli: item?.cli,
    extras: extras
  };

  socket.emit('item_delete', { id: item._id, remove_file: false })

  if (event && (event?.altKey && true === event?.altKey)) {
    toast.info('Removed the item from history, and added it to the new download form.')
    emitter('add_new', item_req)
    return
  }

  socket.emit('add_url', item_req)
}

const pImg = e => e.target.naturalHeight > e.target.naturalWidth ? e.target.classList.add('image-portrait') : null

watch(video_item, v => {
  if (!bg_enable.value) {
    return
  }

  document.querySelector('body').setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

watch(embed_url, v => {
  if (!bg_enable.value) {
    return
  }

  document.querySelector('body').setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

const downloadSelected = () => {
  if (selectedElms.value.length < 1) {
    toast.error('No items selected.')
    return
  }

  const body = document.querySelector('body')

  for (const key in selectedElms.value) {
    const item = stateStore.history[selectedElms.value[key]]
    if ('finished' !== item.status) {
      continue;
    }

    const link = document.createElement('a');
    link.href = makeDownload(config, item);

    let name = item?.filename

    if (name) {
      link.setAttribute('download', name.split('/').reverse()[0]);
    }

    link.setAttribute('target', '_self');
    body.appendChild(link);
    link.click();
    body.removeChild(link);
  }
}
</script>
