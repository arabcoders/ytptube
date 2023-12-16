<template>
  <PageHeader :config="config" @toggleForm="addForm = !addForm" @toggleTasks="showTasks = !showTasks" />
  <formAdd v-if="addForm" :config="config" @addItem="addItem" />
  <pageTasks v-if="showTasks" :tasks="config.tasks" @removeTask="deleteTask" />
  <DownloadingList :config="config" :queue="downloading" @deleteItem="deleteItem" />
  <PageCompleted :config="config" :completed="completed" @deleteItem="deleteItem" @addItem="addItem"
    @playItem="playItem" />

  <div class="modal is-active" v-if="video_link">
    <div class="modal-background"></div>
    <div class="modal-content" style="width:auto;">
      <VideoPlayer type="default" :link="video_link" :isMuted="false" autoplay="true" :isControls="true"
        class="is-fullwidth" />
    </div>
    <button class="modal-close is-large" aria-label="close" @click="video_link = ''"></button>
  </div>
  <PageFooter :app_version="config?.app?.version || 'unknown'" />
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import PageHeader from './components/Page-Header'
import formAdd from './components/Form-Add'
import pageTasks from './components/Page-Tasks'
import DownloadingList from './components/Page-Downloading'
import PageCompleted from './components/Page-Completed'
import PageFooter from './components/Page-Footer'
import VideoPlayer from './components/Video-Player'
import { io } from "socket.io-client";
import { useToast } from 'vue-toastification'
import { useStorage, useEventBus } from '@vueuse/core'

const toast = useToast();
const bus = useEventBus('item_added');

const config = reactive({
  isConnected: false,
  app: {},
  tasks: [],
});

const downloading = reactive({});
const completed = reactive({});
const video_link = ref('');
const addForm = useStorage('addForm', true)
const showTasks = useStorage('showTasks', false)

onMounted(() => {
  const socket = io(process.env.VUE_APP_BASE_URL, {
    path: document.location.pathname + 'socket.io',
  });

  socket.on('connect', () => config.isConnected = true);
  socket.on('disconnect', () => config.isConnected = false);

  socket.on('initial_data', stream => {
    const initialData = JSON.parse(stream);
    config.app = initialData['config'];
    config.tasks = initialData['tasks'];

    for (const id in initialData['queue']) {
      downloading[id] = initialData['queue'][id];
    }

    for (const id in initialData['done']) {
      completed[id] = initialData['done'][id];
    }
  });

  socket.on('added', stream => {
    const item = JSON.parse(stream);
    downloading[item._id] = item;
    toast.success(`Item queued successfully: ${downloading[item._id]?.title}`);
  });

  socket.on('completed', stream => {
    const item = JSON.parse(stream);
    if (item._id in downloading) {
      delete downloading[item._id];
    }
    completed[item._id] = item;
  });

  socket.on('canceled', stream => {
    const id = JSON.parse(stream);
    if (false === (id in downloading)) {
      return
    }

    toast.info('Download canceled: ' + completed[id]?.title);
    delete downloading[id];
  });

  socket.on('cleared', stream => {
    const id = JSON.parse(stream);
    if (false === (id in completed)) {
      return;
    }

    delete completed[id];
  });

  socket.on("updated", stream => {
    const data = JSON.parse(stream);
    let dl = downloading[data._id] ?? {};
    data.deleting = dl?.deleting;
    downloading[data._id] = data;
  });
});

const deleteItem = (type, item) => {
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

  fetch(`${config.app.url_host}${config.app.url_prefix}delete`, {
    method: 'DELETE',
    body: JSON.stringify({
      where: type === 'completed' ? 'done' : 'queue',
      ids: items,
    }),
    headers: {
      'Content-Type': 'application/json'
    }
  }).catch((error) => {
    console.log(error);
    toast.error('Failed to delete/cancel item/s. ' + error);
  });
}

const addItem = (item) => {
  fetch(config.app.url_host + config.app.url_prefix + 'add', {
    method: 'POST',
    body: JSON.stringify(item),
    headers: {
      'Content-Type': 'application/json'
    }
  }).then((response) => response.json()).then((data) => {
    if (data.status === 'error') {
      const message = data.msg?.toString() || 'Failed to add download.';
      bus.emit('item_added', { status: "error", msg: message });
      toast.error(`${data.status[0].toUpperCase() + data.status.slice(1)}: ${message}`);
      return;
    }
    bus.emit('item_added', { status: "ok" });
  }).catch((error) => {
    console.log(error);
    bus.emit('item_added', { status: "error", msg: error });
    toast.error(`Failed to add link. ${error.message}`);
  });
};

const playItem = (item) => {
  let baseDir = 'm3u8/';

  if (item.folder) {
    baseDir += item.folder + '/';
  }

  video_link.value = config.app.url_host + config.app.url_prefix + baseDir + encodeURIComponent(item.filename);
};

const deleteTask = (indexNumber, item) => {
  if (!confirm(`Are you sure you want to delete this task ${item?.name || item.url}?`)) {
    return;
  }
  config.tasks = config.tasks.filter((_, index) => {
    return index !== indexNumber;
  });
}

</script>

