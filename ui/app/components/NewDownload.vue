<template>
  <main class="columns mt-2">
    <div class="column is-12">
      <form autocomplete="off" @submit.prevent="addDownload">
        <div class="box">
          <div class="columns is-multiline is-mobile">
            <div class="column is-12">
              <label class="label is-inline is-unselectable" for="url">
                <span class="icon"><i class="fa-solid fa-link" /></span>
                URLs separated by <span class="is-bold">{{ getSeparatorsName(separator) }}</span>
              </label>
              <div class="field is-grouped">
                <div class="control is-expanded">
                  <input type="text" class="input" id="url" placeholder="URLs to download"
                    :disabled="!socket.isConnected || addInProgress" v-model="form.url">
                </div>
                <div class="control">
                  <button type="submit" class="button is-primary"
                    :class="{ 'is-loading': !socket.isConnected || addInProgress }"
                    :disabled="!socket.isConnected || addInProgress || !form?.url">
                    <span class="icon"><i class="fa-solid fa-plus" /></span>
                    <span>Add</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="column is-4-tablet is-12-mobile" v-if="!config.app.basic_mode">
              <div class="field has-addons">
                <div class="control" @click="show_description = !show_description">
                  <label class="button is-static">
                    <span class="icon"><i class="fa-solid fa-sliders" /></span>
                    <span>Preset</span>
                  </label>
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
                  <label class="button is-static">
                    <span class="icon"><i class="fa-solid fa-folder" /></span>
                    <span>Save in</span>
                  </label>
                </div>
                <div class="control is-expanded">
                  <input type="text" class="input is-fullwidth" id="path" v-model="form.folder"
                    :placeholder="get_download_folder()" :disabled="!socket.isConnected || addInProgress"
                    list="folders">
                </div>
              </div>
            </div>

            <div class="column" v-if="!config.app.basic_mode">
              <button type="button" class="button is-info" @click="showAdvanced = !showAdvanced"
                :class="{ 'is-loading': !socket.isConnected }" :disabled="!socket.isConnected">
                <span class="icon"><i class="fa-solid fa-cog" /></span>
                <span>Advanced Options</span>
              </button>
            </div>

            <div class="column is-12"
              v-if="show_description && !config.app.basic_mode && !hasFormatInConfig && get_preset(form.preset)?.description">
              <div class="is-overflow-auto" style="max-height: 150px;">
                <div class="is-ellipsis is-clickable" @click="expand_description">
                  <span class="icon"><i class="fa-solid fa-info" /></span> {{ get_preset(form.preset)?.description }}
                </div>
              </div>
            </div>
          </div>

          <div class="columns is-multiline is-mobile" v-if="showAdvanced && !config.app.basic_mode">
            <div class="column is-3-tablet is-12-mobile">
              <DLInput id="force_download" type="bool" label="Force download"
                v-model="dlFields['--no-download-archive']" icon="fa-solid fa-download"
                :disabled="!socket.isConnected || addInProgress" description="Ignore archive and re-download." />
            </div>

            <div class="column is-3-tablet is-12-mobile">
              <DLInput id="auto_start" type="bool" label="Auto start" v-model="auto_start" icon="fa-solid fa-play"
                :disabled="!socket.isConnected || addInProgress"
                description="Whether to start the download automatically." />
            </div>

            <div class="column is-6-tablet is-12-mobile">

              <DLInput id="output_template" type="string" label="Output template" v-model="form.template"
                icon="fa-solid fa-file" :disabled="!socket.isConnected || addInProgress"
                :placeholder="get_output_template()">
                <template #help>
                  <span class="help is-bold is-unselectable">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>All output template naming options can be found at <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp#output-template">this page</NuxtLink>.</span>
                  </span>
                </template>
              </DLInput>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <div class="field">
                <label class="label is-unselectable" for="cli_options">
                  <span class="icon"><i class="fa-solid fa-terminal" /></span>
                  <span>Command options for yt-dlp</span>
                </label>
                <TextareaAutocomplete id="cli_options" v-model="form.cli" :options="ytDlpOpt"
                  :disabled="!socket.isConnected || addInProgress" />
                <span class="help is-bold">
                  <span class="icon"><i class="fa-solid fa-info" /></span>
                  <span>
                    <NuxtLink @click="showOptions = true" v-text="'View all options'" />. Not all options are supported
                    <NuxtLink target="_blank"
                      to="https://github.com/arabcoders/ytptube/blob/master/app/library/Utils.py#L26">some
                      are ignored</NuxtLink>. Use with caution.
                  </span>
                </span>
              </div>
            </div>

            <div class="column is-6-tablet is-12-mobile">
              <DLInput id="ytdlpCookies" type="text" label="Cookies for yt-dlp" v-model="form.cookies"
                icon="fa-solid fa-cookie" :disabled="!socket.isConnected || addInProgress">
                <template #help>
                  <span class="help is-bold">
                    <span class="icon"><i class="fa-solid fa-info" /></span>
                    <span>Use the <NuxtLink target="_blank"
                        to="https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp">
                        Recommended addon</NuxtLink> by yt-dlp to export cookies. <span class="has-text-danger">The
                        cookies MUST be in Netscape HTTP Cookie format.</span>
                    </span>
                  </span>
                </template>
              </DLInput>
            </div>
            <template v-if="config.dl_fields.length > 0">
              <div class="column is-6-tablet is-12-mobile" v-for="(fi, index) in sortedDLFields"
                :key="fi.id || `dlf-${index}`">
                <DLInput :id="fi?.id || `dlf-${index}`" :type="fi.kind" :description="fi.description" :label="fi.name"
                  :icon="fi.icon" v-model="dlFields[fi.field]" :field="fi.field"
                  :disabled="!socket.isConnected || addInProgress" />
              </div>
            </template>
            <div class="column is-12 is-hidden-tablet">
              <Dropdown icons="fa-solid fa-cogs" label="Actions">
                <NuxtLink class="dropdown-item" @click="() => showFields = true">
                  <span class="icon has-text-purple"><i class="fa-solid fa-plus" /></span>
                  <span>Custom Fields</span>
                </NuxtLink>
                <hr class="dropdown-divider" />

                <NuxtLink class="dropdown-item" @click="emitter('getInfo', form.url, form.preset)">
                  <span class="icon has-text-info"><i class="fa-solid fa-info" /></span>
                  <span>yt-dlp Information</span>
                </NuxtLink>

                <NuxtLink class="dropdown-item" @click="removeFromArchive(form.url)">
                  <span class="icon has-text-warning"><i class="fa-solid fa-box-archive" /></span>
                  <span>Remove from archive</span>
                </NuxtLink>

                <hr class="dropdown-divider" />
                <NuxtLink class="dropdown-item" @click="resetConfig">
                  <span class="icon has-text-danger"><i class="fa-solid fa-rotate-left" /></span>
                  <span>Reset local settings</span>
                </NuxtLink>
              </Dropdown>
            </div>
            <div class="column is-12">
              <div class="field is-grouped is-justify-self-end is-hidden-mobile">
                <div class="control">
                  <button type="button" class="button is-purple" @click="() => showFields = true"
                    :class="{ 'is-loading': !socket.isConnected }" :disabled="!socket.isConnected">
                    <span class="icon"><i class="fa-solid fa-plus" /></span>
                    <span>Custom Fields</span>
                  </button>
                </div>
                <div class="control">
                  <button type="button" class="button is-info" @click="emitter('getInfo', form.url, form.preset)"
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
                    :disabled="!!(!socket.isConnected || form?.id)" v-tooltip="'Reset local settings'">
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
    <ConfirmDialog v-if="dialog_confirm.visible" :visible="dialog_confirm.visible" :title="dialog_confirm.title"
      :message="dialog_confirm.message" :options="dialog_confirm.options" @confirm="dialog_confirm.confirm"
      @cancel="() => dialog_confirm.visible = false" />

    <DLFields v-if="showFields" @cancel="() => showFields = false" />
    <Modal v-if="showOptions" @close="showOptions = false" :contentClass="'modal-content-max'">
      <YTDLPOptions />
    </Modal>
  </main>
