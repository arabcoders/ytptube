<template>
  <h1 class="mt-3 is-size-3 is-clickable is-unselectable" @click="showQueue = !showQueue">
    <icon class="icon-text">
      <span class="icon">
        <font-awesome-icon :icon="showQueue ? 'fa-solid fa-arrow-up' : 'fa-solid fa-arrow-down'" />
      </span>
      <span>Queue <span v-if="hasQueuedItems">({{ getTotal }})</span></span>
    </icon>
  </h1>

  <div v-if="showQueue">
    <div class="columns has-text-centered" v-if="hasQueuedItems">
      <div class="column">
        <button type="button" class="button is-fullwidth is-ghost" @click="masterSelectAll = !masterSelectAll">
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
        <button type="button" class="button is-fullwidth is-danger" :disabled="!hasSelected"
          @click="$emit('deleteItem', 'queue', selectedElms); selectedElms = []">
          <span class="icon-text">
            <span class="icon">
              <font-awesome-icon icon="fa-solid fa-trash-can" />
            </span>
            <span>Cancel Selected</span>
          </span>
        </button>
      </div>
    </div>

    <div class="columns is-multiline">
      <div class="column is-6" v-for="item in queue" :key="item._id">
        <div class="card">
          <header class="card-header has-tooltip" :data-tooltip="item.title">
            <div class="card-header-title has-text-centered is-text-overflow is-block">
              {{ item.title }}
            </div>
          </header>
          <div class="card-content">
            <div class="columns is-multiline">
              <div class="column is-12">
                <div id="progress-bar" class="is-round">
                  <div id="progress-percentage">{{ updateProgress(item) }}</div>
                  <div id="progress" :style="{ width: percentPipe(item.percent) + '%' }"></div>
                </div>
              </div>
              <div class="column is-4 has-text-centered">
                <span class="icon-text">
                  <span class="icon" :class="{ 'has-text-success': item.status == 'downloading' }">
                    <font-awesome-icon
                      :icon="item.status == 'downloading' ? 'fa-solid fa-download' : 'fa-solid fa-spinner fa-spin'" />
                  </span>
                  <span>{{ capitalize(item.status) }}</span>
                </span>
              </div>
              <div class="column is-4 has-text-centered">
                <span :data-datetime="item.datetime"
                  :data-tooltip="moment(item.datetime).format('MMMM Do YYYY, h:mm:ss a')">
                  {{ moment(item.datetime).fromNow() }}
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
              <div class="column">
                <a class="button is-danger is-fullwidth" @click="$emit('deleteItem', 'queue', item._id)">
                  <span class="icon-text">
                    <span class="icon">
                      <font-awesome-icon icon="fa-solid fa-trash-can" />
                    </span>
                    <span>Cancel</span>
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

    <div class="content has-text-centered" v-if="!hasQueuedItems">
      <p v-if="config.isConnected">
        <span class="icon-text">
          <span class="icon has-text-success">
            <font-awesome-icon icon="fa-solid fa-circle-check" />
          </span>
          <span>No queued items.</span>
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
import { defineProps, defineEmits, ref, watch, computed } from 'vue';
import moment from "moment";
import { useStorage } from '@vueuse/core'

defineEmits(['deleteItem']);

const props = defineProps({
  queue: {
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
const showQueue = useStorage('showQueue', true)

watch(masterSelectAll, (value) => {
  for (const key in props.queue) {
    const element = props.queue[key];
    if (value) {
      selectedElms.value.push(element._id);
    } else {
      selectedElms.value = [];
    }
  }
})

const hasSelected = computed(() => selectedElms.value.length > 0)
const hasQueuedItems = computed(() => Object.keys(props.queue)?.length > 0)
const getTotal = computed(() => Object.keys(props.queue)?.length);

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

  if (item.status == 'preparing') {
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
</script>
