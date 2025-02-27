<template>
  <main class="columns mt-2">
    <div class="column">
      <form id="taskForm" @submit.prevent="checkInfo()">
        <div class="box">
          <div class="columns is-multiline is-mobile">
            <div class="column is-12">
              <h1 class="title is-6" style="border-bottom: 1px solid #dbdbdb;">
                <span class="icon-text">
                  <span class="icon"><i class="fa-solid" :class="reference ? 'fa-cog' : 'fa-plus'" /></span>
                  <span>{{ reference ? 'Edit' : 'Add' }}</span>
                </span>
              </h1>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="name">
                  Task name
                </label>
                <div class="control has-icons-left">
                  <input type="text" class="input" id="name" v-model="form.name" :disabled="addInProgress">
                  <span class="icon is-small is-left"><i class="fa-solid fa-user" /></span>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Task name is used to identify the task in the task list.</span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="url">
                  URL
                </label>
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
                  <span>Downloads are relative to download path, defaults to root path if not set.</span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="folder">
                  Preset
                </label>
                <div class="control has-icons-left">
                  <div class="select is-fullwidth">
                    <select id="preset" class="is-fullwidth" v-model="form.preset"
                      :disabled="addInProgress || hasFormatInConfig"
                      v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the config.' : ''">
                      <option v-for="item in config.presets" :key="item.name" :value="item.name">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>
                  <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Select the preset to use for this URL. The preset will be ignored if format key is present in
                    config.</span>
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
                <label class="label is-inline" for="output_template">
                  Output template
                </label>
                <div class="control has-icons-left">
                  <input type="text" class="input" id="output_template" placeholder="The output template to use"
                    v-model="form.template" :disabled="addInProgress">
                  <span class="icon is-small is-left"><i class="fa-solid fa-file" /></span>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>The output template to use, if not set, it will defaults to
                    <code>{{ config.app.template }}</code></span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="config" v-tooltip="'Extends current global yt-dlp config. (JSON)'">
                  JSON yt-dlp config or CLI options. <NuxtLink
                    v-if="form.config && (typeof form.config === 'string') && !form.config.trim().startsWith('{')"
                    @click="convertOptions()">Convert to JSON</NuxtLink>
                </label>
                <div class="control">
                  <textarea class="textarea" id="config" v-model="form.config" :disabled="addInProgress"
                    placeholder="--no-embed-metadata --no-embed-thumbnail"></textarea>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span> Extends current global yt-dlp config with given options. Some fields are ignored like
                    <code>cookiefile</code>, <code>paths</code>, and <code>outtmpl</code> etc. Warning: Use with caution
                    some of those options can break yt-dlp or the frontend.</span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="cookies" v-tooltip="'Netscape HTTP Cookie format.'">Cookies</label>
                <div class="control">
                  <textarea class="textarea" id="cookies" v-model="form.cookies" :disabled="addInProgress"></textarea>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Use the <NuxtLink target="_blank"
                      to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp">
                      Recommended addon</NuxtLink> by yt-dlp to export cookies. The cookies MUST be in Netscape HTTP
                    Cookie format.</span>
                </span>
              </div>
            </div>

            <div class="column is-12">
              <div class="field is-grouped is-grouped-right">
                <p class="control">
                  <button class="button is-primary" :disabled="addInProgress" type="submit"
                    :class="{ 'is-loading': addInProgress }" form="taskForm">
                    <span class="icon"><i class="fa-solid fa-save" /></span>
                    <span>Save</span>
                  </button>
                </p>
                <p class="control">
                  <button class="button is-danger" @click="emitter('cancel')" :disabled="addInProgress" type="button">
                    <span class="icon"><i class="fa-solid fa-times" /></span>
                    <span>Cancel</span>
                  </button>
                </p>
              </div>
            </div>

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
import { parseExpression } from 'cron-parser'
import { request } from '~/utils/index'

const emitter = defineEmits(['cancel', 'submit']);
const toast = useToast();
const config = useConfigStore();
const convertInProgress = ref(false);

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
  if (props.task?.config && (typeof props.task.config === 'object')) {
    form.config = JSON.stringify(props.task.config, null, 4);
  }

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
      parseExpression(form.timer);
    } catch (e) {
      toast.error('Invalid CRON expression.');
      return;
    }
  }

  try {
    new URL(form.url);
  } catch (e) {
    toast.error('Invalid URL');
    return;
  }

  if (typeof form.config === 'object') {
    form.config = JSON.stringify(form.config, null, 4);
  }

  if (form.config && form.config && !form.config.trim().startsWith('{')) {
    await convertOptions();
  }

  if (form.config) {
    try {
      form.config = JSON.parse(form.config)
    } catch (e) {
      toast.error(`Invalid JSON yt-dlp config. ${e.message}`)
      return;
    }
  }

  emitter('submit', { reference: toRaw(props.reference), task: toRaw(form) });
}

const convertOptions = async () => {
  if (convertInProgress.value) {
    return
  }

  try {
    convertInProgress.value = true
    const response = await convertCliOptions(form.config)
    form.config = JSON.stringify(response.opts, null, 2)
    if (response.output_template) {
      form.template = response.output_template
    }
    if (response.download_path) {
      form.folder = response.download_path
    }
  } catch (e) {
    toast.error(e.message)
  } finally {
    convertInProgress.value = false
  }
}

const hasFormatInConfig = computed(() => {
  if (!form.config) {
    return false
  }
  try {
    const config = JSON.parse(form.config)
    return "format" in config
  } catch (e) {
    return false
  }
})
</script>
