<template>
  <div>
    <Queue />
    <History />
  </div>
</template>

<script setup>
import { io } from "socket.io-client"
import { useConfigStore } from "~/store/ConfigStore"
import { useStateStore } from "~/store/StateStore"

const bus = useEventBus('item_added', 'show_form', 'task_edit')
const config = useConfigStore()

const runtimeConfig = useRuntimeConfig()
const socket = ref()
const downloading = reactive({})
const cli_output = ref([])
const cli_isLoading = ref(false)
const stateStore = useStateStore()

useHead({ title: 'Index' })

onMounted(() => {
  socket.value = io(runtimeConfig.public.wss, {
    path: document.location.pathname + 'socket.io',
  })

  socket.value.on('connect', () => config.isConnected = true);
  socket.value.on('disconnect', () => config.isConnected = false);

  socket.value.on('initial_data', stream => {
    const initialData = JSON.parse(stream)

    config.setAll({
      app: initialData['config'],
      tasks: initialData['tasks'],
      directories: initialData['directories'],
    })
    stateStore.addAll('queue', initialData['queue'] ?? {})
    stateStore.addAll('history', initialData['done'] ?? {})
  })

  socket.value.on('added', stream => {
    const item = JSON.parse(stream);
    stateStore.add('queue', item);
    toast.success(`Item queued successfully: ${downloading[item._id]?.title}`);
  });

  socket.value.on('error', stream => {
    const [item, error] = JSON.parse(stream);
    toast.error(`${item?.id}: Error: ${error}`);
  });

  socket.value.on('completed', stream => {
    const item = JSON.parse(stream);
    if (true === stateStore.has('queue', item._id)) {
      stateStore.move('queue', 'history', item._id);
      return
    }
    stateStore.add('history', item);
  });

  socket.value.on('canceled', stream => {
    const id = JSON.parse(stream);

    if (true !== stateStore.has('queue', id)) {
      return
    }

    toast.info('Download canceled: ' + downloading[id]?.title);
    delete downloading[id];
  });

  socket.value.on('cleared', stream => {
    const id = JSON.parse(stream);
    if (true !== stateStore.has('history', id)) {
      return
    }
    stateStore.remove('history', id);
  });

  socket.value.on("updated", stream => {
    const data = JSON.parse(stream);
    let dl = stateStore.get('queue', data._id, {});
    data.deleting = dl?.deleting;
    stateStore.update('queue', data._id, data);
  });

  socket.value.on("update", stream => {
    const data = JSON.parse(stream);
    if (true === stateStore.has('history', data._id)) {
      stateStore.update('history', data._id, data);
      return;
    }
  });

  socket.value.on('cli_close', () => cli_isLoading.value = false);
  socket.value.on('cli_output', s => cli_output.value.push(s));
});
</script>
