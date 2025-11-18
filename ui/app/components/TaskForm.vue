<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12" v-if="form?.url && is_yt_handle(form.url)">
      <Message title="Information" class="is-info is-background-info-80 has-text-dark" icon="fas fa-info-circle">
        <span>You are using a YouTube link with <b>@handle</b> instead of <b>channel_id</b>. To activate RSS feed
          support for URL click on the <NuxtLink @click="async () => form.url = await convert_url(form.url)"><b>Convert
              URL</b></NuxtLink> link.</span>
      </Message>
    </div>
    <div class="column is-12" v-if="form?.url && is_generic_rss(form.url)">
      <Message title="Information" class="is-info is-background-info-80 has-text-dark" icon="fas fa-info-circle">
        <span>You are using a generic RSS/Atom feed URL. The task handler will automatically download new items found
          in this feed.</span>
      </Message>
    </div>
    <div class="column is-12">
      <form autocomplete="off" id="taskForm" @submit.prevent="checkInfo()">
        <div class="card">

          <div class="card-header">
            <div class="card-header-title is-text-overflow is-block">
              <span class="icon-text">
                <span class="icon"><i class="fa-solid" :class="reference ? 'fa-cog' : 'fa-plus'" /></span>
                <span>{{ reference ? 'Edit' : 'Add' }}</span>
              </span>
            </div>

            <div class="card-header-icon" v-if="reference">
              <button type="button" @click="showImport = !showImport">
                <span class="icon"><i class="fa-solid" :class="{
                  'fa-arrow-down': !showImport,
                  'fa-arrow-up': showImport,
                }" /></span>
                <span>{{ showImport ? 'Hide' : 'Show' }} import</span>
              </button>
            </div>
          </div>

          <div class="card-content">
            <div class="columns is-multiline is-mobile">

              <div class="column is-12" v-if="showImport || !reference">
                <label class="label is-inline" for="import_string">
                  <span class="icon"><i class="fa-solid fa-file-import" /></span>
                  Import string
                </label>

                <div class="field has-addons">
                  <div class="control is-expanded">
                    <input type="text" class="input" id="import_string" v-model="import_string" autocomplete="off">
                  </div>

                  <div class="control">
                    <button class="button is-primary" :disabled="!import_string" type="button" @click="importItem">
                      <span class="icon"><i class="fa-solid fa-add" /></span>
                      <span>Import</span>
                    </button>
                  </div>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>You can use this field to populate the data, using shared string.</span>
                </span>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="name">
                    <span class="icon"><i class="fa-solid fa-user" /></span>
                    Name
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-user" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">The name is used to identify this specific task.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="url">
                    <span class="icon"><i class="fa-solid fa-link" /></span>
                    URL
                    <template v-if="is_yt_handle(form.url)">
                      - <NuxtLink @click="async () => form.url = await convert_url(form.url)">Convert URL</NuxtLink>
                    </template>
                  </label>
                  <div class="control has-icons-left">
                    <input type="url" class="input" id="url" v-model="form.url"
                      :disabled="addInProgress || convertInProgress"
                      placeholder="https://www.youtube.com/channel/UCUi3_cffYenmMTuWEsLHzqg">
                    <span class="icon is-small is-left"><i class="fa-solid fa-link"
                        :class="{ 'fa-spin': convertInProgress }" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">The channel or playlist URL.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="enabled">
                    <span class="icon"><i class="fa-solid fa-power-off" /></span>
                    Enabled
                  </label>
                  <div class="control is-unselectable">
                    <input id="enabled" type="checkbox" v-model="form.enabled" :disabled="addInProgress"
                      class="switch is-success" />
                    <label for="enabled" class="is-unselectable">
                      {{ form.enabled ? 'Yes' : 'No' }}
                    </label>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">Whether the task is enabled.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="auto_start">
                    <span class="icon"><i class="fa-solid fa-circle-play" /></span>
                    Auto Start
                  </label>
                  <div class="control is-unselectable">
                    <input id="auto_start" type="checkbox" v-model="form.auto_start" :disabled="addInProgress"
                      class="switch is-success" />
                    <label for="auto_start" class="is-unselectable">
                      {{ form.auto_start ? 'Yes' : 'No' }}
                    </label>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">Whether to automatically queue and start the download task.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="preset">
                    <span class="icon"><i class="fa-solid fa-sliders" /></span>
                    Preset
                  </label>
                  <div class="control">
                    <div class="select is-fullwidth">
                      <select id="preset" class="is-fullwidth" v-model="form.preset"
                        :disabled="addInProgress || hasFormatInConfig"
                        v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the command options for yt-dlp.' : ''">
                        <optgroup label="Default presets">
                          <option v-for="item in filter_presets(true)" :key="item.name" :value="item.name">
                            {{ item.name }}
                          </option>
                        </optgroup>
                        <optgroup label="Custom presets" v-if="config?.presets.filter(p => !p?.default).length > 0">
                          <option v-for="item in filter_presets(false)" :key="item.name" :value="item.name">
                            {{ item.name }}
                          </option>
                        </optgroup>
                      </select>
                    </div>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">Select the preset to use for this URL. <span class="text-has-danger">If the
                        <code>-f, --format</code> <span class="has-text-danger">
                          argument is present in the command line options, the preset and all
                          it's options will be ignored.</span></span>
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="timer">
                    <span class="icon"><i class="fa-solid fa-clock" /></span>
                    CRON expression timer.
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="timer" v-model="form.timer" :disabled="addInProgress"
                      placeholder="0 12 * * 5">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">
                      The CRON timer expression to use for this task. If not set, the task will be disabled. For more
                      information on CRON expressions, see <NuxtLink to="https://crontab.guru/" target="_blank">
                        crontab.guru</NuxtLink>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="folder">
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    Save in
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="folder" :placeholder="getDefault('folder', '/')"
                      v-model="form.folder" :disabled="addInProgress" list="folders">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">All folders are sub-folders of
                      <code>{{ config.app.download_path }}</code>.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="output_template">
                    <span class="icon"><i class="fa-solid fa-file" /></span>
                    Output template
                  </label>
                  <div class="control">
                    <input type="text" class="input" id="output_template" :disabled="addInProgress"
                      :placeholder="getDefault('template', config.app.output_template || '%(title)s.%(ext)s')"
                      v-model="form.template">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">The template to use for the output file name.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="handler_enabled">
                    <span class="icon"><i class="fa-solid fa-rss" /></span>
                    Enable Handler
                  </label>
                  <div class="control is-unselectable">
                    <input id="handler_enabled" type="checkbox" v-model="form.handler_enabled" :disabled="addInProgress"
                      class="switch is-success" />
                    <label for="handler_enabled" class="is-unselectable">
                      {{ form.handler_enabled ? 'Yes' : 'No' }}
                    </label>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">Some URLs have special handlers to monitor for new content. Like YouTube
                      channels/playlists.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile" v-if="!reference">
                <div class="field">
                  <label class="label is-inline" for="archive_all_after_add">
                    <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                    Mark all existing items as downloaded
                  </label>
                  <div class="control is-unselectable">
                    <input id="archive_all_after_add" type="checkbox" v-model="archiveAllAfterAdd"
                      :disabled="addInProgress" class="switch is-danger" />
                    <label for="archive_all_after_add" class="is-unselectable">
                      {{ archiveAllAfterAdd ? 'Yes' : 'No' }}
                    </label>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span class="is-bold">
                      If enabled, all existing items in the feed will be marked as downloaded after adding the task.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-unselectable" for="cli_options">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    <span>Command options for yt-dlp</span>
                  </label>
                  <TextareaAutocomplete id="cli_options" v-model="form.cli" :options="ytDlpOpt"
                    :placeholder="getDefault('cli', '')" :disabled="addInProgress" />
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      <NuxtLink @click="showOptions = true">View all options</NuxtLink>. Not all options are
                      supported <NuxtLink target="_blank"
                        to="https://github.com/arabcoders/ytptube/blob/master/app/library/Utils.py#L26">some
                        are ignored</NuxtLink>. Use with caution.
                    </span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="card-footer">
            <p class="card-footer-item">
              <button class="button is-fullwidth is-primary" :disabled="addInProgress" type="submit"
                :class="{ 'is-loading': addInProgress }" form="taskForm">
                <span class="icon"><i class="fa-solid fa-save" /></span>
                <span>Save</span>
              </button>
            </p>
            <p class="card-footer-item">
              <button class="button is-fullwidth is-danger" @click="emitter('cancel')" :disabled="addInProgress"
                type="button">
                <span class="icon"><i class="fa-solid fa-times" /></span>
                <span>Cancel</span>
              </button>
            </p>
          </div>
        </div>
      </form>
    </div>

    <div class="column is-12">
      <Message class="is-info" :newStyle="true">
        <span>
          <ul>
            <li><strong>YouTube RSS:</strong> Use <code>channel_id</code> or <code>playlist_id</code> URLs. Other link
              types (custom names, handles, user profiles) are not supported.
            </li>
            <li><strong>Generic RSS/Atom:</strong> URL must end with <code>.rss</code> or <code>.atom</code>. If not
              possible, append <code>&handler=rss</code> to existing query parameters, or add <code>#handler=rss</code>
              as a fragment.
            </li>
            <li><strong>RSS Monitoring Basics:</strong> Runs hourly independently. Timer controls scheduled downloads to
              yt-dlp. Disable <code>Enable Handler</code> to disable RSS monitoring.
            </li>
            <li><strong>Archive Requirement:</strong> RSS monitoring requires <code>--download-archive</code> in
              <code>Command options for yt-dlp</code> (set in task or preset).
            </li>
          </ul>
        </span>
      </Message>
    </div> <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
    <Modal v-if="showOptions" @close="showOptions = false" :contentClass="'modal-content-max'">
      <YTDLPOptions />
    </Modal>
  </main>
