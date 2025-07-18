import { io } from "socket.io-client";
import { ag } from "~/utils/index"
import type { Socket as IOSocket, SocketOptions } from "socket.io-client"
import type { ManagerOptions } from "socket.io-client";

export const useSocketStore = defineStore('socket', () => {
  const runtimeConfig = useRuntimeConfig()
  const config = useConfigStore()
  const stateStore = useStateStore()
  const toast = useNotification()

  const socket = ref<IOSocket | null>(null)
  const isConnected = ref<boolean>(false)

  const connect = () => {
    let opts = {
      transports: ['websocket', 'polling'],
      withCredentials: true,
    } as Partial<ManagerOptions & SocketOptions>

    let url = runtimeConfig.public.wss

    if ('development' !== runtimeConfig.public?.APP_ENV) {
      url = window.origin;
      opts.path = `${runtimeConfig.app.baseURL.replace(/\/$/, '')}/socket.io`;
    }

    socket.value = io(url, opts)

    socket.value.on('connect', () => isConnected.value = true);
    socket.value.on('disconnect', () => isConnected.value = false);

    socket.value.on('connected', stream => {
      const json = JSON.parse(stream)

      config.setAll({
        app: json.data.config,
        tasks: json.data.tasks,
        folders: json.data.folders,
        presets: json.data.presets,
        paused: Boolean(json.data.paused)
      })

      stateStore.addAll('queue', json.data.queue || {})
      stateStore.addAll('history', json.data.done || {})
    })

    socket.value.on('added', stream => {
      const json = JSON.parse(stream);
      stateStore.add('queue', json.data._id, json.data);
      toast.success(`Item queued: ${ag(stateStore.get('queue', json.data._id, {}), 'title')}`);
    });

    ['log_info', 'log_success', 'log_warning', 'log_error'].forEach(event => socket.value?.on(event, stream => {
      const json = JSON.parse(stream);
      const message = json?.message || json?.data?.message;
      const data = json.data?.data || json.data || {};
      switch (event) {
        case 'log_info':
          toast.info(message, data);
          break;
        case 'log_success':
          toast.success(message, data);
          break;
        case 'log_warning':
          toast.warning(message, data);
          break;
        case 'log_error':
          toast.error(message, data);
          break;
      }
    }));

    socket.value.on('completed', stream => {
      const json = JSON.parse(stream);

      if (true === stateStore.has('queue', json.data._id)) {
        stateStore.remove('queue', json.data._id);
      }

      stateStore.add('history', json.data._id, json.data);
    });

    socket.value.on('cancelled', stream => {
      const item = JSON.parse(stream);
      const id = item.data._id

      if (true !== stateStore.has('queue', id)) {
        return
      }

      toast.warning(`Download cancelled: ${ag(stateStore.get('queue', id, {}), 'title')}`);

      if (true === stateStore.has('queue', id)) {
        stateStore.remove('queue', id);
      }
    });

    socket.value.on('cleared', stream => {
      const item = JSON.parse(stream);
      const id = item.data._id

      if (true !== stateStore.has('history', id)) {
        return
      }

      stateStore.remove('history', id);
    });

    socket.value.on("updated", stream => {
      const json = JSON.parse(stream);
      const id = json.data._id;

      if (true === stateStore.has('history', id)) {
        stateStore.update('history', id, json.data);
        return;
      }

      stateStore.update('queue', id, json.data);
    });

    socket.value.on("update", stream => {
      const json = JSON.parse(stream);
      if (true === stateStore.has('history', json.data._id)) {
        stateStore.update('history', json.data._id, json.data);
        return;
      }
    });

    socket.value.on('paused', data => {
      const json = JSON.parse(data);
      const pausedState = Boolean(json.data.paused);
      config.update('paused', pausedState);

      if (false === pausedState) {
        toast.success('Download queue resumed.');
        return;
      }

      toast.warning('Download queue paused.', { timeout: 10000 });
    });

    socket.value.on('presets_update', (data: string) => config.update('presets', JSON.parse(data).data || []));
  }

  const emit = (event: string, data?: any): any => socket.value?.emit(event, data)
  const on = (event: string, callback: (...args: any[]) => void): any => socket.value?.on(event, callback)
  const off = (event: string, callback: (...args: any[]) => void): any => socket.value?.off(event, callback)

  if (false === isConnected.value) {
    connect();
  }

  window.ws = socket.value;

  return { connect, on, off, emit, socket, isConnected };
});