</template>

<script setup lang="ts">
import 'assets/css/bulma-switch.css'
import { useStorage } from '@vueuse/core'
import TextareaAutocomplete from '~/components/TextareaAutocomplete.vue'
import type { item_request } from '~/types/item'
import type { AutoCompleteOptions } from '~/types/autocomplete';

const props = defineProps<{ item?: Partial<item_request> }>()
const emitter = defineEmits<{
  (e: 'getInfo', url: string, preset: string | undefined): void
  (e: 'clear_form'): void
  (e: 'remove_archive', url: string): void
}>()
const config = useConfigStore()
const socket = useSocketStore()
const toast = useNotification()

const showAdvanced = useStorage<boolean>('show_advanced', false)
const separator = useStorage<string>('url_separator', separators[0]?.value ?? ',')
const auto_start = useStorage<boolean>('auto_start', true)
const show_description = useStorage<boolean>('show_description', true)
const dlFields = useStorage<Record<string, any>>('dl_fields', {})

const addInProgress = ref<boolean>(false)
const showFields = ref<boolean>(false)
const showOptions = ref<boolean>(false)
const dlFieldsExtra = ['--no-download-archive']
const ytDlpOpt = ref<AutoCompleteOptions>([])

const form = useStorage<item_request>('local_config_v1', {
  id: null,
  url: '',
  preset: config.app.default_preset,
  cookies: '',
  cli: '',
  template: '',
  folder: '',
  extras: {},
}) as Ref<item_request>


