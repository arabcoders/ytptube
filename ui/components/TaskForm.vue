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
                  Channel or Playlist URL
                </label>
                <div class="control has-icons-left">
                  <input type="url" class="input" id="url" v-model="form.url" :disabled="addInProgress">
                  <span class="icon is-small is-left"><i class="fa-solid fa-link" /></span>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>The YouTube channel or playlist URL</span>
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
                    <select id="preset" class="is-fullwidth" v-model="form.preset" :disabled="addInProgress">
                      <option v-for="item in config.presets" :key="item.name" :value="item.name">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>
                  <span class="icon is-small is-left"><i class="fa-solid fa-tv" /></span>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Select the preset to use for this URL.</span>
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
                    v-model="form.output_template" :disabled="addInProgress">
                  <span class="icon is-small is-left"><i class="fa-solid fa-file" /></span>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>The output template to use, if not set, it will defaults to
                    <code>{{ config.app.output_template }}</code></span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="ytdlp_config"
                  v-tooltip="'Extends current global yt-dlp config. (JSON)'">
                  JSON yt-dlp config or CLI options.
                </label>
                <div class="control">
                  <textarea class="textarea" id="ytdlp_config" v-model="form.ytdlp_config" :disabled="addInProgress"
                    placeholder="--no-embed-metadata --no-embed-thumbnail"></textarea>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Extends current global yt-dlp config with given options. If CLI options are given, they will be
                    converted pre-saving.</span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="ytdlp_cookies" v-tooltip="'JSON exported cookies for downloading.'">
                  yt-dlp Cookies
                </label>
                <div class="control">
                  <textarea class="textarea" id="ytdlp_cookies" v-model="form.ytdlp_cookies"
                    :disabled="addInProgress"></textarea>
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Use <NuxtLink target="_blank" to="https://github.com/jrie/flagCookies">flagCookies</NuxtLink> to
                    extract cookies as JSON string.
                  </span>
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

const emitter = defineEmits(['cancel', 'submit']);
const toast = useToast();
const config = useConfigStore();
const addInProgress = ref(false);
const props = defineProps({
  reference: {
    type: String,
    required: false,
    default: null,
  },
  task: {
    type: Object,
    required: true,
  }
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

  // -- send request to convert cli options to JSON
  if (form.ytdlp_config && form.ytdlp_config.length > 2 && !form.ytdlp_config.trim().startsWith('{')) {
    const response = await fetch(config.app.url_host + config.app.url_prefix + 'api/yt-dlp/convert', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ args: form.ytdlp_config }),
    });

    const data = await response.json()
    if (200 !== response.status) {
      toast.error(`Error: (${response.status}): ${data.error}`)
      return
    }

    form.ytdlp_config = JSON.stringify(data, null, 4)
  }

  // -- check cookies syntax
  if (form.ytdlp_cookies) {
    try {
      JSON.parse(form.ytdlp_cookies);
    } catch (e) {
      toast.error(`Invalid JSON yt-dlp cookies. ${e.message}`)
      return;
    }
  }

  //addInProgress.value = true;
  emitter('submit', { reference: toRaw(props.reference), task: toRaw(form) });
}
</script>