</template>

<script lang="ts" setup>
import 'assets/css/bulma-switch.css'
import { useStorage } from '@vueuse/core'
import { CronExpressionParser } from 'cron-parser'
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue'
import type { AutoCompleteOptions } from '~/types/autocomplete'
import type { exported_task, task_item } from '~/types/tasks'
import { useConfirm } from '~/composables/useConfirm'

const props = defineProps<{
  reference?: string | null | undefined
  task: task_item
  addInProgress?: boolean
}>()

const emitter = defineEmits<{
  (e: 'cancel'): void
  (e: 'submit', payload: { reference: string | null | undefined, task: task_item, archive_all?: boolean }): void
}>()

const toast = useNotification()
const config = useConfigStore()
const box = useConfirm()
const showImport = useStorage('showImport', false)

const convertInProgress = ref<boolean>(false)
const import_string = ref<string>('')
const showOptions = ref<boolean>(false)
const ytDlpOpt = ref<AutoCompleteOptions>([])
const archiveAllAfterAdd = ref<boolean>(false)

const CHANNEL_REGEX = /^https?:\/\/(?:www\.)?youtube\.com\/(?:(?:channel\/(?<channelId>UC[0-9A-Za-z_-]{22}))|(?:c\/(?<customName>[A-Za-z0-9_-]+))|(?:user\/(?<userName>[A-Za-z0-9_-]+))|(?:@(?<handle>[A-Za-z0-9_-]+)))(?<suffix>\/.*)?\/?$/
const GENERIC_RSS_REGEX = /\.(rss|atom)(\?.*)?$|handler=rss/i
const form = reactive<task_item>({ ...props.task })