const dialog_confirm = ref({
  visible: false,
  title: 'Confirm Action',
  confirm: () => { },
  message: '',
  options: [],
})

const addDownload = async () => {
  let form_cli = (form.value?.cli || '').trim()

  const is_valid = (dl_field: string): boolean => {
    if (dlFieldsExtra.includes(dl_field)) {
      return true
    }

    if (config.dl_fields && config.dl_fields.length > 0) {
      return config.dl_fields.some(f => f.field === dl_field)
    }

    return false;
  }

  if (false === config.app.basic_mode) {
    if (dlFields.value && Object.keys(dlFields.value).length > 0) {
      const joined = []
      for (const [key, value] of Object.entries(dlFields.value)) {
        if (false === is_valid(key)) {
          continue
        }

        if ([undefined, null, '', false].includes(value as any)) {
          continue
        }

        const keyRegex = new RegExp(`(^|\s)${key}(\s|$)`);
        if (form_cli && keyRegex.test(form_cli)) {
          continue;
        }

        joined.push(true === value ? `${key}` : `${key} ${value}`)
      }

      if (joined.length > 0) {
        form_cli = form_cli ? `${form_cli} ${joined.join(' ')}` : joined.join(' ')
      }

    }

    if (form_cli && form_cli.trim()) {
      const options = await convertOptions(form_cli)
      if (null === options) {
        return
      }
    }
  }

  const request_data = [] as Array<item_request>

  form.value.url.split(separator.value).forEach(async (url: string) => {
    if (!url.trim()) {
      return
    }

    const data = {
      url: url,
      preset: config.app.basic_mode ? config.app.default_preset : form.value.preset,
      folder: config.app.basic_mode ? null : form.value.folder,
      template: config.app.basic_mode ? null : form.value.template,
      cookies: config.app.basic_mode ? '' : form.value.cookies,
      cli: config.app.basic_mode ? null : form_cli,
      auto_start: config.app.basic_mode ? true : auto_start.value
    } as item_request

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

    let had_errors = false

    data.forEach((item: Record<string, any>) => {
      if (false !== item.status) {
        return
      }
      toast.error(`Error: ${item.msg || 'Failed to add download.'}`)
      had_errors = true
    })

    if (false === had_errors) {
      form.value.url = ''
      emitter('clear_form')
    }
  }
  catch (e: any) {
    console.error(e)
    toast.error(`Error: ${e.message}`)
  } finally {
    addInProgress.value = false
  }
}

const resetConfig = () => {
  dialog_confirm.value.visible = true
  dialog_confirm.value.message = `Reset local configuration?`
  dialog_confirm.value.confirm = reset_config
}

const reset_config = () => {
  form.value = {
    url: '',
    preset: config.app.default_preset,
    cookies: '',
    cli: '',
    template: '',
    folder: '',
    extras: {},
  } as item_request
  dlFields.value = {}

  showAdvanced.value = false

  toast.success('Local configuration has been reset.')
  dialog_confirm.value.visible = false
}

const convertOptions = async (args: string) => {
  try {
    const response = await convertCliOptions(args)

    if (response.output_template) {
      form.value.template = response.output_template
    }

    if (response.download_path) {
      form.value.folder = response.download_path
    }

    return response.opts
  } catch (e: any) {
    toast.error(e.message)
  }

  return null;
}

onUpdated(async () => {
  await nextTick()

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset
  }

  if (config.isLoaded() && form.value?.preset && !config.presets.some(p => p.name === form.value.preset)) {
    form.value.preset = config.app.default_preset
  }
})

