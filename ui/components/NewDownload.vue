<template>
  <main class="columns mt-2">
    <div class="column">
      <div class="box">
        <div class="columns is-multiline is-mobile">
          <div class="column is-12">
            <div class="control has-icons-left">
              <input type="url" class="input" id="url" placeholder="Video or playlist link"
                :disabled="!socket.isConnected || addInProgress" v-model="url">
              <span class="icon is-small is-left">
                <i class="fa-solid fa-link" />
              </span>
            </div>
          </div>
          <div class="column is-4-tablet is-12-mobile">
            <div class="field has-addons">
              <div class="control">
                <a href="#" class="button is-static">Preset</a>
              </div>
              <div class="control is-expanded">
                <div class="select is-fullwidth">
                  <select id="preset" class="is-fullwidth" :disabled="!socket.isConnected" v-model="selectedPreset">
                    <option v-for="item in config.presets" :key="item.name" :value="item.name">
                      {{ item.name }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
          </div>
          <div class="column is-6-tablet is-12-mobile">
            <div class="field has-addons" v-tooltip="'Folder relative to ' + config.app.download_path">
              <div class="control">
                <a href="#" class="button is-static">Save in</a>
              </div>
              <div class="control is-expanded">
                <input type="text" class="input is-fullwidth" id="path" v-model="downloadPath" placeholder="Default"
                  :disabled="!socket.isConnected" list="folders">
              </div>
            </div>
          </div>
          <div class="column">
            <button type="submit" class="button is-primary" @click="addDownload"
              :class="{ 'is-loading': !socket.isConnected || addInProgress }"
              :disabled="!socket.isConnected || addInProgress || !url">
              <span class="icon"><i class="fa-solid fa-plus" /></span>
              <span>Add</span>
            </button>
          </div>
          <div class="column">
            <button type="submit" class="button is-info" @click="showAdvanced = !showAdvanced"
              :class="{ 'is-loading': !socket.isConnected }" :disabled="!socket.isConnected">
              <span class="icon"><i class="fa-solid fa-cog" /></span>
              <span>Opts</span>
            </button>
          </div>
        </div>
        <div class="columns is-multiline is-mobile" v-if="showAdvanced">
          <div class="column is-12">
            <div class="field">
              <label class="label is-inline" for="output_format"
                v-tooltip="'Default Format: ' + config.app.output_template">
                Output Template
              </label>
              <div class="control">
                <input type="text" class="input" v-model="output_template" id="output_format"
                  placeholder="Uses default output template naming if empty.">
              </div>
              <span class="subtitle is-6">
                All output template naming options can be found at <NuxtLink target="_blank" class="has-text-danger"
                  href="https://github.com/yt-dlp/yt-dlp#output-template">this page</NuxtLink>.
              </span>
            </div>
          </div>
          <div class="column is-6-tablet is-12-mobile">
            <div class="field">
              <label class="label is-inline" for="ytdlpConfig"
                v-tooltip="'Extends current global yt-dlp config. (JSON)'">
                JSON yt-dlp config
              </label>
              <div class="control">
                <textarea class="textarea" id="ytdlpConfig" v-model="ytdlpConfig"
                  :disabled="!socket.isConnected"></textarea>
              </div>
              <span class="subtitle is-6">
                Some config fields are ignored like cookiefile, path, and output_format etc.
                Available option can be found at <NuxtLink class="has-text-danger" target="_blank"
                  href="https://github.com/yt-dlp/yt-dlp/blob/a0b19d319a6ce8b7059318fa17a34b144fde1785/yt_dlp/YoutubeDL.py#L194">
                  this page</NuxtLink>. Warning: Use with caution some of those options can break yt-dlp or the
                frontend.
              </span>
            </div>
          </div>
          <div class="column is-6-tablet is-12-mobile">
            <div class="field">
              <label class="label is-inline" for="ytdlpCookies" v-tooltip="'JSON exported cookies for downloading.'">
                yt-dlp Cookies
              </label>
              <div class="control">
                <textarea class="textarea" id="ytdlpCookies" v-model="ytdlpCookies"
                  :disabled="!socket.isConnected"></textarea>
              </div>
              <span class="subtitle is-6">
                Use something like <NuxtLink target="_blank" class="has-text-danger"
                  href="https://github.com/jrie/flagCookies">flagCookies</NuxtLink> to extract cookies as JSON string.
              </span>
            </div>
          </div>
          <div class="column is-6-tablet is-4-mobile has-text-left">
            <button type="submit" class="button is-info" @click="getInfo" :class="{ 'is-loading': !socket.isConnected }"
              :disabled="!socket.isConnected || addInProgress || !url">
              <span class="icon"><i class="fa-solid fa-info" /></span>
              <span>Info</span>
            </button>
          </div>
          <div class="column is-6-tablet is-6-mobile has-text-right">
            <div class="field">
              <div class="control">
                <button type="submit" class="button is-danger" @click="resetConfig" :disabled="!socket.isConnected"
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
    </div>
    <datalist id="folders" v-if="config?.folders">
      <option v-for="dir in config.folders" :key="dir" :value="dir" />
    </datalist>
    <GetInfo v-if="get_info && url" :link="url" @closeModel="get_info = false" />
  </main>
</template>

<script setup>
import { useStorage } from '@vueuse/core'

const config = useConfigStore();
const socket = useSocketStore();
const toast = useToast();

const selectedPreset = useStorage('selectedPreset', '')
const ytdlpConfig = useStorage('ytdlp_config', '')
const ytdlpCookies = useStorage('ytdlp_cookies', '')
const output_template = useStorage('output_template', null)
const downloadPath = useStorage('downloadPath', null)
const url = useStorage('downloadUrl', null)
const showAdvanced = useStorage('show_advanced', false)
const addInProgress = ref(false)
const get_info = ref(false)
const getInfo = () => get_info.value = true

const addDownload = () => {
  addInProgress.value = true;
  url.value.split(',').forEach(url => {
    if (!url.trim()) {
      return;
    }
    socket.emit('add_url', {
      url: url,
      preset: selectedPreset.value,
      folder: downloadPath.value,
      ytdlp_config: ytdlpConfig.value,
      ytdlp_cookies: ytdlpCookies.value,
      output_template: output_template.value,
    });
  });
}

const resetConfig = () => {
  if (true !== confirm('Reset your local configuration?')) {
    return;
  }

  selectedPreset.value = 'default';
  ytdlpConfig.value = '';
  ytdlpCookies.value = '';
  output_template.value = null;
  url.value = null;
  downloadPath.value = null;
  showAdvanced.value = false;

  toast.success('Local configuration has been reset.');
}

const statusHandler = async data => {
  const { status, msg } = JSON.parse(data)

  addInProgress.value = false

  if ('error' === status) {
    toast.error(msg)
    return
  }

  url.value = '';
}

onMounted(() => {
  socket.on('status', statusHandler)
  if ('' === selectedPreset.value) {
    selectedPreset.value = 'default'
  }
})
onUnmounted(() => socket.off('status', statusHandler))
</script>
