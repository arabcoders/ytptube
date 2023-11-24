<template>
  <h1 class="is-size-3">
    Completed
  </h1>

  <div class="columns has-text-centered" v-if="hasItems">
    <div class="column">
      <button type="button" class="button is-fullwidth is-ghost is-inverted" @click="masterSelectAll = !masterSelectAll">
        <span class="icon-text">
          <span class="icon">
            <i :class="!masterSelectAll ? 'fa-regular fa-square-check' : 'fa-regular  fa-square'"></i>
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
            <i class="fa-solid fa-trash-can"></i>
          </span>
          <span>Remove Selected</span>
        </span>
      </button>
    </div>
    <div class="column" v-if="hasCompleted">
      <button type="button" class="button is-fullwidth is-primary is-inverted" @click="clearCompleted">
        <span class="icon-text">
          <span class="icon">
            <i class="fa-solid fa-circle-check"></i>
          </span>
          <span>Clear Completed</span>
        </span>
      </button>
    </div>
    <div class="column" v-if="hasFailed">
      <button type="button" class="button is-fullwidth is-info is-inverted" @click="clearFailed">
        <span class="icon-text">
          <span class="icon">
            <i class="fa-solid fa-circle-xmark"></i>
          </span>
          <span>Clear Failed</span>
        </span>
      </button>
    </div>
    <div class="column" v-if="hasFailed">
      <button type="button" class="button is-fullwidth is-warning is-inverted" @click="requeueFailed">
        <span class="icon-text">
          <span class="icon">
            <i class="fa-solid fa-rotate-right"></i>
          </span>
          <span>Re-queue Failed</span>
        </span>
      </button>
    </div>
  </div>

  <div class="columns is-multiline">
    <div class="column is-6" v-for="item in completed" :key="item._id">
      <div class="card" :class="{ 'is-bordered-danger': item.error ? true : false }">
        <header class="card-header el has-tooltip" :data-tooltip="item.title">
          <div class="card-header-title has-text-centered el is-block">
            <a v-if="item.filename" referrerpolicy="no-referrer" :href="makeDownload(config, item)" target="_blank">
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
            <div class="column is-4 has-text-centered">
              <span class="icon-text">
                <span class="icon">
                  <i v-if="item.status == 'finished'" class="has-text-success fa-solid fa-circle-check"></i>
                  <i v-else class="has-text-danger fa-solid fa-times-circle"></i>
                </span>
                <span>{{ capitalize(item.status) }}</span>
              </span>
            </div>
            <div class="column is-4 has-text-centered">
              <span :data-tooltip="moment(item.timestamp / 1000000).format('MMMM Do YYYY, h:mm:ss a')">
                {{ moment(item.timestamp / 1000000).fromNow() }}
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
                @click="reQueueItem(item._id, item)">
                <span class="icon-text">
                  <span class="icon">
                    <i class="fa-solid fa-rotate-right"></i>
                  </span>
                  <span>Re-queue</span>
                </span>
              </a>
            </div>
            <div class="column" v-if="item.filename">
              <a class="button is-fullwidth is-primary" :href="makeDownload(config, item)">
                <span class="icon-text">
                  <span class="icon">
                    <i class="fa-solid fa-download"></i>
                  </span>
                  <span>Download</span>
                </span>
              </a>
            </div>
            <div class="column">
              <a class="button is-danger is-fullwidth" @click="$emit('deleteItem', 'completed', item._id)">
                <span class="icon-text">
                  <span class="icon">
                    <i class="fa-solid fa-trash-can"></i>
                  </span>
                  <span>Remove</span>
                </span>
              </a>
            </div>
            <div class="column">
              <a referrerpolicy="no-referrer" class="button is-link is-fullwidth" target="_blank" :href="item.url">
                <span class="icon-text">
                  <span class="icon">
                    <i class="fa-solid fa-up-right-from-square"></i>
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

  <div class="content has-text-centered" v-if="!hasCompleted">
    <p>
      <span class="icon-text">
        <span class="icon has-text-success">
          <i class="fa-solid fa-circle-check"></i>
        </span>
        <span v-if="config.isConnected">No completed downloads.</span>
        <span v-else>
          <span class="icon-text">
            <span class="icon is-loading"></span>
            <span>Connecting...</span>
          </span>
        </span>
      </span>
    </p>
  </div>
</template>

<script setup>
import { defineProps, computed, ref, watch, defineEmits } from 'vue';
import moment from "moment";

const emits = defineEmits(['deleteItem', 'addItem']);

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

const hasSelected = computed(() => {
  return selectedElms.value.length > 0;
})

const hasItems = computed(() => {
  return Object.keys(props.completed)?.length > 0;
})

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
  const state = confirm('Are you sure you want to re-queue all failed downloads?');
  if (false === state) {
    return;
  }

  const keys = {};

  for (const key in props.completed) {
    if (props.completed[key].status !== 'finished') {
      keys[key] = props.completed[key]._id;
      emits('deleteItem', 'completed', key);
      emits('addItem', {
        url: props.completed[key].url,
        format: props.completed[key].format,
        quality: props.completed[key].quality,
        path: props.completed[key].folder,
        ytdlp_config: props.completed[key].ytdlp_config,
        ytdlp_cookies: props.completed[key].ytdlp_cookies,
      });
    }
  }
}

const reQueueItem = (id, item) => {
  emits('deleteItem', 'completed', id);
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
