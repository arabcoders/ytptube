<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showQueue = !showQueue">
    <span class="icon-text title is-4">
      <span class="icon">
        <i class="fas" :class="showQueue ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>Queue <span v-if="hasQueuedItems">({{ stateStore.count('queue') }})</span></span>
    </span>
  </h1>

  <div v-if="showQueue">
    <div class="columns is-multiline is-mobile has-text-centered" v-if="hasQueuedItems">
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
      <div class="column is-half-mobile" v-if="('cards' === display_style || hasSelected)">
        <button type="button" class="button is-fullwidth is-danger" :disabled="!hasSelected" @click="cancelSelected">
          <span class="icon-text is-block">
            <span class="icon">
              <i class="fa-solid fa-trash-can" />
            </span>
            <span>Cancel Selected</span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline" v-if="'list' === display_style">
      <div class="column is-12" v-if="hasQueuedItems">
        <div class="table-container is-responsive">
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
              <tr v-for="item in stateStore.queue" :key="item._id">
                <td class="has-text-centered is-vcentered">
                  <label class="checkbox is-block">
                    <input class="completed-checkbox" type="checkbox" v-model="selectedElms"
                      :id="'checkbox-' + item._id" :value="item._id">
                  </label>
                </td>
                <td class="is-text-overflow is-vcentered" v-tooltip="item.title">
                  <NuxtLink target="_blank" :href="item.url">{{ item.title }}</NuxtLink>
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  <span class="icon-text">
                    <span class="icon" :class="setIconColor(item)">
                      <i class="fas fa-solid" :class="setIcon(item)" />
                    </span>
                    <span v-text="setStatus(item)" />
                  </span>
                </td>
                <td>
                  <div class="progress-bar is-unselectable">
                    <div class="progress-percentage">{{ updateProgress(item) }}</div>
                    <div class="progress" :style="{ width: percentPipe(item.percent) + '%' }"></div>
                  </div>
                </td>
                <td class="has-text-centered is-text-overflow is-unselectable">
                  <span :data-datetime="item.datetime"
                    v-tooltip="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                    {{ moment(item.datetime).fromNow() }}
                  </span>
                </td>
                <td class="is-vcentered is-items-center">
                  <div class="field is-grouped is-grouped-centered">
                    <div class="control" v-if="isEmbedable(item.url)">
                      <button @click="() => embed_url = getEmbedable(item.url)" v-tooltip="'Play video'"
                        class="button is-danger is-small">
                        <span class="icon"><i class="fa-solid fa-play" /></span>
                      </button>
                    </div>
                    <div class="control">
                      <button class="button is-warning is-small" @click="confirmCancel(item);"
                        v-tooltip="'Cancel download'">
                        <span class="icon"><i class="fa-solid fa-eject" /></span>
                      </button>
                    </div>
                    <div class="control" v-if="item.url && !config.app.basic_mode">
                      <button class="button is-info is-small" @click="emitter('getInfo', item.url)"
                        v-tooltip="'Show video information'">
                        <span class="icon"><i class="fa-solid fa-info" /></span>
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
      <LateLoader :unrender="true" :min-height="hideThumbnail ? 265 : 475" class="column is-6"
        v-for="item in stateStore.queue" :key="item._id">
        <div class="card">
          <header class="card-header">
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
              <span v-if="isEmbedable(item.url)" @click="embed_url = getEmbedable(item.url)" class="play-overlay">
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
            <div class="columns is-multiline is-mobile">
              <div class="column is-12">
                <div class="progress-bar is-unselectable">
                  <div class="progress-percentage">{{ updateProgress(item) }}</div>
                  <div class="progress" :style="{ width: percentPipe(item.percent) + '%' }"></div>
                </div>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span class="icon-text">
                  <span class="icon" :class="setIconColor(item)">
                    <i class="fas fa-solid" :class="setIcon(item)" />
                  </span>
                  <span v-text="setStatus(item)" />
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <span :data-datetime="item.datetime"
                  v-tooltip="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                  {{ moment(item.datetime).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow is-unselectable">
                <label class="checkbox is-block">
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                  Select
                </label>
              </div>
            </div>
            <div class="columns is-multiline is-mobile">
              <div class="column is-half-mobile">
                <button class="button is-warning is-fullwidth" @click="confirmCancel(item);">
                  <span class="icon-text is-block">
                    <span class="icon"><i class="fa-solid fa-eject" /></span>
                    <span>Cancel</span>
                  </span>
                </button>
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

    <div class="content has-text-centered" v-if="!hasQueuedItems">
      <p v-if="socket.isConnected">
        <span class="icon-text">
          <span class="icon has-text-success">
            <i class="fa-solid fa-circle-check" />
          </span>
          <span>No queued items.</span>
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
import { ucFirst } from '~/utils/index'
import { isEmbedable, getEmbedable } from '~/utils/embedable'

