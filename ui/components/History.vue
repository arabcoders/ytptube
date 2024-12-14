<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showCompleted = !showCompleted">
    <span class="icon-text title is-4">
      <span class="icon">
        <i :class="showCompleted ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>History <span v-if="hasItems">({{ getTotal }})</span></span>
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
          @click="$emit('deleteItem', 'completed', selectedElms); selectedElms = []">
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
      <LazyLoader :unrender="true" :min-height="210" class="column is-6" v-for="item in sortCompleted" :key="item._id">
        <div class="card"
          :class="{ 'is-bordered-danger': item.status === 'error', 'is-bordered-info': item.live_in || item.is_live }">
          <header class="card-header has-tooltip">
            <div class="card-header-title is-text-overflow is-block" v-tooltip="item.title">
              <a v-if="item.filename" referrerpolicy="no-referrer" :href="makeDownload(config, item, 'm3u8')"
                @click.prevent="$emit('playItem', item)">
                {{ item.title }}
              </a>
              <span v-else>{{ item.title }}</span>
            </div>
            <div class="card-header-icon" v-if="item.filename">
              <a :href="makeDownload(config, item)" :download="item.filename?.split('/').reverse()[0]"
                class="has-text-primary" v-tooltip="'Download item.'">
                <span class="icon"><i class="fa-solid fa-download" /></span>
              </a>
            </div>
          </header>
          <div class="card-content">
            <div class="columns is-mobile is-multiline">
              <div class="column is-12" v-if="item.live_in">
                <span class="has-text-info">
                  LIVE stream is scheduled to start at {{ moment(item.live_in).format() }}
                </span>
              </div>
              <div class="column is-12" v-if="item.error">
                <span class="has-text-danger">{{ item.error }}</span>
              </div>
              <div class="column is-12" v-if="showMessage(item)">
                <span class="has-text-danger">{{ item.msg }}</span>
              </div>
              <div class="column is-half-mobile has-text-centered">
                <span v-if="!item.live_in && !item.is_live">
                  <span class="icon-text">
                    <span class="icon"
                      :class="{ 'has-text-success': item.status === 'finished', 'has-text-danger': item.status !== 'finished' }">
                      <i :class="setIcon(item)" />
                    </span>
                    <span v-if="item.status == 'finished' && item.is_live">Stream Ended</span>
                    <span v-else>{{ ucFirst(item.status) }}</span>
                  </span>
                </span>
                <span v-else>
                  <span class="icon-text">
                    <span class="icon has-text-info">
                      <i class="fa-solid fa-calendar" />
                    </span>
                    <span>Live Stream</span>
                  </span>
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered">
                <span :date-datetime="item.datetime" v-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.datetime).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered" v-if="item.live_in && item.status != 'finished'">
                <span :date-datetime="item.datetime"
                  v-tooltip="'Will start at: ' + moment(item.live_in).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.live_in).fromNow() }}
                </span>
              </div>
              <div class="column is-half-mobile has-text-centered" v-if="item.file_size">
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
                <a class="button is-warning is-fullwidth" v-tooltip="'Re-queue incomplete download.'"
                  @click="reQueueItem(item)">
                  <span class="icon-text is-block">
                    <span class="icon">
                      <i class="fa-solid fa-rotate-right" />
                    </span>
                    <span>Re-queue</span>
                  </span>
                </a>
              </div>
              <div class="column is-half-mobile">
                <a class="button is-danger is-fullwidth" @click="$emit('deleteItem', 'completed', item._id)">
                  <span class="icon-text is-block">
                    <span class="icon">
                      <i class="fa-solid fa-trash-can" />
                    </span>
                    <span>Remove</span>
                  </span>
                </a>
              </div>
              <div class="column is-half-mobile" v-if="config.app?.keep_archive && item.status != 'finished'">
                <a class="button is-danger is-light is-fullwidth" v-tooltip="'Add link to archive.'"
                  @click="$emit('archiveItem', 'completed', item)">
                  <span class="icon-text is-block">
                    <span class="icon">
                      <i class="fa-solid fa-box-archive" />
                    </span>
                    <span>Archive</span>
                  </span>
                </a>
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
      </LazyLoader>
    </div>

    <div class="content has-text-centered" v-if="!hasItems">
      <p v-if="config.isConnected">
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
  </div>
