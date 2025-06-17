<template>
  <main class="columns mt-2 is-multiline">
    <div class="column is-12" v-if="form?.url && is_yt_handle(form.url)">
      <Message title="Warning" class="is-background-warning-80 has-text-dark" icon="fas fa-info-circle">
        <span>
          <ul>
            <li>You are using a YouTube link with handle instead of channel_id. To activate RSS feed support for
              channel, you need to use
              the channel ID. For example, <code>https://www.youtube.com/channel/UCUi3_cffYenmMTuWEsLHzqg</code>
            </li>
            <li>
              To get youtube channel_id simply visit the page, click on <b>more about this channel</b>, scroll down to
              <b>share
                channel</b>, click on <code>Copy channel id</code>.
            </li>
          </ul>
        </span>
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
                    <span>The name is used to identify this specific task.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="url">
                    <span class="icon"><i class="fa-solid fa-link" /></span>
                    URL
                  </label>
                  <div class="control has-icons-left">
                    <input type="url" class="input" id="url" v-model="form.url" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-link" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The channel or playlist URL. For youtube there is rss feed support if you use URL with
                      channel_id or playlist_id. For example, https://www.youtube.com/<span
                        class="has-text-danger">channel/UCUi3_cffYenmMTuWEsLHzqg</span>
                    </span>
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
                    <span>Select the preset to use for this URL. <span class="text-has-danger">If the
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
                    <span>
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
                    <input type="text" class="input" id="folder" placeholder="Leave empty to use default download path"
                      v-model="form.folder" :disabled="addInProgress" list="folders">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Current download folder: <code>{{ get_download_folder() }}</code>. All folders are
                      sub-folders of <code>{{ config.app.download_path }}</code>.</span>
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
                      placeholder="Leave empty to use default template." v-model="form.template">
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Current output format: <code>{{ get_output_template() }}</code>.</span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="cli_options">
                    <span class="icon"><i class="fa-solid fa-terminal" /></span>
                    Command options for yt-dlp
                  </label>
                  <div class="control">
                    <textarea type="text" class="textarea is-pre" v-model="form.cli" id="cli_options"
                      :disabled="addInProgress"
                      placeholder="command options to use, e.g. --no-embed-metadata --no-embed-thumbnail" />
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>yt-dlp cli arguments. Check <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#general-options">this page</NuxtLink>.
                      For more info. <span class="has-text-danger">Not all options are supported some are ignored. Use
                        with caution those arguments can break yt-dlp or the frontend.</span>
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
      <Message title="Tips" class="is-background-info-80 has-text-dark" icon="fas fa-info-circle">
        <span>
          <ul>
            <li>To enable YouTube RSS feed monitoring, The task URL must include a <code>channel_id</code> or
              <code>playlist_id</code>. Other link types won’t work.
            </li>
            <li>RSS monitoring runs every hour alongside the actual task execution. It checks each feed for new videos
              and automatically queues any you haven’t downloaded yet.</li>
            <li>To opt out of RSS monitoring for a specific task, append <code>[no_handler]</code> to that task’s name.
            </li>
            <li>To have the task only monitor RSS, set a timer and add <code>[only_handler]</code> to that task’s name.
            </li>
            <li>RSS Feed monitoring will only work if you have <code>--download-archive</code> set in command options
              for ytdlp.cli, preset or task.</li>
            <li>If you don't have <code>--download-archive</code> set but <code>YTP_KEEP_ARCHIVE</code> environment
              option is set to <code>true</code> which is the default, It will also work.
            </li>
          </ul>
        </span>
      </Message>
    </div>

    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
  </main>
</template>

<script setup>
import { useStorage } from '@vueuse/core'
import { CronExpressionParser } from 'cron-parser'

