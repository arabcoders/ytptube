<template>
  <main class="columns mt-2">
    <div class="column">
      <div class="box">
        <div class="columns is-multiline">
          <div class="column is-12">
            <div class="control has-icons-left">
              <input type="url" class="input" id="url" placeholder="Video or playlist link"
                :disabled="!config.isConnected || addInProgress" v-model="url">
              <span class="icon is-small is-left">
                <i class="fa-solid fa-link"></i>
              </span>
            </div>
          </div>
          <div class="column is-3">
            <div class="field has-addons">
              <div class="control">
                <a href="#" class="button is-static">Format</a>
              </div>
              <div class="control is-expanded">
                <div class="select is-fullwidth">
                  <select id="format" class="is-fullwidth" :disabled="!config.isConnected" v-model="selectedFormat"
                    @change="updateQualities">
                    <option v-for="item in downloadFormats" :key="item.id" :value="item.id">
                      {{ item.text }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
          </div>
          <div class="column is-3">
            <div class="field has-addons">
              <div class="control">
                <a href="#" class="button is-static">Quality</a>
              </div>
              <div class="control is-expanded">
                <div class="select is-fullwidth">
                  <select id="quality" class="is-fullwidth" v-model="selectedQuality" :disabled="!config.isConnected">
                    <option v-for="item in qualities" :key="item.id" :value="item.id">{{ item.text }}</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
          <div class="column is-4">
            <div class="field has-addons" :data-tooltip="'Download path relative to ' + config.app.download_path">
              <div class="control">
                <a href="#" class="button is-static">Download Path</a>
              </div>
              <div class="control is-expanded">
                <input type="text" class="input is-fullwidth" id="path" v-model="downloadPath" placeholder="Default"
                  :disabled="!config.isConnected">
              </div>
            </div>
          </div>
          <div class="column">
            <button type="submit" class="button is-primary" @click="addDownload"
              :class="{ 'is-loading': !config.isConnected || addInProgress }"
              :disabled="!config.isConnected || addInProgress || !url">
              <span class="icon">
                <i class="fa-solid fa-plus"></i>
              </span>
              <span>Add Link</span>
            </button>
          </div>
          <div class="column">
            <button type="submit" class="button is-info" @click="showAdvanced = !showAdvanced"
              data-tooltip="Show advanced options" :class="{ 'is-loading': !config.isConnected }"
              :disabled="!config.isConnected">
              <span class="icon">
                <i class="fa-solid fa-cog"></i>
              </span>
            </button>
          </div>
        </div>
        <div class="columns is-multiline" v-if="showAdvanced">
          <div class="column is-12">
            <div class="field">
              <label class="label is-inline" for="output_format"
                :data-tooltip="'Default Format: ' + config.app.output_template">
                Output Format
              </label>
              <div class="control">
                <input type="text" class="input" v-model="output_template" id="output_format"
                  placeholder="Uses default format if non is given.">
              </div>
              <span class="subtitle is-6 has-text-info">
                All format options can be found at <a class="has-text-danger" target="_blank" referrerpolicy="no-referrer"
                  href="https://github.com/yt-dlp/yt-dlp#output-template">this page</a>.
              </span>
            </div>
          </div>
          <div class="column is-6">
            <div class="field">
              <label class="label is-inline" for="ytdlpConfig"
                data-tooltip="Extends current global yt-dlp config. (JSON)">
                JSON yt-dlp config
              </label>
              <div class="control">
                <textarea class="textarea" id="ytdlpConfig" v-model="ytdlpConfig"
                  :disabled="!config.isConnected"></textarea>
              </div>
              <span class="subtitle is-6 has-text-info">
                Some config fields are ignored like cookiefile, path, and output_format etc.
                Available option can be found at <a class="has-text-danger" target="_blank" referrerpolicy="no-referrer"
                  href="https://github.com/yt-dlp/yt-dlp/blob/a0b19d319a6ce8b7059318fa17a34b144fde1785/yt_dlp/YoutubeDL.py#L194">this
                  page</a>.
              </span>
            </div>
          </div>
          <div class="column is-6">
            <div class="field">
              <label class="label is-inline" for="ytdlpCookies" data-tooltip="JSON exported cookies for downloading.">
                yt-dlp Cookies
              </label>
              <div class="control">
                <textarea class="textarea" id="ytdlpCookies" v-model="ytdlpCookies"
                  :disabled="!config.isConnected"></textarea>
              </div>
              <span class="subtitle is-6 has-text-info">
                Use something like <a href="https://github.com/jrie/flagCookies">flagCookies</a> to extract cookies as
                JSON string.
              </span>
            </div>
          </div>
          <div class="column is-12 has-text-right">
            <div class="field">
              <div class="control">
                <button type="submit" class="button is-danger" @click="resetStorage" :disabled="!config.isConnected"
                  data-tooltip="This configuration are stored locally in your browser.">
                  <span class="icon">
                    <i class="fa-solid fa-trash"></i>
                  </span>
                  <span>Reset Storage</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { defineEmits, defineProps, onMounted, ref } from 'vue'
import { downloadFormats } from '../formats.js'
import { useStorage, useEventBus } from '@vueuse/core'

const bus = useEventBus('item_added');
const emits = defineEmits(['addItem']);

const selectedFormat = useStorage('selectedFormat', 'any')
const selectedQuality = useStorage('selectedQuality', '')
const ytdlpConfig = useStorage('ytdlp_config', '')
const ytdlpCookies = useStorage('ytdlp_cookies', '')
const output_template = useStorage('output_template', null)
const downloadPath = useStorage('downloadPath', null)
const url = useStorage('downloadUrl', null)
const showAdvanced = useStorage('show_advanced', false)

const qualities = ref([])
const addInProgress = ref(false)

const updateQualities = () => {
  for (const key in downloadFormats) {
    const item = downloadFormats[key];
    if (item.id === selectedFormat.value) {
      qualities.value = item.qualities;
      break;
    }
  }
  selectedQuality.value = qualities.value[0].id;
}

defineProps({
  config: {
    type: Object,
    required: true
  }
});

onMounted(() => {
  updateQualities();
})

const addDownload = () => {
  addInProgress.value = true;
  emits('addItem', {
    url: url.value,
    format: selectedFormat.value,
    quality: selectedQuality.value,
    folder: downloadPath.value,
    ytdlp_config: ytdlpConfig.value,
    ytdlp_cookies: ytdlpCookies.value,
    output_template: output_template.value,
  });
}

const resetStorage = () => {
  if (!confirm('Are you sure you want to reset the storage?')) {
    return;
  }
  selectedFormat.value = 'any';
  selectedQuality.value = '';
  ytdlpConfig.value = '';
  ytdlpCookies.value = '';
  output_template.value = null;
  url.value = '';
  downloadPath.value = '';
}

bus.on((event, data) => {
  if (event !== 'item_added') {
    return;
  }

  if (data?.status === 'ok') {
    url.value = '';
  }
  addInProgress.value = false;
});
</script>
