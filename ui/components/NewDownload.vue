<template>
  <main class="columns mt-2">
    <div class="column">
      <form autocomplete="off" @submit.prevent="addDownload">
        <div class="box">
          <div class="columns is-multiline is-mobile">
            <div class="column is-12">
              <div class="control has-icons-left">
                <input type="text" class="input" id="url" placeholder="Video or playlist link"
                  :disabled="!socket.isConnected || addInProgress" v-model="url">
                <span class="icon is-small is-left">
                  <i class="fa-solid fa-link" />
                </span>
              </div>
            </div>
            <div class="column is-4-tablet is-12-mobile" v-if="!config.app.basic_mode">
              <div class="field has-addons">
                <div class="control">
                  <a href="#" class="button is-static">Preset</a>
                </div>
                <div class="control is-expanded">
                  <div class="select is-fullwidth">
                    <select id="preset" class="is-fullwidth"
                      :disabled="!socket.isConnected || addInProgress || hasFormatInConfig" v-model="selectedPreset"
                      v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the Command arguments for yt-dlp.' : ''">
                      <option v-for="item in config.presets" :key="item.name" :value="item.name">
                        {{ item.name }}
                      </option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
            <div class="column is-6-tablet is-12-mobile" v-if="!config.app.basic_mode">
              <div class="field has-addons" v-tooltip="'Folder relative to ' + config.app.download_path">
                <div class="control">
                  <a href="#" class="button is-static">Save in</a>
                </div>
                <div class="control is-expanded">
                  <input type="text" class="input is-fullwidth" id="path" v-model="downloadPath" placeholder="Default"
                    :disabled="!socket.isConnected || addInProgress" list="folders">
                </div>
              </div>
            </div>
            <div class="column">
              <button type="submit" class="button is-primary"
                :class="{ 'is-loading': !socket.isConnected || addInProgress }"
                :disabled="!socket.isConnected || addInProgress || !url">
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

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-inline" for="output_format"
                  v-tooltip="'Default Format: ' + config.app.output_template">
                  Output Template
                </label>
                <div class="control has-icons-left">
                  <input type="text" class="input" v-model="output_template" id="output_format"
                    :disabled="!socket.isConnected || addInProgress"
                    placeholder="Uses default output template naming if empty.">
                  <span class="icon is-small is-left"><i class="fa-solid fa-file" /></span>
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
                <label class="label is-inline" for="cli_options">
                  Command arguments for yt-dlp
                </label>
                <div class="control has-icons-left">
                  <input type="text" class="input" v-model="ytdlp_cli" id="cli_options"
                    :disabled="!socket.isConnected || addInProgress"
                    placeholder="command options to use, e.g. --no-embed-metadata --no-embed-thumbnail">
                  <span class="icon is-small is-left"><i class="fa-solid fa-terminal" /></span>
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

            <div class="column is-12">
              <div class="field">
                <label class="label is-inline" for="ytdlpCookies" v-tooltip="'Netscape HTTP Cookie format'">
                  Cookies
                </label>
                <div class="control">
                  <textarea class="textarea is-pre" id="ytdlpCookies" v-model="ytdlpCookies"
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
              <button type="button" class="button is-info" @click="emitter('getInfo', url)"
                :class="{ 'is-loading': !socket.isConnected }" :disabled="!socket.isConnected || addInProgress || !url">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>Information</span>
              </button>
            </div>
            <div class="column is-6-tablet is-6-mobile has-text-right">
              <div class="field">
                <div class="control">
                  <button type="button" class="button is-danger" @click="resetConfig" :disabled="!socket.isConnected"
                    v-tooltip="'This configuration are stored locally in your browser.'">
                    <span class="icon">
                      <i class="fa-solid fa-trash" />
                    </span>
                    <span>Reset Local Configuration</span>
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

const emitter = defineEmits(['getInfo'])
const config = useConfigStore()
const socket = useSocketStore()
const toast = useToast()

const selectedPreset = useStorage('selectedPreset', config.app.default_preset)
const ytdlpCookies = useStorage('ytdlp_cookies', '')
const ytdlp_cli = useStorage('ytdlp_cli', '')
const output_template = useStorage('output_template', null)
const downloadPath = useStorage('downloadPath', null)
const url = useStorage('downloadUrl', null)
const showAdvanced = useStorage('show_advanced', false)
const addInProgress = ref(false)

const addDownload = async () => {
  // -- send request to convert cli options to JSON
  if (ytdlp_cli.value && '' !== ytdlp_cli.value) {
    const options = await convertOptions(ytdlp_cli.value)
    if (null === options) {
      return
    }
  }

  addInProgress.value = true

  url.value.split(',').forEach(url => {
    if (!url.trim()) {
      return
    }
    socket.emit('add_url', {
      url: url,
      preset: config.app.basic_mode ? config.app.default_preset : selectedPreset.value,
      folder: config.app.basic_mode ? null : downloadPath.value,
      cookies: config.app.basic_mode ? '' : ytdlpCookies.value,
      template: config.app.basic_mode ? null : output_template.value,
      cli: config.app.basic_mode ? null : ytdlp_cli.value,
    })
  })
}

const resetConfig = () => {
  if (true !== confirm('Reset your local configuration?')) {
    return
  }

  selectedPreset.value = config.app.default_preset.value
  ytdlpCookies.value = ''
  output_template.value = null
  url.value = null
  downloadPath.value = null
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

  url.value = ''
}

const unlockDownload = async stream => {
  const json = JSON.parse(stream)
  if (!json?.data) {
    return
  }
  if ("unlock" in json.data && json.data.unlock === true) {
    addInProgress.value = false
  }
}

const convertOptions = async args => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      output_template.value = response.output_template
    }

    if (response.download_path) {
      downloadPath.value = response.download_path
    }

    return response.opts
  } catch (e) {
    toast.error(e.message)
  }

  return null;
}

onMounted(() => {
  socket.on('status', statusHandler)
  socket.on('error', unlockDownload)
  if ('' === selectedPreset.value) {
    selectedPreset.value = config.app.default_preset.value
  }
})

onUnmounted(() => {
  socket.off('status', statusHandler)
  socket.off('error', unlockDownload)
})

const hasFormatInConfig = computed(() => {
  if (!ytdlp_cli.value) {
    return false
  }
  if (ytdlp_cli.value.includes('-f') || ytdlp_cli.value.includes('--format')) {
    return true
  }
})
</script>
