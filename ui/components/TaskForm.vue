<template>
  <main class="columns mt-2 is-multiline">
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
                  Import string
                </label>

                <div class="field has-addons">
                  <div class="control has-icons-left is-expanded">
                    <input type="text" class="input" id="import_string" v-model="import_string" autocomplete="off">
                    <span class="icon is-small is-left"><i class="fa-solid fa-t" /></span>
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
                  <label class="label is-inline" for="name" v-text="'Name'" />
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-user" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Task name is used to identify the task in the task list and in logs.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="url" v-text="'URL'" />
                  <div class="control has-icons-left">
                    <input type="url" class="input" id="url" v-model="form.url" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-link" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>The channel or playlist URL.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="preset">Preset</label>
                  <div class="control has-icons-left">
                    <div class="select is-fullwidth">
                      <select id="preset" class="is-fullwidth" v-model="form.preset"
                        :disabled="addInProgress || hasFormatInConfig"
                        v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the command arguments for yt-dlp.' : ''">
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
                    <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Select the preset to use for this URL. <span class="text-has-danger">If the
                        <code>-f, --format</code> argument is present in the command line options, the preset and all
                        it's options will be ignored.</span>
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="timer">
                    CRON expression timer.
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="timer" placeholder="leave empty to run once every hour."
                      v-model="form.timer" :disabled="addInProgress">
                    <span class="icon is-small is-left"><i class="fa-solid fa-clock" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>
                      The CRON timer expression to use for this task. If not set, the task will run once an hour in a
                      random
                      minute. For more information on CRON expressions, see <NuxtLink to="https://crontab.guru/"
                        target="_blank">crontab.guru</NuxtLink>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="folder">
                    Download path
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="folder" placeholder="Leave empty to use default download path"
                      v-model="form.folder" :disabled="addInProgress" list="folders">
                    <span class="icon is-small is-left"><i class="fa-solid fa-folder" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Paths are relative to global download path, defaults to preset download path if set otherwise,
                      fallback root path if not set.</span>
                  </span>
                </div>
              </div>

              <div class="column is-6-tablet is-12-mobile">
                <div class="field">
                  <label class="label is-inline" for="output_template">
                    Output template
                  </label>
                  <div class="control has-icons-left">
                    <input type="text" class="input" id="output_template" :disabled="addInProgress"
                      placeholder="Leave empty to use default template." v-model="form.template">
                    <span class="icon is-small is-left"><i class="fa-solid fa-file" /></span>
                  </div>
                  <span class="help">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use this output template if non are given with URL. if not set, it will defaults to
                      <code>{{ config.app.output_template }}</code>.
                      For more information <NuxtLink href="https://github.com/yt-dlp/yt-dlp#output-template"
                        target="_blank">visit this url</NuxtLink>.
                    </span>
                  </span>
                </div>
              </div>

              <div class="column is-12">
                <div class="field">
                  <label class="label is-inline" for="cli_options">
                    Command arguments for yt-dlp
                  </label>
                  <div class="control">
                    <input type="text" class="input" v-model="form.cli" id="cli_options" :disabled="addInProgress"
                      placeholder="command options to use, e.g. --no-embed-metadata --no-embed-thumbnail">
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
    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
  </main>
</template>

<script setup>
import { useStorage } from '@vueuse/core'
import { CronExpressionParser } from 'cron-parser'

const emitter = defineEmits(['cancel', 'submit']);
const toast = useToast();
const config = useConfigStore();
const showImport = useStorage('showImport', false);
const import_string = ref('');

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

const form = reactive(props.task);

onMounted(() => {
  if (!props.task?.preset || '' === props.task.preset) {
    form.preset = toRaw(config.app.default_preset);
  }
})

const checkInfo = async () => {
  const required = ['name', 'url'];
  for (const key of required) {
    if (!form[key]) {
      toast.error(`The ${key} field is required.`);
      return;
    }
  }

  if (form.timer) {
    try {
      CronExpressionParser.parse(form.timer);
    } catch (e) {
      console.log(e)
      toast.error(`Invalid CRON expression. ${e.message}`);
      return;
    }
  }

  try {
    new URL(form.url);
  } catch (e) {
    toast.error('Invalid URL');
    return;
  }

  if (form?.cli && '' !== form.cli) {
    const options = await convertOptions(form.cli);
    if (null === options) {
      return
    }
    form.cli = form.cli.trim(" ")
  }

  emitter('submit', { reference: toRaw(props.reference), task: toRaw(form) });
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
      if (false === confirm('This will overwrite the current form fields. Are you sure?')) {
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

  return null;
}

const hasFormatInConfig = computed(() => {
  if (!form?.cli) {
    return false
  }

  return /(?<!\w)(-f|--format)(=|:)?(?!\w)/.test(form.cli)
})

const filter_presets = (flag = true) => config.presets.filter(item => item.default === flag)

</script>
