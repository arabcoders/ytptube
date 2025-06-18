import { useStorage } from '@vueuse/core'

const CONFIG_KEYS = {
  showForm: useStorage('showForm', false),
  app: {
    download_path: '/downloads',
    keep_archive: false,
    remove_files: false,
    ui_update_title: true,
    output_template: '',
    ytdlp_version: '',
    max_workers: 1,
    version: '',
    basic_mode: true,
    default_preset: 'default',
    instance_title: null,
    sentry_dsn: null,
    console_enabled: false,
    browser_enabled: false,
    ytdlp_cli: '',
    file_logging: false,
    is_native: false,
    app_version: '',
    app_commit_sha: '',
    app_build_date: '',
  },
  presets: [
    {
      'name': 'default',
      'format': 'default',
      'folder': '',
      'template': '',
      'cookies': '',
      'cli': '',
      'default': true
    }
  ],
  folders: [],
  tasks: [],
  paused: false,
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
