import { io } from "socket.io-client";
import { ag } from "~/utils/index"

export const useSocketStore = defineStore('socket', () => {
  const runtimeConfig = useRuntimeConfig()
  const config = useConfigStore()
  const stateStore = useStateStore()
  const toast = useToast()

  const socket = ref(null);
  const isConnected = ref(false);

  const connect = () => {
    socket.value = io(runtimeConfig.public.wss)

    socket.value.on('connect', () => isConnected.value = true);
    socket.value.on('disconnect', () => isConnected.value = false);

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
      stateStore.add('queue', item._id, item);
      toast.success(`Item queued successfully: ${ag(stateStore.get('queue', item._id, {}), 'title')}`);
    });

    socket.value.on('error', stream => {
      const [item, error] = JSON.parse(stream);
      toast.error(`${item?.id}: Error: ${error}`);
    });

    socket.value.on('completed', stream => {
      const item = JSON.parse(stream);

      console.log(item)
      if (true === stateStore.has('queue', item._id)) {
        stateStore.remove('queue', item._id);
      }

      stateStore.add('history', item._id, item);
    });

    socket.value.on('canceled', stream => {
      const id = JSON.parse(stream);

      if (true !== stateStore.has('queue', id)) {
        console.log(stream)
        return
      }

      toast.info(`Download canceled: ${ag(stateStore.get('queue', id, {}), 'title')}`);

      if (true === stateStore.has('queue', id)) {
        stateStore.remove('queue', id);
      }
    });

    socket.value.on('cleared', stream => {
      const id = JSON.parse(stream);

      if (true !== stateStore.has('history', id)) {
        console.log(stream)
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
  }

  const on = (event, callback) => socket.value.on(event, callback);
  const off = (event, callback) => socket.value.off(event, callback);
  const emit = (event, data) => socket.value.emit(event, data);

  if (false === isConnected.value) {
    connect();
  }

  return { connect, on, off, emit, socket, isConnected };
});