import { useStorage } from '@vueuse/core'
import type { ConfigState } from '~/types/config';
import type { DLField } from '~/types/dl_fields';
import type { Preset } from '~/types/presets';
import type { ConfigFeature, ConfigUpdateAction } from '~/types/sockets';
import { request } from '~/utils';

export const useConfigStore = defineStore('config', () => {
  const state = reactive<ConfigState>({
    showForm: useStorage('showForm', true),
    app: {
      download_path: '/downloads',
      remove_files: false,
      ui_update_title: true,
      output_template: '',
      ytdlp_version: '',
      max_workers: 20,
      max_workers_per_extractor: 2,
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
      simple_mode: false,
      default_pagination: 50,
      check_for_updates: true,
      new_version: '',
      yt_new_version: '',
    },
    presets: [
      {
        'name': 'default',
        'description': 'Default preset',
        'folder': '',
        'template': '',
        'cookies': '',
        'cli': '',
        'default': true,
        'priority': 0
      }
    ],
    dl_fields: [],
    folders: [],
    ytdlp_options: [],
    paused: false,
    is_loaded: false,
    is_loading: false,
  });

  const loadConfig = async () => {
    if (state.is_loading) {
      return;
    }
    state.is_loaded = false;
    state.is_loading = true;
    try {
      const resp = await request('/api/system/configuration');
      if (!resp.ok) {
        return;
      }
      const data = await resp.json();
      const stateStore = useStateStore();

      if ('number' === typeof data.history_count) {
        stateStore.setHistoryCount(data.history_count);
        delete data.history_count;
      }

      if (data.queue) {
        stateStore.addAll('queue', data.queue);
        delete data.queue;
      }

      setAll(data);
    } catch (e: any) {
      console.error('Failed to load configuration', e);
    }
    finally {
      state.is_loaded = true;
      state.is_loading = false;
    }
  }

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
  const isLoaded = () => state.is_loaded

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

  const patch = (feature: ConfigFeature, action: ConfigUpdateAction, data: unknown): void => {
    const supportedFeatures: ConfigFeature[] = ['dl_fields', 'presets']

    if (!supportedFeatures.includes(feature)) {
      return
    }

    if ('presets' === feature) {
      if ('replace' === action) {
        state.presets = data as Array<Preset>
      }
      return
    }

    if ('dl_fields' === feature) {
      const item = data as DLField
      const current = get(feature, []) as Array<DLField>

      if ('create' === action) {
        current.push(item)
        return
      }

      if ('delete' === action) {
        const index = current.findIndex(i => i.id === item.id)
        if (-1 !== index) {
          current.splice(index, 1)
        }
        return
      }

      if ('update' === action) {
        const target = current.find(i => i.id === item.id)
        if (target) {
          Object.assign(target, item)
        }
        return
      }
      if ('replace' === action) {
        state.dl_fields = data as Array<DLField>
        return
      }
      return
    }
  }

  return {
    ...toRefs(state), add, get, update, getAll, setAll, isLoaded, patch, loadConfig
  } as { [K in keyof ConfigState]: Ref<ConfigState[K]> } & {
    add: typeof add
    get: typeof get
    update: typeof update
    getAll: typeof getAll
    setAll: typeof setAll
    patch: typeof patch
    isLoaded: typeof isLoaded
    loadConfig: typeof loadConfig
  }
});