const emitter = defineEmits(['getInfo'])
const config = useConfigStore();
const stateStore = useStateStore();
const socket = useSocketStore();

const selectedElms = ref([]);
const masterSelectAll = ref(false);
const showQueue = useStorage('showQueue', true)
const hideThumbnail = useStorage('hideThumbnailQueue', false)
const display_style = useStorage('display_style', 'cards')

const embed_url = ref('')

const bg_enable = useStorage('random_bg', true)
const bg_opacity = useStorage('random_bg_opacity', 0.85)

watch(masterSelectAll, (value) => {
  for (const key in stateStore.queue) {
    const element = stateStore.queue[key];
    if (value) {
      selectedElms.value.push(element._id);
    } else {
      selectedElms.value = [];
    }
  }
})

const hasSelected = computed(() => selectedElms.value.length > 0)
const hasQueuedItems = computed(() => stateStore.count('queue') > 0)

const setIcon = item => {
  if ('downloading' === item.status && item.is_live) {
    return 'fa-globe fa-spin';
  }

  if ('downloading' === item.status) {
    return 'fa-download';
  }

  if ('postprocessing' === item.status) {
    return 'fa-cog fa-spin';
  }

  if (null === item.status && true === config.paused) {
    return 'fa-pause-circle';
  }

  if (!item.status) {
    return 'fa-question';
  }

  return 'fa-spinner fa-spin';
}

const setStatus = item => {
  if (null === item.status && true === config.paused) {
    return 'Paused';
  }

  if ('downloading' === item.status && item.is_live) {
    return 'Live Streaming';
  }

  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader') ? 'External DL' : 'Preparing..';
  }

  if (!item.status) {
    return 'Unknown..';
  }

  return ucFirst(item.status)
}

const setIconColor = item => {
  if (item.status === 'downloading') {
    return 'has-text-success'
  }

  if ('postprocessing' === item.status) {
    return 'has-text-info'
  }

  if (null === item.status && true === config.paused) {
    return 'has-text-warning'
  }

  return ''
}



const ETAPipe = value => {
  if (value === null || 0 === value) {
    return 'Live';
  }
  if (value < 60) {
    return `${Math.round(value)}s`;
  }
  if (value < 3600) {
    return `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
  }
  const hours = Math.floor(value / 3600)
  const minutes = value % 3600
  return `${hours}h ${Math.floor(minutes / 60)}m ${Math.round(minutes % 60)}s`;
}

const speedPipe = value => {
  if (null === value || 0 === value) {
    return '0KB/s';
  }

  const k = 1024;
  const dm = 2;
  const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s', 'TB/s', 'PB/s', 'EB/s', 'ZB/s', 'YB/s'];
  const i = Math.floor(Math.log(value) / Math.log(k));
  return parseFloat((value / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

const percentPipe = value => {
  if (value === null || 0 === value) {
    return '00.00';
  }
  return parseFloat(value).toFixed(2);
}

const updateProgress = (item) => {
  let string = '';

  if (null === item.status && true === config.paused) {
    return 'Paused';
  }

  if ('postprocessing' === item.status) {
    return 'Post-processors are running.';
  }

  if ('preparing' === item.status) {
    return ag(item, 'extras.external_downloader') ? 'External downloader.' : 'Preparing';
  }

  if (null != item.status) {
    string += item.percent && !item.is_live ? percentPipe(item.percent) + '%' : 'Live';
  }

  string += item.speed ? ' - ' + speedPipe(item.speed) : ' - Waiting..';

  if (null != item.status && item.eta) {
    string += ' - ' + ETAPipe(item.eta);
  }

  return string;
}

const confirmCancel = item => {
  if (true !== confirm(`Are you sure you want to cancel (${item.title})?`)) {
    return false;
  }
  cancelItems(item._id);
  return true;
}

const cancelSelected = () => {
  if (true !== confirm('Are you sure you want to cancel selected items?')) {
    return false;
  }
  cancelItems(selectedElms.value);
  selectedElms.value = [];
  return true;
}

const cancelItems = item => {
  const items = []

  if (typeof item === 'object') {
    for (const key in item) {
      items.push(item[key]);
    }
  } else {
    items.push(item);
  }

  if (items.length < 0) {
    return;
  }

  items.forEach(id => socket.emit('item_cancel', id));
}

const pImg = e => e.target.naturalHeight > e.target.naturalWidth ? e.target.classList.add('image-portrait') : null
watch(embed_url, v => {
  if (!bg_enable.value) {
    return
  }
  document.querySelector('body').setAttribute("style", `opacity: ${v ? 1 : bg_opacity.value}`)
})

</script>
