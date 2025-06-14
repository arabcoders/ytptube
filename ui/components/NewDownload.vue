<template>
  <main class="columns mt-2">
    <div class="column is-12">
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
              <span class="help is-bold">
                <span class="icon"><i class="fa-solid fa-info" /></span>
                <span>You can add multiple URLs separated by <code
                    class="is-bold">{{ getSeparatorsName(separator) }}</code>.</span>
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
                      v-tooltip.bottom="hasFormatInConfig ? 'Presets are disabled. Format key is present in the command options for yt-dlp.' : ''">
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
          <div class="column is-12" v-if="get_preset(form.preset)?.description">
            <div class="is-overflow-auto" style="max-height: 150px;">
              <div class="is-ellipsis is-clickable" @click="expand_description">
                <span class="icon"><i class="fa-solid fa-info" /></span> {{ get_preset(form.preset)?.description }}
              </div>
            </div>
          </div>
          <div class="columns is-multiline is-mobile" v-if="showAdvanced && !config.app.basic_mode">

            <div class="column is-4-tablet is-12-mobile" v-if="!config.app.basic_mode">
              <div class="field">
                <label class="label is-inline is-unselectable">
                  <span class="icon"><i class="fa-solid fa-comment" /></span>
                  <span>URLs Separator</span>
                </label>
                <div class="control">
                  <div class="select is-fullwidth">
                    <select class="is-fullwidth" :disabled="!socket.isConnected || addInProgress" v-model="separator">
                      <option v-for="(sep, index) in separators" :key="`sep-${index}`" :value="sep.value">
                        {{ sep.name }} ({{ sep.value }})
                      </option>
                    </select>
                  </div>
                </div>
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Use this separate multiple URLs in the input field.</span>
                </span>
              </div>
            </div>

            <div class="column is-8-tablet is-12-mobile">
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
                <span class="help is-bold">
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
                  Command options for yt-dlp
                </label>
                <div class="control">
                  <textarea class="textarea is-pre" v-model="form.cli" id="cli_options"
                    :disabled="!socket.isConnected || addInProgress"
                    placeholder="command options to use, e.g. --no-embed-metadata --no-embed-thumbnail" />
                </div>

                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Check <NuxtLink target="_blank" to="https://github.com/yt-dlp/yt-dlp#general-options">this page
                    </NuxtLink> for more info. <span class="has-text-danger">Not all options are supported <NuxtLink
                        target="_blank"
                        to="https://github.com/arabcoders/ytptube/blob/master/app/library/Utils.py#L24-L46">some are
                        ignored</NuxtLink>. Use with caution these options can break yt-dlp or the frontend.</span>
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
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>Use the <NuxtLink target="_blank"
                      to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp">
                      Recommended addon</NuxtLink> by yt-dlp to export cookies. <span class="has-text-danger">The
                      cookies MUST be in Netscape HTTP Cookie format.</span>
                  </span>
                </span>
              </div>
            </div>
            <div class="column is-12">
              <div class="field is-grouped is-justify-self-end">

                <div class="control">
                  <button type="button" class="button is-info" @click="emitter('getInfo', form.url)"
                    :class="{ 'is-loading': !socket.isConnected }"
                    :disabled="!socket.isConnected || addInProgress || !form?.url">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Information</span>
                  </button>
                </div>

                <div class="control">
                  <button type="button" class="button is-warning" @click="removeFromArchive(form.url)"
                    :class="{ 'is-loading': !socket.isConnected }"
                    :disabled="!socket.isConnected || addInProgress || !form?.url">
                    <span class="icon"><i class="fa-solid fa-box-archive" /></span>
                    <span>Remove from archive</span>
                  </button>
                </div>

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

const emitter = defineEmits(['getInfo', 'clear_form', 'remove_archive'])
const config = useConfigStore()
const socket = useSocketStore()
const toast = useNotification()
const box = useConfirm()

const separators = [
  { name: 'Comma', value: ',', },
  { name: 'Semicolon', value: ';', },
  { name: 'Colon', value: ':', },
  { name: 'Pipe', value: '|', },
  { name: 'Space', value: ' ', }
]

const getSeparatorsName = (value) => {
  const sep = separators.find(s => s.value === value)
  return sep ? `${sep.name} (${value})` : 'Unknown'
}

const showAdvanced = useStorage('show_advanced', false)
const separator = useStorage('url_separator', separators[0].value)

const addInProgress = ref(false)

const form = useStorage('local_config_v1', {
  id: null,
  url: '',
  preset: config.app.default_preset,
  cookies: '',
  cli: '',
  template: '',
  folder: '',
  extras: {},
})

const addDownload = async () => {
  if (form.value?.cli && '' !== form.value.cli) {
    const options = await convertOptions(form.value.cli)
    if (null === options) {
      return
    }
  }

  const request_data = []

  form.value.url.split(separator.value).forEach(async (url) => {
    if (!url.trim()) {
      return
    }

    const data = {
      url: url,
      preset: config.app.basic_mode ? config.app.default_preset : form.value.preset,
      folder: config.app.basic_mode ? null : form.value.folder,
      template: config.app.basic_mode ? null : form.value.template,
      cookies: config.app.basic_mode ? '' : form.value.cookies,
      cli: config.app.basic_mode ? null : form.value.cli,
    }

    if (form.value?.extras && Object.keys(form.value.extras).length > 0) {
      data.extras = form.value.extras
    }

    request_data.push(data)
  })

  try {
    addInProgress.value = true
    const response = await request('/api/history', {
      credentials: 'include',
      method: 'POST',
      body: JSON.stringify(request_data),
    })

    const data = await response.json()
    if (!response.ok) {
      toast.error(`Error: ${data.error || 'Failed to add download.'}`)
      return
    }

    data.forEach(item => {
      if (false !== item.status) {
        return
      }
      toast.error(`Error: ${item.msg || 'Failed to add download.'}`)
    })

    form.value.url = ''
    emitter('clear_form')
  }
  catch (e) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    addInProgress.value = false
  }
}

const resetConfig = () => {
  if (true !== box.confirm('Reset your local configuration?')) {
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
    extras: {},
  }

  showAdvanced.value = false
  separator.value = separators[0].value

  toast.success('Local configuration has been reset.')
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
  await nextTick()

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset
  }

  if (props?.item) {
    Object.keys(props.item).forEach(key => {
      if (key in form.value) {
        let value = props.item[key]
        if ('extras' === key) {
          value = JSON.parse(JSON.stringify(props.item[key]))
        }
        form.value[key] = value
      }
    })
    emitter('clear_form');
  }

  await nextTick()
  if (!separators.some(s => s.value === separator.value)) {
    separator.value = separators[0].value
  }
})

const hasFormatInConfig = computed(() => {
  if (!form.value?.cli) {
    return false
  }
  return /(?<!\S)(-f|--format)(=|\s)(\S+)/.test(form.value.cli)
})

const filter_presets = (flag = true) => config.presets.filter(item => item.default === flag)
const get_preset = name => config.presets.find(item => item.name === name)
const expand_description = e => toggleClass(e.target, ['is-ellipsis', 'is-pre-wrap'])


const removeFromArchive = async url => {
  try {
    const req = await request(`/api/archive/0`, {
      credentials: 'include',
      method: 'DELETE',
      body: JSON.stringify({ url }),
    })

    const data = await req.json()

    if (!req.ok) {
      toast.error(data.error)
      return
    }

    toast.success(data.message ?? `Removed item from archive.`)
  } catch (e) {
    toast.error(`Error: ${e.message}`)
  }
}
</script>