</template>

<script setup>
import { defineProps, computed, ref, watch, defineEmits } from 'vue';
import moment from "moment";
import { useStorage } from '@vueuse/core'
import LazyLoader from './LazyLoader'
import { makeDownload, formatBytes, ucFirst } from '~/utils/index'

const emits = defineEmits(['deleteItem', 'addItem', 'playItem', 'archiveItem'])
const config = useConfigStore()
const stateStore = useStateStore()

const selectedElms = ref([]);
const masterSelectAll = ref(false);
const showCompleted = useStorage('showCompleted', true)
const direction = useStorage('sortCompleted', 'desc')

watch(masterSelectAll, (value) => {
  for (const key in stateStore.history) {
    const element = stateStore.history[key];
    if (value) {
      selectedElms.value.push(element._id);
    } else {
      selectedElms.value = [];
    }
  }
})

const sortCompleted = computed(() => {
  const thisDirection = direction.value;
  return Object.values(stateStore.history).sort((a, b) => {
    if ('asc' === thisDirection) {
      return new Date(a.datetime) - new Date(b.datetime);
    }
    return new Date(b.datetime) - new Date(a.datetime);
  })
})

const hasSelected = computed(() => selectedElms.value.length > 0)
const hasItems = computed(() => stateStore.count('history') > 0)
const getTotal = computed(() => stateStore.count('history'));

const showMessage = (item) => {
  if (!item?.msg || item.msg === item?.error) {
    return false
  }

  return item.msg.length > 0;
}

const hasIncomplete = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false;
  }

  for (const key in stateStore.history) {
    const element = stateStore.history[key];
    if (element.status !== 'finished') {
      return true;
    }
  }
  return false;
})

const hasCompleted = computed(() => {
  if (Object.keys(stateStore.history)?.length < 0) {
    return false;
  }

  for (const key in stateStore.history) {
    const element = stateStore.history[key];
    if (element.status === 'finished') {
      return true;
    }
  }
  return false;
})

const clearCompleted = () => {
  const state = confirm('Are you sure you want to clear all completed downloads?');
  if (false === state) {
    return;
  }

  const keys = {};

  for (const key in stateStore.history) {
    if (stateStore.history[key].status === 'finished') {
      keys[key] = stateStore.history[key]._id;
      stateStore.remove('history', key);
    }
  }
}

const clearIncomplete = () => {
  if (false === confirm('Are you sure you want to clear all incomplete downloads?')) {
    return;
  }

  for (const key in stateStore.history) {
    if (stateStore.history[key].status !== 'finished') {
      stateStore.remove('history', key);
    }
  }
}

const setIcon = item => {
  if (item.status === 'finished' && item.is_live) {
    return 'fa-solid fa-globe';
  }

  if (item.status === 'finished') {
    return 'fa-solid fa-circle-check';
  }

  if (item.status === 'error') {
    return 'fa-solid fa-circle-xmark';
  }

  if (item.status === 'canceled') {
    return 'fa-solid fa-eject';
  }

  return 'fa-solid fa-circle';
}

const requeueIncomplete = () => {
  if (false === confirm('Are you sure you want to re-queue all incomplete downloads?')) {
    return false;
  }

  for (const key in stateStore.history) {
    const item = stateStore.history[key];
    if (item.status !== 'finished') {
      emits('deleteItem', 'completed', key);
      emits('addItem', {
        url: item.url,
        format: item.format,
        quality: item.quality,
        folder: item.folder,
        ytdlp_config: item.ytdlp_config,
        ytdlp_cookies: item.ytdlp_cookies,
        output_template: item.output_template,
      });
    }
  }
}

const reQueueItem = (item) => {
  emits('deleteItem', 'completed', item._id);
  emits('addItem', {
    url: item.url,
    format: item.format,
    quality: item.quality,
    folder: item.folder,
    ytdlp_config: item.ytdlp_config,
    ytdlp_cookies: item.ytdlp_cookies,
    output_template: item.output_template,
  });
}
</script>
