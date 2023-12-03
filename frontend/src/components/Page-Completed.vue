<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showCompleted = !showCompleted">
    <span class="icon-text">
      <span class="icon">
        <font-awesome-icon :icon="showCompleted ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>Completed <span v-if="hasItems">({{ getTotal }})</span></span>
    </span>
  </h1>

  <div v-if="showCompleted">
    <div class="columns has-text-centered" v-if="hasItems">
      <div class="column">
        <button type="button" class="button is-fullwidth is-ghost is-inverted"
          @click="masterSelectAll = !masterSelectAll">
          <span class="icon-text">
            <span class="icon">
              <font-awesome-icon :icon="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular fa-square'" />
            </span>
            <span v-if="!masterSelectAll">Select All</span>
            <span v-else>Unselect All</span>
          </span>
        </button>
      </div>
      <div class="column">
        <button type="button" class="button is-fullwidth is-danger is-inverted" :disabled="!hasSelected"
          @click="$emit('deleteItem', 'completed', selectedElms); selectedElms = []">
          <span class="icon-text">
            <span class="icon">
              <font-awesome-icon icon="fa-solid fa-trash-can" />
            </span>
            <span>Remove Selected</span>
          </span>
        </button>
      </div>
      <div class="column" v-if="hasCompleted">
        <button type="button" class="button is-fullwidth is-primary is-inverted" @click="clearCompleted">
          <span class="icon-text">
            <span class="icon">
              <font-awesome-icon icon="fa-solid fa-circle-check" />
            </span>
            <span>Clear Completed</span>
          </span>
        </button>
      </div>
      <div class="column" v-if="hasFailed">
        <button type="button" class="button is-fullwidth is-info is-inverted" @click="clearFailed">
          <span class="icon-text">
            <span class="icon">
              <font-awesome-icon icon="fa-solid fa-circle-xmark" />
            </span>
            <span>Clear Failed</span>
          </span>
        </button>
      </div>
      <div class="column" v-if="hasFailed">
        <button type="button" class="button is-fullwidth is-warning is-inverted" @click="requeueFailed">
          <span class="icon-text">
            <span class="icon">
              <font-awesome-icon icon="fa-solid fa-rotate-right" />
            </span>
            <span>Re-queue Failed</span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline">
      <div class="column is-6" v-for="item in completed" :key="item._id">
        <div class="card" :class="{ 'is-bordered-danger': item.error ? true : false }">
          <header class="card-header has-tooltip" :data-tooltip="item.title">
            <div class="card-header-title has-text-centered is-text-overflow is-block">
              <a v-if="item.filename" referrerpolicy="no-referrer" :href="makeDownload(config, item, 'm3u8')"
                @click.prevent="$emit('playItem', item)">
                {{ item.title }}
              </a>
              <span v-else>{{ item.title }}</span>
            </div>
          </header>
          <div class="card-content">
            <div class="columns is-multiline">
              <div class="column is-12" v-if="item.error">
                <span class="has-text-danger">{{ item.error }}</span>
              </div>
              <div class="column is-4 has-text-centered" v-if="!item.live_in">
                <span class="icon-text">
                  <span class="icon"
                    :class="{ 'has-text-success': item.status === 'finished', 'has-text-danger': item.status !== 'finished' }">
                    <font-awesome-icon
                      :icon="item.status == 'finished' ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'" />
                  </span>
                  <span>{{ capitalize(item.status) }}</span>
                </span>
              </div>
              <div class="column is-4 has-text-centered">
                <span :date-datetime="item.datetime"
                  :data-tooltip="moment(item.datetime).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.datetime).fromNow() }}
                </span>
              </div>
              <div class="column is-4 has-text-centered" v-if="item.live_in && item.status != 'finished'">
                <span :date-datetime="item.datetime" :data-tooltip="'Will start at: ' + moment(item.live_in).format('YYYY-M-DD H:mm Z')">
                  {{ moment(item.live_in).fromNow() }}
                </span>
              </div>
              <div class="column is-4 has-text-centered">
                <label class="checkbox is-block">
                  <input class="completed-checkbox" type="checkbox" v-model="selectedElms" :id="'checkbox-' + item._id"
                    :value="item._id">
                  Select
                </label>
              </div>
            </div>
            <div class="columns">
              <div class="column" v-if="item.status != 'finished'">
                <a class="button is-warning is-fullwidth" data-tooltip="Re-queue failed download."
                  @click="reQueueItem(item)">
                  <span class="icon-text">
                    <span class="icon">
                      <font-awesome-icon icon="fa-solid fa-rotate-right" />
                    </span>
                    <span>Re-queue</span>
                  </span>
                </a>
              </div>
              <div class="column" v-if="item.filename">
                <a class="button is-fullwidth is-primary" :href="makeDownload(config, item)"
                  :download="item.filename?.split('/').reverse()[0]">
                  <span class="icon-text">
                    <span class="icon">
                      <font-awesome-icon icon="fa-solid fa-download" />
                    </span>
                    <span>Download</span>
                  </span>
                </a>
              </div>
              <div class="column">
                <a class="button is-danger is-fullwidth" @click="$emit('deleteItem', 'completed', item._id)">
                  <span class="icon-text">
                    <span class="icon">
                      <font-awesome-icon icon="fa-solid fa-trash-can" />
                    </span>
                    <span>Remove</span>
                  </span>
                </a>
              </div>
              <div class="column">
                <a referrerpolicy="no-referrer" class="button is-link is-fullwidth" target="_blank" :href="item.url">
                  <span class="icon-text">
                    <span class="icon">
                      <font-awesome-icon icon="fa-solid fa-up-right-from-square" />
                    </span>
                    <span>Visit Link</span>
                  </span>
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="content has-text-centered" v-if="!hasItems">
      <p v-if="config.isConnected">
        <span class="icon-text">
          <span class="icon has-text-success">
            <font-awesome-icon icon="fa-solid fa-circle-check" />
          </span>
          <span>No downloads records.</span>
        </span>
      </p>
      <p v-else>
        <span class="icon-text">
          <span class="icon">
            <font-awesome-icon icon="fa-solid fa-spinner fa-spin" />
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

