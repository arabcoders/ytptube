const CONFIG_KEYS = {
  isConnected: false,
  showForm: false,
  showConsole: false,
  showTasks: false,
  tasks: [],
  app: {
    host: '',
    prefix: '',
    keep_archive: false,
    output_template: '',
  },
  presets: [
    {
      name: 'Default - Use Predefined yt-dlp Format',
      format: 'default',
    }
  ],
  directories: [],
};

export const useConfigStore = defineStore('config', () => {
  const state = reactive(CONFIG_KEYS);

  const actions = {
    add(key, value) {
      if (key.includes('.')) {
        const [parentKey, subKey] = key.split('.');
        state[parentKey][subKey] = value;
        return;
      }
      state[key] = value;
    },
    get(key, defaultValue = null) {
      if (key.includes('.')) {
        const [parentKey, subKey] = key.split('.');
        return state[parentKey][subKey] || defaultValue;
      }
      return state[key] || defaultValue;
    },
    update(key, value) {
      if (key.includes('.')) {
        const [parentKey, subKey] = key.split('.');
        state[parentKey][subKey] = value;
        return;
      }
      state[key] = value;
    },
    getAll() {
      return state;
    },
    setAll(data) {
      Object.keys(data).forEach((key) => {
        if (key.includes('.')) {
          const [parentKey, subKey] = key.split('.');
          state[parentKey][subKey] = data[key];
          return;
        }
        state[key] = data[key];
      });
    },
  }

  return { ...toRefs(state), ...actions };
});