watch(() => config.ytdlp_options, newOptions => ytDlpOpt.value = newOptions
  .filter(opt => !opt.ignored)
  .flatMap(opt => opt.flags
    .filter(flag => flag.startsWith('--'))
    .map(flag => ({ value: flag, description: opt.description || '' }))),
  { immediate: true }
)

onMounted(() => {
  if (!props.task?.preset || '' === props.task.preset) {
    form.preset = toRaw(config.app.default_preset)
  }

  if (typeof form.auto_start === 'undefined' || null === form.auto_start) {
    form.auto_start = true
  }

  if (typeof form.handler_enabled === 'undefined' || null === form.handler_enabled) {
    form.handler_enabled = true
  }

  if (typeof form.enabled === 'undefined' || null === form.enabled) {
    form.enabled = true
  }

})

const checkInfo = async (): Promise<void> => {
  const required = ['name', 'url'] as const
  for (const key of required) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`)
      return
    }
  }

  if (form.timer) {
    try {
      CronExpressionParser.parse(form.timer)
    } catch (e: any) {
      console.error(e)
      toast.error(`Invalid CRON expression. ${e.message}`)
      return
    }
  }

  try {
    new URL(form.url)
  } catch {
    toast.error('Invalid URL')
    return
  }

  if (form.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli)
    if (null === options) return
    form.cli = form.cli.trim()
  }

  emitter('submit', { reference: toRaw(props.reference), task: toRaw(form), archive_all: archiveAllAfterAdd.value })
}

const importItem = async (): Promise<void> => {
  const val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  try {
    const item = decode(val) as exported_task

    if ('task' !== item._type) {
      toast.error(`Invalid import string. Expected type 'task', got '${item._type}'.`)
      import_string.value = ''
      return
    }

    if (form.url || form.timer) {
      if (false === (await box.confirm('Overwrite the current form fields?'))) {
        return
      }
    }

    form.name = item.name ?? form.name
    form.url = item.url ?? form.url
    form.template = item.template ?? form.template
    form.timer = item.timer ?? form.timer
    form.folder = item.folder ?? form.folder
    form.cli = item.cli ?? form.cli
    form.auto_start = item.auto_start ?? true
    form.handler_enabled = item.handler_enabled ?? true
    form.enabled = item.enabled ?? true

    if (item.preset) {
      const preset = config.presets.find(p => p.name === item.preset)
      if (!preset) {
        toast.warning(`Preset '${item.preset}' not found. Preset will be set to default.`)
        form.preset = 'default'
      } else {
        form.preset = item.preset
      }
    }

    import_string.value = ''
  } catch (e: any) {
    console.error(e)
    toast.error(`Failed to import string. ${e.message}`)
  }
}

const convertOptions = async (args: string): Promise<Record<string, any> | null> => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.template = response.output_template
    }

    if (response.download_path) {
      form.folder = response.download_path
    }

    return response.opts as Record<string, any>
  } catch (e: any) {
    toast.error(e.message)
  }

  return null
}

const hasFormatInConfig = computed<boolean>(() => !!form.cli && /(?<!\S)(-f|--format)(=|\s)(\S+)/.test(form.cli))

const filter_presets = (flag = true) => config.presets.filter(item => item.default === flag)

const is_yt_handle = (url: string): boolean => {
  if (!url || '' === url) {
    return false
  }
  const m = url.match(CHANNEL_REGEX)
  if (m?.groups) {
    return !m.groups.channelId
  }
  return false
}

const is_generic_rss = (url: string): boolean => {
  if (!url || '' === url) {
    return false
  }
  return GENERIC_RSS_REGEX.test(url)
}

const convert_url = async (url: string): Promise<string> => {
  if (!url || '' === url) {
    return url
  }

  const m = url.match(CHANNEL_REGEX)
  if (!m?.groups || !m.groups.handle) {
    return url
  }

  const params = new URLSearchParams()
  params.append('url', url)
  params.append('args', '-I0')

  try {
    convertInProgress.value = true
    const resp = await request('/api/yt-dlp/url/info?' + params.toString())
    const body = await resp.json()
    const channel_id = ag(body, 'channel_id', null)

    if (channel_id) {
      return url.replace(`/@${m.groups.handle}`, `/channel/${channel_id}`)
    }
  } catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    convertInProgress.value = false
  }

  return url
}

const getDefault = (type: 'cookies' | 'cli' | 'template' | 'folder', ret: string = '') => {
  if (false !== hasFormatInConfig.value || !form.preset) {
    return ret
  }

  const preset = config.presets.find(p => p.name === form.preset)

  if (!preset) {
    return ret
  }

  if (type === 'cookies' && preset.cookies) {
    return preset.cookies
  }

  if (type === 'cli' && preset.cli) {
    return preset.cli
  }

  if (type === 'template' && preset.template) {
    return preset.template
  }

  if (type === 'folder' && preset.folder) {
    return preset.folder.replace(config.app.download_path, '') || ret
  }

  return ret
}

</script>
