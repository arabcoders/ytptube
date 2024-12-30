const CONFIG_KEYS = {
  showForm: false,
  app: {
    download_path: '/downloads',
    keep_archive: false,
    remove_files: false,
    ui_update_title: true,
    output_template: '',
    ytdlp_version: '',
    max_workers: 1,
    version: '',
    url_host: '',
    url_prefix: '',
  },
  presets: [
    {
      'name': 'Default - Use default yt-dlp format',
      'format': 'default',
      'postprocessors': [],
      'args': {}
    }
  ],
  folders: [],
  tasks: [],
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