const emits = defineEmits(['deleteItem', 'addItem', 'playItem']);

const props = defineProps({
  completed: {
    type: Object,
    required: true
  },
  config: {
    type: Object,
    required: true
  },
})

const selectedElms = ref([]);
const masterSelectAll = ref(false);
const showCompleted = useStorage('showCompleted', true)

watch(masterSelectAll, (value) => {
  for (const key in props.completed) {
    const element = props.completed[key];
    if (value) {
      selectedElms.value.push(element._id);
    } else {
      selectedElms.value = [];
    }
  }
})

const hasSelected = computed(() => selectedElms.value.length > 0)
const hasItems = computed(() => Object.keys(props.completed)?.length > 0)
const getTotal = computed(() => Object.keys(props.completed)?.length);

const hasFailed = computed(() => {
  if (Object.keys(props.completed)?.length < 0) {
    return false;
  }

  for (const key in props.completed) {
    const element = props.completed[key];
    if (element.status !== 'finished') {
      return true;
    }
  }
  return false;
})

const hasCompleted = computed(() => {
  if (Object.keys(props.completed)?.length < 0) {
    return false;
  }

  for (const key in props.completed) {
    const element = props.completed[key];
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

  for (const key in props.completed) {
    if (props.completed[key].status === 'finished') {
      keys[key] = props.completed[key]._id;
    }
  }

  emits('deleteItem', 'completed', keys);
}

const clearFailed = () => {
  const state = confirm('Are you sure you want to clear all failed downloads?');
  if (false === state) {
    return;
  }

  const keys = {};

  for (const key in props.completed) {
    if (props.completed[key].status !== 'finished') {
      keys[key] = props.completed[key]._id;
    }
  }

  emits('deleteItem', 'completed', keys);
}

const requeueFailed = () => {
  if (false === confirm('Are you sure you want to re-queue all failed downloads?')) {
    return false;
  }

  for (const key in props.completed) {
    const item = props.completed[key];
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
