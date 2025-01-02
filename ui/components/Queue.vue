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
      <div class="column is-half-mobile">
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
      <div class="column is-half-mobile">
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

    <div class="columns is-multiline">
      <LateLoader :unrender="true" :min-height="265" class="column is-6" v-for="item in stateStore.queue"
        :key="item._id">
        <div class="card">
          <header class="card-header has-tooltip" v-tooltip="item.title">
            <div class="card-header-title has-text-centered is-text-overflow is-block">
              {{ item.title }}
            </div>
            <div class="card-header-icon">
              <button @click="hideThumbnail = !hideThumbnail">
                <span class="icon"><i class="fa-solid"
                    :class="{ 'fa-arrow-down': hideThumbnail, 'fa-arrow-up': !hideThumbnail, }" /></span>
              </button>
            </div>
          </header>
          <div v-if="false === hideThumbnail" class="card-image">
            <figure class="image is-3by1" v-if="item.extras?.thumbnail">
              <NuxtLink v-tooltip="item.title" :href="item.url" target="_blank">
                <img
                  :src="config.app.url_host + config.app.url_prefix + 'thumbnail?url=' + encodePath(item.extras.thumbnail)"
                  :alt="item.title" />
              </NuxtLink>
            </figure>
            <figure class="image is-3by1" v-else>
              <NuxtLink target="_blank" :href="item.url" v-tooltip="`Open: ${item.title} link`">
                <img :src="config.app.url_host + config.app.url_prefix + 'images/placeholder.png'" :alt="item.title" />
              </NuxtLink>
            </figure>
          </div>
          <div class="card-content">
            <div class="columns is-multiline is-mobile">
              <div class="column is-12">
                <div class="progress-bar is-round">
                  <div class="progress-percentage">{{ updateProgress(item) }}</div>
                  <div class="progress" :style="{ width: percentPipe(item.percent) + '%' }"></div>
                </div>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow">
                <span class="icon-text">
                  <span class="icon" :class="{ 'has-text-success': item.status == 'downloading' }">
                    <i class="fas" :class="setIcon(item)" />
                  </span>
                  <span v-if="item.status == 'downloading' && item.is_live">Live Streaming</span>
                  <span v-else>{{ ucFirst(item.status) }}</span>
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow">
                <span :data-datetime="item.datetime"
                  v-tooltip="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                  {{ moment(item.datetime).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered is-text-overflow">
                <label class="checkbox is-block">
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                  Select
                </label>
              </div>
            </div>
            <div class="columns is-multiline is-mobile">
              <div class="column is-half-mobile">
                <button class="button is-danger is-fullwidth" @click="confirmCancel(item);">
                  <span class="icon-text is-block">
                    <span class="icon">
                      <i class="fa-solid fa-trash-can" />
                    </span>
                    <span>Cancel</span>
                  </span>
                </button>
              </div>
              <div class="column is-half-mobile">
                <a referrerpolicy="no-referrer" class="button is-link is-fullwidth" target="_blank" :href="item.url">
                  <span class="icon-text is-block">
                    <span class="icon">
                      <i class="fa-solid fa-up-right-from-square" />
                    </span>
                    <span>Visit Link</span>
                  </span>
                </a>
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
  </div>
</template>

<script setup>
import moment from 'moment'
import { useStorage } from '@vueuse/core'
import { ucFirst } from '~/utils/index'

const toast = useToast();
const config = useConfigStore();
const stateStore = useStateStore();
const socket = useSocketStore();

const selectedElms = ref([]);
const masterSelectAll = ref(false);
const showQueue = useStorage('showQueue', true)
const hideThumbnail = useStorage('hideThumbnailQueue', false)

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
    return 'fa-solid fa-globe';
  }

  if ('downloading' === item.status) {
    return 'fa-solid fa-circle-check';
  }

  if (null === item.status && true === config.paused) {
    return 'fa-solid fa-pause-circle';
  }

  return 'fa-solid fa-spinner fa-spin';
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
  if (value === null || 0 === value) {
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

  if ('preparing' === item.status) {
    return 'Preparing';
  }

  if (item.status != null) {
    string += item.percent && !item.is_live ? percentPipe(item.percent) + '%' : 'Live';
  }

  string += item.speed ? ' - ' + speedPipe(item.speed) : ' - Waiting..';

  if (item.status != null && item.eta) {
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
</script>
