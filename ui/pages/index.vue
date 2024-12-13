<template>
  <div>
    <Queue :config="config" :queue="downloading" @deleteItem="deleteItem" />
    <History :config="config" :completed="completed" @deleteItem="deleteItem" @addItem="addItem"
    @playItem="playItem" @archiveItem="archiveItem" />
  </div>
</template>

<script setup>
import { io } from "socket.io-client";
const bus = useEventBus('item_added', 'show_form', 'task_edit')

const config = reactive({
  isConnected: false,
  app: {},
  tasks: [],
})

const runtimeConfig = useRuntimeConfig()
const socket = ref()
const downloading = reactive({})
const completed = reactive({})
const cli_output = ref([])
const cli_isLoading = ref(false)

useHead({ title: 'Index' })

onMounted(() => {
  socket.value = io(runtimeConfig.public.wss, {
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
  socket.value.on('cli_output', s => cli_output.value.push(s));
});


</script>
