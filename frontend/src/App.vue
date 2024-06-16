<template>
  <PageHeader :config="config" @toggleForm="addForm = !addForm" @toggleTasks="showTasks = !showTasks"
    @toggleConsole="showConsole = !showConsole" @reload="reloadWindow" />

  <CliConsole v-if="showConsole" @runCommand="runCommand" :cli_output="cli_output" :isLoading="cli_isLoading"
    @cli_clear="cli_output = []" />
  <template v-else>
    <formAdd v-if="addForm" :config="config" @addItem="addItem" />
    <pageTasks v-if="showTasks" :tasks="config.tasks" />
    <DownloadingList :config="config" :queue="downloading" @deleteItem="deleteItem" />
    <PageCompleted :config="config" :completed="completed" @deleteItem="deleteItem" @addItem="addItem"
      @playItem="playItem" />
  </template>

  <div class="modal is-active" v-if="video_link">
    <div class="modal-background"></div>
    <div class="modal-content">
      <VideoPlayer type="default" :link="video_link" :isMuted="false" autoplay="true" :isControls="true"
        class="is-fullwidth" @closeModel="video_link = ''" />
    </div>
    <button class="modal-close is-large" aria-label="close" @click="video_link = ''"></button>
  </div>
  <PageFooter :app_version="config?.app?.version || 'unknown'" :ytdlp_version="config?.app.ytdlp_version || 'unknown'"
    :started="config?.app.started || 0" />
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
import CliConsole from './components/CLI-Console.vue'

const toast = useToast()
const bus = useEventBus('item_added', 'show_form', 'task_edit')

const config = reactive({
  isConnected: false,
  app: {},
  tasks: [],
})

const socket = ref()
const downloading = reactive({})
const completed = reactive({})
const video_link = ref('')
const addForm = useStorage('addForm', true)
const showTasks = useStorage('showTasks', false)
const cli_output = ref([])
const cli_isLoading = ref(false)
const showConsole = ref(false)

const runCommand = (args) => {
  cli_output.value = [];
  cli_isLoading.value = true;
  console.log(args)
  socket.value.emit('cli_post', args);
}

onMounted(() => {
  socket.value = io(process.env.VUE_APP_BASE_URL, {
    path: document.location.pathname + 'socket.io',
  })

  socket.value.on('connect', () => config.isConnected = true);
  socket.value.on('disconnect', () => config.isConnected = false);

  socket.value.on('initial_data', stream => {
    const initialData = JSON.parse(stream);
    config.app = initialData['config'];
    config.tasks = initialData['tasks'];
    config.directories = initialData['directories'];

    for (const id in initialData['queue']) {
      downloading[id] = initialData['queue'][id];
    }

    for (const id in initialData['done']) {
      completed[id] = initialData['done'][id];
    }
  })

  socket.value.on('added', stream => {
    const item = JSON.parse(stream);
    downloading[item._id] = item;
    toast.success(`Item queued successfully: ${downloading[item._id]?.title}`);
  });

  socket.value.on('error', stream => {
    const [item, error] = JSON.parse(stream);
    toast.error(`${item?.id}: Error: ${error}`);
  });

  socket.value.on('completed', stream => {
    const item = JSON.parse(stream);
    if (item._id in downloading) {
      delete downloading[item._id];
    }
    completed[item._id] = item;
  });

  socket.value.on('canceled', stream => {
    const id = JSON.parse(stream);
    if (false === (id in downloading)) {
      return
    }

    toast.info('Download canceled: ' + downloading[id]?.title);
    delete downloading[id];
  });

  socket.value.on('cleared', stream => {
    const id = JSON.parse(stream);
    if (false === (id in completed)) {
      return;
    }

    delete completed[id];
  });

  socket.value.on("updated", stream => {
    const data = JSON.parse(stream);
    let dl = downloading[data._id] ?? {};
    data.deleting = dl?.deleting;
    downloading[data._id] = data;
  });

  socket.value.on("update", stream => {
    const data = JSON.parse(stream);
    if (false === (data._id in completed)) {
      return;
    }
    completed[data._id] = data;
  });

  socket.value.on('cli_close', () => cli_isLoading.value = false);
  socket.value.on('cli_output', stream => {
    console.log(stream)
    cli_output.value.push(stream)
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
  }).then(resp => resp.json()).then(json => {
    for (const key in items) {
      const itemId = items[key];
      if (itemId in json && json[itemId] === 'ok') {
        if (true === (itemId in completed)) {
          delete completed[itemId];
        }
        if (true === (itemId in downloading)) {
          toast.info('Download canceled: ' + downloading[itemId]?.title);
          delete downloading[itemId];
        }
      }
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
    item.folder = item.folder.replace('#', '%23');
    baseDir += item.folder + '/';
  }

  video_link.value = config.app.url_host + config.app.url_prefix + baseDir + encodeURIComponent(item.filename);
};

const reloadWindow = () => window.location.reload();

bus.on((event, data) => {
  if (!['show_form'].includes(event)) {
    return true;
  }
  if ('show_form' === event) {
    addForm.value = true;
    setTimeout(() => bus.emit('task_edit', data), 500);
  }
});

</script>