watch(() => config.ytdlp_options, newOptions => ytDlpOpt.value = newOptions
  .filter(opt => !opt.ignored)
  .flatMap(opt => opt.flags
    .filter(flag => flag.startsWith('--'))
    .map(flag => ({ value: flag, description: opt.description || '' }))),
  { immediate: true }
)

onMounted(async () => {
  await nextTick()

  if ('' === form.value?.preset) {
    form.value.preset = config.app.default_preset
  }

  if (config.isLoaded() && form.value?.preset && !config.presets.some(p => p.name === form.value.preset)) {
    form.value.preset = config.app.default_preset
  }

  if (props?.item) {
    const updates: Partial<item_request> = {}
    const keys = Object.keys(props.item) as (keyof item_request)[]
    for (const key of keys) {
      const value = props.item[key]
      updates[key] = key === 'extras' ? JSON.parse(JSON.stringify(value)) : value!
    }
    form.value = { ...form.value, ...updates }
    emitter('clear_form')
  }

  await nextTick()

  if (!separators.some(s => s.value === separator.value)) {
    separator.value = separators[0]?.value ?? '.'
  }
})

const hasFormatInConfig = computed((): boolean => !!form.value.cli?.match(/(?<!\S)(-f|--format)(=|\s)(\S+)/))

const filter_presets = (flag: boolean = true) => config.presets.filter(item => item.default === flag)
const get_preset = (name: string | undefined) => config.presets.find(item => item.name === name)
const expand_description = (e: Event) => toggleClass(e.target as HTMLElement, ['is-ellipsis', 'is-pre-wrap'])

const removeFromArchive = async (url: string) => {
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
  } catch (e: any) {
    toast.error(`Error: ${e.message}`)
  }
}

const get_output_template = () => {
  if (form.value.preset && !hasFormatInConfig.value) {
    const preset = config.presets.find(p => p.name === form.value.preset)
    if (preset && preset.template) {
      return preset.template
    }
  }
  return config.app.output_template || '%(title)s.%(ext)s'
}

const get_download_folder = (): string => {
  if (form.value.preset && false === hasFormatInConfig.value) {
    const preset = config.presets.find(p => p.name === form.value.preset)
    if (preset?.folder) {
      return preset.folder.replace(config.app.download_path, '')
    }
  }
  return '/'
}

const sortedDLFields = computed(() => config.dl_fields.sort((a, b) => (a.order || 0) - (b.order || 0)))
</script>
