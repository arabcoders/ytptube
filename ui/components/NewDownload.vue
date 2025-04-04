<template>
  <main class="columns mt-2">
    <div class="column">
      <form autocomplete="off" @submit.prevent="addDownload">
        <div class="box">
          <div class="columns is-multiline is-mobile">
            <div class="column is-12">
              <label class="label is-inline is-unselectable" for="url">
                <span class="icon"><i class="fa-solid fa-link" /></span>
                URLs
              </label>
              <div class="control">
                <input type="text" class="input" id="url" placeholder="Video or playlist link"
                  :disabled="!socket.isConnected || addInProgress" v-model="form.url">
              </div>
              <span class="help">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>You can add multiple URLs separated by a comma <code>,</code>.</span>
              </span>
            </div>
            <div class="column is-4-tablet is-12-mobile" v-if="!config.app.basic_mode">
              <div class="field has-addons">
                <div class="control">
                  <a href="#" class="button is-static">
                    <span class="icon"><i class="fa-solid fa-sliders" /></span>
                    <span>Preset</span>
                  </a>
                </div>
                <div class="control is-expanded">
                  <div class="select is-fullwidth">
                    <select id="preset" class="is-fullwidth"
                      :disabled="!socket.isConnected || addInProgress || hasFormatInConfig" v-model="form.preset"
                      v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the Command arguments for yt-dlp.' : ''">
                      <optgroup label="Custom presets" v-if="config?.presets.filter(p => !p?.default).length > 0">
                        <option v-for="item in filter_presets(false)" :key="item.name" :value="item.name">
                          {{ item.name }}
                        </option>
                      </optgroup>
                      <optgroup label="Default presets">
                        <option v-for="item in filter_presets(true)" :key="item.name" :value="item.name">
                          {{ item.name }}
                        </option>
                      </optgroup>
                    </select>
                  </div>
                </div>
              </div>
            </div>
            <div class="column is-6-tablet is-12-mobile" v-if="!config.app.basic_mode">
              <div class="field has-addons" v-tooltip="'Folder relative to ' + config.app.download_path">
                <div class="control">
                  <a href="#" class="button is-static">
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    <span>Save in</span>
                  </a>
                </div>
                <div class="control is-expanded">
                  <input type="text" class="input is-fullwidth" id="path" v-model="form.folder" placeholder="Default"
                    :disabled="!socket.isConnected || addInProgress" list="folders">
                </div>
              </div>
            </div>
            <div class="column">
              <button type="submit" class="button is-primary"
                :class="{ 'is-loading': !socket.isConnected || addInProgress }"
                :disabled="!socket.isConnected || addInProgress || !form?.url">
                <span class="icon"><i class="fa-solid fa-plus" /></span>
                <span>Add</span>
              </button>
            </div>
            <div class="column" v-if="!config.app.basic_mode">
              <button type="button" class="button is-info" @click="showAdvanced = !showAdvanced"
                :class="{ 'is-loading': !socket.isConnected }" :disabled="!socket.isConnected">
                <span class="icon"><i class="fa-solid fa-cog" /></span>
                <span>Opts</span>
              </button>
            </div>
          </div>
          <div class="columns is-multiline is-mobile" v-if="showAdvanced && !config.app.basic_mode">
            <div class="column is-12">
              <div class="field">
                <label class="label is-inline is-unselectable" for="output_format"
                  v-tooltip="'Default: ' + config.app.output_template">
                  <span class="icon"><i class="fa-solid fa-file" /></span>
                  Output Template
                </label>
                <div class="control">
                  <input type="text" class="input" v-model="form.template" id="output_format"
                    :disabled="!socket.isConnected || addInProgress"
                    placeholder="Uses default output template naming if empty.">
                </div>
                <span class="help">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>All output template naming options can be found at <NuxtLink target="_blank"
                      to="https://github.com/yt-dlp/yt-dlp#output-template">this page</NuxtLink>.</span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline is-unselectable" for="cli_options">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  Command arguments for yt-dlp
                </label>
                <div class="control">
                  <textarea class="textarea is-pre" v-model="form.cli" id="cli_options"
                    :disabled="!socket.isConnected || addInProgress"
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

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline is-unselectable" for="ytdlpCookies">
                  <span class="icon"><i class="fa-solid fa-cookie" /></span>
                  Cookies
                </label>
                <div class="control">
                  <textarea class="textarea is-pre" id="ytdlpCookies" v-model="form.cookies"
                    :disabled="!socket.isConnected || addInProgress" />
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
            <div class="column is-6-tablet is-4-mobile has-text-left">
              <button type="button" class="button is-info" @click="emitter('getInfo', form.url)"
                :class="{ 'is-loading': !socket.isConnected }"
                :disabled="!socket.isConnected || addInProgress || !form?.url">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Information</span>
              </button>
            </div>
            <div class="column is-6-tablet is-6-mobile has-text-right">
              <div class="field is-grouped is-justify-self-end">
                <div class="control">
                  <button type="button" class="button is-danger" @click="resetConfig"
                    :disabled="!socket.isConnected || form?.id" v-tooltip="'Reset local settings'">
                    <span class="icon"><i class="fa-solid fa-rotate-left" /></span>
                    <span>Reset</span>
                  </button>
                </div>
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
import { useStorage } from '@vueuse/core'