const props = defineProps({
  reference: {
    type: String,
    required: false,
    default: null,
  },
  task: {
    type: Object,
    required: true,
  },
  addInProgress: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emitter = defineEmits(['cancel', 'submit'])

const toast = useNotification()
const config = useConfigStore()
const box = useConfirm()
const showImport = useStorage('showImport', false)

const import_string = ref('')

const CHANNEL_REGEX = /^https?:\/\/(?:www\.)?youtube\.com\/(?:(?:channel\/(?<channelId>UC[0-9A-Za-z_-]{22}))|(?:c\/(?<customName>[A-Za-z0-9_-]+))|(?:user\/(?<userName>[A-Za-z0-9_-]+))|(?:@(?<handle>[A-Za-z0-9_-]+)))\/?$/;

const form = reactive(props.task)

onMounted(() => {
  if (!props.task?.preset || '' === props.task.preset) {
    form.preset = toRaw(config.app.default_preset)
  }
})

const checkInfo = async () => {
  const required = ['name', 'url']
  for (const key of required) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`)
      return
    }
  }

  if (form.timer) {
    try {
      CronExpressionParser.parse(form.timer)
    } catch (e) {
      console.error(e)
      toast.error(`Invalid CRON expression. ${e.message}`)
      return
    }
  }

  try {
    new URL(form.url)
  } catch (e) {
    toast.error('Invalid URL')
    return
  }

  if (form?.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli)
    if (null === options) {
      return
    }
    form.cli = form.cli.trim(" ")
  }

  emitter('submit', { reference: toRaw(props.reference), task: toRaw(form) })
}

const importItem = async () => {
  let val = import_string.value.trim()
  if (!val) {
    toast.error('The import string is required.')
    return
  }

  if (false === val.startsWith('{')) {
    try {
      val = base64UrlDecode(val)
    } catch (e) {
      console.error(e)
      toast.error(`Failed to decode string. ${e.message}`)
      return
    }
  }

  try {
    const item = JSON.parse(val)

    if ('task' !== item._type) {
      toast.error(`Invalid import string. Expected type 'task', got '${item._type}'.`)
      import_string.value = ''
      return
    }

    if (form.url || form.timer) {
      if (false === box.confirm('This will overwrite the current form fields. Are you sure?', true)) {
        return
      }
    }

    if (item.name) {
      form.name = item.name
    }

    if (item.url) {
      form.url = item.url
    }

    if (item.template) {
      form.template = item.template
    }

    if (item.timer) {
      form.timer = item.timer
    }

    if (item.folder) {
      form.folder = item.folder
    }

    if (item.cli) {
      form.cli = item.cli
    }

    if (item.preset) {
      //  -- check if the preset exists in config.presets
      const preset = config.presets.find(p => p.name === item.preset)
      if (!preset) {
        toast.warning(`Preset '${item.preset}' not found. Preset will be set to default.`)
        form.preset = 'default'
      } else {
        form.preset = item.preset
      }
    }

    import_string.value = ''
  } catch (e) {
    console.error(e)
    toast.error(`Failed to import string. ${e.message}`)
  }
}

const convertOptions = async args => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.template = response.output_template
    }

    if (response.download_path) {
      form.folder = response.download_path
    }

    return response.opts
  } catch (e) {
    toast.error(e.message)
  }

  return null
}

const hasFormatInConfig = computed(() => {
  if (!form?.cli) {
    return false
  }

  return /(?<!\S)(-f|--format)(=|\s)(\S+)/.test(form.cli)
})

const filter_presets = (flag = true) => config.presets.filter(item => item.default === flag)

const get_download_folder = () => {
  if (form.preset && !hasFormatInConfig.value) {
    const preset = config.presets.find(p => p.name === form.preset)
    if (preset && preset.folder) {
      return preset.folder.replace(config.app.download_path, '')
    }
  }
  return '/'
}

const get_output_template = () => {
  if (form.preset && !hasFormatInConfig.value) {
    const preset = config.presets.find(p => p.name === form.preset)
    if (preset && preset.template) {
      return preset.template
    }
  }
  return config.app.output_template || '%(title)s.%(ext)s'
}

function is_yt_handle(url) {
  let m = url.match(CHANNEL_REGEX);
  if (m?.groups) {
    if (m.groups?.channelId) {
      return false
    }
    return true
  }
  return false
}
</script>
