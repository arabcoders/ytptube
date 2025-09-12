import { useStorage } from '@vueuse/core'
import type { ConfigState } from '~/types/config';

export const useConfigStore = defineStore('config', () => {
  const state = reactive<ConfigState>({
    showForm: useStorage('showForm', false),
    app: {
      download_path: '/downloads',
      remove_files: false,
      ui_update_title: true,
      output_template: '',
      ytdlp_version: '',
      max_workers: 1,
      default_preset: 'default',
      instance_title: null,
      console_enabled: false,
      browser_control_enabled: false,
      file_logging: false,
      is_native: false,
      app_version: '',
      app_commit_sha: '',
      app_build_date: '',
      app_branch: '',
      started: 0,
      app_env: 'production',
    },
    presets: [
      {
        'name': 'default',
        'description': 'Default preset',
        'folder': '',
        'template': '',
        'cookies': '',
        'cli': '',
        'default': true
      }
    ],
    dl_fields: [],
    folders: [],
    ytdlp_options: [],
    paused: false,
    is_loaded: false,
  });

  const add = (key: string, value: any) => {
    if (key.includes('.')) {
      const [parentKey, subKey] = key.split('.') as [keyof ConfigState, string]
      state[parentKey][subKey] = value;
      return;
    }
    (state as any)[key] = value
  }

  const get = (key: string, defaultValue: any = null): any => {
    if (key.includes('.')) {
      const [parentKey, subKey] = key.split('.') as [keyof ConfigState, string]
      const parent = state[parentKey] as any
      return parent?.[subKey] ?? defaultValue
    }
    return (state as any)[key] ?? defaultValue
  }

  const update = add

  const getAll = (): ConfigState => state

  const setAll = (data: Record<string, any>) => {
    Object.keys(data).forEach((key) => {
      if (key.includes('.')) {
        const [parentKey, subKey] = key.split('.') as [keyof ConfigState, string]
        const parent = state[parentKey] as any
        parent[subKey] = data[key]
        return
      }
      (state as any)[key] = data[key]
    })

    state.is_loaded = true
  }

  const isLoaded = () => state.is_loaded

  return {
    ...toRefs(state), add, get, update, getAll, setAll, isLoaded,
  } as { [K in keyof ConfigState]: Ref<ConfigState[K]> } & {
    add: typeof add
    get: typeof get
    update: typeof update
    getAll: typeof getAll
    setAll: typeof setAll
    isLoaded: typeof isLoaded
  }
});