const props = defineProps({
  item: {
    type: Object,
    required: false,
    default: () => { },
  },
})

const emitter = defineEmits(['getInfo', 'clear_form'])
const config = useConfigStore()
const socket = useSocketStore()
const toast = useToast()

const showAdvanced = useStorage('show_advanced', false)
const addInProgress = ref(false)

const form = useStorage('local_config', {
  id: null,
  url: '',
  preset: config.app.default_preset,
  cookies: '',
  cli: '',
  template: '',
  folder: '',
})

const addDownload = async () => {
  if (form.value?.cli && '' !== form.value.cli) {
    const options = await convertOptions(form.value.cli)
    if (null === options) {
      return
    }
  }

  addInProgress.value = true

  form.value.url.split(',').forEach(url => {
    if (!url.trim()) {
      return
    }
    socket.emit('add_url', {
      url: url,
      preset: config.app.basic_mode ? config.app.default_preset : form.value.preset,
      folder: config.app.basic_mode ? null : form.value.folder,
      template: config.app.basic_mode ? null : form.value.template,
      cookies: config.app.basic_mode ? '' : form.value.cookies,
      cli: config.app.basic_mode ? null : form.value.cli,
    })
  })
}

const resetConfig = () => {
  if (true !== confirm('Reset your local configuration?')) {
    return
  }

  form.value = {
    id: null,
    url: '',
    preset: config.app.default_preset,
    cookies: '',
    cli: '',
    template: '',
    folder: '',
  }

  showAdvanced.value = false

  toast.success('Local configuration has been reset.')
}

const statusHandler = async stream => {
  const { status, msg } = JSON.parse(stream)

  addInProgress.value = false

  if ('error' === status) {
    toast.error(msg)
    return
  }

  form.value.url = ''
}

const unlockDownload = async stream => {
  const json = JSON.parse(stream)
  if (!json?.data) {
    return
  }
  if ("unlock" in json.data && true === json.data.unlock) {
    addInProgress.value = false
  }
}

const convertOptions = async args => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.value.template = response.output_template
    }

    if (response.download_path) {
      form.value.folder = response.download_path
    }

    return response.opts
  } catch (e) {
    toast.error(e.message)
  }

  return null;
}

onMounted(async () => {
  socket.on('status', statusHandler)
  socket.on('error', unlockDownload)

  await nextTick()

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset
  }

  if (props?.item) {
    Object.keys(props.item).forEach(key => {
      console.log(key, form.value[key], props.item[key])
      if (key in form.value) {
        form.value[key] = props.item[key]
      }
    })
    emitter('clear_form');
  }
})

onUnmounted(() => {
  socket.off('status', statusHandler)
  socket.off('error', unlockDownload)
})

const hasFormatInConfig = computed(() => {
  if (!form?.value?.value) {
    return false
  }

  return /(?<!\S)(-f|--format)(=|\s)(\S+)/.test(form.value.cli)
})

const filter_presets = (flag = true) => config.presets.filter(item => item.default === flag)
</script>
